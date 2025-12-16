#!/usr/bin/env python3
# pylint: disable=too-many-lines
# Rationale: Self-contained PR review script kept in one file for portability.
# Only ~30 lines over limit; splitting would fragment tightly-coupled workflow logic.
"""
Gemini PR Review Script with incremental review support and concise output.

Key features:
- Tracks last reviewed commit to provide incremental feedback
- Enforces strict brevity limits (500 words, single reaction)
- Uses Flash model for condensation when reviews exceed limits
- Shows full diff context with NEW markers for updated PRs
"""

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml


def _file_has_valid_syntax(filepath: str) -> bool:
    """Check if a Python file has valid syntax.

    Args:
        filepath: Path to the Python file to check

    Returns:
        True if the file has valid syntax or is not a Python file, False if syntax error
    """
    if not filepath.endswith(".py"):
        return True  # Non-Python files - can't validate, assume OK

    try:
        with open(filepath, encoding="utf-8") as f:
            ast.parse(f.read())
        return True
    except (SyntaxError, FileNotFoundError, UnicodeDecodeError):
        return False


# Model constants
# Using explicit model with API key to avoid 404 errors and OAuth hangs
# API key is free tier with generous limits (comparable to OAuth)
NO_MODEL = ""  # Indicates no model was successfully used
DEFAULT_MODEL_TIMEOUT = 600  # seconds (10 minutes for large PR reviews)
# Models can be overridden via environment variables (useful for testing/CI)
PRIMARY_MODEL = os.environ.get("GEMINI_PRIMARY_MODEL", "gemini-3-pro-preview")  # Latest preview (NOT 3.0!)
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")  # Fast fallback
MAX_RETRIES = 5  # For rate limiting on free tier (3 preview may have stricter limits)

# Review constraints
MAX_REVIEW_WORDS = 500  # Target word limit for reviews
CONDENSATION_THRESHOLD = 600  # Trigger condensation if above this
MAX_DIFF_CHARS = 1500000  # Max diff size before truncation (Gemini supports 1M+ token context)


def _call_gemini_with_model(prompt: str, model: str, max_retries: int = MAX_RETRIES) -> Tuple[str, str]:
    """Calls Gemini CLI with a specific model, handling rate limits.

    Args:
        prompt: The prompt to send
        model: Model name (e.g., "gemini-3-pro-preview")
        max_retries: Maximum retry attempts for rate limiting

    Returns:
        (analysis, model_used) or ("", NO_MODEL) on failure
    """
    # Check for API key
    # Check for API key - accept both names for compatibility
    # GOOGLE_API_KEY: Standard Google API key name
    # GEMINI_API_KEY: GitHub workflow secret name (for compatibility)
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: No API Key found in environment variables.")
        print("  Set GOOGLE_API_KEY (standard) or GEMINI_API_KEY (workflow secret)")
        return "Authentication Failed - No API Key", NO_MODEL

    print(f"Attempting analysis with {model} (API Key)...")

    # Use npx to bypass any PATH manipulation or wrappers
    # This ensures we use the official package logic, not /tmp/gemini wrapper
    print("🚀 Resolving Gemini CLI via npx (bypassing any wrappers)...")
    cmd = ["npx", "--yes", "@google/gemini-cli", "prompt", "--model", model, "--output-format", "text"]

    print(f"🚀 Executing command: {' '.join(cmd)}")

    # Retry loop for rate limiting
    for attempt in range(max_retries):
        try:
            # Run with standard subprocess (no PTY wrapper)
            # input= handles stdin and sends EOF properly
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                check=False,
                timeout=DEFAULT_MODEL_TIMEOUT,
                env={**os.environ, "GOOGLE_API_KEY": api_key},
            )

            # Check for errors
            if result.returncode != 0:
                stderr_lower = result.stderr.lower()

                # Handle rate limiting with exponential backoff
                if "429" in result.stderr or "exhausted" in stderr_lower or "quota" in stderr_lower:
                    wait_time = (2**attempt) * 5  # 5s, 10s, 20s, 40s, 80s
                    print(f"⚠️  Rate limit hit (attempt {attempt + 1}/{max_retries})")
                    print(f"    Sleeping {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue  # Retry

                # Handle 404 - model not available
                if "404" in result.stderr:
                    print(f"❌ Model {model} not found")
                    return "", NO_MODEL  # Signal to try fallback

                # Other errors - expose full details
                print(f"❌ CLI Error (Code {result.returncode})")
                print(f"STDERR: {result.stderr}")
                print(f"STDOUT: {result.stdout}")
                return f"Error - CLI Failed: {result.stderr[:200]}", NO_MODEL

            # Success! Clean output
            output = result.stdout.strip()
            lines = output.split("\n")
            cleaned = []
            for line in lines:
                if any(
                    skip in line
                    for skip in [
                        "Loaded cached credentials",
                        "Data collection is disabled",
                        "Telemetry collection is disabled",
                    ]
                ):
                    continue
                cleaned.append(line)

            return "\n".join(cleaned).strip(), model

        except subprocess.TimeoutExpired:
            print(f"❌ Timeout after {DEFAULT_MODEL_TIMEOUT}s (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                continue
            return "", NO_MODEL

        except FileNotFoundError:
            print(f"❌ Critical: Executable not found. PATH is: {os.environ.get('PATH')}")
            print(f"    Attempted command: {' '.join(cmd)}")
            return "Error - Gemini Executable Not Found", NO_MODEL

        except Exception as e:
            print(f"❌ Python Exception: {str(e)}")
            print(f"    Exception type: {type(e).__name__}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return f"Error - Exception: {str(e)}", NO_MODEL

    return "", NO_MODEL  # All retries exhausted


def _call_gemini_with_fallback(prompt: str) -> Tuple[str, str]:
    """Calls Gemini CLI with primary model, falling back to Flash on failure.

    This implementation:
    - Uses API key instead of OAuth to avoid browser-based auth hangs
    - Explicitly specifies model to avoid 404 errors
    - Uses standard stdin (no PTY wrapper) which properly sends EOF
    - Implements exponential backoff for rate limiting on free tier
    - Falls back to gemini-2.5-flash if primary model fails

    Args:
        prompt: The prompt to send to Gemini

    Returns:
        (analysis, model_used) - The analysis result and which model was used
    """

    # Try primary model first (gemini-3.0-pro-preview)
    result, model_used = _call_gemini_with_model(prompt, PRIMARY_MODEL)
    if model_used != NO_MODEL and result:
        return result, model_used

    # Fallback to Flash model
    print(f"⚠️  Primary model failed, falling back to {FALLBACK_MODEL}...")
    result, model_used = _call_gemini_with_model(prompt, FALLBACK_MODEL, max_retries=3)
    if model_used != NO_MODEL and result:
        return result, model_used

    # Both models failed
    return "All models failed - check GOOGLE_API_KEY and model availability", NO_MODEL


def _truncate_at_newline(text: str, max_chars: int) -> str:
    """Truncate text at the nearest newline before max_chars.

    This ensures we don't cut in the middle of a line, which would
    produce invalid diff syntax for the LLM.
    """
    if len(text) <= max_chars:
        return text

    # Find the last newline before max_chars
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")

    if last_newline > 0:
        return truncated[:last_newline]
    return truncated  # No newline found, fall back to hard cut


def get_current_commit_sha() -> str:
    """Get the current HEAD commit SHA (short form)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_last_reviewed_commit(pr_number: str) -> Optional[str]:
    """Extract the last reviewed commit SHA from existing Gemini comments.

    Looks for the marker: <!-- gemini-review-marker:commit:abc123 -->

    Returns:
        The commit SHA if found, None otherwise
    """
    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "comments"],
            capture_output=True,
            text=True,
            check=True,
        )
        pr_data = json.loads(result.stdout)
        comments = pr_data.get("comments", [])

        # Find the most recent Gemini review with commit marker
        for comment in reversed(comments):
            body = comment.get("body", "")
            # Look for the commit marker
            match = re.search(r"<!-- gemini-review-marker:commit:([a-f0-9]+) -->", body)
            if match:
                return match.group(1)

        return None
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return None


def get_files_changed_since_commit(since_commit: str) -> Tuple[List[str], bool]:
    """Get list of files changed since a specific commit.

    Args:
        since_commit: The commit SHA to compare from

    Returns:
        Tuple of (list of file paths that changed, success boolean)
        If git diff fails (e.g., shallow clone), returns ([], False)
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{since_commit}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f.strip() for f in result.stdout.split("\n") if f.strip()]
        return files, True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Warning: Could not get incremental diff from {since_commit}")
        print(f"   Error: {e.stderr if e.stderr else 'git diff failed'}")
        print("   This may happen with shallow clones in CI. Falling back to full review.")
        return [], False
    except FileNotFoundError:
        print("⚠️  Warning: git not found in PATH. Falling back to full review.")
        return [], False


def mark_new_changes_in_diff(full_diff: str, new_files: List[str]) -> str:
    """Add [NEW] markers to files that changed since last review.

    Args:
        full_diff: The complete PR diff
        new_files: List of files that are new/changed since last review

    Returns:
        Diff with [NEW] markers added to relevant file headers
    """
    if not new_files:
        return full_diff

    new_files_set = set(new_files)
    lines = full_diff.split("\n")
    marked_lines = []

    # Pattern to extract filepath from git diff header
    # Handles: "diff --git a/path b/path" and "diff --git a/path with spaces b/path with spaces"
    diff_header_pattern = re.compile(r"^diff --git a/(.+) b/\1$")

    for line in lines:
        if line.startswith("diff --git"):
            # Try regex match first (handles files with spaces correctly)
            match = diff_header_pattern.match(line)
            if match:
                filepath = match.group(1)
            else:
                # Fallback for renamed files: extract destination path (b/...)
                # Format: "diff --git a/old b/new" -> we want "new" (what git diff --name-only returns)
                # Use rpartition to find the LAST " b/" to handle edge cases like "a/sub b/folder/file"
                _, sep, after_b = line.rpartition(" b/")
                if sep:
                    filepath = after_b
                else:
                    filepath = ""

            if filepath and filepath in new_files_set:
                line = f"{line}  [NEW SINCE LAST REVIEW]"
        marked_lines.append(line)

    return "\n".join(marked_lines)


def condense_review_with_flash(review: str) -> str:
    """Use Flash model to condense a verbose review.

    Focuses on:
    - Keeping only actionable issues
    - Removing duplicate praise/comments
    - Maintaining single reaction at end
    - Staying under word limit

    Args:
        review: The verbose review to condense

    Returns:
        Condensed review text
    """
    word_count = len(review.split())
    if word_count <= CONDENSATION_THRESHOLD:
        return review

    print(f"Review exceeds {CONDENSATION_THRESHOLD} words ({word_count}), condensing with Flash...")

    condensation_prompt = f"""Condense this code review to under {MAX_REVIEW_WORDS} words.

RULES:
1. Keep ONLY actionable issues (bugs, security concerns, required fixes)
2. Remove ALL generic praise ("good job", "well done", "solid work")
3. Remove duplicate or similar comments - keep only the first mention
4. Keep exactly ONE reaction image at the very end
5. Remove verbose explanations - use bullet points
6. Keep specific file references and line numbers
7. Remove "Verdict" or "Summary" sections that just restate issues

INPUT REVIEW:
{review}

OUTPUT (condensed review, {MAX_REVIEW_WORDS} words max):"""

    condensed, model = _call_gemini_with_model(condensation_prompt, FALLBACK_MODEL, max_retries=2)

    if model == NO_MODEL or not condensed:
        print("⚠️  Condensation failed, using original review")
        return review

    # Verify condensation actually reduced length
    condensed_words = len(condensed.split())
    if condensed_words < word_count:
        print(f"✅ Condensed from {word_count} to {condensed_words} words")
        return condensed

    print(f"⚠️  Condensation did not reduce length ({condensed_words} words), using original")
    return review


def check_gemini_cli() -> bool:
    """Check if Gemini CLI is available"""
    try:
        result = subprocess.run(["which", "gemini"], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except Exception:
        return False


def get_pr_info() -> Dict[str, Any]:
    """Get PR information from GitHub context"""
    pr_number = os.environ.get("PR_NUMBER", "")
    pr_title = os.environ.get("PR_TITLE", "")
    pr_body = os.environ.get("PR_BODY", "")
    pr_author = os.environ.get("PR_AUTHOR", "")
    base_branch = os.environ.get("BASE_BRANCH", "main")
    head_branch = os.environ.get("HEAD_BRANCH", "")

    return {
        "number": pr_number,
        "title": pr_title,
        "body": pr_body,
        "author": pr_author,
        "base_branch": base_branch,
        "head_branch": head_branch,
    }


def get_changed_files() -> List[str]:
    """Get list of changed files in the PR"""
    if os.path.exists("changed_files.txt"):
        with open("changed_files.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []


def get_file_stats() -> Dict[str, int]:
    """Get statistics about changed files"""
    try:
        base_branch = os.environ.get("BASE_BRANCH", "main")
        result = subprocess.run(
            ["git", "diff", "--stat", f"origin/{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )

        stats = {"additions": 0, "deletions": 0, "files": 0}
        for line in result.stdout.split("\n"):
            if "files changed" in line:
                parts = line.split(",")
                for part in parts:
                    if "insertion" in part:
                        stats["additions"] = int(part.strip().split()[0])
                    elif "deletion" in part:
                        stats["deletions"] = int(part.strip().split()[0])
                    elif "file" in part:
                        stats["files"] = int(part.strip().split()[0])
        return stats
    except Exception:
        return {"additions": 0, "deletions": 0, "files": 0}


def get_pr_diff() -> str:
    """Get the full diff of the PR"""
    try:
        base_branch = os.environ.get("BASE_BRANCH", "main")
        result = subprocess.run(
            ["git", "diff", f"origin/{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return "Could not generate diff"


def get_file_content(filepath: str) -> str:
    """Get the content of a specific file"""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{filepath}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except Exception:
        return f"Could not read {filepath}"


def get_project_context() -> str:
    """Get project context for better code review, including Gemini's expression philosophy"""
    combined_context = []

    # First, try to read the main project context
    project_context_file = Path("docs/agents/project-context.md")
    if not project_context_file.exists():
        # Try alternate location
        project_context_file = Path("PROJECT_CONTEXT.md")

    if project_context_file.exists():
        try:
            combined_context.append(project_context_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: Could not read project context: {e}")

    # If no project context found, use fallback
    if not combined_context:
        combined_context.append(
            "This is a container-first project where all Python tools run in "
            "Docker containers. It's maintained by a single developer with "
            "self-hosted infrastructure. Focus on code quality, security, and "
            "container configurations."
        )

    # Now append Gemini's expression philosophy for personality and style
    gemini_expression_file = Path("docs/agents/gemini-expression.md")
    if gemini_expression_file.exists():
        try:
            print("Including Gemini expression philosophy in review context...")
            expression_content = gemini_expression_file.read_text(encoding="utf-8")
            combined_context.append("\n\n---\n\n")
            combined_context.append(expression_content)
        except Exception as e:
            print(f"Warning: Could not read Gemini expression file: {e}")
    else:
        print("Note: Gemini expression file not found at docs/agents/gemini-expression.md")

    return "".join(combined_context)


def get_all_pr_comments(pr_number: str) -> List[Dict[str, Any]]:
    """Get all PR comments for summarization

    Returns:
        List of comment dictionaries with 'author' and 'body' keys
    """
    try:
        # Get all PR comments
        result = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "comments"],
            capture_output=True,
            text=True,
            check=True,
        )

        pr_data = json.loads(result.stdout)
        comments: List[Dict[str, Any]] = pr_data.get("comments", [])

        return comments
    except subprocess.CalledProcessError as e:
        print(f"Warning: GitHub CLI command failed: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse PR comments JSON: {e}")
        return []
    except Exception as e:
        print(f"Warning: Unexpected error fetching PR comments: {e}")
        return []


def get_recent_pr_comments(pr_number: str) -> str:
    """Get PR comments since last Gemini review"""
    try:
        comments = get_all_pr_comments(pr_number)

        # Find last Gemini comment index
        last_gemini_idx = -1
        for idx, comment in enumerate(comments):
            body = comment.get("body", "")
            # Look for the unique HTML comment marker for more robust detection
            if "<!-- gemini-review-marker -->" in body:
                last_gemini_idx = idx

        # Get comments after last Gemini review
        if last_gemini_idx >= 0:
            recent_comments = comments[last_gemini_idx + 1 :]
            if recent_comments:
                formatted = ["## Recent PR Comments Since Last Gemini Review\n"]
                for comment in recent_comments:
                    author = comment.get("author", {}).get("login", "Unknown")
                    body = comment.get("body", "").strip()
                    formatted.append(f"**@{author}**: {body}\n")
                return "\n".join(formatted)

        return ""
    except Exception as e:
        print(f"Warning: Unexpected error processing PR comments: {e}")
        return ""


def extract_previous_issues(pr_number: str, changed_files: Optional[List[str]] = None) -> Tuple[str, str]:
    """Extract specific issues from previous Gemini reviews for verification.

    Uses Flash model to parse previous Gemini review comments and extract
    a structured list of issues that were flagged. This list is then provided
    to the main review to check if issues are still present or resolved.

    Issues are filtered to only include files that are actually in the current
    diff - issues for files not in the diff cannot be verified and are dropped.

    Args:
        pr_number: The PR number
        changed_files: List of files changed in the PR (for filtering)

    Returns:
        Tuple of (issues_list, model_used) or ("", NO_MODEL) if no reviews found
    """
    try:
        comments = get_all_pr_comments(pr_number)

        # Find all Gemini review comments
        gemini_reviews = []
        for comment in comments:
            body = comment.get("body", "")
            if "<!-- gemini-review-marker" in body and "## Issues" in body:
                gemini_reviews.append(body)

        if not gemini_reviews:
            print("No previous Gemini reviews with issues found")
            return "", NO_MODEL

        # Combine all reviews (most recent last for context)
        all_reviews = "\n\n---\n\n".join(gemini_reviews[-3:])  # Last 3 reviews max

        # Use Flash to extract structured issues
        prompt = f"""Extract all specific code issues from these Gemini PR reviews.

**Previous Gemini Reviews:**
{all_reviews[:8000]}

**Your task:**
Extract ONLY concrete code issues (bugs, security, critical items) into this exact format:
- One issue per line
- Format: `FILE:LINE - [SEVERITY] Description`
- SEVERITY must be: CRITICAL, SECURITY, BUG, or WARNING
- Skip suggestions, notes, and resolved items
- Skip vague comments without specific file references

**Example output:**
```
auth.py:42 - [SECURITY] SQL injection vulnerability in user query
utils.py:100 - [BUG] Off-by-one error in loop bounds
config.py:15 - [CRITICAL] Hardcoded API key exposed
```

If no concrete issues were found, respond with: `NO_ISSUES_FOUND`

**Extracted issues:**"""

        print(f"Extracting issues from {len(gemini_reviews)} previous Gemini review(s)...")
        result, model_used = _call_gemini_with_model(prompt, FALLBACK_MODEL, max_retries=2)

        if model_used == NO_MODEL or not result:
            print("Warning: Issue extraction failed")
            return "", NO_MODEL

        # Check for no issues - robust validation
        result_upper = result.upper().strip()

        # Explicit marker check
        if "NO_ISSUES_FOUND" in result_upper:
            print("No concrete issues found in previous reviews (explicit marker)")
            return "", model_used

        # Validate result looks like an issue list (FILE:LINE format expected)
        # Pattern: any valid filepath followed by :line_number
        # Supports: file.py:10, path/to/file.py:20, Dockerfile:5, my-file.py:30
        issue_pattern = re.compile(r"[\w\-\./]+:\d+")
        has_issue_format = bool(issue_pattern.search(result))

        if not has_issue_format:
            # Model returned conversational text without actual issues
            print("No valid issue format found in response - treating as no issues")
            return "", model_used

        # Filter issues to only include files actually in the diff
        # Issues for files not in the diff cannot be verified
        if changed_files:
            filtered_lines = []
            dropped_count = 0
            for line in result.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Check if any changed file is mentioned in this issue line
                # Issue format: FILE:LINE - [SEVERITY] Description
                # Use boundary-aware matching to avoid false positives like
                # "utils.py" matching "test_utils.py"
                file_in_diff = False
                for changed_file in changed_files:
                    # Check for exact path match followed by colon (line number)
                    if f"{changed_file}:" in line:
                        file_in_diff = True
                        break
                    # Check for path ending with the changed file at a boundary
                    # (preceded by / or start of line)
                    if line.startswith(changed_file) or f"/{changed_file}" in line:
                        file_in_diff = True
                        break
                if file_in_diff:
                    filtered_lines.append(line)
                else:
                    dropped_count += 1

            if dropped_count > 0:
                print(f"Dropped {dropped_count} previous issues for files not in current diff")

            if not filtered_lines:
                print("No verifiable issues remain after filtering")
                return "", model_used

            # Second pass: validate syntax error claims
            # If an issue claims "syntax error" but the file parses fine, it's a false positive
            syntax_keywords = ["syntax error", "syntax:", "syntaxerror", "invalid syntax"]
            validated_lines = []
            syntax_fp_count = 0
            for line in filtered_lines:
                line_lower = line.lower()
                is_syntax_claim = any(kw in line_lower for kw in syntax_keywords)

                if is_syntax_claim:
                    # Extract file path from the issue line
                    # Format: FILE:LINE - [SEVERITY] Description
                    file_match = re.match(r"([\w\-\./]+\.py):\d+", line)
                    if file_match:
                        claimed_file = file_match.group(1)
                        if _file_has_valid_syntax(claimed_file):
                            # File parses fine - this is a false positive
                            syntax_fp_count += 1
                            continue  # Skip this false positive
                validated_lines.append(line)

            if syntax_fp_count > 0:
                print(f"Dropped {syntax_fp_count} false positive syntax error claims (files parse correctly)")

            if not validated_lines:
                print("No verifiable issues remain after syntax validation")
                return "", model_used

            result = "\n".join(validated_lines)

        print("Extracted previous issues for verification")
        return result.strip(), model_used

    except Exception as e:
        print(f"Warning: Error extracting previous issues: {type(e).__name__}: {e}")
        return "", NO_MODEL


def summarize_all_pr_comments(pr_number: str, pr_title: str) -> Tuple[str, str]:
    """Summarize all PR comments using Gemini Flash model for context retention

    This function analyzes the complete comment history to extract important context
    such as admin decisions, false positives, architectural agreements, and completed
    action items. The summary is used to inform subsequent code reviews.

    Args:
        pr_number: The PR number
        pr_title: The PR title

    Returns:
        Tuple of (summary_text, model_used) or ("", NO_MODEL) if no comments or failure
    """
    try:
        comments = get_all_pr_comments(pr_number)

        # No comments to summarize
        if not comments:
            print("No PR comments found - skipping summarization")
            return "", NO_MODEL

        # Filter out Gemini's own reviews to avoid circular context
        human_comments = [c for c in comments if "<!-- gemini-review-marker -->" not in c.get("body", "")]

        if not human_comments:
            print("No human comments found (only Gemini reviews) - skipping summarization")
            return "", NO_MODEL

        # Limit to most recent 50 comments + all admin comments for manageability
        admin_comments = [c for c in human_comments if c.get("author", {}).get("login") == "AndrewAltimit"]
        recent_comments = human_comments[-50:]

        # Combine admin + recent (deduplicate)
        comment_ids_seen = set()
        comments_to_analyze = []
        for comment in admin_comments + recent_comments:
            comment_id = comment.get("id")
            if comment_id and comment_id not in comment_ids_seen:
                comment_ids_seen.add(comment_id)
                comments_to_analyze.append(comment)

        # Format comments for analysis
        formatted_comments = []
        for comment in comments_to_analyze:
            author = comment.get("author", {}).get("login", "Unknown")
            body = comment.get("body", "").strip()
            formatted_comments.append(f"**@{author}**: {body}")

        comments_text = "\n\n".join(formatted_comments)

        # Build summarization prompt
        prompt = f"""You are analyzing the complete comment history of PR #{pr_number}: {pr_title}
to extract context for a new code review.

**All PR Comments ({len(comments_to_analyze)} comments):**

{comments_text}

**Your task:**
Summarize this discussion focusing on:

1. **Admin Decisions**: What has @AndrewAltimit explicitly approved or requested?
2. **False Positives**: Which reported issues were determined to be incorrect or not actual bugs?
3. **Architectural Agreements**: Key design decisions that were agreed upon
4. **Completed Items**: Action items that have been addressed in subsequent commits
5. **Open Concerns**: Unresolved issues that still need attention

**Guidelines:**
- Keep the summary concise (300-500 words maximum)
- Use clear markdown headings for each section
- Only include sections that have relevant content (skip empty sections)
- Be specific about what was decided and why
- If there are no substantive comments, say "No significant discussion history"

Generate the summary now:"""

        # Use Flash model for fast, cost-effective summarization
        print(f"Summarizing {len(comments_to_analyze)} PR comments with {FALLBACK_MODEL}...")
        summary, model_used = _call_gemini_with_model(prompt, FALLBACK_MODEL, max_retries=3)

        if model_used == NO_MODEL or not summary:
            print("⚠️  Comment summarization failed - proceeding without historical context")
            return "", NO_MODEL

        print(f"✅ Successfully summarized PR comment history ({len(summary)} chars)")
        return summary, model_used

    except Exception as e:
        print(f"Warning: Error during comment summarization: {e}")
        print("   Proceeding without comment summary")
        return "", NO_MODEL


def analyze_pr(
    diff: str,
    changed_files: List[str],
    pr_info: Dict[str, Any],
    is_incremental: bool = False,
    new_files_since_last: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """Analyze a PR with a single, focused review.

    Uses strict brevity limits and issues-focused output format.

    Args:
        diff: The PR diff (may have [NEW] markers for incremental reviews)
        changed_files: List of all changed files
        pr_info: PR information dictionary
        is_incremental: Whether this is an incremental review (PR was updated)
        new_files_since_last: Files changed since last review (for incremental)

    Returns: (analysis, model_used)
    """
    project_context = get_project_context()
    file_stats = get_file_stats()

    # Get comment history for context
    comment_summary, _ = summarize_all_pr_comments(pr_info["number"], pr_info["title"])
    recent_comments = get_recent_pr_comments(pr_info["number"])

    # For incremental reviews, extract specific issues from previous Gemini reviews
    # Only include issues for files actually in the diff (others can't be verified)
    previous_issues = ""
    if is_incremental:
        previous_issues, _ = extract_previous_issues(pr_info["number"], changed_files)

    # For GitHub workflow files, include more complete content
    workflow_contents = {}
    for file in changed_files:
        if ".github/workflows" in file and file.endswith(".yml"):
            content = get_file_content(file)
            if content and len(content) < 5000:
                workflow_contents[file] = content

    # Build the concise review prompt
    prompt = f"""You are Gemini, an expert code reviewer. Analyze this pull request.

**STRICT OUTPUT RULES:**
- Maximum {MAX_REVIEW_WORDS} words total
- Use bullet points, not paragraphs
- Only report ACTIONABLE issues (bugs, security, required fixes)
- Skip generic praise - only mention positive aspects if exceptional
- ONE reaction image at the very end (from the reaction protocol)

**CRITICAL - SYNTAX ERROR VERIFICATION:**
- ALL Python files in this PR have been verified to pass `python -m py_compile` before commit
- Do NOT report syntax errors unless you can quote the EXACT invalid syntax from the diff
- File paths appearing in diff headers (like `diff --git a/path/to/file.py`) are NOT code
- If you see `@patch` decorators in the diff, they are VALID - do not claim they are corrupted
- Decorator lines like `@patch("module.function")` are standard unittest.mock usage
- No "Summary" or "Verdict" sections that repeat issues

**PROJECT CONTEXT:**
{project_context[:3000]}

"""

    # Add incremental context if this is an update
    if is_incremental and new_files_since_last:
        prompt += f"""**INCREMENTAL REVIEW - TWO-TIER APPROACH:**
This PR was previously reviewed. Files are marked in the diff as follows:
- `[NEW SINCE LAST REVIEW]` = Changed since last review (PRIMARY FOCUS)
- No marker = Already reviewed in a previous pass

**TIER 1 - NEW FILES (report all issues):**
Files marked [NEW SINCE LAST REVIEW]: {len(new_files_since_last)}
{', '.join(new_files_since_last[:10])}
{'(and ' + str(len(new_files_since_last) - 10) + ' more)' if len(new_files_since_last) > 10 else ''}
Report ANY issues found in these files (bugs, security, suggestions).

**TIER 2 - ALREADY REVIEWED FILES (limited reporting):**
For files WITHOUT the [NEW] marker:
- DO NOT report new stylistic issues, minor suggestions, or nitpicks
- Check the "Previous Issues to Verify" list below and report status of each
- If a previously-flagged issue appears FIXED, note it as [RESOLVED]
- If still present, note it as [STILL UNRESOLVED]

"""
        # Add specific previous issues to verify
        if previous_issues:
            # Use smart truncation to avoid cutting issues mid-line
            # Increased limit from 2000 to 4000 for PRs with many previous issues
            max_issues_chars = 4000
            issues_to_include = _truncate_at_newline(previous_issues, max_issues_chars)
            if len(previous_issues) > max_issues_chars:
                truncated_count = previous_issues.count("\n") - issues_to_include.count("\n")
                print(f"Warning: Truncated {truncated_count} previous issues due to size limit")
            prompt += f"""**PREVIOUS ISSUES TO VERIFY:**
The following issues were flagged in earlier reviews. VERIFY each against the ACTUAL DIFF below:
```
{issues_to_include}
```
**CRITICAL VERIFICATION RULES:**
- ONLY mark as [STILL UNRESOLVED] if you can see the EXACT problematic code in the diff
- If the claimed issue is NOT visible in the diff, mark as [RESOLVED] or [NOT FOUND IN DIFF]
- Do NOT echo previous issues blindly - you must verify each one against the actual code
- Syntax errors should be verifiable: if the code looks syntactically correct in the diff, the issue is resolved

"""

    # Add comment summary if available
    if comment_summary:
        prompt += f"""**PREVIOUS DISCUSSION (respect these decisions):**
{comment_summary[:1500]}

"""

    # Add recent comments if any
    if recent_comments:
        prompt += f"{recent_comments[:1000]}\n\n"

    # Build file list - for incremental reviews, mark which files are new
    new_files_set = set(new_files_since_last) if new_files_since_last else set()

    def format_file(f: str) -> str:
        if is_incremental and f in new_files_set:
            return f"- {f} [NEW]"
        return f"- {f}"

    prompt += f"""**PR INFO:**
- PR #{pr_info['number']}: {pr_info['title']}
- Author: {pr_info['author']}
- Stats: {file_stats['files']} files, +{file_stats['additions']}/-{file_stats['deletions']} lines

**FILES ({len(changed_files)} total{f', {len(new_files_since_last or [])} new' if is_incremental else ''}):**
{chr(10).join(format_file(f) for f in changed_files[:20])}
{'... and ' + str(len(changed_files) - 20) + ' more' if len(changed_files) > 20 else ''}

{format_workflow_contents(workflow_contents)}

**DIFF:**
```diff
{_truncate_at_newline(diff, MAX_DIFF_CHARS)}
```
{'... (truncated)' if len(diff) > MAX_DIFF_CHARS else ''}

**OUTPUT FORMAT:**
## Issues (if any)
- [CRITICAL/SECURITY/BUG] File:line - Brief description
**IMPORTANT: Only report issues you can ACTUALLY SEE in the diff above. Do not invent or hallucinate issues.**
{'''
## Previous Issues (for incremental reviews)
- [STILL UNRESOLVED] File:line - Issue VISIBLE in diff that is still present
- [RESOLVED] File:line - Issue fixed OR not found in current diff
- [NOT FOUND IN DIFF] File:line - Claimed issue cannot be verified in diff
''' if is_incremental else ''}
## Suggestions (if any)
- File:line - Brief suggestion

## Notes
- Any important observations

**REACTION (required, exactly one at the end):**
Use this exact URL format: ![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/FILENAME)
Available reactions: rem_glasses.png, miku_confused.png, menhera_stare.webp, kurisu_thumbs_up.webp
Example: ![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/rem_glasses.png)
"""

    return _call_gemini_with_fallback(prompt)


def format_workflow_contents(workflow_contents: Dict[str, str]) -> str:
    """Format workflow file contents for review"""
    if not workflow_contents:
        return ""

    formatted = "\n**GITHUB WORKFLOW FILES (Full Content):**\n"
    for filepath, content in workflow_contents.items():
        formatted += f"\n--- {filepath} ---\n```yaml\n{content}\n```\n"

    return formatted


def get_valid_reaction_urls() -> List[str]:
    """Fetch and parse the reaction config YAML to get valid reaction URLs

    Returns:
        List of valid reaction URLs
    """
    try:
        config_url = "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml"
        print(f"Fetching reaction config from {config_url}...")

        response = requests.get(config_url, timeout=10)
        response.raise_for_status()

        config = yaml.safe_load(response.text)
        reaction_images = config.get("reaction_images", [])

        valid_urls = []
        for reaction_data in reaction_images:
            source_url = reaction_data.get("source_url")
            if source_url:
                valid_urls.append(source_url)

        print(f"✅ Loaded {len(valid_urls)} valid reaction URLs")
        return valid_urls

    except Exception as e:
        print(f"⚠️  Warning: Could not fetch reaction config: {e}")
        print("   Proceeding without reaction URL fixing")
        return []


def fix_reaction_urls(review_text: str, valid_urls: List[str]) -> str:
    """Automatically fix reaction URLs by cross-referencing against valid URLs.

    This function:
    - Finds ANY ![Reaction](...) pattern (not just correct domain)
    - Extracts filename and tries to match against valid reactions
    - Replaces invalid URLs with correct ones or a default

    Args:
        review_text: The review text to fix
        valid_urls: List of valid reaction URLs from config

    Returns:
        Fixed review text with corrected URLs
    """
    if not valid_urls:
        print("⚠️  No valid URLs available, skipping reaction URL fixing")
        return review_text

    # Build a dict of base filename (without extension) -> full valid URL
    valid_reactions = {}
    for url in valid_urls:
        filename = url.split("/")[-1]
        # Remove query params if present (e.g., ?raw=true)
        filename = filename.split("?")[0]
        base_name = filename.rsplit(".", 1)[0]
        valid_reactions[base_name] = url

    # Default reaction if we can't match
    default_reaction = valid_reactions.get("rem_glasses", valid_urls[0] if valid_urls else "")

    # Find ANY ![Reaction](...) pattern - not just the correct domain
    # This catches malformed URLs like github.com/repo/blob/... or completely wrong formats
    reaction_pattern = r"!\[Reaction\]\(([^\)]+)\)"
    matches = list(re.finditer(reaction_pattern, review_text))

    if not matches:
        print("No reaction URLs found in review, skipping")
        return review_text

    print(f"Found {len(matches)} reaction URL(s) to validate...")

    # Fix each URL
    num_fixes = 0
    fixed_review = review_text

    for match in matches:
        url = match.group(1)
        full_match = match.group(0)

        # Check if URL is already valid
        if url in valid_urls:
            print(f"✅ Valid: {url.split('/')[-1]}")
            continue

        # Extract filename from URL (handle various formats)
        # Could be: .../reaction/name.png, .../name.png?raw=true, etc.
        filename = url.split("/")[-1]
        filename = filename.split("?")[0]  # Remove query params
        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename

        # Try to match base filename
        if base_name in valid_reactions:
            fixed_url = valid_reactions[base_name]
            num_fixes += 1
            print(f"🔧 Fixed: {filename} → {fixed_url.split('/')[-1]}")
            fixed_review = fixed_review.replace(full_match, f"![Reaction]({fixed_url})")
        else:
            # Can't match - use default reaction
            num_fixes += 1
            print(f"🔧 Unknown reaction '{base_name}', using default: {default_reaction.split('/')[-1]}")
            fixed_review = fixed_review.replace(full_match, f"![Reaction]({default_reaction})")

    if num_fixes > 0:
        print(f"✅ Fixed {num_fixes} reaction URL(s)")
    else:
        print("✅ All reaction URLs are valid")

    return fixed_review


def format_github_comment(
    analysis: str,
    model_used: str = "default",
    commit_sha: str = "",
    is_incremental: bool = False,
    diff_truncated: bool = False,
    truncated_chars: int = 0,
) -> str:
    """Format the analysis as a GitHub PR comment.

    Args:
        analysis: The review analysis text
        model_used: Which model generated the review
        commit_sha: Current commit SHA to track for incremental reviews
        is_incremental: Whether this is an incremental review
        diff_truncated: Whether the diff was truncated due to size limits
        truncated_chars: Number of characters that were truncated

    Returns:
        Formatted GitHub comment with commit tracking marker
    """
    # Map model names to display names for transparency
    model_display_map = {
        "gemini-3-pro-preview": "Gemini 3 Pro (Preview)",
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini-2.5-pro": "Gemini 2.5 Pro",
        "default": "Gemini (Preview)",
    }
    if model_used == NO_MODEL:
        model_display = "Error - No model available"
    else:
        model_display = model_display_map.get(model_used, f"Gemini ({model_used})")

    # Include commit SHA in marker for incremental tracking
    marker = f"<!-- gemini-review-marker:commit:{commit_sha} -->" if commit_sha else "<!-- gemini-review-marker -->"

    # Add incremental review header if applicable
    review_type = "Incremental Review" if is_incremental else "Code Review"
    incremental_note = (
        "\n*This is an incremental review focusing on changes since the last review.*\n" if is_incremental else ""
    )

    # Add truncation warning if applicable
    truncation_warning = ""
    if diff_truncated:
        truncation_warning = (
            f"\n⚠️ **Note:** This PR's diff was truncated ({truncated_chars:,} chars omitted). "
            "Some changes at the end of the diff may not have been reviewed.\n"
        )

    comment = f"""## Gemini AI {review_type}
{marker}
{incremental_note}{truncation_warning}
{analysis}

---
*Generated by Gemini AI ({model_display}). Supplementary to human reviews.*
"""
    return comment


def post_pr_comment(comment: str, pr_info: Dict[str, Any]):
    """Post the comment to the PR using GitHub CLI"""
    try:
        # Save comment to temporary file
        comment_file = f"/tmp/gemini_comment_{pr_info['number']}.md"
        with open(comment_file, "w", encoding="utf-8") as f:
            f.write(comment)

        # Use gh CLI to post comment
        subprocess.run(
            [
                "gh",
                "pr",
                "comment",
                pr_info["number"],
                "--body-file",
                comment_file,
            ],
            check=True,
        )

        print("Successfully posted Gemini review to PR")

        # Clean up
        os.unlink(comment_file)
    except subprocess.CalledProcessError as e:
        print(f"Failed to post comment: {e}")
        # Save locally as backup
        with open("gemini-review.md", "w", encoding="utf-8") as f:
            f.write(comment)
        print("Review saved to gemini-review.md")


def main() -> None:
    """Main function with incremental review support."""
    print("Starting Gemini PR Review (v2 - Incremental + Concise)...")

    # Check if Gemini CLI is available
    if not check_gemini_cli():
        print("ERROR: Gemini CLI not found")
        print("Setup instructions:")
        print("1. Install Node.js 18+")
        print("2. npm install -g @google/gemini-cli")
        print("3. Run 'gemini' to authenticate")
        sys.exit(0)

    # Get PR information
    pr_info = get_pr_info()
    if not pr_info["number"]:
        print("ERROR: Not running in PR context")
        sys.exit(1)

    print(f"Analyzing PR #{pr_info['number']}: {pr_info['title']}")

    # Get current commit SHA for tracking
    current_commit = get_current_commit_sha()
    print(f"Current commit: {current_commit}")

    # Check for previous review (incremental review detection)
    last_reviewed_commit = get_last_reviewed_commit(pr_info["number"])
    is_incremental = False
    new_files_since_last: List[str] = []

    if last_reviewed_commit:
        print(f"Previous review found at commit: {last_reviewed_commit}")

        # Early exit if we've already reviewed this exact commit
        if current_commit and last_reviewed_commit.startswith(current_commit[:8]):
            print("✅ Current commit already reviewed - skipping to avoid duplicate comments")
            print("Gemini PR review complete (no new commits)!")
            return

        new_files_since_last, diff_success = get_files_changed_since_commit(last_reviewed_commit)
        if new_files_since_last:
            is_incremental = True
            print(f"Incremental review: {len(new_files_since_last)} files changed since last review")
        elif diff_success:
            # git diff succeeded but returned no files - same commit state
            print("✅ No new changes since last review - skipping to avoid duplicate comments")
            print("Gemini PR review complete (no changes)!")
            return
        else:
            # git diff failed (shallow clone, etc.) - fall back to full review
            print("Falling back to full review due to incremental diff failure")
    else:
        print("No previous review found - this is the first review")

    # Get changed files
    changed_files = get_changed_files()
    print(f"Total changed files in PR: {len(changed_files)}")

    # Always get full PR diff (latest code state) for complete context
    # For incremental reviews, we mark which files are new but still show everything
    # This allows Gemini to verify if previously-flagged issues were fixed
    print("Getting complete PR diff...")
    diff = get_pr_diff()

    # For incremental reviews, mark new files so Gemini knows what to focus on
    if is_incremental and new_files_since_last:
        diff = mark_new_changes_in_diff(diff, new_files_since_last)
        print(f"Marked {len(new_files_since_last)} files as [NEW SINCE LAST REVIEW]")

    original_diff_size = len(diff)
    print(f"Diff size: {original_diff_size:,} characters")

    # Track if diff will be truncated
    diff_truncated = original_diff_size > MAX_DIFF_CHARS
    truncated_chars = original_diff_size - MAX_DIFF_CHARS if diff_truncated else 0
    if diff_truncated:
        print(f"⚠️  Diff will be truncated: {truncated_chars:,} chars will be omitted")

    # Analyze with Gemini (single-pass, concise review)
    print("Consulting Gemini AI...")
    analysis, model_used = analyze_pr(
        diff=diff,
        changed_files=changed_files,
        pr_info=pr_info,
        is_incremental=is_incremental,
        new_files_since_last=new_files_since_last,
    )

    # Condense if review is too verbose
    analysis = condense_review_with_flash(analysis)

    # Format as GitHub comment with commit tracking
    comment = format_github_comment(
        analysis=analysis,
        model_used=model_used,
        commit_sha=current_commit,
        is_incremental=is_incremental,
        diff_truncated=diff_truncated,
        truncated_chars=truncated_chars,
    )

    # Fix reaction URLs before posting (auto-fix bad extensions)
    print("\n🔍 Fixing reaction URLs...")
    valid_urls = get_valid_reaction_urls()
    validated_comment = fix_reaction_urls(comment, valid_urls)

    # Post to PR
    post_pr_comment(validated_comment, pr_info)

    # Save to step summary (use validated comment)
    with open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("\n\n" + validated_comment)

    print("Gemini PR review complete!")


if __name__ == "__main__":
    main()

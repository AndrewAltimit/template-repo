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


def get_current_commit_sha() -> str:
    """Get the current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()[:12]  # Short SHA
    except subprocess.CalledProcessError:
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
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def get_files_changed_since_commit(since_commit: str) -> List[str]:
    """Get list of files changed since a specific commit.

    Args:
        since_commit: The commit SHA to compare from

    Returns:
        List of file paths that changed
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{since_commit}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.split("\n") if f.strip()]
    except subprocess.CalledProcessError:
        return []


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

    for line in lines:
        if line.startswith("diff --git"):
            # Extract filename from diff header
            parts = line.split()
            if len(parts) >= 3:
                filepath = parts[2].replace("a/", "")
                if filepath in new_files_set:
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
- No "Summary" or "Verdict" sections that repeat issues

**PROJECT CONTEXT:**
{project_context[:3000]}

"""

    # Add incremental context if this is an update
    if is_incremental and new_files_since_last:
        prompt += f"""**INCREMENTAL REVIEW:**
This PR was previously reviewed. Focus on files marked [NEW SINCE LAST REVIEW].
New/changed files: {', '.join(new_files_since_last[:10])}
{'(and ' + str(len(new_files_since_last) - 10) + ' more)' if len(new_files_since_last) > 10 else ''}

"""

    # Add comment summary if available
    if comment_summary:
        prompt += f"""**PREVIOUS DISCUSSION (respect these decisions):**
{comment_summary[:1500]}

"""

    # Add recent comments if any
    if recent_comments:
        prompt += f"{recent_comments[:1000]}\n\n"

    prompt += f"""**PR INFO:**
- PR #{pr_info['number']}: {pr_info['title']}
- Author: {pr_info['author']}
- Stats: {file_stats['files']} files, +{file_stats['additions']}/-{file_stats['deletions']} lines

**FILES ({len(changed_files)} total):**
{chr(10).join(f'- {f}' for f in changed_files[:20])}
{'... and ' + str(len(changed_files) - 20) + ' more' if len(changed_files) > 20 else ''}

{format_workflow_contents(workflow_contents)}

**DIFF:**
```diff
{diff[:60000]}
```
{'... (truncated)' if len(diff) > 60000 else ''}

**OUTPUT FORMAT:**
## Issues (if any)
- [CRITICAL/SECURITY/BUG] File:line - Brief description

## Suggestions (if any)
- File:line - Brief suggestion

## Notes
- Any important observations

![Reaction](reaction_url_here)
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
    """Automatically fix reaction URLs by cross-referencing extensions against valid URLs

    This function:
    - Extracts filenames from reaction URLs
    - Matches base filenames (without extension) against valid URLs
    - Auto-fixes incorrect extensions (e.g., .png → .webp)

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
        base_name = filename.rsplit(".", 1)[0]
        valid_reactions[base_name] = url

    # Extract all reaction URLs from the review text
    reaction_pattern = r"!\[Reaction\]\((https://raw\.githubusercontent\.com/AndrewAltimit/Media/[^\)]+)\)"
    found_urls = re.findall(reaction_pattern, review_text)

    if not found_urls:
        print("No reaction URLs found in review, skipping")
        return review_text

    print(f"Found {len(found_urls)} reaction URL(s) to validate...")

    # Fix each URL
    num_fixes = 0
    fixed_review = review_text

    for url in found_urls:
        # Check if URL is already valid
        if url in valid_urls:
            continue

        # Extract filename and base name
        filename = url.split("/")[-1]
        base_name = filename.rsplit(".", 1)[0]

        # Try to match base filename
        if base_name in valid_reactions:
            fixed_url = valid_reactions[base_name]
            if fixed_url != url:
                num_fixes += 1
                print(f"🔧 Fixed: {filename} → {fixed_url.split('/')[-1]}")
                fixed_review = fixed_review.replace(f"![Reaction]({url})", f"![Reaction]({fixed_url})")

    if num_fixes > 0:
        print(f"✅ Fixed {num_fixes} reaction URL(s)")
    else:
        print("✅ All reaction URLs are valid")

    return fixed_review


def format_github_comment(
    analysis: str,
    pr_info: Dict[str, Any],
    model_used: str = "default",
    commit_sha: str = "",
    is_incremental: bool = False,
) -> str:
    """Format the analysis as a GitHub PR comment.

    Args:
        analysis: The review analysis text
        pr_info: PR information dictionary
        model_used: Which model generated the review
        commit_sha: Current commit SHA to track for incremental reviews
        is_incremental: Whether this is an incremental review

    Returns:
        Formatted GitHub comment with commit tracking marker
    """
    if model_used == "default" or model_used != NO_MODEL:
        model_display = "Gemini (Preview)"
    else:
        model_display = "Error - No model available"

    # Include commit SHA in marker for incremental tracking
    marker = f"<!-- gemini-review-marker:commit:{commit_sha} -->" if commit_sha else "<!-- gemini-review-marker -->"

    # Add incremental review header if applicable
    review_type = "Incremental Review" if is_incremental else "Code Review"
    incremental_note = (
        "\n*This is an incremental review focusing on changes since the last review.*\n" if is_incremental else ""
    )

    comment = f"""## Gemini AI {review_type}
{marker}
{incremental_note}
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


def main():
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
        new_files_since_last = get_files_changed_since_commit(last_reviewed_commit)
        if new_files_since_last:
            is_incremental = True
            print(f"Incremental review: {len(new_files_since_last)} files changed since last review")
        else:
            print("No new changes since last review - will provide full review")
    else:
        print("No previous review found - this is the first review")

    # Get changed files
    changed_files = get_changed_files()
    print(f"Total changed files in PR: {len(changed_files)}")

    # Get PR diff
    print("Getting complete PR diff...")
    diff = get_pr_diff()
    print(f"Diff size: {len(diff):,} characters")

    # Mark new changes in diff for incremental reviews
    if is_incremental and new_files_since_last:
        diff = mark_new_changes_in_diff(diff, new_files_since_last)
        print(f"Marked {len(new_files_since_last)} files as [NEW SINCE LAST REVIEW]")

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
        pr_info=pr_info,
        model_used=model_used,
        commit_sha=current_commit,
        is_incremental=is_incremental,
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

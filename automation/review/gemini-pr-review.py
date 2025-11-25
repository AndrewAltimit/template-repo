#!/usr/bin/env python3
"""
Improved Gemini PR Review Script with better context handling
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


def chunk_diff_by_files(diff: str) -> List[Tuple[str, str]]:
    """Split diff into per-file chunks"""
    chunks = []
    current_file = None
    current_chunk = []

    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            if current_file and current_chunk:
                chunks.append((current_file, "\n".join(current_chunk)))
            # Extract filename from diff header
            parts = line.split()
            if len(parts) >= 3:
                current_file = parts[2].replace("a/", "").replace("b/", "")
            current_chunk = [line]
        elif current_chunk is not None:
            current_chunk.append(line)

    # Don't forget the last chunk
    if current_file and current_chunk:
        chunks.append((current_file, "\n".join(current_chunk)))

    return chunks


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


def analyze_large_pr(diff: str, changed_files: List[str], pr_info: Dict[str, Any]) -> Tuple[str, str]:
    """Analyze large PRs by breaking them down into manageable chunks

    Returns: (analysis, model_used)
    """

    project_context = get_project_context()
    file_stats = get_file_stats()
    diff_size = len(diff)

    # If diff is small enough, use single analysis
    # Use conservative threshold to avoid ARG_MAX limit (~128KB on most systems)
    # Leaving room for prompt formatting and context, use 50KB as safe threshold
    if diff_size < 50000:  # 50KB threshold - avoid ARG_MAX errors
        return analyze_complete_diff(diff, changed_files, pr_info, project_context, file_stats)

    # For large diffs, analyze by file groups
    print(f"Large diff detected ({diff_size:,} chars), using chunked analysis...")

    # Get comment summary for context retention across reviews
    comment_summary, _ = summarize_all_pr_comments(pr_info["number"], pr_info["title"])

    file_chunks = chunk_diff_by_files(diff)
    model_used = NO_MODEL  # Start with no model, will be updated if any analysis succeeds
    successful_models = []  # Track which models were successfully used

    # Group files by type for more coherent analysis
    file_groups: Dict[str, List[Tuple[str, str]]] = {
        "workflows": [],
        "python": [],
        "docker": [],
        "config": [],
        "docs": [],
        "other": [],
    }

    for filepath, file_diff in file_chunks:
        if ".github/workflows" in filepath:
            file_groups["workflows"].append((filepath, file_diff))
        elif filepath.endswith(".py"):
            file_groups["python"].append((filepath, file_diff))
        elif "docker" in filepath.lower() or filepath.endswith("Dockerfile"):
            file_groups["docker"].append((filepath, file_diff))
        elif filepath.endswith((".yml", ".yaml", ".json", ".toml")):
            file_groups["config"].append((filepath, file_diff))
        elif filepath.endswith((".md", ".rst", ".txt")):
            file_groups["docs"].append((filepath, file_diff))
        else:
            file_groups["other"].append((filepath, file_diff))

    # Get recent PR comments for context
    recent_comments = get_recent_pr_comments(pr_info["number"])

    # Create temporary directory for review sections
    review_dir = Path(f"/tmp/gemini_review_{pr_info['number']}")
    review_dir.mkdir(exist_ok=True)

    # Analyze each group and save to separate files
    review_files = []
    for group_name, group_files in file_groups.items():
        if not group_files:
            continue

        group_analysis, group_model = analyze_file_group(
            group_name, group_files, pr_info, project_context, comment_summary, recent_comments
        )
        if group_analysis and group_model != NO_MODEL:
            # Save to file
            review_file = review_dir / f"review_{group_name}.txt"
            review_file.write_text(group_analysis, encoding="utf-8")
            review_files.append(review_file)
            successful_models.append(group_model)

    # Determine if any analysis succeeded
    if successful_models:
        model_used = "default"
    elif review_files:
        model_used = "default"
    else:
        model_used = NO_MODEL

    # Only return analysis if we have content
    if not review_files:
        return "Unable to analyze PR - all file group analyses failed.", NO_MODEL

    # Consolidate reviews using the consolidation script
    print(f"\nConsolidating {len(review_files)} review sections with Gemini...")
    try:
        consolidate_script = Path(__file__).parent / "consolidate-gemini-review.py"
        result = subprocess.run(
            [sys.executable, str(consolidate_script), str(review_dir), pr_info["number"], pr_info["title"]],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,  # 5 minute timeout for consolidation
        )

        if result.returncode == 0:
            # Read consolidated review
            consolidated_file = review_dir / "review_consolidated.txt"
            if consolidated_file.exists():
                consolidated_analysis = consolidated_file.read_text(encoding="utf-8")
                print("✅ Successfully consolidated reviews")
                return consolidated_analysis, model_used
            print("⚠️  Consolidation completed but output file not found, using fallback")
        else:
            print(f"⚠️  Consolidation failed: {result.stderr}")
            print("   Falling back to simple concatenation")

    except Exception as e:
        print(f"⚠️  Error during consolidation: {e}")
        print("   Falling back to simple concatenation")

    # Fallback: simple concatenation if consolidation fails
    analyses = []
    for review_file in review_files:
        group_name = review_file.stem.replace("review_", "").replace("_", " ").title()
        content = review_file.read_text(encoding="utf-8")
        analyses.append(f"### {group_name} Changes\n{content}")

    combined_analysis = f"""## Overall Summary

**PR Stats**: {file_stats['files']} files changed, \
+{file_stats['additions']}/-{file_stats['deletions']} lines

{chr(10).join(analyses)}

## Overall Assessment

Based on the comprehensive analysis above, this PR appears to be making \
significant changes across multiple areas of the codebase. Please ensure all \
changes are tested, especially given the container-first architecture of this project.
"""

    return combined_analysis, model_used


def analyze_file_group(
    group_name: str,
    files: List[Tuple[str, str]],
    pr_info: Dict[str, Any],
    project_context: str,
    comment_summary: str = "",
    recent_comments: str = "",
) -> Tuple[str, str]:
    """Analyze a group of related files

    Args:
        group_name: Name of the file group (e.g., "python", "workflows")
        files: List of (filepath, file_diff) tuples
        pr_info: PR information dictionary
        project_context: Project-specific context
        comment_summary: Summary of all PR comment history
        recent_comments: Comments since last Gemini review

    Returns: (analysis, model_used)
    """

    # Combine diffs for the group (limit to reasonable size)
    combined_diff = ""
    file_list = []

    for filepath, file_diff in files[:10]:  # Max 10 files per group to stay under ARG_MAX
        file_list.append(filepath)
        # Include file diff up to 3KB per file to keep total under ARG_MAX
        file_content = file_diff[:3000]  # 3KB per file, 10 files = ~30KB + overhead
        combined_diff += f"\n\n=== {filepath} ===\n{file_content}"
        if len(file_diff) > 3000:
            combined_diff += f"\n... (truncated {len(file_diff) - 3000} chars)"

    prompt = (
        f"You are an expert code reviewer. Analyze this group of {group_name} changes from "
        f"PR #{pr_info['number']}.\n\n"
        f"**PROJECT CONTEXT:**\n"
        f"{project_context}\n\n"
    )

    # Add comment summary if provided (historical context)
    if comment_summary:
        prompt += (
            f"**HISTORICAL PR DISCUSSION (Summary):**\n"
            f"{comment_summary}\n\n"
            f"*Note: Use this to avoid re-reporting false positives and respect admin decisions.*\n\n"
        )

    # Add recent comments if provided
    if recent_comments:
        prompt += f"{recent_comments}\n\n"

    prompt += (
        f"**Files in this group:**\n"
        f"{chr(10).join(f'- {f}' for f in file_list)}\n\n"
        f"**Relevant diffs:**\n"
        f"```diff\n"
        f"{combined_diff[:35000]}\n"  # Conservative limit for ARG_MAX
        f"```\n\n"
        f"Focus on:\n"
        f"1. Correctness and potential bugs\n"
        f"2. Security implications\n"
        f"3. Best practices for {group_name} files\n"
        f"4. Consistency with project's container-first approach\n\n"
    )

    # Add guidance about using historical context
    if comment_summary:
        prompt += (
            "**Review Guidelines:**\n"
            "- Do NOT re-report issues marked as false positives in the discussion history\n"
            "- Build on decisions already made rather than questioning them\n"
            "- Reference the historical context when relevant\n"
            "- Focus on new issues not previously discussed\n\n"
        )

    prompt += "Keep response concise but thorough."

    # Use the helper function for Gemini API calls with fallback
    return _call_gemini_with_fallback(prompt)


def analyze_complete_diff(
    diff: str,
    changed_files: List[str],
    pr_info: Dict[str, Any],
    project_context: str,
    file_stats: Dict[str, int],
) -> Tuple[str, str]:
    """Analyze complete diff for smaller PRs

    Returns: (analysis, model_used)
    """

    # Get comment summary for context retention across reviews
    comment_summary, _ = summarize_all_pr_comments(pr_info["number"], pr_info["title"])

    # For GitHub workflow files, include more complete content
    workflow_contents = {}
    for file in changed_files:
        if ".github/workflows" in file and file.endswith(".yml"):
            content = get_file_content(file)
            if content and len(content) < 5000:  # Only include if reasonable size
                workflow_contents[file] = content

    # Get recent PR comments since last Gemini review
    recent_comments = get_recent_pr_comments(pr_info["number"])

    prompt = (
        "You are an expert code reviewer. Please analyze this pull request "
        "comprehensively.\n\n"
        f"**PROJECT CONTEXT:**\n"
        f"{project_context}\n\n"
    )

    # Add comment summary if provided (historical context)
    if comment_summary:
        prompt += (
            f"**HISTORICAL PR DISCUSSION (Summary):**\n"
            f"{comment_summary}\n\n"
            f"*Note: Use this to avoid re-reporting false positives and respect admin decisions.*\n\n"
        )

    prompt += (
        f"**PULL REQUEST INFORMATION:**\n"
        f"- PR #{pr_info['number']}: {pr_info['title']}\n"
        f"- Author: {pr_info['author']}\n"
        f"- Description: {pr_info['body']}\n"
        f"- Stats: {file_stats['files']} files, "
        f"+{file_stats['additions']}/-{file_stats['deletions']} lines\n\n"
    )

    # Add recent comments if any
    if recent_comments:
        prompt += f"{recent_comments}\n\n"

    prompt += (
        f"**CHANGED FILES ({len(changed_files)} total):**\n"
        f"{chr(10).join(f'- {file}' for file in changed_files)}\n\n"
        f"{format_workflow_contents(workflow_contents)}\n"
        f"**COMPLETE DIFF:**\n"
        f"```diff\n"
        f"{diff[:40000]}\n"  # Conservative limit to stay under ARG_MAX
        f"```\n"
    )

    # Add truncation message if needed
    if len(diff) > 40000:
        prompt += f"... (diff truncated, {len(diff) - 40000} chars omitted)\n\n"
    else:
        prompt += "\n"

    prompt += (
        "Please provide:\n"
        "1. **Summary**: What are the key changes?\n"
        "2. **Code Quality**: Any issues with style, structure, or best practices?\n"
        "3. **Potential Issues**: Bugs, security concerns, or logic errors?\n"
        "4. **Suggestions**: Specific improvements\n"
        "5. **Positive Aspects**: What's well done?\n\n"
    )

    # Add guidance about using historical context
    if comment_summary:
        prompt += (
            "**Review Guidelines:**\n"
            "- Do NOT re-report issues marked as false positives in the discussion history\n"
            "- Build on decisions already made rather than questioning them\n"
            "- Reference the historical context when relevant\n"
            "- Focus on new issues not previously discussed\n\n"
        )

    prompt += "Focus on actionable feedback considering the container-first architecture."

    # Use the helper function for Gemini API calls with fallback
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


def format_github_comment(analysis: str, pr_info: Dict[str, Any], model_used: str = "default") -> str:
    """Format the analysis as a GitHub PR comment"""
    if model_used == "default":
        model_display = "Gemini (Preview)"
    else:
        model_display = "Error - No model available"
    comment = f"""## Gemini AI Code Review
<!-- gemini-review-marker -->

Hello @{pr_info['author']}! I've analyzed your pull request \
"{pr_info['title']}" and here's my comprehensive feedback:

{analysis}

---
*This review was automatically generated by Gemini AI ({model_display}) via CLI. \
This is supplementary feedback to human reviews.*
*If the analysis seems incomplete, check the [workflow logs](../actions) \
for the full diff size.*
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
    """Main function"""
    print("Starting Improved Gemini PR Review...")

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

    # Get changed files
    changed_files = get_changed_files()
    print(f"Found {len(changed_files)} changed files")

    # Get PR diff
    print("Getting complete PR diff...")
    diff = get_pr_diff()
    print(f"Diff size: {len(diff):,} characters")

    # Analyze with Gemini
    print("Consulting Gemini AI...")
    analysis, model_used = analyze_large_pr(diff, changed_files, pr_info)

    # Format as GitHub comment
    comment = format_github_comment(analysis, pr_info, model_used)

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

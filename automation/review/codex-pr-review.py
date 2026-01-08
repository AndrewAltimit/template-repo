#!/usr/bin/env python3
"""
Codex PR Review Script - Secondary AI reviewer for pull requests.

This script provides a second AI perspective on PRs, running after Gemini's review.
Key features:
- Uses OpenAI Codex CLI for code-focused analysis
- Receives Gemini's review as context for complementary feedback
- Focuses on code quality, patterns, and implementation details
- Provides consolidated marker for downstream processing
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

# Maximum characters for diff to avoid context limits
MAX_DIFF_CHARS = 100000
MAX_REVIEW_WORDS = 400


def check_prerequisites() -> Tuple[bool, List[str]]:
    """Check if all prerequisites are met for running Codex CLI.

    Returns:
        Tuple of (all_ok, list_of_errors)
    """
    errors = []

    # Check for Codex CLI
    try:
        result = subprocess.run(
            ["which", "codex"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            errors.append("Codex CLI not found. Install with: npm install -g @openai/codex@0.79.0")
    except Exception as e:
        errors.append(f"Failed to check for Codex CLI: {e}")

    # Check for Codex auth
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        errors.append(f"Codex auth not found at {auth_path}. Run 'codex auth' to authenticate.")

    return (len(errors) == 0, errors)


def get_pr_info() -> Dict[str, Any]:
    """Get PR information from environment variables."""
    return {
        "number": os.environ.get("PR_NUMBER", ""),
        "title": os.environ.get("PR_TITLE", "Unknown PR"),
        "body": os.environ.get("PR_BODY", ""),
        "author": os.environ.get("PR_AUTHOR", "unknown"),
        "base_branch": os.environ.get("BASE_BRANCH", "main"),
        "head_branch": os.environ.get("HEAD_BRANCH", ""),
    }


def get_current_commit_sha() -> str:
    """Get the current commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_changed_files() -> List[str]:
    """Get list of files changed in the PR."""
    base_branch = os.environ.get("BASE_BRANCH", "main")
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception as e:
        print(f"Warning: Failed to get changed files: {e}")

    return []


def get_pr_diff() -> str:
    """Get the PR diff."""
    base_branch = os.environ.get("BASE_BRANCH", "main")

    # Try multiple methods to get diff
    methods = [
        ["git", "diff", f"origin/{base_branch}...HEAD"],
        ["gh", "pr", "diff", os.environ.get("PR_NUMBER", "")],
    ]

    for cmd in methods:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            continue

    return ""


def load_gemini_review() -> Optional[str]:
    """Load Gemini's review from artifact or environment.

    Checks multiple sources:
    1. GEMINI_REVIEW_PATH environment variable (artifact path)
    2. GEMINI_REVIEW_CONTENT environment variable (inline content)
    3. gemini-review.md file in current directory
    """
    # Check environment variable for artifact path
    review_path = os.environ.get("GEMINI_REVIEW_PATH")
    if review_path and Path(review_path).exists():
        try:
            with open(review_path, encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    print(f"Loaded Gemini review from artifact: {review_path}")
                    return content
        except Exception as e:
            print(f"Warning: Failed to load Gemini review from {review_path}: {e}")

    # Check environment variable for inline content
    review_content = os.environ.get("GEMINI_REVIEW_CONTENT")
    if review_content:
        print("Loaded Gemini review from environment variable")
        return review_content

    # Check local file
    local_path = Path("gemini-review.md")
    if local_path.exists():
        try:
            with open(local_path, encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    print("Loaded Gemini review from gemini-review.md")
                    return content
        except Exception as e:
            print(f"Warning: Failed to load gemini-review.md: {e}")

    print("No Gemini review found - Codex will review independently")
    return None


def call_codex(prompt: str, timeout: int = 300) -> Tuple[str, bool]:
    """Call Codex CLI with the given prompt.

    Args:
        prompt: The prompt to send to Codex
        timeout: Timeout in seconds

    Returns:
        Tuple of (response_text, success)
    """
    try:
        # Build command - use exec mode with sandbox for safety
        cmd = [
            "codex",
            "exec",
            "--sandbox",
            "workspace-write",
            "--full-auto",
            "--json",
            prompt,
        ]

        # Check if bypass sandbox is enabled (only for already-sandboxed environments)
        if os.environ.get("CODEX_BYPASS_SANDBOX") == "true":
            cmd = [
                "codex",
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--json",
                prompt,
            ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            print(f"Codex CLI error: {error_msg}")
            return f"Codex execution failed: {error_msg}", False

        # Parse JSONL output
        output = result.stdout.strip()
        if not output:
            return "No output from Codex", False

        messages = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if "msg" in event:
                    msg = event["msg"]
                    msg_type = msg.get("type")
                    if msg_type == "agent_message":
                        messages.append(msg.get("message", ""))
                    elif msg_type == "agent_reasoning":
                        text = msg.get("text", "")
                        if text and not text.startswith("**"):
                            messages.append(f"[Reasoning] {text}")
                elif event.get("type") == "message":
                    messages.append(event.get("message", ""))
            except json.JSONDecodeError:
                if line and not line.startswith("["):
                    messages.append(line)

        combined = "\n".join(messages) if messages else output
        return combined, True

    except subprocess.TimeoutExpired:
        return f"Codex execution timed out after {timeout} seconds", False
    except Exception as e:
        return f"Failed to execute Codex: {e}", False


def analyze_pr(
    diff: str,
    changed_files: List[str],
    pr_info: Dict[str, Any],
    gemini_review: Optional[str] = None,
) -> Tuple[str, bool]:
    """Analyze the PR using Codex.

    Args:
        diff: The PR diff
        changed_files: List of changed files
        pr_info: PR metadata
        gemini_review: Optional Gemini review for context

    Returns:
        Tuple of (analysis_text, success)
    """
    # Build the review prompt
    prompt = f"""You are Codex, an expert code reviewer. Provide a focused code review for this pull request.

**REVIEW FOCUS:**
- Code quality and patterns
- Implementation correctness
- Potential bugs or edge cases
- Performance considerations
- Security implications (if applicable)

**STRICT OUTPUT RULES:**
- Maximum {MAX_REVIEW_WORDS} words total
- Use bullet points, not paragraphs
- Only report ACTIONABLE issues (bugs, security, required fixes)
- Skip generic praise - be concise and technical
- If you agree with Gemini's assessment, say "Concur with Gemini" and add any NEW findings
- Do NOT repeat issues already covered by Gemini

"""

    # Add Gemini review context if available
    if gemini_review:
        # Truncate Gemini review if too long
        truncated_review = gemini_review[:4000] if len(gemini_review) > 4000 else gemini_review
        prompt += f"""**GEMINI'S REVIEW (for context - do not repeat):**
```
{truncated_review}
```

**IMPORTANT:** Your role is to provide a COMPLEMENTARY review. Focus on:
1. Issues Gemini may have MISSED
2. Alternative perspectives on flagged issues
3. Code patterns or architectural concerns
4. Areas where you DISAGREE with Gemini (explain why)

"""

    prompt += f"""**PR INFO:**
- PR #{pr_info["number"]}: {pr_info["title"]}
- Author: {pr_info["author"]}
- Branch: {pr_info.get("head_branch", "unknown")} -> {pr_info.get("base_branch", "main")}

**FILES CHANGED ({len(changed_files)}):**
{chr(10).join(f"- {f}" for f in changed_files[:20])}
{"... and " + str(len(changed_files) - 20) + " more" if len(changed_files) > 20 else ""}

**DIFF:**
```diff
{diff[:MAX_DIFF_CHARS]}
```
{"... (truncated)" if len(diff) > MAX_DIFF_CHARS else ""}

**OUTPUT FORMAT:**
## Codex Review

### {"Additional Issues (beyond Gemini's)" if gemini_review else "Issues"} (if any)
- [SEVERITY] File:line - Brief description

### Code Quality Notes
- Brief observations about patterns, style, or architecture

### {"Agreement/Disagreement with Gemini" if gemini_review else "Summary"}
- {"State agreement or provide alternative perspective" if gemini_review else "Brief summary of findings"}

---
*Generated by Codex AI. Complementary to {"Gemini review" if gemini_review else "human review"}.*
"""

    return call_codex(prompt)


def format_github_comment(
    analysis: str,
    commit_sha: str,
    has_gemini_context: bool,
) -> str:
    """Format the analysis as a GitHub comment.

    Args:
        analysis: The Codex analysis text
        commit_sha: Current commit SHA
        has_gemini_context: Whether Gemini review was available

    Returns:
        Formatted comment string
    """
    # Add commit marker for tracking (similar to Gemini's format)
    marker = f"<!-- codex-review-marker:commit:{commit_sha} -->"

    header = "## Codex AI Code Review"
    if has_gemini_context:
        header += " (Secondary Review)"

    comment = f"""{header}
{marker}

{analysis}

---
*Generated by Codex AI (OpenAI). {"Complementary to Gemini review." if has_gemini_context else "Independent review."}*
"""

    return comment


def post_pr_comment(comment: str, pr_info: Dict[str, Any]) -> None:
    """Post the comment to the PR using GitHub CLI."""
    fd, comment_file = tempfile.mkstemp(suffix=".md", prefix=f"codex_comment_{pr_info['number']}_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(comment)

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

        print("Successfully posted Codex review to PR")
    except subprocess.CalledProcessError as e:
        print(f"Failed to post comment: {e}")
        # Save locally as backup
        with open("codex-review.md", "w", encoding="utf-8") as f:
            f.write(comment)
        print("Review saved to codex-review.md")
    except FileNotFoundError:
        print("Failed to post comment: gh CLI not found")
    finally:
        if os.path.exists(comment_file):
            os.unlink(comment_file)


def main() -> None:
    """Main function."""
    print("Starting Codex PR Review (Secondary AI Reviewer)...")

    # Check prerequisites
    prereqs_ok, errors = check_prerequisites()
    if not prereqs_ok:
        print("ERROR: Prerequisites not met")
        for error in errors:
            print(f"  - {error}")
        print("\nSetup instructions:")
        print("1. Install Codex CLI: npm install -g @openai/codex@0.79.0")
        print("2. Authenticate: codex auth")
        exit_code = 1 if os.environ.get("CODEX_REVIEW_REQUIRED", "").lower() in ("1", "true") else 0
        sys.exit(exit_code)

    # Get PR information
    pr_info = get_pr_info()
    if not pr_info["number"]:
        print("ERROR: Not running in PR context (PR_NUMBER not set)")
        sys.exit(1)

    print(f"Analyzing PR #{pr_info['number']}: {pr_info['title']}")

    # Get current commit SHA
    current_commit = get_current_commit_sha()
    print(f"Current commit: {current_commit}")

    # Load Gemini's review for context
    gemini_review = load_gemini_review()
    has_gemini_context = gemini_review is not None

    # Get changed files and diff
    changed_files = get_changed_files()
    print(f"Changed files: {len(changed_files)}")

    diff = get_pr_diff()
    print(f"Diff size: {len(diff):,} characters")

    # Analyze with Codex
    print("Consulting Codex AI...")
    analysis, success = analyze_pr(
        diff=diff,
        changed_files=changed_files,
        pr_info=pr_info,
        gemini_review=gemini_review,
    )

    if not success:
        print(f"Warning: Codex analysis failed: {analysis}")
        # Create a minimal review noting the failure
        analysis = f"""### Review Status

Codex analysis encountered an issue: {analysis}

Please rely on Gemini's review for this PR.
"""

    # Format as GitHub comment
    comment = format_github_comment(
        analysis=analysis,
        commit_sha=current_commit,
        has_gemini_context=has_gemini_context,
    )

    # Post to PR
    post_pr_comment(comment, pr_info)

    # Save to step summary
    with open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("\n\n" + comment)

    # Save review artifact for downstream processing
    with open("codex-review.md", "w", encoding="utf-8") as f:
        f.write(comment)
    print("Saved Codex review to codex-review.md")

    print("Codex PR review complete!")


if __name__ == "__main__":
    main()

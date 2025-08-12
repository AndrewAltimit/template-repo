#!/usr/bin/env python3
"""
Improved Gemini PR Review Script with better context handling
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Model constants
PRO_MODEL = "gemini-2.5-pro"
FLASH_MODEL = "gemini-2.5-flash"
NO_MODEL = ""  # Indicates no model was successfully used
PRO_MODEL_TIMEOUT = 90  # seconds
FLASH_MODEL_TIMEOUT = 60  # seconds


def _call_gemini_with_fallback(prompt: str) -> Tuple[str, str]:
    """Calls the Gemini API with a fallback from Pro to Flash model.

    Args:
        prompt: The prompt to send to Gemini

    Returns:
        (analysis, model_used) - The analysis result and which model was used
    """

    # Helper function to clean credential messages from output
    def clean_output(output: str) -> str:
        if "Loaded cached credentials" in output:
            lines = output.split("\n")
            return "\n".join(line for line in lines if "Loaded cached credentials" not in line)
        return output

    # Try with Pro model first
    try:
        print("🔍 Attempting analysis with Gemini 2.5 Pro model...")
        result = subprocess.run(
            ["gemini", "-m", PRO_MODEL],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
            timeout=PRO_MODEL_TIMEOUT,
        )
        output = clean_output(result.stdout.strip())
        return output.strip(), PRO_MODEL
    except subprocess.TimeoutExpired:
        print(f"⏱️  Pro model timed out after {PRO_MODEL_TIMEOUT}s, trying Flash model...")
        print("   (This is likely due to network latency in CI, not a quota issue)")
    except subprocess.CalledProcessError as e:
        # Check if it's a quota limit error
        if e.stderr:
            error_text = e.stderr.lower()
            if "quota limit" in error_text or "api error" in error_text or "quota exceeded" in error_text:
                print("⚡ Quota limit reached for Pro model, falling back to Flash...")
            else:
                # Non-quota error from Pro model - surface the error
                err_msg = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
                return f"❌ Pro model failed with error: {err_msg}", NO_MODEL
        else:
            # No stderr, return the error
            return f"❌ Pro model failed with error: {str(e)}", NO_MODEL
    except Exception as e:
        # Unexpected error
        return f"❌ Unexpected error with Pro model: {str(e)}", NO_MODEL

    # Fallback to Flash model
    try:
        print("🔍 Attempting analysis with Gemini 2.5 Flash model...")
        result = subprocess.run(
            ["gemini", "-m", FLASH_MODEL],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
            timeout=FLASH_MODEL_TIMEOUT,
        )
        output = clean_output(result.stdout.strip())
        return output.strip(), FLASH_MODEL
    except subprocess.TimeoutExpired:
        err_msg = f"Flash model timed out after {FLASH_MODEL_TIMEOUT}s"
        print(f"❌ {err_msg}")
        return f"❌ Both Pro and Flash models failed. {err_msg}", NO_MODEL
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
        print(f"❌ Flash model failed: {err_msg}")
        return f"❌ Both Pro and Flash models failed. Flash error: {err_msg}", NO_MODEL
    except Exception as e:
        err_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {err_msg}")
        return f"❌ Both Pro and Flash models failed. {err_msg}", NO_MODEL


def check_gemini_cli() -> bool:
    """Check if Gemini CLI is available"""
    try:
        result = subprocess.run(["which", "gemini"], capture_output=True, text=True)
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
        with open("changed_files.txt", "r") as f:
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
    project_context_file = Path(".context/PROJECT_CONTEXT.md")
    if not project_context_file.exists():
        # Try alternate location
        project_context_file = Path("PROJECT_CONTEXT.md")

    if project_context_file.exists():
        try:
            combined_context.append(project_context_file.read_text())
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
    gemini_expression_file = Path(".context/GEMINI_EXPRESSION.md")
    if gemini_expression_file.exists():
        try:
            print("📝 Including Gemini expression philosophy in review context...")
            expression_content = gemini_expression_file.read_text()
            combined_context.append("\n\n---\n\n")
            combined_context.append(expression_content)
        except Exception as e:
            print(f"Warning: Could not read Gemini expression file: {e}")
    else:
        print("Note: Gemini expression file not found at .context/GEMINI_EXPRESSION.md")

    return "".join(combined_context)


def get_recent_pr_comments(pr_number: str) -> str:
    """Get PR comments since last Gemini review"""
    try:
        # Get all PR comments
        result = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "comments"],
            capture_output=True,
            text=True,
            check=True,
        )

        pr_data = json.loads(result.stdout)
        comments = pr_data.get("comments", [])

        # Find last Gemini comment index
        last_gemini_idx = -1
        for idx, comment in enumerate(comments):
            body = comment.get("body", "")
            if "🤖 Gemini AI Code Review" in body:
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
    except subprocess.CalledProcessError as e:
        print(f"Warning: GitHub CLI command failed: {e}")
        return ""
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse PR comments JSON: {e}")
        return ""
    except Exception as e:
        print(f"Warning: Unexpected error fetching PR comments: {e}")
        return ""


def analyze_large_pr(diff: str, changed_files: List[str], pr_info: Dict[str, Any]) -> Tuple[str, str]:
    """Analyze large PRs by breaking them down into manageable chunks

    Returns: (analysis, model_used)
    """

    project_context = get_project_context()
    file_stats = get_file_stats()
    diff_size = len(diff)

    # If diff is small enough, use single analysis
    if diff_size < 500000:  # 500KB threshold - Gemini can handle much larger context
        return analyze_complete_diff(diff, changed_files, pr_info, project_context, file_stats)

    # For large diffs, analyze by file groups
    print(f"📦 Large diff detected ({diff_size:,} chars), using chunked analysis...")

    file_chunks = chunk_diff_by_files(diff)
    analyses = []
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

    # Analyze each group
    for group_name, group_files in file_groups.items():
        if not group_files:
            continue

        group_analysis, group_model = analyze_file_group(group_name, group_files, pr_info, project_context, recent_comments)
        if group_analysis and group_model != NO_MODEL:
            analyses.append(f"### {group_name.title()} Changes\n{group_analysis}")
            successful_models.append(group_model)

    # Determine which model was predominantly used
    if successful_models:
        # If any analysis used Flash, report Flash (as it's the fallback)
        model_used = FLASH_MODEL if FLASH_MODEL in successful_models else PRO_MODEL
    else:
        # No successful analyses
        model_used = NO_MODEL

    # Combine analyses with overall summary
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
    recent_comments: str = "",
) -> Tuple[str, str]:
    """Analyze a group of related files

    Returns: (analysis, model_used)
    """

    # Combine diffs for the group (limit to reasonable size)
    combined_diff = ""
    file_list = []

    for filepath, file_diff in files[:20]:  # Increased to max 20 files per group
        file_list.append(filepath)
        # Include full file diff up to 50KB per file
        file_content = file_diff[:50000]  # 50KB per file should be safe
        combined_diff += f"\n\n=== {filepath} ===\n{file_content}"
        if len(file_diff) > 50000:
            combined_diff += f"\n... (truncated {len(file_diff) - 50000} chars)"

    prompt = f"Analyze this group of {group_name} changes from " f"PR #{pr_info['number']}:\n\n"

    # Add recent comments if provided
    if recent_comments:
        prompt += f"{recent_comments}\n\n"

    prompt += (
        f"**Files in this group:**\n"
        f"{chr(10).join(f'- {f}' for f in file_list)}\n\n"
        f"**Relevant diffs:**\n"
        f"```diff\n"
        f"{combined_diff[:200000]}\n"
        f"```\n\n"
        f"Focus on:\n"
        f"1. Correctness and potential bugs\n"
        f"2. Security implications\n"
        f"3. Best practices for {group_name} files\n"
        f"4. Consistency with project's container-first approach\n\n"
        f"Keep response concise but thorough."
    )

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
        f"{diff[:500000]}  # Increased limit to 500KB - Gemini can handle it\n"
        f"```\n"
    )

    # Add truncation message if needed
    if len(diff) > 500000:
        prompt += f"... (diff truncated, {len(diff) - 500000} chars omitted)\n\n"
    else:
        prompt += "\n"

    prompt += (
        "Please provide:\n"
        "1. **Summary**: What are the key changes?\n"
        "2. **Code Quality**: Any issues with style, structure, or best practices?\n"
        "3. **Potential Issues**: Bugs, security concerns, or logic errors?\n"
        "4. **Suggestions**: Specific improvements\n"
        "5. **Positive Aspects**: What's well done?\n\n"
        "Focus on actionable feedback considering the container-first architecture."
    )

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


def format_github_comment(analysis: str, pr_info: Dict[str, Any], model_used: str = PRO_MODEL) -> str:
    """Format the analysis as a GitHub PR comment"""
    if model_used == PRO_MODEL:
        model_display = "v2.5 Pro"
    elif model_used == FLASH_MODEL:
        model_display = "v2.5 Flash"
    else:
        model_display = "Error - No model available"
    comment = f"""## 🤖 Gemini AI Code Review

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
        with open(comment_file, "w") as f:
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

        print("✅ Successfully posted Gemini review to PR")

        # Clean up
        os.unlink(comment_file)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to post comment: {e}")
        # Save locally as backup
        with open("gemini-review.md", "w") as f:
            f.write(comment)
        print("💾 Review saved to gemini-review.md")


def main():
    """Main function"""
    print("🤖 Starting Improved Gemini PR Review...")

    # Check if Gemini CLI is available
    if not check_gemini_cli():
        print("❌ Gemini CLI not found")
        print("Setup instructions:")
        print("1. Install Node.js 18+")
        print("2. npm install -g @google/gemini-cli")
        print("3. Run 'gemini' to authenticate")
        sys.exit(0)

    # Get PR information
    pr_info = get_pr_info()
    if not pr_info["number"]:
        print("❌ Not running in PR context")
        sys.exit(1)

    print(f"📋 Analyzing PR #{pr_info['number']}: {pr_info['title']}")

    # Get changed files
    changed_files = get_changed_files()
    print(f"📁 Found {len(changed_files)} changed files")

    # Get PR diff
    print("🔍 Getting complete PR diff...")
    diff = get_pr_diff()
    print(f"📏 Diff size: {len(diff):,} characters")

    # Analyze with Gemini
    print("🧠 Consulting Gemini AI...")
    analysis, model_used = analyze_large_pr(diff, changed_files, pr_info)

    # Format as GitHub comment
    comment = format_github_comment(analysis, pr_info, model_used)

    # Post to PR
    post_pr_comment(comment, pr_info)

    # Save to step summary
    with open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a") as f:
        f.write("\n\n" + comment)

    print("✅ Gemini PR review complete!")


if __name__ == "__main__":
    main()

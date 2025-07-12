#!/usr/bin/env python3
"""
Gemini PR Review Script using CLI
Consults Gemini AI for code review insights on pull requests using the Gemini CLI
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def check_gemini_cli() -> bool:
    """Check if Gemini CLI is available"""
    try:
        # Check if gemini command exists
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


def get_pr_diff() -> str:
    """Get the actual diff of the PR"""
    try:
        # Get the diff between base and head
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


def get_project_context() -> str:
    """Get project context for better code review"""
    context_file = Path("PROJECT_CONTEXT.md")
    if context_file.exists():
        try:
            return context_file.read_text()
        except Exception as e:
            print(f"Warning: Could not read project context: {e}")
    
    # Fallback context if file doesn't exist
    return """This is a container-first project where all Python tools run in Docker containers.
It's maintained by a single developer with self-hosted infrastructure.
Focus on code quality, security, and container configurations."""


def analyze_code_changes(
    diff: str, changed_files: List[str], pr_info: Dict[str, Any]
) -> str:
    """Use Gemini CLI to analyze code changes"""
    
    # Get project context
    project_context = get_project_context()

    # Prepare the prompt
    prompt = f"""You are an expert code reviewer. Please analyze the following pull request with the project context in mind.

**PROJECT CONTEXT:**
{project_context}

**PULL REQUEST TO REVIEW:**

**Pull Request Information:**
- Title: {pr_info['title']}
- Author: {pr_info['author']}
- Description: {pr_info['body']}
- Base Branch: {pr_info['base_branch']}
- Changed Files: {len(changed_files)} files

**Changed Files:**
{chr(10).join(f'- {file}' for file in changed_files[:20])}  # Limit to first 20 files

**Code Diff (truncated if too long):**
```diff
{diff[:10000]}  # Limit diff to 10k characters
```

Please provide:
1. **Summary**: Brief overview of the changes
2. **Key Observations**: What are the main changes?
3. **Potential Issues**: Any bugs, security concerns, or code quality issues?
4. **Suggestions**: Specific improvements or recommendations
5. **Positive Aspects**: What's done well in this PR?

Keep your response concise but thorough. Focus on actionable feedback based on the project's container-first philosophy and single-maintainer design."""

    try:
        # Use piping to send prompt to Gemini CLI
        result = subprocess.run(
            [
                "gemini",
                "-m",
                "gemini-2.5-pro",
            ],  # Use the pro model for better code review
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # If it fails, try without model specification
        try:
            result = subprocess.run(
                ["gemini"], input=prompt, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e2:
            return f"Error consulting Gemini CLI: {e2.stderr}"
    except Exception as e:
        return f"Error consulting Gemini: {str(e)}"


def format_github_comment(analysis: str, pr_info: Dict[str, Any]) -> str:
    """Format the analysis as a GitHub PR comment"""
    comment = f"""## 🤖 Gemini AI Code Review

Hello @{pr_info['author']}! I've analyzed your pull request and here's my feedback:

{analysis}

---
*This review was automatically generated by Gemini AI via CLI. Please consider this as supplementary feedback to human reviews.*
"""
    return comment


def post_pr_comment(comment: str, pr_info: Dict[str, Any]):
    """Post the comment to the PR using GitHub CLI"""
    try:
        # Save comment to temporary file to avoid shell escaping issues
        with open("/tmp/gemini_comment.md", "w") as f:
            f.write(comment)

        # Use gh CLI to post comment
        subprocess.run(
            [
                "gh",
                "pr",
                "comment",
                pr_info["number"],
                "--body-file",
                "/tmp/gemini_comment.md",
            ],
            check=True,
        )

        print("✅ Successfully posted Gemini review to PR")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to post comment: {e}")
        # Still save the comment locally
        with open("gemini-review.md", "w") as f:
            f.write(comment)
        print("💾 Review saved to gemini-review.md")


def main():
    """Main function"""
    print("🤖 Starting Gemini PR Review (CLI version)...")

    # Check if Gemini CLI is available
    if not check_gemini_cli():
        print("❌ Gemini CLI not found")
        print("To set up Gemini CLI:")
        print("1. Install Node.js 18+ (recommended 22.16.0): nvm use 22.16.0")
        print("2. Install Gemini CLI: npm install -g @google/gemini-cli")
        print(
            "3. Run 'gemini' command to authenticate (happens automatically on first use)"
        )
        sys.exit(0)  # Exit gracefully since this is optional

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
    print("🔍 Getting PR diff...")
    diff = get_pr_diff()

    # Analyze with Gemini
    print("🧠 Consulting Gemini AI via CLI...")
    analysis = analyze_code_changes(diff, changed_files, pr_info)

    # Format as GitHub comment
    comment = format_github_comment(analysis, pr_info)

    # Post to PR
    post_pr_comment(comment, pr_info)

    # Also save to step summary
    with open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a") as f:
        f.write("\n\n" + comment)

    print("✅ Gemini PR review complete!")


if __name__ == "__main__":
    main()

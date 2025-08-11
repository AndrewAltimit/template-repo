#!/usr/bin/env python3
"""
Post-tool-use hook for git push detection and PR monitoring reminder.

This hook runs after Bash commands and checks if a git push was performed.
If a push is detected, it:
1. Identifies the current PR (if any)
2. Gets the pushed commit SHA
3. Reminds the agent to monitor for feedback
4. Shows the exact command to use with the commit starting point
"""

import json
import re
import subprocess
import sys


def get_current_branch():
    """Get the current git branch name."""
    try:
        result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return None


def get_pr_for_branch(branch):
    """Get PR number for the current branch."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--json", "number", "--jq", ".[0].number"],
            capture_output=True,
            text=True,
            check=True,
        )
        pr_number = result.stdout.strip()
        return pr_number if pr_number else None
    except Exception:
        return None


def get_last_commit_sha():
    """Get the SHA of the last commit."""
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return result.stdout.strip()[:8]  # Short SHA
    except Exception:
        return None


def extract_pushed_commit(output):
    """Extract the commit SHA from git push output."""
    # Look for patterns like:
    # "abc1234..def5678  branch -> branch"
    # "* [new branch]      branch -> branch"
    patterns = [
        r"([a-f0-9]{7,})\.\.([a-f0-9]{7,})",  # Range push
        r"\[new branch\].*?([a-f0-9]{7,})",  # New branch with SHA
    ]

    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            # For range, return the second SHA (new commit)
            if ".." in pattern:
                return match.group(2)[:8]
            return match.group(1)[:8]

    # If no specific SHA found, use HEAD
    return get_last_commit_sha()


def main():
    """Main hook entry point."""
    try:
        # Read the tool execution data
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        # No valid input, nothing to do
        return

    # Check if this was a Bash tool execution
    tool_name = input_data.get("tool_name")
    if tool_name != "Bash":
        return

    # Check if the command was a git push
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # Extract output from tool_response structure
    tool_response = input_data.get("tool_response", {})
    tool_output = tool_response.get("stdout", "") + tool_response.get("stderr", "")

    # Detect git push command
    if not ("git push" in command or "git push" in tool_output):
        return

    # Check if push was successful
    if "error:" in tool_output.lower() or "rejected" in tool_output.lower():
        return

    # Get current branch and PR info
    branch = get_current_branch()
    if not branch:
        return

    pr_number = get_pr_for_branch(branch)
    if not pr_number:
        # No PR exists yet, might want to create one
        print("\n💡 **Tip**: You just pushed commits but there's no open PR for this branch.", file=sys.stderr)
        print("   Consider creating a PR with: `gh pr create`", file=sys.stderr)
        return

    # Extract the pushed commit SHA
    commit_sha = extract_pushed_commit(tool_output)
    if not commit_sha:
        commit_sha = get_last_commit_sha()

    # Generate the monitoring reminder
    print("\n" + "=" * 60, file=sys.stderr)
    print("🔄 **PR FEEDBACK MONITORING REMINDER**", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"\nYou just pushed commits to PR #{pr_number} on branch '{branch}'.", file=sys.stderr)
    print("Consider monitoring for feedback on your changes:", file=sys.stderr)
    print("\n  📍 Monitor from this commit onwards:", file=sys.stderr)
    print(f"     `python scripts/pr-monitoring/pr_monitor_agent.py {pr_number} --since-commit {commit_sha}`", file=sys.stderr)
    print("\n  🔄 Or monitor all new comments:", file=sys.stderr)
    print(f"     `python scripts/pr-monitoring/pr_monitor_agent.py {pr_number}`", file=sys.stderr)
    print("\nThis will watch for:", file=sys.stderr)
    print("  • Admin comments and commands", file=sys.stderr)
    print("  • Gemini AI code review feedback", file=sys.stderr)
    print("  • CI/CD validation results", file=sys.stderr)
    print("\n💡 The monitor will return structured data when relevant comments are detected.", file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)


if __name__ == "__main__":
    main()

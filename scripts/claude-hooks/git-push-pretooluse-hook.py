#!/usr/bin/env python3
"""
PreToolUse hook that adds PR monitoring reminder to git push commands.

When a git push command is detected, this hook modifies it to include
a reminder message that displays after successful push.
"""

import datetime
import json
import re
import subprocess
import sys


def get_current_branch():
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
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


def main():
    """Main hook entry point."""
    try:
        # Read the tool execution data
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        # No valid input, pass through
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Debug: write to file to verify hook is being called
    with open(".hook-trace.log", "a") as f:
        cmd = input_data.get("tool_input", {}).get("command", "")[:50]
        f.write(f"{datetime.datetime.now()}: Hook called with tool_name={input_data.get('tool_name')}, command={cmd}\n")

    # Check if this is a Bash tool execution
    tool_name = input_data.get("tool_name")
    if tool_name != "Bash":
        # Not a bash command, pass through with allow permission
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Check if the command is a git push
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only process git push commands (not pull, clone, etc)
    if not re.search(r"\bgit\s+push\b", command):
        # Not a git push, pass through with allow permission
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Get current branch and PR info
    branch = get_current_branch()
    if not branch:
        # Can't determine branch, pass through original
        print(json.dumps({"permissionDecision": "allow"}))
        return

    pr_number = get_pr_for_branch(branch)

    # Build the reminder message
    if pr_number:
        reminder = f"""
\\n============================================================
🔄 PR FEEDBACK MONITORING REMINDER
============================================================

You just pushed commits to PR #{pr_number} on branch '{branch}'.
Consider monitoring for feedback on your changes:

  📍 Monitor from this commit onwards:
     python scripts/pr-monitoring/pr_monitor_agent.py {pr_number} --since-commit $(git rev-parse --short HEAD)

  🔄 Or monitor all new comments:
     python scripts/pr-monitoring/pr_monitor_agent.py {pr_number}

This will watch for:
  • Admin comments and commands
  • Gemini AI code review feedback
  • CI/CD validation results

💡 The monitor will return structured data when relevant comments are detected.
============================================================
"""
    else:
        reminder = f"""
\\n💡 Tip: You just pushed commits to branch '{branch}' but there's no open PR.
   Consider creating a PR with: gh pr create
"""

    # Modify the command to include the reminder on success
    # Try a simpler approach without subshell
    modified_command = f'{command} && echo "{reminder}"'

    # Update the input data with modified command
    input_data["tool_input"]["command"] = modified_command

    # Return the modified input with permission to proceed
    # Match the exact structure of the working security hook
    response = {}
    response["permissionDecision"] = "allow_with_modifications"
    response["tool_input"] = input_data.get("tool_input", {}).copy()
    response["tool_input"]["command"] = modified_command

    print(json.dumps(response))


if __name__ == "__main__":
    main()

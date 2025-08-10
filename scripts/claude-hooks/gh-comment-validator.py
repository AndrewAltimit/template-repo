#!/usr/bin/env python3
"""
Claude Code PreToolUse hook to validate GitHub comment formatting.

This hook prevents incorrect GitHub comment/PR description formatting that would
escape the ! character in ![Reaction] image tags. It enforces the proper method:
1. Use Write tool to create a temporary markdown file
2. Use gh comment --body-file to post the comment

This prevents shell escaping issues with heredocs, echo, printf, and direct --body flags.
"""

import json
import re
import sys


def main():
    # Read the tool input from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        # If we can't parse input, allow the tool to run
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Only check Bash tool calls
    if input_data.get("tool_name") != "Bash":
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Get the command being executed
    command = input_data.get("tool_input", {}).get("command", "")

    # Check if this is a GitHub comment/PR/issue command
    gh_comment_patterns = [
        r"gh\s+pr\s+comment",
        r"gh\s+issue\s+comment",
        r"gh\s+pr\s+create",
        r"gh\s+issue\s+create",
    ]

    is_gh_comment = any(re.search(pattern, command) for pattern in gh_comment_patterns)

    if not is_gh_comment:
        # Not a GitHub comment command, allow it
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Check for problematic patterns
    problematic_patterns = [
        # Direct --body flag with markdown image (handles escaped quotes in JSON)
        (r'--body\s+[\\"\']+.*!\[.*\]', "Direct --body flag with reaction images"),
        (r"--body\s+\S*.*!\[.*\]", "Direct --body flag with reaction images"),
        # Heredocs
        (r'<<\s*[\'"]?EOF', "Heredoc (cat <<EOF)"),
        (r'<<-\s*[\'"]?EOF', "Heredoc (cat <<-EOF)"),
        (r"cat\s*>.*<<", "Heredoc with cat"),
        # Echo/printf with markdown images
        (r"echo.*!\[.*\].*\|.*gh\s+(pr|issue)", "echo piped to gh"),
        (r"printf.*!\[.*\].*\|.*gh\s+(pr|issue)", "printf piped to gh"),
        # Variable expansion with markdown images
        (r"\$\(.*echo.*!\[.*\].*\)", "Command substitution with echo"),
        (r"\$\(.*printf.*!\[.*\].*\)", "Command substitution with printf"),
    ]

    violations = []
    for pattern, description in problematic_patterns:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            violations.append(description)

    # Check if command contains reaction images at all
    # Note: In JSON input, the ! might be escaped as \!
    has_reaction_image = bool(re.search(r"\\?!\[.*\]\(.*reaction.*\)", command, re.IGNORECASE))

    if violations and has_reaction_image:
        # Block the command and provide guidance
        error_message = f"""❌ Incorrect GitHub comment formatting detected!

Found issues: {', '.join(violations)}

The command contains reaction images but uses methods that will escape the '!' character.

✅ CORRECT method (documented in CLAUDE.md):
1. Use the Write tool to create a temporary markdown file:
   Write("/tmp/comment.md", "Your markdown with ![Reaction](url)")
2. Use gh with --body-file flag:
   Bash("gh pr comment PR_NUMBER --body-file /tmp/comment.md")

This preserves markdown formatting and prevents shell escaping issues.
"""

        print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": error_message}))
        return

    # Check for --body-file usage (the correct method)
    if re.search(r"--body-file\s+", command):
        # This is the correct method, ensure the file was created with Write tool
        # We can't check this directly, but we can allow it
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # For other GitHub commands without reaction images, allow them
    print(json.dumps({"permissionDecision": "allow"}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Claude Code PreToolUse hook to validate GitHub comment formatting.

This hook prevents:
1. Incorrect formatting that would escape the ! character in ![Reaction] image tags
2. Unicode emoji characters that may display as corrupted (�) in GitHub

It enforces the proper method:
1. Use Write tool to create a temporary markdown file
2. Use gh comment --body-file to post the comment
3. Use ASCII characters or reaction images instead of Unicode emojis

This prevents shell escaping issues and character corruption.
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
        # Direct --body flag with markdown image
        (r'--body\s+["\'].*!\[.*\]', "Direct --body flag with reaction images"),
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

    # Check for Unicode emoji characters that may get corrupted
    def contains_unicode_emoji(text):
        """Check if text contains Unicode emoji characters."""
        emoji_ranges = [
            (0x1F600, 0x1F64F),  # Emoticons
            (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
            (0x1F680, 0x1F6FF),  # Transport and Map
            (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
            (0x2600, 0x26FF),  # Misc symbols
            (0x2700, 0x27BF),  # Dingbats (includes checkmark 0x2705)
            (0x1F1E0, 0x1F1FF),  # Regional indicator symbols (flags)
            (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
        ]

        for char in text:
            code_point = ord(char)
            for start, end in emoji_ranges:
                if start <= code_point <= end:
                    return True, char
        return False, None

    has_emoji, emoji_char = contains_unicode_emoji(command)

    # Check if this is posting content (not just reading/listing)
    is_posting_content = bool(
        re.search(r"--body", command)
        or re.search(r"--body-file", command)
        or re.search(r"comment", command, re.IGNORECASE)
        or re.search(r"create", command, re.IGNORECASE)
    )

    if has_emoji and is_posting_content:
        # Block commands with Unicode emojis in GitHub comments
        error_message = f"""[ERROR] Unicode emoji detected in GitHub comment!

Found Unicode emoji character that may display as corrupted (replacement character) in GitHub.
Detected emoji: {repr(emoji_char)} (Unicode {hex(ord(emoji_char))})

[!] PROBLEM: Unicode emojis often appear corrupted in GitHub comments.

[SOLUTIONS]:
1. Use ASCII alternatives:
   - Instead of checkmark emoji use: [x] or DONE
   - Instead of X emoji use: [ ] or TODO
   - Instead of refresh emoji use: (refresh) or [SYNC]
   - Instead of pin emoji use: -> or [PIN]

2. Use reaction images for visual elements:
   ![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/...)

3. Use markdown formatting:
   - **Bold** for emphasis
   - _Italic_ for notes
   - `code` for technical terms
   - > Blockquotes for important messages

This prevents character corruption and ensures your message displays correctly.
"""
        print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": error_message}))
        return

    # Check if command contains reaction images at all
    # Note: In JSON input, the ! is typically escaped as \!
    # Check for both escaped and unescaped versions, and look for common reaction URLs
    has_reaction_image = bool(
        re.search(r"\\?!\[.*\]\(.*reaction.*\)", command, re.IGNORECASE)
        or re.search(r"\\?!\[.*\]\(.*githubusercontent.com/AndrewAltimit/Media.*\)", command, re.IGNORECASE)
        or re.search(r"\\?!\[Reaction\]", command, re.IGNORECASE)
    )

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

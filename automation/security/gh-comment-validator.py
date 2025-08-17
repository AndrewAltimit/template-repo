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
import logging
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from typing import List, Tuple
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def is_safe_url(url: str) -> Tuple[bool, str]:
    """Check if a URL is safe from SSRF attacks using a whitelist approach.

    To prevent DNS rebinding attacks, we use a strict whitelist of allowed
    hostnames for reaction images rather than trying to validate IPs.

    Returns (is_safe, error_message)
    """
    try:
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        scheme = parsed_url.scheme

        if not hostname:
            return False, "Invalid URL: no hostname"

        # Only allow HTTPS for security
        if scheme != "https":
            return False, f"Only HTTPS URLs are allowed, got: {scheme}"

        # Whitelist of allowed hostnames for reaction images
        # This prevents DNS rebinding since we never resolve untrusted hostnames
        ALLOWED_HOSTNAMES = [
            "raw.githubusercontent.com",  # GitHub raw content
            "github.com",  # GitHub main site
            "user-images.githubusercontent.com",  # GitHub user images
            "camo.githubusercontent.com",  # GitHub's image proxy
        ]

        # Check if hostname is in our whitelist
        hostname_lower = hostname.lower()
        if hostname_lower not in ALLOWED_HOSTNAMES:
            return False, f"Hostname not in whitelist: {hostname}"

        # Additional path validation for GitHub URLs
        if hostname_lower == "raw.githubusercontent.com":
            # Ensure it's a valid GitHub raw URL path
            path = parsed_url.path
            if not path:
                return False, "Invalid GitHub raw URL: missing path"

            # Basic validation that it looks like a GitHub raw URL
            # Format: /owner/repo/refs/heads/branch/path
            path_parts = path.strip("/").split("/")
            if len(path_parts) < 5:
                return False, "Invalid GitHub raw URL format"

            # Check that it's pointing to a reasonable file extension for images
            if path_parts[-1]:
                ext = path_parts[-1].split(".")[-1].lower() if "." in path_parts[-1] else ""
                allowed_extensions = ["png", "jpg", "jpeg", "gif", "webp", "svg"]
                if ext not in allowed_extensions:
                    return False, f"Invalid image extension: {ext}"

        # Reject any URL with numeric IP addresses (even in whitelist check above)
        # This prevents bypasses like https://127.0.0.1 or https://192.168.1.1
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", hostname):
            return False, "Direct IP addresses are not allowed"

        # Reject IPv6 addresses
        if ":" in hostname and "[" in hostname:
            return False, "IPv6 addresses are not allowed"

        return True, ""

    except Exception as e:
        # On any parsing error, reject the URL
        return False, f"Error validating URL: {str(e)}"


def extract_reaction_urls(text: str) -> List[Tuple[str, str]]:
    """Extract reaction image URLs from markdown text.

    Returns list of tuples: (full_match, url)
    """
    urls = []

    # Pattern to match reaction images
    # Handles both escaped and unescaped versions
    patterns = [
        r"!\[([^\]]*)\]\((https?://[^)]+(?:reaction|Media)[^)]+)\)",
        r"\\!\[([^\]]*)\]\((https?://[^)]+(?:reaction|Media)[^)]+)\)",
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            full_match = match.group(0)
            url = match.group(2) if len(match.groups()) >= 2 else match.group(1)
            # Clean up escaped quotes if present
            url = url.replace('\\"', '"').replace("\\/", "/")
            urls.append((full_match, url))

    return urls


def validate_reaction_url(url: str, timeout: int = 5) -> Tuple[bool, str]:
    """Check if a reaction image URL exists.

    Returns (is_valid, error_message)
    """
    # First, check if the URL is safe from SSRF attacks
    is_safe, safety_error = is_safe_url(url)
    if not is_safe:
        return False, f"Security violation: {safety_error}"

    try:
        # Create a HEAD request to check if the URL exists
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "gh-comment-validator/1.0")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Check if we got a successful response
            if response.status == 200:
                return True, ""
            else:
                return False, f"URL returned status {response.status}"

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "Image not found (404)"
        else:
            return False, f"HTTP error {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL error: {str(e)}"
    except Exception as e:
        # For any other errors, we'll be lenient and allow it
        # (network might be down, etc.)
        # Log the issue for visibility without failing the check
        logging.warning(f"Could not verify URL {url}: {e}")
        return True, f"Could not verify (network issue): {str(e)}"


def check_reaction_urls_in_file(filepath: str) -> List[Tuple[str, str]]:
    """Check reaction URLs in a file that will be used with --body-file.

    Returns list of invalid URLs with error messages.
    """
    invalid_urls = []

    try:
        # Security check: Ensure the file path is within allowed directories
        # We allow temp directory and current working directory's temp files
        temp_dir = os.path.realpath(tempfile.gettempdir())
        cwd = os.path.realpath(os.getcwd())

        # Resolve the filepath to prevent traversal attacks
        resolved_path = os.path.realpath(filepath)

        # Check if the resolved path is within allowed directories
        allowed = False
        if resolved_path.startswith(temp_dir):
            allowed = True
        elif resolved_path.startswith(cwd):
            # Only allow if it's in a temp-like subdirectory of CWD
            relative_path = os.path.relpath(resolved_path, cwd)
            if relative_path.startswith("tmp") or relative_path.startswith(".tmp"):
                allowed = True

        if not allowed:
            # Security violation - path traversal attempt or unauthorized location
            return [(filepath, "Security violation: file path is outside allowed directories")]

        # Try to read the file that will be used
        with open(resolved_path, "r") as f:
            content = f.read()

        # Extract and validate URLs
        urls = extract_reaction_urls(content)
        for full_match, url in urls:
            is_valid, error = validate_reaction_url(url)
            if not is_valid:
                invalid_urls.append((url, error))

    except FileNotFoundError:
        # File doesn't exist yet (might be created later), skip validation
        pass
    except Exception as e:
        # Any other error reading the file, skip validation but log warning
        print(f"Warning: Could not validate URLs in {filepath} due to an unexpected error: {e}", file=sys.stderr)

    return invalid_urls


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
        print(
            json.dumps(
                {
                    "permissionDecision": "deny",
                    "permissionDecisionReason": error_message,
                }
            )
        )
        return

    # Check if command contains reaction images at all
    # Note: In JSON input, the ! is typically escaped as \!
    # Check for both escaped and unescaped versions, and look for common reaction URLs
    has_reaction_image = bool(
        re.search(r"\\?!\[.*\]\(.*reaction.*\)", command, re.IGNORECASE)
        or re.search(
            r"\\?!\[.*\]\(.*githubusercontent.com/AndrewAltimit/Media.*\)",
            command,
            re.IGNORECASE,
        )
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

        print(
            json.dumps(
                {
                    "permissionDecision": "deny",
                    "permissionDecisionReason": error_message,
                }
            )
        )
        return

    # Check for --body-file usage (the correct method)
    if re.search(r"--body-file\s+", command):
        # This is the correct method, but let's validate the reaction URLs
        # Extract the filepath from the command
        file_match = re.search(r"--body-file\s+([^\s]+)", command)
        if file_match:
            filepath = file_match.group(1)
            # Remove quotes if present
            filepath = filepath.strip('"').strip("'")

            # Check reaction URLs in the file
            invalid_urls = check_reaction_urls_in_file(filepath)

            if invalid_urls:
                # Build error message
                error_lines = ["❌ Invalid reaction image URLs detected!"]
                error_lines.append("")
                for url, error in invalid_urls:
                    error_lines.append(f"• {url}")
                    error_lines.append(f"  Error: {error}")
                    error_lines.append("")

                error_lines.append("Please check that the reaction image URLs exist.")
                error_lines.append("Available reactions: https://github.com/AndrewAltimit/Media/tree/main/reaction")
                error_lines.append("")
                error_lines.append("Common reaction images:")
                error_lines.append("• teamwork.webp")
                error_lines.append("• felix.webp")
                error_lines.append("• miku_typing.webp")
                error_lines.append("• confused.gif")
                error_lines.append("• youre_absolutely_right.webp")

                error_message = "\n".join(error_lines)

                print(
                    json.dumps(
                        {
                            "permissionDecision": "deny",
                            "permissionDecisionReason": error_message,
                        }
                    )
                )
                return

        # URLs are valid or couldn't be checked, allow the command
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # For other GitHub commands without reaction images, allow them
    print(json.dumps({"permissionDecision": "allow"}))


if __name__ == "__main__":
    main()

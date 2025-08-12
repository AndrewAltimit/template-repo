#!/usr/bin/env python3
"""
Automatic secret masking for GitHub comments.
Ensures no secrets are ever posted to GitHub by any agent or automation tool.
Uses .secrets.yaml configuration from repository root.
"""

import json
import os
import re
import sys
from pathlib import Path

import yaml


class SecretMasker:
    def __init__(self):
        self.config = self._load_config()
        self.secrets = self._load_secrets()
        self.patterns = self._compile_patterns()

    def _load_config(self):
        """Load configuration from .secrets.yaml in repository root."""
        # Try multiple locations for the config file
        possible_paths = [
            Path(__file__).parent.parent.parent / ".secrets.yaml",  # Repository root
            Path.cwd() / ".secrets.yaml",  # Current working directory
            Path(__file__).parent / "secrets-config.yaml",  # Local fallback for compatibility
        ]

        for config_path in possible_paths:
            if config_path.exists():
                try:
                    with open(config_path, "r") as f:
                        if config_path.suffix == ".yaml":
                            return yaml.safe_load(f)
                        else:
                            return json.load(f)
                except (FileNotFoundError, yaml.YAMLError, json.JSONDecodeError) as e:
                    print(
                        f"[Secret Masker] Warning: Could not load config from {config_path}: {e}",
                        file=sys.stderr,
                    )

        # Fail-closed: deny commands if no config file found (security-critical component)
        print(
            "[Secret Masker] ERROR: No configuration file found. Blocking command for security.",
            file=sys.stderr,
        )
        print(
            "[Secret Masker] Please ensure .secrets.yaml exists in repository root.",
            file=sys.stderr,
        )
        raise FileNotFoundError("Security configuration file .secrets.yaml not found - failing closed for security")

    def _load_secrets(self):
        """Load all potential secrets from environment based on config."""
        secrets = {}
        # Handle both list and dict format for environment_variables
        env_vars = self.config.get("environment_variables", [])
        if isinstance(env_vars, dict):
            env_vars = env_vars.get("secrets", [])

        auto_detect = self.config.get("auto_detection", {})
        settings = self.config.get("settings", {})
        min_length = settings.get("minimum_secret_length", 4)

        # Load explicitly configured environment variables
        for var_name in env_vars:
            if var_name in os.environ:
                value = os.environ[var_name]
                if value and len(value) >= min_length:
                    secrets[var_name] = value

        # Auto-detect sensitive environment variables if enabled
        if auto_detect.get("enabled", True):
            patterns = auto_detect.get("include_patterns", auto_detect.get("patterns", []))
            excludes = auto_detect.get("exclude_patterns", auto_detect.get("exclude", []))

            for key, value in os.environ.items():
                # Skip if already added
                if key in secrets:
                    continue

                # Check exclusion patterns
                excluded = False
                for exclude_pattern in excludes:
                    if self._matches_pattern(key.upper(), exclude_pattern):
                        excluded = True
                        break

                if excluded:
                    continue

                # Check inclusion patterns
                for pattern in patterns:
                    if self._matches_pattern(key.upper(), pattern):
                        if value and len(value) >= min_length:
                            secrets[key] = value
                        break

        # Add explicitly defined mask vars from MASK_ENV_VARS (backward compatibility)
        mask_vars = os.getenv("MASK_ENV_VARS", "").split(",")
        for var in mask_vars:
            var = var.strip()
            if var and var in os.environ:
                value = os.environ[var]
                if value and len(value) >= min_length:
                    secrets[var] = value

        return secrets

    def _matches_pattern(self, text, pattern):
        """Check if text matches a glob-like pattern."""
        # Convert glob pattern to regex
        regex_pattern = pattern.replace("*", ".*")
        regex_pattern = f"^{regex_pattern}$"
        return bool(re.match(regex_pattern, text))

    def _compile_patterns(self):
        """Compile regex patterns from config."""
        patterns = []
        # Handle both list and dict format for patterns
        pattern_items = self.config.get("patterns", [])
        if isinstance(pattern_items, dict):
            pattern_items = pattern_items.get("items", [])

        settings = self.config.get("settings", {})
        case_sensitive = settings.get("case_sensitive_patterns", False)

        for item in pattern_items:
            pattern = item.get("pattern")
            name = item.get("name", "SECRET")

            if pattern:
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    compiled = re.compile(pattern, flags)
                    patterns.append((compiled, name))
                except re.error as e:
                    print(
                        f"[Secret Masker] Invalid regex pattern for {name}: {e}",
                        file=sys.stderr,
                    )

        return patterns

    def mask_text(self, text):
        """Mask all secrets in text."""
        masked = text
        settings = self.config.get("settings", {})
        mask_format = settings.get("mask_format", "[MASKED_{name}]")

        # First mask known environment secrets (longest first to avoid partial matches)
        # Sort by length (longest first) to prevent partial masking,
        # e.g., masking "SECRET" inside "SUPER_SECRET"
        sorted_secrets = sorted(self.secrets.items(), key=lambda x: len(x[1]), reverse=True)

        for key, value in sorted_secrets:
            if value and value in masked:
                # Use the variable name in the mask for clarity
                mask = mask_format.replace("{name}", key)
                masked = masked.replace(value, mask)

        # Then mask pattern-based secrets
        for pattern, name in self.patterns:

            def replace_with_mask(match):
                mask = mask_format.replace("{name}", name)
                return mask

            masked = pattern.sub(replace_with_mask, masked)

        return masked

    def process_command(self, command):
        """Process and mask secrets in gh commands."""
        # Check if this is a gh comment command
        gh_patterns = [
            r"gh\s+pr\s+comment",
            r"gh\s+issue\s+comment",
            r"gh\s+pr\s+create",
            r"gh\s+issue\s+create",
            r"gh\s+pr\s+review",
        ]

        is_gh_comment = any(re.search(p, command) for p in gh_patterns)
        if not is_gh_comment:
            return command  # Not a gh comment, return unchanged

        # Security check: Block commands that read body from stdin (--body-file - or --body-file=-)
        # This is necessary because we cannot inspect or sanitize stdin content
        if re.search(r"--body-file(\s+|=)-(\s|$)", command):
            return "BLOCK_STDIN"

        # Handle different body formats

        # Pattern 1: --body with quotes (single or double)
        body_match = re.search(r'--body\s+(["\'])(.+?)\1', command, re.DOTALL)
        if body_match:
            body_content = body_match.group(2)
            masked_body = self.mask_text(body_content)

            if masked_body != body_content:
                quote = body_match.group(1)
                masked_command = command.replace(body_match.group(0), f"--body {quote}{masked_body}{quote}")
                return masked_command

        # Pattern 2: --body with heredoc or command substitution
        # e.g., --body "$(cat <<EOF ... EOF)"
        heredoc_match = re.search(r'--body\s+["\']?\$\(cat\s*<<.*?\)[\"\']?', command, re.DOTALL)
        if heredoc_match:
            # Extract the content between heredoc markers
            heredoc_content_match = re.search(r'<<[\'"]?(\w+)[\'"]?\n(.*?)\n\1', command, re.DOTALL)
            if heredoc_content_match:
                content = heredoc_content_match.group(2)
                masked_content = self.mask_text(content)
                if masked_content != content:
                    masked_command = command.replace(content, masked_content)
                    return masked_command

        # Pattern 3: --body-file (check if we need to warn about file contents)
        # We can't mask file contents here, but we return unchanged
        if re.search(r"--body-file\s+", command):
            return command

        # Pattern 4: Unquoted --body (less common but possible)
        unquoted_match = re.search(r"--body\s+([^\s\-]+)", command)
        if unquoted_match:
            body_content = unquoted_match.group(1)
            masked_body = self.mask_text(body_content)

            if masked_body != body_content:
                masked_command = command.replace(unquoted_match.group(0), f'--body "{masked_body}"')
                return masked_command

        return command


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Only process Bash commands
    if input_data.get("tool_name") != "Bash":
        # Pass through non-Bash commands unchanged with permission
        print(json.dumps({"permissionDecision": "allow"}))
        return

    command = input_data.get("tool_input", {}).get("command", "")

    try:
        # Initialize masker and process
        masker = SecretMasker()
        processed_result = masker.process_command(command)
    except FileNotFoundError as e:
        # Fail-closed: block the command if config not found
        print(json.dumps({"permissionDecision": "block", "reason": str(e)}))
        return

    # Check if command should be blocked due to stdin usage
    if processed_result == "BLOCK_STDIN":
        print(
            json.dumps(
                {
                    "permissionDecision": "block",
                    "reason": (
                        "Security risk: Reading comment body from stdin (--body-file -) "
                        "is not allowed as it cannot be sanitized for secrets."
                    ),
                }
            )
        )
        return

    masked_command = processed_result

    # Prepare the response
    response = {}

    # If command was modified, update it and log
    if masked_command != command:
        # Log what we masked (for debugging) - to stderr so it doesn't affect the JSON output
        settings = masker.config.get("settings", {})
        if settings.get("log_masked_secrets", True):
            print(
                "[Secret Masker] Automatically masked secrets in GitHub comment",
                file=sys.stderr,
            )

        # Return modified command with appropriate permission
        response["permissionDecision"] = "allow_with_modifications"
        response["tool_input"] = input_data.get("tool_input", {}).copy()
        response["tool_input"]["command"] = masked_command
    else:
        # No modifications needed, allow the original command
        response["permissionDecision"] = "allow"

    # Output the complete response
    print(json.dumps(response))


if __name__ == "__main__":
    main()

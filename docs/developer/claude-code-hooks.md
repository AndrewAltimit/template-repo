# gh-validator Security System

This document describes the gh-validator security system that protects GitHub comments from secrets and formatting issues.

## Overview

The `gh-validator` is a Rust binary that shadows the `gh` CLI. It intercepts all `gh` commands and validates content-posting commands before execution.

## Installation

### Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/AndrewAltimit/template-repo/main/tools/rust/gh-validator/install.sh | bash
```

### Manual Install

1. Download the binary for your platform from [Releases](https://github.com/AndrewAltimit/template-repo/releases)
2. Place it in `~/.local/bin/gh`
3. Ensure `~/.local/bin` comes before `/usr/bin` in your PATH:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

## How It Works

1. Agent executes `gh` command
2. The gh-validator binary intercepts it (via PATH shadowing)
3. For non-content commands (e.g., `gh pr list`), passes through immediately
4. For content commands (e.g., `gh pr comment`):
   - Masks secrets based on `.secrets.yaml` config
   - Blocks Unicode emojis
   - Validates reaction image URLs
   - Checks for stdin usage (blocked)
5. Executes the real `gh` binary with validated/masked arguments

## What It Validates

- **Secret Masking**: Detects and masks secrets from environment variables and regex patterns
- **Unicode Emoji Detection**: Blocks emojis that may display as corrupted characters
- **URL Validation**: Verifies reaction image URLs exist (with SSRF protection)
- **Stdin Blocking**: Prevents `--body-file -` for security

## Configuration

Secrets to mask are configured in `.secrets.yaml` in repository root:

```yaml
environment_variables:
  - GITHUB_TOKEN
  - OPENROUTER_API_KEY
  - DB_PASSWORD

patterns:
  - name: GITHUB_TOKEN
    pattern: "ghp_[A-Za-z0-9_]{36,}"

auto_detection:
  enabled: true
  include_patterns: ["*_TOKEN", "*_SECRET", "*_KEY"]
  exclude_patterns: ["PUBLIC_*"]
```

The validator searches for config in:
1. Current directory (up to git root)
2. Binary directory (up to git root)
3. `~/.secrets.yaml`
4. `~/.config/gh-validator/.secrets.yaml`

## Correct GitHub Comment Method

When posting GitHub comments with reaction images, always use this pattern:

```python
# Step 1: Use Write tool to create markdown file
Write("/tmp/comment.md", """
Your comment text here.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_typing.webp)
""")

# Step 2: Use gh with --body-file flag
Bash("gh pr comment 50 --body-file /tmp/comment.md")
```

This preserves markdown formatting and allows URL validation.

## Testing

### Verify installation
```bash
which gh
# Should show: ~/.local/bin/gh

gh --version
# Should show the real gh version (validator passes through)
```

### Test emoji blocking
```bash
gh pr comment 1 --body "Test with emoji (celebration)"
# Should be blocked with error about Unicode emoji
```

### Test secret masking
```bash
export TEST_SECRET="super-secret-value"
# Add TEST_SECRET to .secrets.yaml environment_variables
gh pr comment 1 --body "Secret is super-secret-value"
# Should mask the secret before posting
```

## Benefits

- **No Python Runtime**: Single binary with no dependencies
- **Cross-Platform**: Builds for Linux, macOS, and Windows
- **Fast**: Rust implementation with minimal overhead
- **Fail-Closed**: Blocks commands if config missing or URLs unverifiable
- **SSRF Protection**: Only allows whitelisted hostnames for reaction images

## Troubleshooting

If validation isn't working:

1. **Check PATH order**:
   ```bash
   echo $PATH | tr ':' '\n' | head -5
   # ~/.local/bin should be before /usr/bin
   ```

2. **Verify binary is executable**:
   ```bash
   ls -la ~/.local/bin/gh
   ```

3. **Check config is found**:
   The validator will error if no `.secrets.yaml` is found (fail-closed).

## Source Code

The gh-validator source is at `tools/rust/gh-validator/`. See the [README](../../tools/rust/gh-validator/README.md) for development details.

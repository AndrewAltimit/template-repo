# Security Hooks (Universal Approach)

This document describes the universal security hook system that works with ALL agents including Claude Code.

## Overview

**Important Change**: Claude Code no longer uses agent-specific hooks. Instead, ALL agents (including Claude Code) use the same universal wrapper approach through shell aliasing.

## Universal Security System

### How It Works

All agents use the same security validation path:
1. Agent executes `gh` command
2. Shell alias redirects to `gh-wrapper.sh`
3. Wrapper validates command through Python validators
4. If validated, actual `gh` command executes

### Setup

For ALL agents including Claude Code:

```bash
# One-time setup
source automation/security/setup-agent-hooks.sh

# Or add to shell configuration for permanent setup
echo 'source /path/to/automation/security/setup-agent-hooks.sh' >> ~/.bashrc
```

### Components

1. **Universal Wrapper** (`automation/security/gh-wrapper.sh`)
   - POSIX-compliant shell script
   - Works with all shells (sh, dash, bash, zsh)
   - Validates based on arguments (--body, --notes, --message, etc.)
   - Dynamic gh binary discovery
   - Python 3 dependency checking

2. **Secret Masker** (`automation/security/github-secrets-masker.py`)
   - Automatically masks secrets in GitHub comments
   - Uses `.secrets.yaml` configuration from repository root
   - Works transparently - agents don't know masking occurred
   - Prevents exposure of API keys, tokens, passwords, etc.

3. **GitHub Comment Validator** (`automation/security/gh-comment-validator.py`)
   - Prevents incorrect GitHub comment formatting
   - Blocks Unicode emojis that may appear corrupted
   - Ensures reaction images aren't escaped
   - Enforces proper use of `--body-file` for complex markdown

## Configuration

### `.claude/settings.json` and `.claude/README.md`

The `.claude/settings.json` is now simplified to an empty configuration:
```json
{}
```

No hooks are needed - Claude Code uses the universal wrapper like all other agents.

For more details, see `.claude/README.md` which explains the empty configuration and the universal security wrapper approach.

### Secret Masking (`.secrets.yaml`)

Secrets to mask are configured in `.secrets.yaml` in repository root:

```yaml
environment_variables:
  - GITHUB_TOKEN
  - OPENROUTER_API_KEY
  - DB_PASSWORD
  # ... more variables

patterns:
  - name: GITHUB_TOKEN
    pattern: "ghp_[A-Za-z0-9_]{36,}"
  # ... more patterns

auto_detection:
  enabled: true
  include_patterns: ["*_TOKEN", "*_SECRET", "*_KEY"]
  exclude_patterns: ["PUBLIC_*"]
```

## What It Prevents

- Secrets appearing in public GitHub comments
- Direct `--body` flag usage with reaction images
- Heredocs (`cat <<EOF`) that can escape special characters
- Echo/printf piped to gh commands
- Command substitution containing reaction images
- Unicode emojis that display as corrupted characters

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

This preserves markdown formatting and prevents shell escaping issues.

## Testing

### Check if hooks are active
```bash
agent_hooks_status
```

### Test secret masking
```bash
export TEST_SECRET="super-secret-value"
echo "  - TEST_SECRET" >> .secrets.yaml
gh pr comment 1 --body "Secret is super-secret-value"
# Should mask the secret
```

### Test validators directly
```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "gh pr comment 1 --body \"Token is ghp_test123\""}}' | \
  python3 automation/security/github-secrets-masker.py
```

## Benefits

- **Universal Protection**: All agents use the same security validation
- **No Configuration Needed**: Works automatically through shell aliasing
- **Prevents Common Mistakes**: Catches issues before they happen
- **Provides Guidance**: Explains the correct approach when blocking
- **Maintains Code Quality**: Enforces project conventions automatically
- **Learning Tool**: Helps users understand best practices

## Troubleshooting

If security hooks aren't working:

1. **Re-source the setup script**:
   ```bash
   source automation/security/setup-agent-hooks.sh
   ```

2. **Check alias is active**:
   ```bash
   alias gh
   # Should show: alias gh='/path/to/automation/security/gh-wrapper.sh'
   ```

3. **Verify Python 3 is available**:
   ```bash
   python3 --version
   ```

4. **Check wrapper permissions**:
   ```bash
   chmod +x automation/security/*.sh
   ```

## Migration from Claude Code Hooks

If you previously used Claude Code hooks:
1. The old hooks in `.claude/settings.json` have been removed (see `.claude/README.md` for details)
2. The `bash-pretooluse-hook.sh` file has been removed
3. Everything now works through the universal wrapper
4. No action needed - just source the setup script

## References

- [Universal Security Hooks Documentation](../../automation/security/README.md)
- [GitHub Etiquette Guide](../ai-agents/github-etiquette.md)
- [Project Instructions](../../CLAUDE.md)

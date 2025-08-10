# Claude Code Hooks

This document describes the Claude Code hook system that helps enforce best practices and prevent common mistakes when using Claude Code.

## Overview

Claude Code supports custom hooks that run before or after tool executions. These hooks can validate parameters, block problematic commands, or provide guidance to ensure correct usage patterns.

## Current Hooks

### Security Hooks (Universal)

**Purpose**: Automatic secret masking and validation for all agents.

**Main Hook**: `scripts/security-hooks/bash-pretooluse-hook.sh`

**Components**:

1. **Secret Masker** (`scripts/security-hooks/github-secrets-masker.py`)
   - Automatically masks secrets in GitHub comments
   - Uses `.secrets.yaml` configuration from repository root
   - Works transparently - agents don't know masking occurred
   - Prevents exposure of API keys, tokens, passwords, etc.

2. **GitHub Comment Formatter** (`scripts/claude-hooks/gh-comment-validator.py`)
   - Prevents incorrect GitHub comment formatting
   - Ensures reaction images aren't escaped
   - Claude-specific but available to all agents

**What it prevents**:
- Secrets appearing in public GitHub comments
- Direct `--body` flag usage with reaction images
- Heredocs (`cat <<EOF`) that can escape special characters
- Echo/printf piped to gh commands
- Command substitution containing reaction images

**Why this matters**:
- Secrets in public comments are a security risk
- Shell escaping can turn `![Reaction]` into `\![Reaction]`, breaking image display

## Configuration

### Claude Code
Hooks are configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": {
      "Bash": "./scripts/security-hooks/bash-pretooluse-hook.sh"
    }
  }
}
```

### Secret Masking
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

## How It Works

1. When Claude Code attempts to use a tool, the PreToolUse hook is triggered
2. The hook receives tool parameters as JSON on stdin
3. The hook validates the parameters and returns a permission decision:
   - `{"permissionDecision": "allow"}` - Tool execution proceeds
   - `{"permissionDecision": "deny", "permissionDecisionReason": "..."}` - Tool is blocked with explanation
   - `{"permissionDecision": "ask"}` - User is prompted for confirmation

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

## Creating New Hooks

To add a new hook:

1. Create a Python script in `scripts/claude-hooks/`
2. Read tool input from stdin as JSON
3. Implement validation logic
4. Return permission decision as JSON
5. Register in `.claude/settings.json`

Example hook structure:

```python
#!/usr/bin/env python3
import json
import sys

def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"permissionDecision": "allow"}))
        return

    # Validation logic here
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input", {})

    # Return decision
    if some_condition:
        print(json.dumps({
            "permissionDecision": "deny",
            "permissionDecisionReason": "Explanation of why blocked"
        }))
    else:
        print(json.dumps({"permissionDecision": "allow"}))

if __name__ == "__main__":
    main()
```

## Testing Hooks

Test hooks manually by piping JSON input:

```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "test command"}}' | \
  python3 scripts/claude-hooks/your-hook.py
```

## Benefits

- **Prevents Common Mistakes**: Catches issues before they happen
- **Provides Guidance**: Explains the correct approach when blocking
- **Maintains Code Quality**: Enforces project conventions automatically
- **Learning Tool**: Helps users understand best practices

## Future Enhancements

Potential areas for additional hooks:
- Git commit message formatting validation
- Security checks for sensitive file operations
- Docker command validation for proper user permissions
- API key exposure prevention

## References

- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [GitHub Etiquette Guide](GITHUB_ETIQUETTE_FOR_AI_AGENTS.md)
- [Project Instructions](../CLAUDE.md)

# Agent-Agnostic Security Hooks

This directory contains security hooks that can be used by any AI agent or automation tool, not just Claude Code.

## Overview

The security hooks provide:
1. **Secret masking** - Automatically masks sensitive information in GitHub comments
2. **Format validation** - Ensures correct markdown formatting for GitHub comments
3. **Unicode emoji prevention** - Blocks Unicode emojis that may appear corrupted

## Components

### For Claude Code

Claude Code uses hooks via `.claude/settings.json`:
- `bash-pretooluse-hook.sh` - Main hook chain for Bash commands
- `github-secrets-masker.py` - Masks sensitive information
- `gh-comment-validator.py` - Validates GitHub comment formatting

### For Other AI Agents

Other agents can use the wrapper approach:
- `gh-wrapper.sh` - Wrapper script for gh CLI commands
- `setup-agent-hooks.sh` - Setup script to enable the wrapper

## Usage

### Method 1: Claude Code (Automatic)

Claude Code automatically uses these hooks via the configuration in `.claude/settings.json`. No setup required.

### Method 2: Wrapper Script (For Other Agents)

#### One-time Setup

```bash
# Source the setup script in your agent's environment
source /path/to/scripts/security-hooks/setup-agent-hooks.sh
```

This creates an alias for `gh` that routes commands through the validation wrapper.

#### Permanent Setup

Add to your agent's shell configuration (`.bashrc`, `.zshrc`, etc.):

```bash
# Enable security hooks for GitHub operations
source /path/to/template-repo/scripts/security-hooks/setup-agent-hooks.sh
```

#### Docker/Container Setup

In your Dockerfile or entrypoint script:

```dockerfile
# Copy hooks
COPY scripts/security-hooks /app/security-hooks

# Set up alias in container
RUN echo 'source /app/security-hooks/setup-agent-hooks.sh' >> /etc/bash.bashrc
```

#### Python Agent Setup

For Python-based agents that use subprocess:

```python
import subprocess
import os

# Set up environment with gh alias
env = os.environ.copy()
hooks_dir = "/path/to/scripts/security-hooks"
env['PATH'] = f"{hooks_dir}:{env['PATH']}"

# Now gh commands will use the wrapper
result = subprocess.run(
    ["gh", "pr", "comment", "123", "--body-file", "/tmp/comment.md"],
    env=env,
    capture_output=True
)
```

### Method 3: Direct Validation (API)

For agents that need programmatic validation:

```python
import json
import subprocess

def validate_gh_command(command):
    """Validate a gh command before execution."""
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": f"gh {command}"}
    }

    # Run through validators
    result = subprocess.run(
        ["python3", "/path/to/github-secrets-masker.py"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True
    )

    response = json.loads(result.stdout)
    if response.get("permissionDecision") == "deny":
        raise ValueError(response.get("permissionDecisionReason"))

    return response.get("modifiedCommand", f"gh {command}")
```

## What Gets Validated

### GitHub Comment Commands

The following commands are validated:
- `gh pr comment`
- `gh issue comment`
- `gh pr create`
- `gh issue create`

### Validation Rules

1. **Secret Masking**
   - API tokens and keys are automatically masked
   - Sensitive patterns are replaced with `[MASKED]`

2. **Format Validation**
   - Blocks direct `--body` with reaction images
   - Prevents heredocs that would escape markdown
   - Requires using `--body-file` for complex markdown

3. **Unicode Emoji Prevention**
   - Blocks Unicode emoji characters (🎉, ✅, etc.)
   - Suggests ASCII alternatives or reaction images
   - Prevents character corruption in GitHub

## Testing

### Test the Wrapper

```bash
# Source the setup
source scripts/security-hooks/setup-agent-hooks.sh

# Test with a valid command
gh pr list

# Test with a problematic command (should be blocked)
gh pr comment 123 --body "Test ✅ done!"
# ERROR: Unicode emoji detected

# Test with correct format
echo "Test comment" > /tmp/comment.md
gh pr comment 123 --body-file /tmp/comment.md
# Success
```

### Test Individual Validators

```bash
# Test secret masking
echo '{"tool_name": "Bash", "tool_input": {"command": "gh pr comment 123 --body \"API_KEY=sk-1234\""}}' | \
  python3 scripts/security-hooks/github-secrets-masker.py

# Test comment validation
echo '{"tool_name": "Bash", "tool_input": {"command": "gh pr comment 123 --body \"![Reaction](url)\""}}' | \
  python3 scripts/security-hooks/gh-comment-validator.py
```

## Troubleshooting

### Hooks Not Working

Check if hooks are active:
```bash
agent_hooks_status
```

### Permission Denied

Make sure scripts are executable:
```bash
chmod +x scripts/security-hooks/*.sh
```

### Python Module Errors

Ensure Python 3 is available:
```bash
python3 --version
```

## Security Considerations

- These hooks run with the same permissions as the calling agent
- They do not prevent all security issues, only common ones
- Always review agent-generated commands before production use
- Consider additional sandboxing for untrusted agents

## Contributing

When adding new validators:
1. Create a new Python script following the existing pattern
2. Add it to the hook chain in `bash-pretooluse-hook.sh`
3. Update `gh-wrapper.sh` to include the new validator
4. Add tests and documentation

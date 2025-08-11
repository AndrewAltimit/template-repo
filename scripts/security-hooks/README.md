# Security Hooks

This directory contains agent-agnostic security hooks that can be used by any AI agent or automation tool to prevent accidental exposure of secrets and ensure proper formatting in public outputs.

## Overview

The security hooks system provides automatic secret masking for all GitHub comments and public outputs, ensuring that sensitive information is never exposed in:
- Pull request comments
- Issue comments
- PR descriptions
- Review comments

## Components

### 1. `github-secrets-masker.py`
**Purpose**: Automatically masks secrets in GitHub comments before they are posted.

**Features**:
- Loads configuration from `.secrets.yaml` in repository root
- Detects and masks environment variable values
- Identifies common secret patterns (API keys, tokens, etc.)
- Transparent operation - agents don't know masking occurred

**How it works**:
1. Intercepts `gh` commands that post comments
2. Extracts comment body content
3. Replaces any detected secrets with `[MASKED_VARNAME]`
4. Returns modified command for execution

### 2. `bash-pretooluse-hook.sh`
**Purpose**: Main entry point for Bash command validation and security.

**Features**:
- Chains multiple security validators
- Works with any AI agent that supports hooks
- Gracefully handles missing validators
- Maintains compatibility with agent-specific hooks

### 3. `gh-comment-validator.py`
**Purpose**: Validates GitHub comment formatting for reaction images and prevents Unicode emoji corruption.

**Features**:
- Prevents incorrect markdown formatting that would escape `!` characters
- Blocks Unicode emojis that may appear corrupted in GitHub
- Enforces proper use of `--body-file` for complex markdown

### 4. `gh-wrapper.sh` (NEW - Agent-Agnostic)
**Purpose**: Wrapper script for gh CLI that any agent can use via alias.

**Features**:
- Works with any AI agent or automation tool
- Applies same validations as Claude Code hooks
- Can be enabled via simple alias setup
- Transparent operation - agents use `gh` normally

### 5. `setup-agent-hooks.sh` (NEW - Agent-Agnostic)
**Purpose**: Setup script to enable security hooks for any agent.

**Features**:
- One-line setup for any shell environment
- Creates gh alias automatically
- Can be sourced in containers or shell configs

## Configuration

The system uses `.secrets.yaml` in the repository root for configuration:

```yaml
# Environment variables to mask
environment_variables:
  - GITHUB_TOKEN
  - OPENROUTER_API_KEY
  - DB_PASSWORD
  # ... more variables

# Secret patterns to detect
patterns:
  - name: GITHUB_TOKEN
    pattern: "ghp_[A-Za-z0-9_]{36,}"
    description: "GitHub personal access token"
  # ... more patterns

# Auto-detection settings
auto_detection:
  enabled: true
  include_patterns:
    - "*_TOKEN"
    - "*_SECRET"
    - "*_KEY"
  exclude_patterns:
    - "PUBLIC_*"
```

## Installation

### Method 1: For Claude Code

Add to `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/security-hooks/bash-pretooluse-hook.sh"
          }
        ]
      }
    ]
  }
}
```

### Method 2: For Any Agent (Agent-Agnostic)

Use the wrapper script approach:

```bash
# One-time setup
source /path/to/scripts/security-hooks/setup-agent-hooks.sh

# Or add to shell configuration for permanent setup
echo 'source /path/to/scripts/security-hooks/setup-agent-hooks.sh' >> ~/.bashrc
```

### Method 3: For Docker/Containers

```dockerfile
# In your Dockerfile
COPY scripts/security-hooks /app/security-hooks
RUN chmod +x /app/security-hooks/*.sh
RUN echo 'source /app/security-hooks/setup-agent-hooks.sh' >> /etc/bash.bashrc
```

### Method 4: For Python Agents

```python
import os
# Add wrapper to PATH
os.environ['PATH'] = f"/path/to/scripts/security-hooks:{os.environ['PATH']}"
# Now subprocess calls to 'gh' will use the wrapper
```

## Testing

Test the secret masking:
```bash
# Run the test script
./scripts/security-hooks/test-masking.sh

# Test individual components
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token is ghp_test123\""}}' | \
  python3 scripts/security-hooks/github-secrets-masker.py
```

## How to Add New Secrets

1. **Add to `.secrets.yaml`**:
   - Add environment variable name to `environment_variables` list
   - Or add pattern to `patterns` list

2. **Use auto-detection**:
   - Variables matching patterns like `*_TOKEN`, `*_SECRET` are auto-detected
   - Exclude safe variables with `exclude_patterns`

## Security Considerations

- **Never disable masking** in production environments
- **Test thoroughly** when adding new patterns to avoid over-masking
- **Keep `.secrets.yaml` updated** as new services are added
- **Review logs** periodically for masking effectiveness

## Troubleshooting

### Secrets not being masked
1. Check if environment variable is in `.secrets.yaml`
2. Verify minimum secret length (default: 4 characters)
3. Check auto-detection patterns match variable name
4. Look for `[Secret Masker]` messages in stderr

### Over-masking (too many things masked)
1. Add variable to `exclude_patterns` in auto-detection
2. Adjust `minimum_secret_length` if needed
3. Make patterns more specific

### Hook not working
1. Verify hook script is executable: `chmod +x scripts/security-hooks/*.sh`
2. Check agent configuration points to correct path
3. Test hook directly with sample input

## Contributing

When adding new services or API integrations:
1. Add their secret environment variables to `.secrets.yaml`
2. Add any unique token patterns to the patterns list
3. Test masking with real (expired) tokens
4. Update this documentation

## Architecture

```
Agent Tool Call
      ↓
PreToolUse Hook
      ↓
bash-pretooluse-hook.sh
      ↓
github-secrets-masker.py (masks secrets)
      ↓
gh-comment-validator.py (optional, validates formatting)
      ↓
Tool Execution (with masked content)
```

This layered approach ensures secrets are masked before any validation or execution occurs.

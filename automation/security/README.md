# Security Hooks

This directory contains universal security hooks that work with ALL AI agents and automation tools (including Claude Code) to prevent accidental exposure of secrets and ensure proper formatting in public outputs.

## Overview

The security hooks system provides automatic secret masking for all GitHub comments and public outputs through a universal wrapper approach, ensuring that sensitive information is never exposed in:
- Pull request comments
- Issue comments
- PR descriptions
- Review comments

## Universal Approach

**ALL agents, including Claude Code, use the same security framework via shell aliasing.** There are no agent-specific hooks - everyone uses the same `gh-wrapper.sh` through an alias.

## Components

### 1. `gh-wrapper.sh` (Universal Wrapper)
**Purpose**: Wrapper script for gh CLI that ALL agents use via alias.

**Features**:
- Works with every AI agent and automation tool
- Validates based on arguments (--body, --notes, --message, etc.)
- POSIX-compliant for maximum shell compatibility
- Captures and displays stderr from validators for debugging
- Dynamic gh binary discovery
- Python 3 dependency checking
- Transparent operation - agents use `gh` normally

### 2. `github-secrets-masker.py`
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

### 3. `gh-comment-validator.py`
**Purpose**: Validates GitHub comment formatting for reaction images and prevents Unicode emoji corruption.

**Features**:
- Prevents incorrect markdown formatting that would escape `!` characters
- Blocks Unicode emojis that may appear corrupted in GitHub
- Enforces proper use of `--body-file` for complex markdown

### 4. `setup-agent-hooks.sh` (Universal Setup)
**Purpose**: Setup script to enable security hooks for any environment.

**Features**:
- One-line setup for any shell environment
- POSIX-compliant (works with sh, dash, bash, zsh)
- Creates gh alias automatically
- Provides diagnostic function (agent_hooks_status)
- Can be sourced in containers or shell configs
- Works for Claude Code, other AI agents, and human developers

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

### Universal Setup (All Agents Including Claude Code)

```bash
# One-time setup for current session
source /path/to/automation/security/setup-agent-hooks.sh

# Or add to shell configuration for permanent setup
echo 'source /path/to/automation/security/setup-agent-hooks.sh' >> ~/.bashrc
```

### For Docker/Containers

```dockerfile
# In your Dockerfile
COPY automation/security /app/security-hooks
RUN chmod +x /app/security-hooks/*.sh
RUN echo 'source /app/security-hooks/setup-agent-hooks.sh' >> /etc/bash.bashrc
```

### For Python Agents

```python
import os
# Add wrapper to PATH
os.environ['PATH'] = f"/path/to/automation/security:{os.environ['PATH']}"
# Now subprocess calls to 'gh' will use the wrapper
```

### For CI/CD Pipelines

```yaml
# GitHub Actions example
- name: Setup security hooks
  run: |
    source automation/security/setup-agent-hooks.sh
    # All subsequent gh commands will be validated
```

## Testing

Test the secret masking:
```bash
# Check if hooks are active
agent_hooks_status

# Test secret masking
export TEST_SECRET="super-secret-value"
echo "  - TEST_SECRET" >> .secrets.yaml
gh pr comment 1 --body "Secret is super-secret-value"
# Should mask the secret

# Test individual components
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token is ghp_test123\""}}' | \
  python3 automation/security/github-secrets-masker.py
```

## How to Add New Secrets

1. **Add to `.secrets.yaml`**:
   - Add environment variable name to `environment_variables` list
   - Or add pattern to `patterns` list

2. **Use auto-detection**:
   - Variables matching patterns like `*_TOKEN`, `*_SECRET` are auto-detected
   - Exclude safe variables with `exclude_patterns`

## Security Considerations

- **Universal protection** - All agents use the same security validation
- **Never disable masking** in production environments
- **Test thoroughly** when adding new patterns to avoid over-masking
- **Keep `.secrets.yaml` updated** as new services are added
- **Review logs** periodically for masking effectiveness

## Troubleshooting

### Hooks not active
```bash
# Check status
agent_hooks_status

# Re-source the setup script
source automation/security/setup-agent-hooks.sh
```

### Secrets not being masked
1. Check if environment variable is in `.secrets.yaml`
2. Verify minimum secret length (default: 4 characters)
3. Check auto-detection patterns match variable name
4. Look for `[Secret Masker]` messages in stderr

### Over-masking (too many things masked)
1. Add variable to `exclude_patterns` in auto-detection
2. Adjust `minimum_secret_length` if needed
3. Make patterns more specific

### Python not found
```bash
# Install Python 3 or run in container
# The wrapper requires Python 3 for validators
```

## Contributing

When adding new services or API integrations:
1. Add their secret environment variables to `.secrets.yaml`
2. Add any unique token patterns to the patterns list
3. Test masking with real (expired) tokens
4. Update this documentation

## Architecture

```
Agent executes: gh [command]
      ↓
gh alias → gh-wrapper.sh
      ↓
github-secrets-masker.py (masks secrets)
      ↓
gh-comment-validator.py (validates formatting)
      ↓
Actual gh execution (with masked content)
```

This unified approach ensures ALL agents (including Claude Code) use the same security validation path through shell aliasing. No agent-specific hooks are needed.

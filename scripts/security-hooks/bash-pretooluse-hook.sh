#!/bin/bash
# Universal PreToolUse hook for Bash commands
# Used by all AI agents and automation tools
#
# Security features:
# 1. Automatic secret masking in GitHub comments
# 2. GitHub comment formatting validation
#
# Order matters:
# 1. First mask any secrets in GitHub comments (transparent modification)
# 2. Then validate GitHub comment formatting (may block with guidance)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read input once
input=$(cat)

# Pass through secret masker first (modifies commands transparently)
# The masker returns the modified input data for chaining
masked_input=$(echo "$input" | python3 "${SCRIPT_DIR}/github-secrets-masker.py")

# Check if gh-comment-validator exists (for Claude-specific validation)
# Other agents may not need this specific validation
if [ -f "${SCRIPT_DIR}/gh-comment-validator.py" ]; then
    echo "$masked_input" | python3 "${SCRIPT_DIR}/gh-comment-validator.py"
elif [ -f "${SCRIPT_DIR}/../claude-hooks/gh-comment-validator.py" ]; then
    # Fallback to claude-hooks location for compatibility
    echo "$masked_input" | python3 "${SCRIPT_DIR}/../claude-hooks/gh-comment-validator.py"
else
    # If no comment validator exists, just return the masked input as allowed
    # Extract the command from the masked input and return permission
    echo '{"permissionDecision": "allow"}'
fi

#!/bin/bash
# Universal PreToolUse hook for Bash commands
# Used by all AI agents and automation tools
#
# Security features:
# 1. Automatic secret masking in GitHub comments
# 2. GitHub comment formatting validation (when validator is available)
#
# The secret masker is the single source of truth for permission decisions

# Shell hardening: exit on error, undefined variables, and pipe failures
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read input once
input=$(cat)

# Pass through secret masker - it handles permission decisions and modifications
# The masker returns a complete JSON response with permissionDecision
masked_output=$(echo "$input" | python3 "${SCRIPT_DIR}/github-secrets-masker.py")

# Check if gh-comment-validator exists for additional validation
# Only apply validator if masker allowed the command (with or without modifications)
permission=$(echo "$masked_output" | python3 -c "import json, sys; print(json.loads(sys.stdin.read()).get('permissionDecision', 'allow'))" 2>/dev/null || echo "allow")

if [[ "$permission" == "allow" ]] || [[ "$permission" == "allow_with_modifications" ]]; then
    # Command was allowed by masker, check for additional validators
    if [ -f "${SCRIPT_DIR}/gh-comment-validator.py" ]; then
        # Pass the original input through the validator
        # The validator needs the original tool input to check for issues
        echo "$input" | python3 "${SCRIPT_DIR}/gh-comment-validator.py"
    else
        # No additional validators - return the masker's output directly
        echo "$masked_output"
    fi
else
    # Command was blocked by masker - return its decision
    echo "$masked_output"
fi

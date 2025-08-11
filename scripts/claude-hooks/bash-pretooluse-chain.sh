#!/bin/bash
# Chain multiple PreToolUse hooks for Bash commands
# Runs security masking first, then git push reminder injection

set -euo pipefail

# Read input once
input=$(cat)

# First pass through security masker
masked_output=$(echo "$input" | ./scripts/security-hooks/bash-pretooluse-hook.sh)

# Check if security hook blocked the command
permission=$(echo "$masked_output" | python3 -c "import json, sys; print(json.loads(sys.stdin.read()).get('permissionDecision', 'allow'))" 2>/dev/null || echo "allow")

if [[ "$permission" == "block" ]]; then
    # Command was blocked, return the blocker's decision
    echo "$masked_output"
else
    # Command was allowed (with or without modifications)
    # Now pass through git push reminder injector
    echo "$masked_output" | python3 "./scripts/claude-hooks/git-push-pretooluse-hook.py"
fi

#!/bin/bash
# Simple PostToolUse hook that creates a marker file when git push is detected

# Read the JSON input
input=$(cat)

# Check if this was a git push command
if echo "$input" | grep -q '"command".*git push'; then
    # Extract PR and commit info using the Python script
    echo "$input" | python3 ./scripts/claude-hooks/git-push-posttooluse-hook.py
fi

# Always pass through the input unchanged
echo "{}"

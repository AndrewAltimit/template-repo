#!/bin/bash
# Example wrapper script showing how to use Claude Code subagents from shell scripts
# This demonstrates migrating from the old shell script approach to the new subagent system

set -e

# Parse arguments
ISSUE_NUMBER="$1"
BRANCH_NAME="$2"

# Validate arguments
if [ -z "$ISSUE_NUMBER" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Error: Issue number and branch name are required"
    echo "Usage: $0 <issue_number> <branch_name>"
    exit 1
fi

# Get repository from environment
REPO="${GITHUB_REPOSITORY}"
if [ -z "$REPO" ]; then
    echo "Error: GITHUB_REPOSITORY environment variable not set"
    exit 1
fi

echo "Using Claude Code tech-lead subagent to implement issue #${ISSUE_NUMBER}..."

# Call the Claude subagent CLI tool
python "$(dirname "$0")/../claude_subagent.py" \
    tech-lead \
    implement \
    --issue "${ISSUE_NUMBER}" \
    --repo "${REPO}" \
    --branch "${BRANCH_NAME}" \
    --verbose

# The exit code from the Python script will be passed through
exit $?

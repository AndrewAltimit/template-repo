#!/bin/bash
# Example wrapper script for using Claude Code QA reviewer subagent
# This shows how to address PR review feedback using the new system

set -e

# Parse arguments
PR_NUMBER="$1"
BRANCH_NAME="$2"

# Validate arguments
if [ -z "$PR_NUMBER" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Error: PR number and branch name are required"
    echo "Usage: $0 <pr_number> <branch_name>"
    exit 1
fi

# Get repository from environment
REPO="${GITHUB_REPOSITORY}"
if [ -z "$REPO" ]; then
    echo "Error: GITHUB_REPOSITORY environment variable not set"
    exit 1
fi

echo "Using Claude Code QA reviewer subagent to address PR #${PR_NUMBER} feedback..."

# Call the Claude subagent CLI tool
python "$(dirname "$0")/../claude_subagent.py" \
    qa-reviewer \
    review \
    --pr "${PR_NUMBER}" \
    --repo "${REPO}" \
    --branch "${BRANCH_NAME}" \
    --verbose

# The exit code from the Python script will be passed through
exit $?

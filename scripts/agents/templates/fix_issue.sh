#!/bin/bash
# Script to implement fixes for GitHub issues using Claude Code
# Usage: fix_issue.sh <issue_number> <branch_name>
# Issue data (title and body) is passed via stdin as JSON

set -e  # Exit on error

# Parse arguments
ISSUE_NUMBER="$1"
BRANCH_NAME="$2"

# Validate arguments
if [ -z "$ISSUE_NUMBER" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Error: Issue number and branch name are required"
    echo "Usage: $0 <issue_number> <branch_name>"
    echo "Issue data should be passed via stdin as JSON"
    exit 1
fi

# Read issue data from stdin
ISSUE_DATA=$(cat)
ISSUE_TITLE=$(echo "$ISSUE_DATA" | jq -r '.title')
ISSUE_BODY=$(echo "$ISSUE_DATA" | jq -r '.body')

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Create and checkout branch
echo "Creating branch: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME"

# Use Claude Code to implement the fix
echo "Running Claude Code to implement fix for issue #$ISSUE_NUMBER..."
npx --yes @anthropic-ai/claude-code@1.0.59 << EOF
Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}

${ISSUE_BODY}

Please implement a fix for this issue. Make sure to:
1. Address all the concerns mentioned in the issue
2. Add appropriate tests if needed
3. Update documentation if necessary
4. Follow the project's coding standards

After implementation, create a commit with a descriptive message.
EOF

# Create PR
echo "Creating pull request..."
gh pr create --title "Fix: ${ISSUE_TITLE} (#${ISSUE_NUMBER})" \
    --body "This PR addresses issue #${ISSUE_NUMBER}.

## Changes
- Implemented fix as described in the issue
- Added tests where appropriate
- Updated documentation

## Testing
- All existing tests pass
- New tests added for the fix

Closes #${ISSUE_NUMBER}

*This PR was created by an AI agent.*" \
    --assignee @me \
    --label "automated"

echo "Successfully created PR for issue #$ISSUE_NUMBER!"

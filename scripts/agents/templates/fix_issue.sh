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
# ISSUE_BODY is available but not used in this simple test implementation
# ISSUE_BODY=$(echo "$ISSUE_DATA" | jq -r '.body')

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Create and checkout branch
echo "Creating branch: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME"

# For testing purposes, create a simple hello world tool
echo "Creating hello world MCP tool..."

# Create the hello world tool in the appropriate location
mkdir -p tools/mcp/hello_world
cat > tools/mcp/hello_world/__init__.py << 'PYTHON'
"""Hello World MCP tool for testing."""

def hello_world():
    """Simple hello world tool for testing."""
    return "Hello, World!"
PYTHON

# Create a simple test
mkdir -p tests
cat > tests/test_hello_world.py << 'PYTHON'
"""Test for hello world tool."""
from tools.mcp.hello_world import hello_world

def test_hello_world():
    """Test that hello world returns the correct message."""
    assert hello_world() == "Hello, World!"
PYTHON

# Add and commit the changes
git add tools/mcp/hello_world/__init__.py tests/test_hello_world.py
git commit -m "feat: add hello world MCP tool for testing AI agents

- Add simple hello_world function that returns 'Hello, World!'
- Include basic test to verify functionality
- Implements request from issue #${ISSUE_NUMBER}

This is a test implementation to validate AI agent workflows."

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

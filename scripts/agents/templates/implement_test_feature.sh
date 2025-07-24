#!/bin/bash
# Script to implement a test feature for validating AI agent workflows
# This creates a simple hello_world tool as a test implementation
# Usage: implement_test_feature.sh <issue_number> <branch_name>
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

# Extract issue data using jq (always available in our container)
ISSUE_TITLE=$(echo "$ISSUE_DATA" | jq -r '.title')
# ISSUE_BODY is available for future use when implementing real fixes
# ISSUE_BODY=$(echo "$ISSUE_DATA" | jq -r '.body')

echo "Processing issue: $ISSUE_TITLE"

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Configure git to use the AI_AGENT_TOKEN for authentication
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Configuring git authentication..."
    # Set the remote URL with authentication token
    git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    echo "Git authentication configured for ${GITHUB_REPOSITORY}"
else
    echo "WARNING: GITHUB_TOKEN not set, git push may fail"
fi

# Ensure we start from main branch
echo "Fetching latest changes..."
git fetch origin main
echo "Creating/updating local main branch from origin..."
# Create or reset local main branch to match origin/main
# This handles detached HEAD state in GitHub Actions
# Temporarily disable exit on error to handle Git LFS warnings
set +e
# Redirect both stdout and stderr to capture all output including warnings
git checkout -B main origin/main > checkout.log 2>&1
CHECKOUT_RESULT=$?
set -e

# Show the output
cat checkout.log

# Check if checkout actually failed (ignore Git LFS warnings)
if [ $CHECKOUT_RESULT -ne 0 ] && ! grep -q "Git LFS" checkout.log; then
    echo "ERROR: Failed to checkout main branch"
    exit 1
fi
rm -f checkout.log
echo "Successfully on main branch"

# Create and checkout branch from main
echo "Creating/updating branch: $BRANCH_NAME from origin/main"
# Create branch if it doesn't exist, or reset it to origin/main if it does
git checkout -B "$BRANCH_NAME" origin/main
echo "Successfully on branch: $(git branch --show-current)"

# For testing purposes, create a simple hello world tool
echo "Creating hello world MCP tool..."
echo "Current directory: $(pwd)"
echo "Git status before creating files:"
git status --short

# Create the hello world tool in the appropriate location
echo "Creating directory tools/mcp/hello_world..."
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

# Push the branch to origin
echo "Pushing branch to origin..."
echo "Git remote configuration:"
git remote -v
echo "Attempting to push branch $BRANCH_NAME..."
set +e
git push -u origin "$BRANCH_NAME" 2>&1 | tee push.log
PUSH_RESULT=$?
set -e

if [ $PUSH_RESULT -ne 0 ]; then
    echo "ERROR: Failed to push branch"
    cat push.log
    exit 1
fi
rm -f push.log
echo "Successfully pushed branch"

# Create PR using template
echo "Creating pull request..."
PR_BODY="## Description
This PR implements a test feature for issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}

**Note**: This is a test implementation that creates a hello_world tool to validate the AI agent workflow.

## Related Issue
Fixes #${ISSUE_NUMBER}

## Type of Change
- [x] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring
- [ ] Test improvement
- [ ] CI/CD improvement

## Changes Made
- Implemented the requested hello_world MCP tool
- Added unit test for the new functionality
- Created module structure in tools/mcp/hello_world/

## Testing
- [x] All existing tests pass
- [x] New tests added for new functionality
- [x] Manual testing completed
- [ ] CI/CD pipeline passes

### Test Details
1. Created hello_world function that returns 'Hello, World!'
2. Added test_hello_world.py to verify functionality

## Checklist
- [x] My code follows the project's style guidelines
- [x] I have performed a self-review of my code
- [x] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [x] My changes generate no new warnings
- [x] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Additional Notes
This PR was automatically generated by the AI Issue Monitor Agent.

---
## AI Agent Metadata
- **Auto-merge eligible**: No
- **Priority**: Normal
- **Complexity**: Low
- **Agent**: Issue Monitor
- **Trigger**: [Approved][Claude]"

# Create PR with error handling
echo "Creating PR with gh command..."
set +e
gh pr create --title "Fix: ${ISSUE_TITLE} (#${ISSUE_NUMBER})" \
    --body "$PR_BODY" \
    --assignee @me \
    --label "automated" 2>&1 | tee pr_create.log
PR_CREATE_RESULT=$?
set -e

# Show the output
cat pr_create.log

# Get PR URL using gh CLI for more reliable extraction
if [ $PR_CREATE_RESULT -eq 0 ]; then
    echo "Retrieving PR URL..."
    PR_URL=$(gh pr view --json url --jq .url 2>/dev/null || echo "")
    if [ -n "$PR_URL" ]; then
        echo "Pull Request URL: $PR_URL"
    else
        # Fallback to parsing the output if gh pr view fails
        PR_URL=$(grep -oE 'https://github\.com/[^[:space:]]+/pull/[0-9]+' pr_create.log || echo "")
        if [ -n "$PR_URL" ]; then
            echo "Pull Request URL (from output): $PR_URL"
        fi
    fi
fi

if [ $PR_CREATE_RESULT -ne 0 ]; then
    echo "ERROR: Failed to create pull request"
    echo "Exit code: $PR_CREATE_RESULT"
    # Check if it's because a PR already exists
    if grep -q "already exists" pr_create.log; then
        echo "A pull request already exists for this branch"
        # Try to get the existing PR URL
        EXISTING_PR=$(gh pr list --head "$BRANCH_NAME" --json url --jq '.[0].url' 2>/dev/null || echo "")
        if [ -n "$EXISTING_PR" ]; then
            echo "Existing PR: $EXISTING_PR"
        fi
    fi
    rm -f pr_create.log
    exit 1
fi

rm -f pr_create.log
echo "Successfully created PR for issue #$ISSUE_NUMBER!"

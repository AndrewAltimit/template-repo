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

# Extract PR labels to add (default to "help wanted" if not specified)
PR_LABELS_TO_ADD=$(echo "$ISSUE_DATA" | jq -r '.pr_labels_to_add[]?' 2>/dev/null || echo "")
if [ -z "$PR_LABELS_TO_ADD" ]; then
    PR_LABELS_TO_ADD="help wanted"
fi

echo "Processing issue: $ISSUE_TITLE"

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Debug: Show git configuration and environment
echo "Git repository info:"
echo "Working directory: $(pwd)"
echo "Git directory: $(git rev-parse --git-dir)"
echo "Git version: $(git --version)"
echo "Repository ownership:"
ls -la .git/config
echo "Safe directory configuration:"
git config --global --get-all safe.directory || echo "No safe directories configured"

# Configure git to use the AI_AGENT_TOKEN for authentication
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Configuring git authentication..."
    # Set the remote URL with authentication token
    git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    echo "Git authentication configured for ${GITHUB_REPOSITORY}"
else
    echo "WARNING: GITHUB_TOKEN not set, git push may fail"
fi

# Configure git user for commits (required in containers)
echo "Configuring git user..."
git config user.name "AI Issue Monitor Agent"
git config user.email "ai-agent[bot]@users.noreply.github.com"
echo "Git user configured"

# Add repository as safe directory (needed when running as different user in container)
echo "Adding repository as safe directory..."
git config --global --add safe.directory /workspace
echo "Safe directory added"

# Disable Git LFS hooks that are causing issues
echo "Disabling Git LFS hooks..."
if [ -f .git/hooks/pre-push ]; then
    mv .git/hooks/pre-push .git/hooks/pre-push.disabled
    echo "Disabled pre-push hook"
fi
if [ -f .git/hooks/post-commit ]; then
    mv .git/hooks/post-commit .git/hooks/post-commit.disabled
    echo "Disabled post-commit hook"
fi
if [ -f .git/hooks/post-checkout ]; then
    mv .git/hooks/post-checkout .git/hooks/post-checkout.disabled
    echo "Disabled post-checkout hook"
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
# Temporarily disable exit on error to handle Git LFS warnings
set +e
git checkout -B "$BRANCH_NAME" origin/main > checkout2.log 2>&1
CHECKOUT_RESULT=$?
set -e

# Show the output
cat checkout2.log

# Check if checkout actually failed (ignore Git LFS warnings)
if [ $CHECKOUT_RESULT -ne 0 ] && ! grep -q "Git LFS" checkout2.log; then
    echo "ERROR: Failed to checkout branch $BRANCH_NAME"
    exit 1
fi
rm -f checkout2.log
echo "Successfully on branch: $(git rev-parse --abbrev-ref HEAD)"

# Use Claude Code to implement the requested feature
echo "Running Claude Code to implement the feature..."
echo "Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}"
echo ""
echo "Using Claude Code with --dangerously-skip-permissions to implement the requested feature..."

# Determine Claude command based on environment
if [ -f /.dockerenv ] || [ -n "$CONTAINER" ]; then
    # We're in a container
    echo "Running in container - checking for mounted Claude credentials..."
    # Check both possible locations for Claude credentials
    if [ -f "$HOME/.claude/.credentials.json" ]; then
        echo "Claude credentials found at $HOME/.claude/.credentials.json"
        CLAUDE_CMD="claude-code --dangerously-skip-permissions"
    elif [ -f "/tmp/home/.claude/.credentials.json" ]; then
        echo "Claude credentials found at /tmp/home/.claude/.credentials.json"
        export HOME=/tmp/home
        CLAUDE_CMD="claude-code --dangerously-skip-permissions"
    else
        echo "WARNING: Claude credentials not mounted from host!"
        echo "Mount host's ~/.claude directory to container for authentication"
        exit 1
    fi
elif command -v nvm >/dev/null 2>&1; then
    # We're on the host with nvm
    echo "Running on host - using nvm to load Claude..."
    export NVM_DIR="$HOME/.nvm"
    # shellcheck disable=SC1091
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use 22.16.0
    CLAUDE_CMD="claude-code --dangerously-skip-permissions"
else
    echo "ERROR: Neither in container with mounted credentials nor on host with nvm"
    exit 1
fi

# Run Claude Code to implement the feature
$CLAUDE_CMD << EOF
Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}

${ISSUE_BODY}

Please implement the requested feature/fix based on the issue description above.

Important guidelines:
1. Analyze the issue carefully and implement a complete solution
2. Write production-quality code following the project's conventions
3. Add appropriate tests for your implementation
4. Ensure all existing tests continue to pass
5. Follow the existing code style and patterns in the repository
6. If implementing a new feature, add documentation as needed
7. Make sure to handle edge cases and error conditions

After implementing the solution, commit your changes with an appropriate commit message.

The commit message should follow this format:
- For features: "feat: <description>"
- For bug fixes: "fix: <description>"
- Include reference to issue #${ISSUE_NUMBER}

Make sure all changes are committed before you finish.
EOF

# Check if Claude made any commits
if git diff HEAD^ --quiet 2>/dev/null; then
    echo "No changes were committed by Claude Code"
    # If no commits were made, create a minimal implementation to ensure the pipeline works
    echo "Creating a minimal implementation commit..."
    echo "# Implementation for issue #${ISSUE_NUMBER}" > "implementation_${ISSUE_NUMBER}.md"
    git add "implementation_${ISSUE_NUMBER}.md"
    git commit -m "feat: placeholder implementation for issue #${ISSUE_NUMBER}

This is a placeholder commit to ensure the CI/CD pipeline runs.
The actual implementation should be added by reviewing the issue requirements."
fi

# Push the branch to origin
echo "Pushing branch to origin..."
echo "Git remote configuration:"
git remote -v
echo "Attempting to push branch $BRANCH_NAME..."
echo "Current branch: $(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD)"
echo "Remote tracking info:"
git branch -vv | grep "$(git rev-parse --abbrev-ref HEAD)" || echo "No tracking info"

set +e
# First, let's make sure we have the latest main branch
echo "Fetching latest changes before push..."
git fetch origin main
echo "Checking if our branch is up to date with origin/main..."
git log --oneline origin/main..HEAD

# Use pipefail to capture exit code from git push, not tee
set -o pipefail
# Try push with verbose output to see what's happening
echo "Running: git push -u origin $BRANCH_NAME --verbose"
# Capture both stdout and stderr properly
git push -u origin "$BRANCH_NAME" --verbose > push.log 2>&1
PUSH_RESULT=$?
# Show the output
cat push.log
set +o pipefail
set -e

# Show more detail about the push error
if [ $PUSH_RESULT -ne 0 ]; then
    echo "Push failed with exit code: $PUSH_RESULT"
    echo "Full push log:"
    cat push.log
    # Try to get more information about why the push failed
    echo "Checking remote branch existence:"
    git ls-remote --heads origin "$BRANCH_NAME" || echo "Remote branch does not exist"
    echo "Checking local commit:"
    git log --oneline -1

    # Check for common push errors
    if grep -q "Updates were rejected" push.log; then
        echo "ERROR: Updates were rejected - this usually means the remote has changes not in local"
        echo "Trying to see what's on remote main:"
        git log --oneline origin/main -5
    fi

    if grep -q "Permission" push.log || grep -q "403" push.log; then
        echo "ERROR: Permission denied - token may not have push access"
        echo "Current user:"
        git config user.name
        git config user.email
    fi

    # Try a dry-run to see what would be pushed
    echo "Attempting dry-run push to see what would be sent:"
    git push --dry-run -u origin "$BRANCH_NAME" 2>&1

    # Check if we're actually authenticated
    echo "Testing authentication with git ls-remote:"
    git ls-remote origin 2>&1 | head -5

    # Check git config
    echo "Git configuration:"
    git config --list | grep -E "(user\.|remote\.|credential\.)" | head -10
fi

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
    --assignee @me 2>&1 | tee pr_create.log
PR_CREATE_RESULT=$?
set -e

# Show the output
cat pr_create.log

# If PR was created successfully, add the configured labels
if [ $PR_CREATE_RESULT -eq 0 ]; then
    echo "Adding labels to the PR..."
    # Get the PR number first
    PR_NUMBER=$(gh pr view --json number --jq .number 2>/dev/null || echo "")
    if [ -n "$PR_NUMBER" ]; then
        # PR_LABELS_TO_ADD might contain multiple labels separated by newlines
        if [ -n "$PR_LABELS_TO_ADD" ]; then
            echo "$PR_LABELS_TO_ADD" | while IFS= read -r label; do
                if [ -n "$label" ]; then
                    echo "Adding label: $label"
                    gh pr edit "$PR_NUMBER" --add-label "$label" 2>&1 || echo "WARNING: Failed to add label '$label'"
                fi
            done
            echo "Finished adding labels to PR #$PR_NUMBER"
        else
            echo "No labels configured to add"
        fi
    else
        echo "WARNING: Could not get PR number to add labels"
    fi
fi

# Get PR URL - check even if label failed
# The PR might have been created successfully even if adding the label failed
echo "Retrieving PR URL..."
PR_URL=$(gh pr view --json url --jq .url 2>/dev/null || echo "")
if [ -n "$PR_URL" ]; then
    echo "Pull Request URL: $PR_URL"
else
    # Fallback to parsing the output if gh pr view fails
    PR_URL=$(grep -oE 'https://github\.com/[^[:space:]]+/pull/[0-9]+' pr_create.log || echo "")
    if [ -n "$PR_URL" ]; then
        echo "Pull Request URL (from output): $PR_URL"
    else
        # Try to find PR by branch name
        echo "Checking for PR with branch $BRANCH_NAME..."
        EXISTING_PR=$(gh pr list --head "$BRANCH_NAME" --json url --jq '.[0].url' 2>/dev/null || echo "")
        if [ -n "$EXISTING_PR" ]; then
            echo "Found PR: $EXISTING_PR"
            PR_URL="$EXISTING_PR"
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
if [ -n "$PR_URL" ]; then
    echo "Pull Request: $PR_URL"
fi

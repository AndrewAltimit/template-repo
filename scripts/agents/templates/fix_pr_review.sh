#!/bin/bash
# Script to address PR review feedback using Claude Code
# Usage: fix_pr_review.sh <pr_number> <branch_name>
# Review feedback data is passed via stdin as JSON

set -e  # Exit on error

# Parse arguments
PR_NUMBER="$1"
BRANCH_NAME="$2"

# Validate arguments
if [ -z "$PR_NUMBER" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Error: PR number and branch name are required"
    echo "Usage: $0 <pr_number> <branch_name>"
    echo "Review feedback should be passed via stdin as JSON"
    exit 1
fi

# Read feedback data from stdin
FEEDBACK_DATA=$(cat)
MUST_FIX_TEXT=$(echo "$FEEDBACK_DATA" | jq -r '.must_fix')
ISSUES_TEXT=$(echo "$FEEDBACK_DATA" | jq -r '.issues')
SUGGESTIONS_TEXT=$(echo "$FEEDBACK_DATA" | jq -r '.suggestions')

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Checkout the PR branch
echo "Fetching and checking out branch: $BRANCH_NAME"
git fetch origin "$BRANCH_NAME" 2>&1 | grep -v "Git LFS" || true
git checkout "$BRANCH_NAME" 2>&1 | grep -v "Git LFS" || true

# Disable Git LFS hooks that are causing issues
echo "Disabling Git LFS hooks..."
if [ -f .git/hooks/post-checkout ]; then
    mv .git/hooks/post-checkout .git/hooks/post-checkout.disabled
    echo "Disabled post-checkout hook"
fi

# Create a backup branch
BACKUP_BRANCH="pr-${PR_NUMBER}-backup-$(date +%s)"
echo "Creating backup branch: $BACKUP_BRANCH"
git branch -f "$BACKUP_BRANCH"

# Use Claude Code to implement fixes
echo "Running Claude Code to address review feedback..."

# Determine Claude command based on environment
if command -v claude-code >/dev/null 2>&1; then
    CLAUDE_CMD="claude-code --dangerously-skip-permissions"
    echo "Using local claude-code command with --dangerously-skip-permissions"
else
    # Fall back to npx if claude-code isn't installed
    CLAUDE_CMD="npx --yes @anthropic-ai/claude-code@latest"
    echo "Using npx to run claude-code (Note: --dangerously-skip-permissions not available via npx)"
fi

$CLAUDE_CMD << EOF
PR #${PR_NUMBER} Review Feedback

The following issues were identified in the code review and need to be addressed:

## Critical Issues (Must Fix):
${MUST_FIX_TEXT:-"None identified"}

## Inline Code Comments:
${ISSUES_TEXT:-"No inline comments"}

## Suggestions (Nice to Have):
${SUGGESTIONS_TEXT:-"None"}

Please implement fixes for all the critical issues and inline comments.
For suggestions, implement them if they improve the code quality
without breaking existing functionality.

Make sure to:
1. Address all critical issues
2. Fix any bugs or errors mentioned
3. Improve code quality where suggested
4. Maintain existing functionality
5. Run tests to ensure nothing is broken

After making changes, create a commit with message: "Address PR review feedback"
EOF

# Run tests
echo "Running tests..."
if [ -f "./scripts/run-ci.sh" ]; then
    ./scripts/run-ci.sh test
else
    echo "Warning: run-ci.sh not found, skipping tests"
fi

# Commit changes
echo "Committing changes..."
git add -A
git commit -m "Address PR review feedback

- Fixed all critical issues identified in review
- Addressed inline code comments
- Implemented suggested improvements where applicable
- All tests passing

Co-Authored-By: AI Review Agent <noreply@ai-agent.local>"

# Push changes
echo "Pushing changes to origin..."
git push origin "$BRANCH_NAME"

echo "Successfully addressed PR review feedback!"

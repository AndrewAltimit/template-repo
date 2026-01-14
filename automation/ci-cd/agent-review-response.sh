#!/bin/bash
# Agent Review Response Script
# Responds to Gemini/Codex AI reviews by parsing feedback and making fixes
#
# Usage: agent-review-response.sh <pr_number> <branch_name> <iteration_count>
#
# Environment variables:
#   GITHUB_TOKEN - Required for pushing changes
#   GITHUB_REPOSITORY - Required for git remote URL
#   GEMINI_REVIEW_PATH - Path to Gemini review markdown (optional)
#   CODEX_REVIEW_PATH - Path to Codex review markdown (optional)

set -e
set -o pipefail

# Parse arguments
PR_NUMBER="$1"
BRANCH_NAME="$2"
ITERATION_COUNT="${3:-1}"
MAX_ITERATIONS="${4:-5}"

# Validate arguments
if [ -z "$PR_NUMBER" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Error: PR number and branch name are required"
    echo "Usage: $0 <pr_number> <branch_name> [iteration_count] [max_iterations]"
    exit 1
fi

echo "=== Agent Review Response ==="
echo "PR Number: $PR_NUMBER"
echo "Branch: $BRANCH_NAME"
echo "Iteration: $ITERATION_COUNT / $MAX_ITERATIONS"
echo "============================="

# Check for gh CLI availability early
if ! command -v gh &> /dev/null; then
    echo "WARNING: gh CLI not found - PR comments will be skipped"
    echo "Install gh CLI for full functionality: https://cli.github.com/"
fi

# Function to post a comment on the PR explaining agent decisions
post_agent_comment() {
    local comment_body="$1"

    if [ -z "$GITHUB_TOKEN" ] || [ -z "$PR_NUMBER" ]; then
        echo "Cannot post comment: missing GITHUB_TOKEN or PR_NUMBER"
        return 1
    fi

    # Use gh CLI to post comment
    if command -v gh &> /dev/null; then
        echo "$comment_body" | gh pr comment "$PR_NUMBER" --body-file - || {
            echo "Failed to post PR comment"
            return 1
        }
        echo "Posted agent status comment to PR #$PR_NUMBER"
    else
        echo "gh CLI not found, skipping PR comment"
    fi
}

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Collect review feedback BEFORE any git operations
# (git checkout would remove downloaded artifacts)
REVIEW_CONTENT=""

echo "Looking for review artifacts..."

if [ -f "${GEMINI_REVIEW_PATH:-gemini-review.md}" ]; then
    echo "Found Gemini review at: ${GEMINI_REVIEW_PATH:-gemini-review.md}"
    REVIEW_CONTENT+="## Gemini Review Feedback\n\n"
    REVIEW_CONTENT+=$(cat "${GEMINI_REVIEW_PATH:-gemini-review.md}")
    REVIEW_CONTENT+="\n\n"
fi

if [ -f "${CODEX_REVIEW_PATH:-codex-review.md}" ]; then
    echo "Found Codex review at: ${CODEX_REVIEW_PATH:-codex-review.md}"
    REVIEW_CONTENT+="## Codex Review Feedback\n\n"
    REVIEW_CONTENT+=$(cat "${CODEX_REVIEW_PATH:-codex-review.md}")
    REVIEW_CONTENT+="\n\n"
fi

# Fallback: check current directory if env vars not set
if [ -z "$REVIEW_CONTENT" ]; then
    if [ -f "gemini-review.md" ]; then
        echo "Found Gemini review in current directory"
        REVIEW_CONTENT+="## Gemini Review Feedback\n\n"
        REVIEW_CONTENT+=$(cat "gemini-review.md")
        REVIEW_CONTENT+="\n\n"
    fi

    if [ -f "codex-review.md" ]; then
        echo "Found Codex review in current directory"
        REVIEW_CONTENT+="## Codex Review Feedback\n\n"
        REVIEW_CONTENT+=$(cat "codex-review.md")
        REVIEW_CONTENT+="\n\n"
    fi
fi

# Configure git authentication
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPOSITORY" ]; then
    echo "Configuring git authentication..."
    git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    git config user.name "AI Review Agent"
    git config user.email "ai-review-agent@localhost"
else
    echo "WARNING: GITHUB_TOKEN or GITHUB_REPOSITORY not set"
fi

# Checkout the PR branch (after reading artifacts)
echo "Checking out branch: $BRANCH_NAME"
if ! git fetch origin "$BRANCH_NAME" 2>&1; then
    echo "Error: Failed to fetch branch $BRANCH_NAME"
    exit 1
fi
if ! git checkout "$BRANCH_NAME" 2>&1; then
    echo "Error: Failed to checkout branch $BRANCH_NAME"
    exit 1
fi

if [ -z "$REVIEW_CONTENT" ]; then
    echo "No review feedback found, nothing to do"

    # Post comment explaining no reviews were found
    post_agent_comment "## Agent Review Response

**Status**: No action taken

No review artifacts were found for this iteration. This can happen if:
- AI reviews haven't completed yet
- Review artifacts weren't properly downloaded

_Iteration ${ITERATION_COUNT}/${MAX_ITERATIONS}_"

    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

# Check if there are actionable items in the review
# Look for patterns indicating issues to fix
HAS_ACTIONABLE_ITEMS=false

# Patterns that indicate actionable feedback
# Avoid broad patterns that could match negations like "No type error found"
# Note: Gemini uses formats like [CRITICAL/BUG] so we need flexible matching
ACTIONABLE_PATTERNS=(
    "must fix"
    "should fix"
    "needs to be"
    "please fix"
    "unused import"
    "remove unused"
    "missing import"
    "\[.*BUG.*\]"
    "\[.*ERROR.*\]"
    "\[.*ISSUE.*\]"
    "\[CRITICAL"
    "\[STILL UNRESOLVED\]"
    "STILL UNRESOLVED"
)

MATCHED_PATTERNS=""
for pattern in "${ACTIONABLE_PATTERNS[@]}"; do
    if printf '%s\n' "$REVIEW_CONTENT" | grep -qiE "$pattern"; then
        HAS_ACTIONABLE_ITEMS=true
        MATCHED_PATTERNS+="- \`$pattern\`\n"
        echo "Found actionable pattern: $pattern"
    fi
done

if [ "$HAS_ACTIONABLE_ITEMS" = "false" ]; then
    echo "No actionable items found in reviews"

    # Build list of patterns that were checked
    PATTERNS_CHECKED=""
    for pattern in "${ACTIONABLE_PATTERNS[@]}"; do
        PATTERNS_CHECKED+="- \`$pattern\`\n"
    done

    # Determine which reviews were found
    REVIEWS_FOUND=""
    if [ -f "${GEMINI_REVIEW_PATH:-gemini-review.md}" ] || [ -f "gemini-review.md" ]; then
        REVIEWS_FOUND+="- Gemini review\n"
    fi
    if [ -f "${CODEX_REVIEW_PATH:-codex-review.md}" ] || [ -f "codex-review.md" ]; then
        REVIEWS_FOUND+="- Codex review\n"
    fi

    # Post detailed comment about the decision
    post_agent_comment "## Agent Review Response

**Status**: No actionable items detected

The agent reviewed the AI feedback but found no patterns requiring automated fixes.

### Reviews Analyzed
$(printf '%b' "$REVIEWS_FOUND")

### Patterns Checked (none matched)
$(printf '%b' "$PATTERNS_CHECKED")

### What This Means
The AI reviews may have:
- Found no issues (all clear)
- Reported issues that don't match our actionable patterns
- Reported false positives that don't require changes

If you believe the agent missed something, please review the AI feedback comments above and either:
1. Fix manually if needed
2. Open an issue to improve pattern detection

_Iteration ${ITERATION_COUNT}/${MAX_ITERATIONS}_"

    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

echo "Actionable items detected, proceeding with fixes..."

# Post comment about what patterns were detected
post_agent_comment "## Agent Review Response

**Status**: Actionable items detected - proceeding with fixes

### Patterns Matched
$(printf '%b' "$MATCHED_PATTERNS")

The agent will attempt to address these issues automatically. A follow-up commit will be pushed if fixes are made.

_Iteration ${ITERATION_COUNT}/${MAX_ITERATIONS}_"

# Step 1: Run autoformat first (quick wins)
echo ""
echo "=== Step 1: Running autoformat ==="
if [ -f "./automation/ci-cd/run-ci.sh" ]; then
    ./automation/ci-cd/run-ci.sh autoformat 2>&1 || echo "Autoformat completed with warnings"
else
    echo "run-ci.sh not found, skipping autoformat"
fi

# Check if autoformat made any changes
if ! git diff --quiet 2>/dev/null; then
    echo "Autoformat made changes"
else
    echo "No changes from autoformat"
fi

# Step 2: Invoke Claude for remaining issues
echo ""
echo "=== Step 2: Invoking Claude for review feedback ==="

# Build prompt for Claude
CLAUDE_PROMPT=$(cat << 'PROMPT_EOF'
You are addressing AI code review feedback for a pull request.

IMPORTANT INSTRUCTIONS:
1. Focus ONLY on formatting, linting, and code style issues
2. DO NOT modify test logic or business logic
3. Fix unused imports, formatting issues, type hints
4. Make minimal changes - only what's needed to address the feedback

Review feedback to address:

PROMPT_EOF
)

CLAUDE_PROMPT+=$(printf '%s\n' "$REVIEW_CONTENT")

CLAUDE_PROMPT+=$(cat << 'PROMPT_EOF'

Please analyze the review feedback above and make the necessary fixes.
Focus on:
- Unused imports (remove them)
- Formatting issues (fix indentation, spacing)
- Type hint issues
- Linting errors mentioned

After making changes, provide a brief summary of what was fixed.
PROMPT_EOF
)

# Save prompt to temp file
PROMPT_FILE=$(mktemp)
echo "$CLAUDE_PROMPT" > "$PROMPT_FILE"

# Determine Claude command
CLAUDE_CMD=""
if command -v claude &> /dev/null; then
    CLAUDE_CMD="claude --print --dangerously-skip-permissions"
elif command -v claude-code &> /dev/null; then
    CLAUDE_CMD="claude-code --print --dangerously-skip-permissions"
fi

if [ -n "$CLAUDE_CMD" ]; then
    echo "Running Claude with prompt..."

    # Set timeout for Claude execution (10 minutes)
    TIMEOUT_CMD="timeout 600"
    if ! command -v timeout &> /dev/null; then
        TIMEOUT_CMD=""
    fi

    # Run Claude (prompt is passed as positional argument)
    # shellcheck disable=SC2086
    $TIMEOUT_CMD $CLAUDE_CMD "$(cat "$PROMPT_FILE")" 2>&1 || {
        exit_code=$?
        echo "Claude exited with code: $exit_code"
        if [ $exit_code -eq 124 ]; then
            echo "Claude timed out after 10 minutes"
        fi
    }

    rm -f "$PROMPT_FILE"
else
    echo "WARNING: Claude CLI not found, skipping AI-assisted fixes"
    rm -f "$PROMPT_FILE"
fi

# Step 3: Check for changes and commit
echo ""
echo "=== Step 3: Checking for changes ==="

# Stage all changes
git add -A

if git diff --cached --quiet 2>/dev/null; then
    echo "No changes to commit"
    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

echo "Changes detected, creating commit..."

# Create commit message
COMMIT_MSG_FILE=$(mktemp)
cat > "$COMMIT_MSG_FILE" << COMMIT_EOF
fix: address AI review feedback

Automated fix by Claude in response to Gemini/Codex review.

This commit addresses formatting, linting, and code style issues
identified in the automated code review.

Iteration: ${ITERATION_COUNT}/${MAX_ITERATIONS}

Co-Authored-By: AI Review Agent <noreply@anthropic.com>
COMMIT_EOF

# Commit changes
git commit -F "$COMMIT_MSG_FILE"
rm -f "$COMMIT_MSG_FILE"

echo "Commit created successfully"

# Step 4: Push changes
echo ""
echo "=== Step 4: Pushing changes ==="

# Disable pre-push hooks that might interfere
# Use trap to ensure hook is restored even on crash/early exit
restore_hook() {
    if [ -f .git/hooks/pre-push.disabled ]; then
        mv .git/hooks/pre-push.disabled .git/hooks/pre-push 2>/dev/null || true
    fi
}
trap restore_hook EXIT

if [ -f .git/hooks/pre-push ]; then
    mv .git/hooks/pre-push .git/hooks/pre-push.disabled
    echo "Disabled pre-push hook temporarily"
fi

git push origin "$BRANCH_NAME" 2>&1 || {
    echo "Push failed"
    exit 1
}

# Hook will be restored by trap on exit

echo ""
echo "=== Agent Review Response Complete ==="
echo "Changes pushed to branch: $BRANCH_NAME"
echo "Pipeline will be retriggered automatically"
echo "made_changes=true" >> "${GITHUB_OUTPUT:-/dev/null}"

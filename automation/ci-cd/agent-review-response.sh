#!/bin/bash
# Agent Review Response Script
# Responds to Gemini/Codex AI reviews by invoking Claude to analyze and fix issues.
#
# Philosophy: Trust Claude to intelligently evaluate review feedback and decide
# what to fix. Claude has access to tools (Read, Edit, Grep) to verify claims
# before making changes.
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

# =============================================================================
# PR COMMENTING FUNCTIONS
# =============================================================================

# Function to post a comment on the PR explaining agent decisions
post_agent_comment() {
    local comment_body="$1"

    if [ -z "$GITHUB_TOKEN" ] || [ -z "$PR_NUMBER" ]; then
        echo "Cannot post comment: missing GITHUB_TOKEN or PR_NUMBER"
        return 1
    fi

    # Use gh CLI to post comment
    if command -v gh &> /dev/null; then
        # Write to temp file - gh-validator blocks stdin for security
        local temp_file
        temp_file=$(mktemp)
        echo "$comment_body" > "$temp_file"

        # Build gh command as array to avoid word-splitting issues
        # The --gh-validator-strip-invalid-images flag auto-removes broken reaction
        # images instead of failing. This makes CI pipelines more resilient.
        local gh_cmd=("gh")
        if gh --gh-validator-strip-invalid-images --help &>/dev/null 2>&1; then
            gh_cmd=("gh" "--gh-validator-strip-invalid-images")
        fi

        "${gh_cmd[@]}" pr comment "$PR_NUMBER" --body-file "$temp_file" || {
            rm -f "$temp_file"
            echo "Failed to post PR comment"
            return 1
        }
        rm -f "$temp_file"
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
    post_agent_comment "No review feedback found to process - the AI reviews might not have completed yet or the artifacts didn't download properly.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_confused.png)"

    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

echo "Review content found, passing to Claude for analysis..."

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

# Load CLAUDE.md for codebase context if it exists
CLAUDE_MD_CONTEXT=""
if [ -f "CLAUDE.md" ]; then
    echo "Loading CLAUDE.md for codebase context..."
    CLAUDE_MD_CONTEXT=$(cat "CLAUDE.md")
fi

# Build prompt for Claude - balanced and trusting
CLAUDE_PROMPT=$(cat << 'PROMPT_EOF'
You are addressing AI code review feedback for a pull request.

## Your Task
Review the feedback from Gemini and Codex below, and fix any legitimate issues you find.

## How to Work
1. **Read the files first** - Use the Read tool to examine any file mentioned in the feedback before deciding whether to fix it
2. **Verify claims** - Check if the reported issue actually exists in the code
3. **Fix real issues** - If the issue is real, fix it using the Edit tool
4. **Skip non-issues** - If a claim doesn't match reality, skip it and note why

## What to Fix
- Security issues (like unsafe shell commands, injection vulnerabilities)
- Real bugs in the code
- Formatting and style issues
- Unused imports or variables
- Type hint issues

## What NOT to Fix
- Architectural suggestions (those need human discussion)
- Style preferences that aren't bugs
- GitHub Actions version changes (we use current versions intentionally)

## Important
- Trust the review feedback as a starting point, but verify before fixing
- If you're unsure, read the file to check
- Make minimal, focused changes
- Be concise in your summary

PROMPT_EOF
)

# Add CLAUDE.md context if available
if [ -n "$CLAUDE_MD_CONTEXT" ]; then
    CLAUDE_PROMPT+="

## Codebase Context (from CLAUDE.md)
$CLAUDE_MD_CONTEXT
"
fi

# Add the review content
CLAUDE_PROMPT+="

## Review Feedback to Address

$(printf '%s' "$REVIEW_CONTENT")

---

Please analyze the feedback above, verify each issue by reading the relevant files, and fix what's actually broken. Summarize what you fixed and what you skipped (and why).
"

# Save prompt to temp file
PROMPT_FILE=$(mktemp)
printf '%s' "$CLAUDE_PROMPT" > "$PROMPT_FILE"

# Determine Claude command - use interactive mode (NOT --print) so Claude can use tools
CLAUDE_CMD=""
if command -v claude &> /dev/null; then
    # Interactive mode with auto-approval for CI - Claude can read files and make edits
    CLAUDE_CMD="claude --dangerously-skip-permissions"
elif command -v claude-code &> /dev/null; then
    CLAUDE_CMD="claude-code --dangerously-skip-permissions"
fi

# Capture Claude's output for use in PR comments
CLAUDE_OUTPUT_FILE=$(mktemp)

if [ -n "$CLAUDE_CMD" ]; then
    echo "Running Claude in interactive mode (with tool access)..."

    # Set timeout for Claude execution (10 minutes)
    TIMEOUT_CMD="timeout 600"
    if ! command -v timeout &> /dev/null; then
        TIMEOUT_CMD=""
    fi

    # Run Claude with the prompt - it will use tools to read/edit files
    # shellcheck disable=SC2086
    $TIMEOUT_CMD $CLAUDE_CMD "$(cat "$PROMPT_FILE")" 2>&1 | tee "$CLAUDE_OUTPUT_FILE" || {
        exit_code=$?
        echo "Claude exited with code: $exit_code"
        if [ $exit_code -eq 124 ]; then
            echo "Claude timed out after 10 minutes"
        fi
    }

    rm -f "$PROMPT_FILE"
else
    echo "WARNING: Claude CLI not found, skipping AI-assisted fixes"
    echo "Claude CLI not available" > "$CLAUDE_OUTPUT_FILE"
    rm -f "$PROMPT_FILE"
fi

# Step 3: Check for changes and commit
echo ""
echo "=== Step 3: Checking for changes ==="

# Stage all changes
git add -A

if git diff --cached --quiet 2>/dev/null; then
    echo "No changes to commit"

    # Extract Claude's summary for the comment
    CLAUDE_SUMMARY=""
    if [ -f "$CLAUDE_OUTPUT_FILE" ] && [ -s "$CLAUDE_OUTPUT_FILE" ]; then
        # Get the last meaningful lines from Claude's output (likely the summary)
        CLAUDE_SUMMARY=$(tail -50 "$CLAUDE_OUTPUT_FILE" | grep -v "^$" | tail -20 | head -c 1500) || true
    fi

    post_agent_comment "Reviewed the feedback from Gemini and Codex.

**Result:** No changes needed.

$(if [ -n "$CLAUDE_SUMMARY" ]; then echo "**Details:** $CLAUDE_SUMMARY"; fi)

If something actually needs fixing, let me know and I'll take another look.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_shrug.png)"

    rm -f "$CLAUDE_OUTPUT_FILE"
    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

# Clean up Claude output file since we're proceeding with changes
rm -f "$CLAUDE_OUTPUT_FILE"

echo "Changes detected, creating commit..."

# Create commit message
COMMIT_MSG_FILE=$(mktemp)
cat > "$COMMIT_MSG_FILE" << COMMIT_EOF
fix: address AI review feedback

Automated fix by Claude in response to Gemini/Codex review.

This commit addresses issues identified in the automated code review.

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

# IMPORTANT: Post comment BEFORE pushing!
# The push will trigger a pipeline restart that may terminate this job,
# so we must post the comment first to ensure it's always visible.
post_agent_comment "Fixed issues from the review feedback and pushing the changes now.

Pipeline will re-run to verify everything's good.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/kurisu_thumbs_up.webp)"

echo "Comment posted, now pushing..."

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

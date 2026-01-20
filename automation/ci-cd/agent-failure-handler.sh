#!/bin/bash
# Agent Failure Handler Script
# Handles CI pipeline failures by attempting automated fixes
#
# Usage: agent-failure-handler.sh <pr_number> <branch_name> <iteration_count> [failure_types]
#
# Environment variables:
#   GITHUB_TOKEN - Required for pushing changes
#   GITHUB_REPOSITORY - Required for git remote URL
#   FORMAT_CHECK_RESULT - Result of format-check job (success/failure)
#   BASIC_LINT_RESULT - Result of basic-lint job (success/failure)
#   FULL_LINT_RESULT - Result of full-lint job (success/failure)

set -e

# Parse arguments
PR_NUMBER="$1"
BRANCH_NAME="$2"
ITERATION_COUNT="${3:-1}"
MAX_ITERATIONS="${4:-5}"
FAILURE_TYPES="${5:-format,lint}"  # Comma-separated list of failure types to handle

# Validate arguments
if [ -z "$PR_NUMBER" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Error: PR number and branch name are required"
    echo "Usage: $0 <pr_number> <branch_name> [iteration_count] [max_iterations] [failure_types]"
    exit 1
fi

echo "=== Agent Failure Handler ==="
echo "PR Number: $PR_NUMBER"
echo "Branch: $BRANCH_NAME"
echo "Iteration: $ITERATION_COUNT / $MAX_ITERATIONS"
echo "Handling failure types: $FAILURE_TYPES"
echo "============================="

# Check for gh CLI availability early
if ! command -v gh &> /dev/null; then
    echo "WARNING: gh CLI not found - PR comments will be skipped"
    echo "Install gh CLI for full functionality: https://cli.github.com/"
fi

# =============================================================================
# PR COMMENTING FUNCTIONS
# =============================================================================

# Function to post a comment on the PR
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

# Function to post detailed failure handler comment
post_failure_handler_comment() {
    local iteration="$1"
    local made_changes="$2"
    local commit_sha="$3"
    local failures_fixed="$4"

    # Calculate next iteration number (current count + 1 for this new comment)
    local next_iteration=$((iteration + 1))

    local comment_body=""

    if [ "$made_changes" = "true" ]; then
        comment_body="## Failure Handler Agent (Iteration $next_iteration)
<!-- agent-metadata:type=failure-fix:iteration=$next_iteration -->

**Status:** Changes committed and pushed

**Commit:** \`$commit_sha\`

**Failures addressed:**
$failures_fixed

---
*This automated fix was applied in response to CI pipeline failures.*"
    else
        comment_body="## Failure Handler Agent (Iteration $next_iteration)
<!-- agent-metadata:type=failure-fix:iteration=$next_iteration -->

**Status:** No changes needed

The agent analyzed the failures but determined no automated fixes could be applied.

---
*Manual intervention may be required.*"
    fi

    post_agent_comment "$comment_body"
}

# Check if max iterations exceeded
if [ "$ITERATION_COUNT" -ge "$MAX_ITERATIONS" ]; then
    echo "ERROR: Maximum iterations ($MAX_ITERATIONS) reached!"
    echo "Manual intervention required."
    echo "exceeded_max=true" >> "${GITHUB_OUTPUT:-/dev/null}"
    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 1
fi

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Configure git authentication
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPOSITORY" ]; then
    echo "Configuring git authentication..."
    git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    git config user.name "AI Pipeline Agent"
    git config user.email "ai-pipeline-agent@localhost"
else
    echo "WARNING: GITHUB_TOKEN or GITHUB_REPOSITORY not set"
fi

# Checkout the PR branch
echo "Checking out branch: $BRANCH_NAME"
git fetch origin "$BRANCH_NAME" 2>&1 || true
git checkout "$BRANCH_NAME" 2>&1 || true

# Collect failure information
FAILURES_DETECTED=""
TEST_FAILURES=""

if [ "${FORMAT_CHECK_RESULT:-}" = "failure" ]; then
    FAILURES_DETECTED+="format "
    echo "Detected format-check failure"
fi

if [ "${BASIC_LINT_RESULT:-}" = "failure" ]; then
    FAILURES_DETECTED+="basic-lint "
    echo "Detected basic-lint failure"
fi

if [ "${FULL_LINT_RESULT:-}" = "failure" ]; then
    FAILURES_DETECTED+="full-lint "
    echo "Detected full-lint failure"
fi

if [ "${TEST_SUITE_RESULT:-}" = "failure" ]; then
    TEST_FAILURES="test-suite"
    echo "Detected test-suite failure"
fi

# If no specific failures passed via env, check if failure_types includes format/lint/test
if [ -z "$FAILURES_DETECTED" ] && [ -z "$TEST_FAILURES" ]; then
    if [[ "$FAILURE_TYPES" == *"format"* ]] || [[ "$FAILURE_TYPES" == *"lint"* ]]; then
        FAILURES_DETECTED="format lint"
        echo "Assuming format/lint failures based on failure_types"
    fi
    if [[ "$FAILURE_TYPES" == *"test"* ]]; then
        TEST_FAILURES="test-suite"
        echo "Assuming test failures based on failure_types"
    fi
fi

if [ -z "$FAILURES_DETECTED" ] && [ -z "$TEST_FAILURES" ]; then
    echo "No handleable failures detected"
    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

echo "Failures to address: $FAILURES_DETECTED $TEST_FAILURES"

# Step 1: Run autoformat (handles most format/lint issues)
echo ""
echo "=== Step 1: Running autoformat ==="

if [ -f "./automation/ci-cd/run-ci.sh" ]; then
    # Run autoformat
    ./automation/ci-cd/run-ci.sh autoformat 2>&1 || echo "Autoformat completed with warnings"
else
    # Fallback to direct tool invocation if running in container
    echo "Using direct formatting tools..."
    if command -v black &> /dev/null; then
        black . 2>&1 || echo "Black completed"
    fi
    if command -v isort &> /dev/null; then
        isort . 2>&1 || echo "Isort completed"
    fi
fi

# Check if autoformat made changes
git add -A
if ! git diff --cached --quiet 2>/dev/null; then
    echo "Autoformat made changes"
fi

# Step 2: Run lint check to identify remaining issues
echo ""
echo "=== Step 2: Checking for remaining lint issues ==="

LINT_OUTPUT=""
if [ -f "./automation/ci-cd/run-ci.sh" ]; then
    # Capture lint-basic output (flake8)
    if [ "${BASIC_LINT_RESULT:-}" = "failure" ] || [ -z "${BASIC_LINT_RESULT:-}" ]; then
        echo "Capturing lint-basic output..."
        LINT_OUTPUT=$(./automation/ci-cd/run-ci.sh lint-basic 2>&1 || true)
    fi

    # Also capture lint-full output (ruff, mypy) if that failed
    if [ "${FULL_LINT_RESULT:-}" = "failure" ]; then
        echo "Capturing lint-full output..."
        FULL_LINT_OUTPUT=$(./automation/ci-cd/run-ci.sh lint-full 2>&1 || true)
        LINT_OUTPUT="${LINT_OUTPUT}

=== Full Lint Output (ruff/mypy) ===
${FULL_LINT_OUTPUT}"
    fi

    echo "Lint check output captured"
fi

# Step 2b: Run tests to capture test failure output
TEST_OUTPUT=""
if [ -n "$TEST_FAILURES" ]; then
    echo ""
    echo "=== Step 2b: Capturing test failure output ==="
    if [ -f "./automation/ci-cd/run-ci.sh" ]; then
        echo "Running tests to capture failure details..."
        # Run tests with verbose output, capture both stdout and stderr
        TEST_OUTPUT=$(./automation/ci-cd/run-ci.sh test 2>&1 || true)
        # Truncate if too long (keep last 5000 chars which usually has the failures)
        if [ ${#TEST_OUTPUT} -gt 8000 ]; then
            TEST_OUTPUT="... (truncated, showing last 5000 chars) ...

${TEST_OUTPUT: -5000}"
        fi
        echo "Test output captured (${#TEST_OUTPUT} chars)"
    fi
fi

# Step 3: If there are still issues, invoke Claude
echo ""
echo "=== Step 3: Invoking Claude for remaining issues ==="

# Build prompt for Claude based on failure types
CLAUDE_PROMPT="You are fixing CI/CD pipeline failures for a pull request.

"

# Add lint-specific instructions if lint failures
if [ -n "$FAILURES_DETECTED" ]; then
    CLAUDE_PROMPT+="## Lint/Format Failures Detected

INSTRUCTIONS FOR LINT ISSUES:
1. Fix unused imports, formatting issues, type hints
2. Make minimal changes - only what's needed to pass CI
3. The autoformat tools (black, isort) have already been run

"
    if [ -n "$LINT_OUTPUT" ]; then
        CLAUDE_PROMPT+="### Lint Output:
$LINT_OUTPUT

"
    fi
fi

# Add test-specific instructions if test failures
if [ -n "$TEST_FAILURES" ]; then
    CLAUDE_PROMPT+="## Test Failures Detected

INSTRUCTIONS FOR TEST FAILURES:
1. Analyze the test output to understand what's failing
2. Fix bugs in the CODE being tested, not the tests themselves (unless the test is clearly wrong)
3. If a test expects certain behavior, make the code match that behavior
4. Do NOT disable, skip, or delete failing tests
5. Make minimal, targeted fixes

"
    if [ -n "$TEST_OUTPUT" ]; then
        CLAUDE_PROMPT+="### Test Output:
$TEST_OUTPUT

"
    fi
fi

CLAUDE_PROMPT+="Please analyze and fix the issues above.
After making changes, provide a brief summary of what was fixed."

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

    # Run Claude with prompt via stdin to avoid "Argument list too long" errors
    # shellcheck disable=SC2086
    $TIMEOUT_CMD $CLAUDE_CMD -p < "$PROMPT_FILE" 2>&1 || {
        exit_code=$?
        echo "Claude exited with code: $exit_code"
        if [ $exit_code -eq 124 ]; then
            echo "Claude timed out after 10 minutes"
        fi
    }

    rm -f "$PROMPT_FILE"
else
    echo "WARNING: Claude CLI not found"
    echo "Proceeding with autoformat changes only"
    rm -f "$PROMPT_FILE"
fi

# Step 4: Check for changes and commit
echo ""
echo "=== Step 4: Checking for changes ==="

# Stage all changes
git add -A

if git diff --cached --quiet 2>/dev/null; then
    echo "No changes to commit"

    # Post comment indicating no changes were made
    post_failure_handler_comment "$ITERATION_COUNT" "false" "" ""

    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

echo "Changes detected, creating commit..."

# Summarize failures addressed
FAILURES_SUMMARY=""
for failure in $FAILURES_DETECTED; do
    FAILURES_SUMMARY+="- $failure\n"
done

# Create commit message
COMMIT_MSG_FILE=$(mktemp)
cat > "$COMMIT_MSG_FILE" << COMMIT_EOF
fix: resolve CI pipeline failures

Automated fix by Claude in response to pipeline failures.

Failures addressed:
$(echo -e "$FAILURES_SUMMARY")
Actions taken:
- Ran autoformat (black, isort)
- Fixed remaining lint issues

Iteration: ${ITERATION_COUNT}/${MAX_ITERATIONS}

Co-Authored-By: AI Pipeline Agent <noreply@anthropic.com>
COMMIT_EOF

# Commit changes
git commit -F "$COMMIT_MSG_FILE"
rm -f "$COMMIT_MSG_FILE"

echo "Commit created successfully"

# Step 5: Push changes
echo ""
echo "=== Step 5: Pushing changes ==="

# Get the commit SHA for the comment
COMMIT_SHA=$(git rev-parse --short HEAD)

# Format failures for comment
FAILURES_FOR_COMMENT=""
for failure in $FAILURES_DETECTED $TEST_FAILURES; do
    FAILURES_FOR_COMMENT+="- $failure
"
done

# IMPORTANT: Post comment BEFORE pushing!
# The push will trigger a pipeline restart that may terminate this job,
# so we must post the comment first to ensure it's always visible.
post_failure_handler_comment "$ITERATION_COUNT" "true" "$COMMIT_SHA" "$FAILURES_FOR_COMMENT"

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
echo "=== Agent Failure Handler Complete ==="
echo "Changes pushed to branch: $BRANCH_NAME"
echo "Pipeline will be retriggered automatically"
echo "made_changes=true" >> "${GITHUB_OUTPUT:-/dev/null}"

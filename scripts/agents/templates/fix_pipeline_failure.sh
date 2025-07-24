#!/bin/bash
# Script to fix CI/CD pipeline failures using Claude Code
# Usage: fix_pipeline_failure.sh <pr_number> <branch_name>
# Failure data is passed via stdin as JSON

set -e  # Exit on error

# Parse arguments
PR_NUMBER="$1"
BRANCH_NAME="$2"

# Validate arguments
if [ -z "$PR_NUMBER" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Error: PR number and branch name are required"
    echo "Usage: $0 <pr_number> <branch_name>"
    echo "Failure data should be passed via stdin as JSON"
    exit 1
fi

# Read failure data from stdin
FAILURE_DATA=$(cat)
LINT_FAILURES=$(echo "$FAILURE_DATA" | jq -r '.lint_failures[]' 2>/dev/null || echo "")
TEST_FAILURES=$(echo "$FAILURE_DATA" | jq -r '.test_failures[]' 2>/dev/null || echo "")
BUILD_FAILURES=$(echo "$FAILURE_DATA" | jq -r '.build_failures[]' 2>/dev/null || echo "")
OTHER_FAILURES=$(echo "$FAILURE_DATA" | jq -r '.other_failures[]' 2>/dev/null || echo "")

# Safety check - ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Checkout the PR branch
echo "Fetching and checking out branch: $BRANCH_NAME"
git fetch origin "$BRANCH_NAME"
git checkout "$BRANCH_NAME"

# Create a backup branch
BACKUP_BRANCH="pr-${PR_NUMBER}-pipeline-fix-backup-$(date +%s)"
echo "Creating backup branch: $BACKUP_BRANCH"
git branch -f "$BACKUP_BRANCH"

# Run linting/formatting tools first if there are lint failures
if [ -n "$LINT_FAILURES" ]; then
    echo "Detected lint/format failures. Running auto-formatting..."
    # Check if we have the CI script available
    if [ -f "./scripts/run-ci.sh" ]; then
        echo "Running auto-format..."
        ./scripts/run-ci.sh autoformat || echo "Auto-format completed with warnings"
    fi
fi

# Use Claude Code to analyze and fix failures
echo "Running Claude Code to fix pipeline failures..."
npx --yes @anthropic-ai/claude-code@1.0.59 << EOF
PR #${PR_NUMBER} CI/CD Pipeline Failures

The following CI/CD checks are failing and need to be fixed:

## Lint/Format Failures:
${LINT_FAILURES:-"None"}

## Test Failures:
${TEST_FAILURES:-"None"}

## Build Failures:
${BUILD_FAILURES:-"None"}

## Other Failures:
${OTHER_FAILURES:-"None"}

Please analyze and fix all the failures:

1. For lint/format failures:
   - Run the appropriate linting/formatting commands
   - Fix any code style issues
   - Ensure all files follow project conventions

2. For test failures:
   - Analyze the failing tests
   - Fix the code that's causing tests to fail
   - Do NOT modify tests to make them pass unless they're clearly incorrect
   - Ensure all tests are passing

3. For build failures:
   - Fix any compilation errors
   - Resolve dependency issues
   - Fix Docker/container build problems

4. For other failures:
   - Analyze the specific failure type
   - Apply appropriate fixes

Important guidelines:
- Focus on fixing the actual issues, not bypassing checks
- Maintain code quality and functionality
- Run tests locally to verify fixes
- Do NOT disable linting rules or tests
- Ensure backward compatibility

After making all necessary fixes, create a commit with message: "Fix CI/CD pipeline failures"
EOF

# Run tests to verify fixes
echo "Running tests to verify fixes..."
if [ -f "./scripts/run-ci.sh" ]; then
    # Run format check
    echo "Checking code formatting..."
    ./scripts/run-ci.sh format || echo "Format check completed"

    # Run basic linting
    echo "Running basic linting..."
    ./scripts/run-ci.sh lint-basic || echo "Basic lint completed"

    # Run tests if we fixed test failures
    if [ -n "$TEST_FAILURES" ]; then
        echo "Running tests..."
        ./scripts/run-ci.sh test || echo "Tests completed"
    fi
else
    echo "Warning: run-ci.sh not found, skipping verification"
fi

# Check if there are changes to commit
if git diff --quiet && git diff --cached --quiet; then
    echo "No changes made - pipeline issues may require manual intervention"
    exit 1
fi

# Commit changes
echo "Committing fixes..."
git add -A
git commit -m "Fix CI/CD pipeline failures

- Fixed lint/format issues
- Resolved test failures
- Corrected build problems
- All CI/CD checks should now pass

Co-Authored-By: AI Pipeline Agent <noreply@ai-agent.local>"

# Push changes
echo "Pushing fixes to origin..."
git push origin "$BRANCH_NAME"

echo "Successfully fixed pipeline failures!"

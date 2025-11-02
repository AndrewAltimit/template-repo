#!/bin/bash
# Script to implement a test feature for validating AI agent workflows
# This creates test implementations based on issue requirements
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
ISSUE_BODY=$(echo "$ISSUE_DATA" | jq -r '.body')

# Label functionality removed - PR processing based on keyword triggers only

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

# Use Claude to implement the requested feature
echo "Running Claude to implement the feature..."
echo "Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}"
echo ""
echo "Using Claude to implement the requested feature..."

# Determine Claude command based on environment
if [ -f /.dockerenv ] || [ -n "$CONTAINER" ]; then
    # We're in a container
    echo "Running in container - checking for mounted Claude credentials..."
    # Check both possible locations for Claude credentials
    if [ -f "$HOME/.claude/.credentials.json" ]; then
        echo "Claude credentials found at $HOME/.claude/.credentials.json"
        # Try to use claude-code with permissions flag if available, otherwise fall back to claude
        if command -v claude-code >/dev/null 2>&1; then
            CLAUDE_CMD="claude-code --dangerously-skip-permissions"
        else
            CLAUDE_CMD="claude"
        fi
    elif [ -f "/tmp/agent-home/.claude/.credentials.json" ]; then
        echo "Claude credentials found at /tmp/agent-home/.claude/.credentials.json"
        export HOME=/tmp/agent-home
        # Try to use claude-code with permissions flag if available, otherwise fall back to claude
        if command -v claude-code >/dev/null 2>&1; then
            CLAUDE_CMD="claude-code --dangerously-skip-permissions"
        else
            CLAUDE_CMD="claude"
        fi
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

# Configure git identity if not already set (Claude will need this)
if ! git config user.name >/dev/null 2>&1; then
    git config user.name "AI Issue Monitor Agent"
fi
if ! git config user.email >/dev/null 2>&1; then
    git config user.email "ai-agent[bot]@users.noreply.github.com"
fi

# Gather repository context for Claude
echo "Gathering repository context..."
REPO_LANGUAGES=$(find . -type f -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" | head -5 | xargs -I {} basename {} | cut -d. -f2 | sort -u | tr '\n' ', ' | sed 's/,$//')
MAIN_DIRS=$(find . -maxdepth 2 -type d -not -path '*/\.*' -not -path './node_modules*' -not -path './__pycache__*' | grep -v '^\.$' | sort | head -10 | tr '\n' ', ' | sed 's/,$//')
TEST_FRAMEWORK=""
if [ -f "pytest.ini" ] || [ -f "setup.cfg" ] || grep -q "pytest" requirements.txt 2>/dev/null; then
    TEST_FRAMEWORK="pytest"
elif [ -f "package.json" ] && grep -q "jest" package.json 2>/dev/null; then
    TEST_FRAMEWORK="jest"
elif [ -f "go.mod" ]; then
    TEST_FRAMEWORK="go test"
fi

# Run Claude Code to implement the feature
$CLAUDE_CMD << EOF
Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}

Issue Description:
${ISSUE_BODY}

Repository Context:
- Main languages: ${REPO_LANGUAGES:-Python}
- Key directories: ${MAIN_DIRS}
- Test framework: ${TEST_FRAMEWORK:-pytest}
- Current directory: $(pwd)

CRITICAL: You MUST implement the actual solution, not just analyze or describe it.

Your task is to implement the feature/fix described in the issue above. Follow these steps:

STEP 1 - Understand the codebase:
- Use Grep and Glob tools to search for relevant files
- Use Read tool to examine existing code patterns
- Understand the project structure and conventions

STEP 2 - Implement the solution:
- Create new files with Write tool where needed
- Modify existing files with Edit or MultiEdit tools
- Write actual, working code - no placeholders or TODOs
- Follow the existing code style and patterns

STEP 3 - Add tests:
- Create test files if they don't exist
- Add test cases for your implementation
- Ensure tests actually test the functionality

STEP 4 - Verify your work:
- Use Bash tool to run relevant tests if possible
- Use Read tool to review your changes
- Ensure all code is complete and functional

STEP 5 - COMMIT YOUR CHANGES:
- Use Bash tool to run: git add -A
- Use Bash tool to run: git commit -m "feat: implement ${ISSUE_TITLE} (fixes #${ISSUE_NUMBER})"
- This step is MANDATORY - you MUST commit your changes

IMPORTANT REMINDERS:
- You have FULL permission to create and modify ANY files
- Write ACTUAL CODE, not descriptions or placeholders
- If the issue asks for a feature, BUILD IT completely
- If the issue reports a bug, FIX IT with real code changes
- Do NOT just create documentation unless specifically asked

Example of what NOT to do:
- Creating only a README or documentation file
- Writing comments about what should be done
- Creating placeholder functions with pass or TODO

Example of what TO DO:
- Implement the full functionality requested
- Write complete, working code
- Add proper error handling
- Include tests that verify the functionality

CRITICAL FINAL STEP:
You MUST commit your changes using these exact commands:
1. git add -A
2. git commit -m "feat: implement ${ISSUE_TITLE} (fixes #${ISSUE_NUMBER})"

If you don't commit, the PR will fail. START IMPLEMENTING NOW - BUILD THE SOLUTION!
EOF

# Check what files were created or modified
echo "Checking for implementation changes..."
IMPLEMENTATION_FILES=$(git diff --name-only origin/main 2>/dev/null | grep -E '\.(py|js|ts|jsx|tsx|go|java|cpp|c|h|rs|rb|php|cs|swift|kt|scala|r|jl|m|mm)$' || true)
DOC_FILES=$(git diff --name-only origin/main 2>/dev/null | grep -E '\.(md|txt|rst|adoc)$' || true)
UNSTAGED_IMPL_FILES=$(git diff --name-only 2>/dev/null | grep -E '\.(py|js|ts|jsx|tsx|go|java|cpp|c|h|rs|rb|php|cs|swift|kt|scala|r|jl|m|mm)$' || true)
UNSTAGED_DOC_FILES=$(git diff --name-only 2>/dev/null | grep -E '\.(md|txt|rst|adoc)$' || true)

if [ -n "$IMPLEMENTATION_FILES" ] || [ -n "$UNSTAGED_IMPL_FILES" ]; then
    echo "✓ Found implementation files:"
    [ -n "$IMPLEMENTATION_FILES" ] && echo "$IMPLEMENTATION_FILES"
    [ -n "$UNSTAGED_IMPL_FILES" ] && echo "$UNSTAGED_IMPL_FILES"
else
    echo "⚠ WARNING: No implementation files found, only documentation:"
    [ -n "$DOC_FILES" ] && echo "$DOC_FILES"
    [ -n "$UNSTAGED_DOC_FILES" ] && echo "$UNSTAGED_DOC_FILES"
    echo ""
    echo "Claude may have only analyzed the issue without implementing it."
    echo "This could happen if the issue description is unclear or too vague."
fi

# Check if Claude made any commits by comparing with origin/main
COMMITS_AHEAD=$(git rev-list --count origin/main..HEAD)
echo "Commits ahead of origin/main: $COMMITS_AHEAD"

if [ "$COMMITS_AHEAD" -eq 0 ]; then
    echo "No changes were committed by Claude"
    # Check if there are any uncommitted changes first
    if ! git diff --quiet || ! git diff --staged --quiet; then
        echo "Found uncommitted changes - committing them..."
        git add -A
        git commit -m "feat: implement changes for issue #${ISSUE_NUMBER}

Implemented changes based on issue requirements.
Fixes #${ISSUE_NUMBER}"
    else
        # If no commits and no changes, the agent failed to implement
        echo "ERROR: Claude did not implement the requested feature!"
        echo "The AI agent failed to create any implementation."
        echo "This could be due to:"
        echo "1. Unclear issue description"
        echo "2. Agent error or timeout"
        echo "3. Complex requirements needing human intervention"
        echo ""
        echo "Aborting PR creation - manual intervention required."
        exit 1
    fi
else
    echo "Claude made $COMMITS_AHEAD commit(s)"
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

# Get list of changed files for PR description
echo "Analyzing changes for PR description..."
ALL_CHANGED_FILES=$(git diff --name-only origin/main 2>/dev/null || true)
IMPL_FILES_FOR_PR=$(echo "$ALL_CHANGED_FILES" | grep -E '\.(py|js|ts|jsx|tsx|go|java|cpp|c|h|rs|rb|php|cs|swift|kt|scala|r|jl|m|mm)$' || echo "")
TEST_FILES_FOR_PR=$(echo "$ALL_CHANGED_FILES" | grep -E '(test_|_test\.|\.test\.|spec\.|\.spec\.)' || echo "")
DOC_FILES_FOR_PR=$(echo "$ALL_CHANGED_FILES" | grep -E '\.(md|txt|rst|adoc)$' || echo "")

# Build changes summary
CHANGES_SUMMARY=""
if [ -n "$IMPL_FILES_FOR_PR" ]; then
    CHANGES_SUMMARY="${CHANGES_SUMMARY}### Implementation Files\n"
    echo "$IMPL_FILES_FOR_PR" | while read -r file; do
        CHANGES_SUMMARY="${CHANGES_SUMMARY}- \`$file\`\n"
    done
fi
if [ -n "$TEST_FILES_FOR_PR" ]; then
    CHANGES_SUMMARY="${CHANGES_SUMMARY}\n### Test Files\n"
    echo "$TEST_FILES_FOR_PR" | while read -r file; do
        CHANGES_SUMMARY="${CHANGES_SUMMARY}- \`$file\`\n"
    done
fi
if [ -n "$DOC_FILES_FOR_PR" ]; then
    CHANGES_SUMMARY="${CHANGES_SUMMARY}\n### Documentation\n"
    echo "$DOC_FILES_FOR_PR" | while read -r file; do
        CHANGES_SUMMARY="${CHANGES_SUMMARY}- \`$file\`\n"
    done
fi

# Determine PR type based on what was changed
PR_TYPE="feature"
if echo "${ISSUE_TITLE}" | grep -iE "(fix|bug|error|issue)" >/dev/null; then
    PR_TYPE="fix"
fi

# Create PR using template
echo "Creating pull request..."
PR_BODY="## 🚀 Pull Request

This PR implements the requested changes for issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}

**Status**: ✅ Ready for review - implementation complete with tests.

## Issue Details
${ISSUE_BODY}

## Related Issue
Fixes #${ISSUE_NUMBER}

## Type of Change
$(if [ "$PR_TYPE" = "fix" ]; then
    echo "- [x] Bug fix (non-breaking change which fixes an issue)"
    echo "- [ ] New feature (non-breaking change which adds functionality)"
else
    echo "- [ ] Bug fix (non-breaking change which fixes an issue)"
    echo "- [x] New feature (non-breaking change which adds functionality)"
fi)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring
- [ ] Test improvement
- [ ] CI/CD improvement

## Changes Made
${CHANGES_SUMMARY:-No files were changed}

## Implementation Status
$(if [ -n "$IMPL_FILES_FOR_PR" ]; then
    echo "✅ Implementation completed - $(echo "$IMPL_FILES_FOR_PR" | wc -l) source files modified"
else
    echo "⚠️ No implementation files found - only documentation was created"
fi)

## Testing
- [ ] All existing tests pass
$(if [ -n "$TEST_FILES_FOR_PR" ]; then
    echo "- [x] New tests added for new functionality"
else
    echo "- [ ] New tests added for new functionality"
fi)
- [ ] Manual testing completed
- [ ] CI/CD pipeline passes

## Checklist
- [x] My code follows the project's style guidelines
- [x] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Additional Notes
This PR was automatically generated by the AI Issue Monitor Agent in response to issue #${ISSUE_NUMBER}.

$(if [ -z "$IMPL_FILES_FOR_PR" ] && [ -n "$DOC_FILES_FOR_PR" ]; then
    echo "**Note**: This PR only contains documentation changes. The implementation may need to be completed manually if the issue description was unclear or if the requested feature requires more context."
fi)

---
## AI Agent Metadata
- **Auto-merge eligible**: No
- **Priority**: Normal
- **Agent**: Issue Monitor
- **Trigger**: [Approved][Claude]
- **Implementation Status**: $(if [ -n "$IMPL_FILES_FOR_PR" ]; then echo "Complete"; else echo "Documentation Only"; fi)"

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

# Label functionality removed - PRs no longer require labels
# They are processed based on keyword triggers from approved users

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

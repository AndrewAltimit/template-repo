#!/bin/bash
# Agent Review Response Script
# Responds to Gemini/Codex AI reviews by passing all feedback to Claude for
# intelligent analysis and decision-making.
#
# Philosophy: Let the agent see all feedback and decide intelligently what to fix.
# No pattern matching gating - the agent applies judgment to each piece of feedback.
#
# The script still validates file/line references to detect potential hallucinations
# and provides this context to Claude, but does not skip based on pattern matching.
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

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

# Validate that a reported file exists
validate_file_exists() {
    local file="$1"
    [ -f "$file" ]
}

# Validate that a line number is within file bounds
validate_line_number() {
    local file="$1"
    local line="$2"

    if [ ! -f "$file" ]; then
        return 1
    fi

    local total_lines
    total_lines=$(wc -l < "$file")
    [ "$line" -le "$total_lines" ] 2>/dev/null
}

# Validate an import issue by checking if the import exists
validate_import_issue() {
    local file="$1"
    local import_name="$2"

    if [ ! -f "$file" ]; then
        return 1
    fi

    # Check if the import is actually present (handles multiple formats):
    # - import module
    # - import module, module2, module3
    # - from module import ...
    # - import module as alias
    # Also handles indented imports (e.g., inside try/except blocks)
    # Use word boundary \b to prevent partial matches (e.g., "os" matching "osgeo")
    if grep -qE "^[[:space:]]*(import[[:space:]]+(${import_name}\b|[^#]*,[[:space:]]*${import_name}\b)|from[[:space:]]+${import_name}\b)" "$file"; then
        return 1  # Import exists, not a valid issue
    fi

    # Check if the module is used in the file
    if grep -qE "\b${import_name}\." "$file"; then
        return 0  # Module used but not imported - valid issue
    fi

    return 1
}

# Run static analysis to confirm issues at a specific line
# Parameters:
#   $1 - file path
#   $2 - line number (optional, validates whole file if not provided)
#   $3 - error pattern (optional, defaults to common import/syntax errors)
validate_with_linter() {
    local file="$1"
    local line_num="${2:-}"
    local error_pattern="${3:-F401|F811|E999|E902}"

    if [ ! -f "$file" ]; then
        return 1
    fi

    local linter_output=""

    # Try flake8 if available
    if command -v flake8 &> /dev/null; then
        linter_output=$(flake8 "$file" 2>/dev/null) || true
    elif command -v docker &> /dev/null && [ -f "docker-compose.yml" ]; then
        # Try running in container if available
        linter_output=$(docker-compose run --rm python-ci flake8 "$file" 2>/dev/null) || true
    fi

    if [ -z "$linter_output" ]; then
        return 1  # No linter output, can't validate
    fi

    # If line number provided, check for issues on that specific line
    if [ -n "$line_num" ]; then
        if echo "$linter_output" | grep -qE ":${line_num}:.*($error_pattern)"; then
            return 0  # Found matching error on the specific line
        fi
        return 1  # No matching error on that line
    fi

    # No line number - check if file has any matching errors
    if echo "$linter_output" | grep -qE "$error_pattern"; then
        return 0  # Linter found matching issues somewhere in file
    fi

    return 1
}

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
        gh pr comment "$PR_NUMBER" --body-file "$temp_file" || {
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

# Determine which reviews were found for reporting
REVIEWS_FOUND=""
if [ -f "${GEMINI_REVIEW_PATH:-gemini-review.md}" ] || [ -f "gemini-review.md" ]; then
    REVIEWS_FOUND+="- Gemini review\n"
fi
if [ -f "${CODEX_REVIEW_PATH:-codex-review.md}" ] || [ -f "codex-review.md" ]; then
    REVIEWS_FOUND+="- Codex review\n"
fi

echo "Review content found, passing to agent for intelligent analysis..."
echo "Reviews found:"
printf '%b' "$REVIEWS_FOUND"

# =============================================================================
# VALIDATE AI FEEDBACK (provide context, but don't gate on patterns)
# =============================================================================

# Track validation results for reporting
VALIDATED_ISSUES=0
HALLUCINATION_SUSPECTS=0

# Analyze individual feedback items for validation
echo ""
echo "=== Validating AI Feedback ==="
echo "IMPORTANT: AI reviewers can hallucinate. Validating claims..."

# Track linter-validated issues separately
LINTER_VALIDATED=0

# Extract file references from review and validate them
while IFS= read -r line; do
    # Skip empty lines
    [ -z "$line" ] && continue

    # Reset per-line tracking
    current_file=""
    current_line=""

    # Check if line mentions a file path
    if printf '%s\n' "$line" | grep -qE "\.(py|js|ts|yaml|yml|sh|md)"; then
        # Try to extract file path
        current_file=$(printf '%s\n' "$line" | grep -oE "[a-zA-Z0-9_/.-]+\.(py|js|ts|yaml|yml|sh|md)" | head -1) || true

        if [ -n "$current_file" ]; then
            if validate_file_exists "$current_file"; then
                echo "[VALIDATE] File exists: $current_file"
                ((VALIDATED_ISSUES++)) || true
            else
                # Check if context indicates file was intentionally deleted/removed
                # (in which case non-existence is expected, not a hallucination)
                # Use word boundaries to avoid false matches (e.g., "stub" shouldn't match "stubborn")
                if printf '%s\n' "$line" | grep -qiE '\b(delet(e|ed|ion)?|remov(e|ed|al|ing)?|deprecat(e|ed)?|migrat(e|ed|ion)?|stubs?)\b|no longer'; then
                    echo "[VALIDATE] File $current_file doesn't exist but context indicates intentional deletion - skipping"
                else
                    echo "[VALIDATE] WARNING: File does not exist: $current_file (possible hallucination)"
                    ((HALLUCINATION_SUSPECTS++)) || true
                fi
                continue  # Skip further validation for non-existent file
            fi
        fi
    fi

    # Check for line number references
    if printf '%s\n' "$line" | grep -qE "line [0-9]+|Line [0-9]+|:[0-9]+:"; then
        current_line=$(printf '%s\n' "$line" | grep -oE "[0-9]+" | head -1) || true
        if [ -n "$current_file" ] && [ -n "$current_line" ]; then
            if validate_line_number "$current_file" "$current_line"; then
                echo "[VALIDATE] Line $current_line valid in $current_file"
            else
                echo "[VALIDATE] WARNING: Line $current_line out of range in $current_file (possible hallucination)"
                ((HALLUCINATION_SUSPECTS++)) || true
            fi
        fi
    fi

    # === SEMANTIC VALIDATION ===
    # Now perform deeper validation using linter and import checks

    # Check for import-related issues
    if printf '%s\n' "$line" | grep -qiE "import|missing.*import|unused.*import|F401"; then
        # Try to extract module name from feedback
        # Common patterns: "import os", "missing import: requests", "unused import 'json'"
        module_name=$(printf '%s\n' "$line" | grep -oE "(import|module)[[:space:]]+['\"]?([a-zA-Z_][a-zA-Z0-9_]*)['\"]?" | grep -oE "[a-zA-Z_][a-zA-Z0-9_]*$" | head -1) || true

        if [ -n "$module_name" ] && [ -n "$current_file" ] && [[ "$current_file" == *.py ]]; then
            echo "[VALIDATE] Checking import issue for module '$module_name' in $current_file"
            if validate_import_issue "$current_file" "$module_name"; then
                echo "[VALIDATE] CONFIRMED: Module '$module_name' is used but not imported"
                ((LINTER_VALIDATED++)) || true
            else
                echo "[VALIDATE] Import issue NOT confirmed (module exists or not used)"
            fi
        fi
    fi

    # Run linter validation for Python files with specific line references
    if [ -n "$current_file" ] && [[ "$current_file" == *.py ]]; then
        if [ -n "$current_line" ]; then
            echo "[VALIDATE] Running linter check on $current_file:$current_line"
            if validate_with_linter "$current_file" "$current_line"; then
                echo "[VALIDATE] CONFIRMED: Linter found issue at $current_file:$current_line"
                ((LINTER_VALIDATED++)) || true
            else
                echo "[VALIDATE] Linter did NOT confirm issue at $current_file:$current_line"
            fi
        fi
    fi
done < <(printf '%s\n' "$REVIEW_CONTENT") || true
# Note: || true is needed because 'read' returns 1 on EOF, which triggers set -e

echo ""
echo "[RUBRIC] Validation summary:"
echo "  - File/line checks passed: $VALIDATED_ISSUES"
echo "  - Linter-confirmed issues: $LINTER_VALIDATED"
echo "  - Suspected hallucinations: $HALLUCINATION_SUSPECTS"

# Always proceed to Claude - let the agent decide intelligently what to fix
# No pattern matching gating - the agent sees all feedback and uses judgment
echo ""
echo "[RUBRIC] Proceeding with agent analysis..."
echo "[RUBRIC] Validation context: $VALIDATED_ISSUES validated, $HALLUCINATION_SUSPECTS suspected hallucinations"

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

CRITICAL: AI REVIEWERS CAN HALLUCINATE
The feedback below comes from AI reviewers (Gemini, Codex) which are known to:
- Report bugs in code that doesn't exist
- Reference incorrect file paths or line numbers
- Flag correct code as incorrect
- Suggest unnecessary changes

KNOWN HALLUCINATION PATTERNS (ignore these):
- Suggesting downgrades to GitHub Actions versions - we use latest versions intentionally
- Calling explicit config options "redundant" - explicit is better than implicit
- Claiming files don't exist when they do - always verify with actual file reads
- Suggesting architectural changes disguised as "improvements"

YOU MUST VALIDATE EVERY CLAIM before making changes:
1. Verify the file exists before editing it
2. Verify line numbers are within file bounds
3. Confirm the reported issue actually exists in the code
4. If you cannot validate an issue, SKIP IT - do not guess

IMPORTANT INSTRUCTIONS:
1. Focus ONLY on formatting, linting, and code style issues
2. DO NOT modify test logic or business logic
3. Fix unused imports, formatting issues, type hints
4. Make minimal changes - only what's needed to address the feedback
5. SKIP any feedback that cannot be validated or seems like a hallucination
6. DO NOT make tool/dependency changes - those require admin approval
7. DO NOT make architectural or design changes - those are debatable
8. NEVER downgrade GitHub Actions versions - reviewers often hallucinate this

Review feedback to address:

PROMPT_EOF
)

CLAUDE_PROMPT+=$(printf '%s\n' "$REVIEW_CONTENT")

CLAUDE_PROMPT+=$(cat << 'PROMPT_EOF'

Analyze the review feedback above and fix what's actually broken.

Before fixing anything, validate it:
- Does the file exist? Read it first
- Is the issue actually there? Don't trust the reviewer blindly
- Is this a real bug or just a style preference?

Focus on real issues:
- Actual unused imports (verify they're unused)
- Real formatting problems
- Genuine linting errors

Skip anything that's:
- A hallucination (file/line doesn't exist)
- An architectural suggestion
- A style preference disguised as a bug

Be brief in your summary - just note what you fixed and what you skipped.
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

# Capture Claude's output for use in PR comments
CLAUDE_OUTPUT_FILE=$(mktemp)

if [ -n "$CLAUDE_CMD" ]; then
    echo "Running Claude with prompt..."

    # Set timeout for Claude execution (10 minutes)
    TIMEOUT_CMD="timeout 600"
    if ! command -v timeout &> /dev/null; then
        TIMEOUT_CMD=""
    fi

    # Run Claude and capture output (prompt is passed as positional argument)
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

    # IMPORTANT: Always explain why no changes were made
    # This prevents misleading situations where the agent appears to have acted but didn't

    # Extract key findings from Claude's output for the comment
    CLAUDE_SUMMARY=""
    if [ -f "$CLAUDE_OUTPUT_FILE" ] && [ -s "$CLAUDE_OUTPUT_FILE" ]; then
        # Look for summary/decision sections in Claude's output
        # Truncate to avoid overly long comments (max 1500 chars)
        CLAUDE_SUMMARY=$(grep -iE "(validated|skipped|hallucination|no changes|architectural|design|debatable)" "$CLAUDE_OUTPUT_FILE" | head -20 | cut -c1-200 | head -c 1500) || true
    fi

    post_agent_comment "Reviewed the feedback from Gemini and Codex but didn't find anything that needed fixing.

$(if [ "$HALLUCINATION_SUSPECTS" -gt 0 ]; then echo "Found $HALLUCINATION_SUSPECTS reference(s) to files or lines that don't exist - looks like hallucinations."; fi)
$(if [ "$VALIDATED_ISSUES" -gt 0 ] && [ "$LINTER_VALIDATED" -eq 0 ]; then echo "The issues mentioned were either style preferences or architectural suggestions that shouldn't be auto-fixed."; fi)

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

# IMPORTANT: Post comment BEFORE pushing!
# The push will trigger a pipeline restart that may terminate this job,
# so we must post the comment first to ensure it's always visible.
post_agent_comment "Fixed the issues from the review feedback and pushing the changes now.

$(if [ "$HALLUCINATION_SUSPECTS" -gt 0 ]; then echo "Ignored $HALLUCINATION_SUSPECTS hallucination(s) that referenced non-existent files or lines."; fi)

Pipeline will re-run to verify everything's good now.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_thumbsup.png)"

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

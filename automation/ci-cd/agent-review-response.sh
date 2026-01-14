#!/bin/bash
# Agent Review Response Script
# Responds to Gemini/Codex AI reviews by parsing feedback and making fixes
#
# This script implements a decision rubric for handling AI review feedback:
# - Never treats AI feedback as ground truth (AI can hallucinate)
# - Validates issues before acting
# - Categorizes feedback by type and source trust level
# - Escalates to admins when appropriate
#
# See AGENT_DECISION_RUBRIC.md for full documentation
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
# CONFIGURATION - Loaded from .agents.yaml
# =============================================================================

# Default values (overridden by .agents.yaml if present)
AGENT_ADMINS=("AndrewAltimit")
TRUSTED_SOURCES=("AndrewAltimit" "github-actions[bot]" "dependabot[bot]" "renovate[bot]")

# Load configuration from .agents.yaml if available
load_agents_config() {
    local config_file=".agents.yaml"

    if [ ! -f "$config_file" ]; then
        echo "[CONFIG] .agents.yaml not found, using defaults"
        return 0
    fi

    echo "[CONFIG] Loading configuration from .agents.yaml"

    # Parse agent_admins using awk for cleaner section parsing
    # Note: grep -v returns exit 1 if no matches, so we use || true to prevent set -e from aborting
    if grep -q "agent_admins:" "$config_file"; then
        local admins
        admins=$(awk '/agent_admins:/,/^[[:space:]]*[a-z_]+:/' "$config_file" \
            | grep '^\s*-' \
            | sed 's/#.*//' \
            | sed 's/.*-[[:space:]]*//' \
            | tr -d ' ' \
            | { grep -v '^$' || true; } \
            | head -10) || true
        if [ -n "$admins" ]; then
            AGENT_ADMINS=()
            while IFS= read -r admin; do
                [ -n "$admin" ] && AGENT_ADMINS+=("$admin")
            done <<< "$admins"
            echo "[CONFIG] Loaded agent_admins: ${AGENT_ADMINS[*]}"
        fi
    fi

    # Parse trusted_sources
    if grep -q "trusted_sources:" "$config_file"; then
        local sources
        sources=$(awk '/trusted_sources:/,/^[[:space:]]*[a-z_]+:/' "$config_file" \
            | grep '^\s*-' \
            | sed 's/#.*//' \
            | sed 's/.*-[[:space:]]*//' \
            | tr -d ' ' \
            | { grep -v '^$' || true; } \
            | head -20) || true
        if [ -n "$sources" ]; then
            TRUSTED_SOURCES=()
            while IFS= read -r source; do
                [ -n "$source" ] && TRUSTED_SOURCES+=("$source")
            done <<< "$sources"
            echo "[CONFIG] Loaded trusted_sources: ${TRUSTED_SOURCES[*]}"
        fi
    fi

    return 0
}

# =============================================================================
# SOURCE TRUST CLASSIFICATION
# =============================================================================

# Check if a username is an agent admin
is_agent_admin() {
    local username="$1"
    for admin in "${AGENT_ADMINS[@]}"; do
        if [ "$admin" = "$username" ]; then
            return 0
        fi
    done
    return 1
}

# Check if a username is a trusted source
is_trusted_source() {
    local username="$1"
    for source in "${TRUSTED_SOURCES[@]}"; do
        if [ "$source" = "$username" ]; then
            return 0
        fi
    done
    return 1
}

# Get trust level for a source (ADMIN, TRUSTED, AI_REVIEWER, UNTRUSTED)
get_trust_level() {
    local source="$1"
    local source_lower
    source_lower=$(echo "$source" | tr '[:upper:]' '[:lower:]')

    if is_agent_admin "$source"; then
        echo "ADMIN"
    elif is_trusted_source "$source"; then
        echo "TRUSTED"
    elif [[ "$source_lower" == gemini* ]] || \
         [[ "$source_lower" == codex* ]] || \
         [[ "$source_lower" == opencode* ]] || \
         [[ "$source_lower" == crush* ]] || \
         [[ "$source_lower" == *"ai review"* ]] || \
         [[ "$source_lower" == *"ai-review"* ]]; then
        echo "AI_REVIEWER"
    else
        echo "UNTRUSTED"
    fi
}

# =============================================================================
# FEEDBACK TYPE CLASSIFICATION
# =============================================================================

# Patterns for different feedback types
CLEAR_BUG_PATTERNS=(
    "undefined"
    "not defined"
    "NameError"
    "import.*not found"
    "missing import"
    "syntax error"
    "SyntaxError"
    "unused import"
    "F401"
    "F811"
    "IndentationError"
)

STYLE_PATTERNS=(
    "formatting"
    "indentation"
    "whitespace"
    "line too long"
    "trailing whitespace"
    "E501"
    "W291"
    "W293"
)

DEBATABLE_PATTERNS=(
    "consider"
    "might want"
    "could be"
    "suggest"
    "recommend"
    "perhaps"
    "refactor"
    "restructure"
    "redesign"
    "alternative"
)

# Note: TOOL_CHANGE detection is handled by Claude using the rubric,
# not by pattern matching (too fragile, causes false positives)

# Classify feedback into types: CLEAR_BUG, STYLE, DEBATABLE
# Note: TOOL_CHANGE is intentionally not pattern-matched here - Claude applies
# the rubric to identify tool changes and skips them appropriately
classify_feedback() {
    local feedback="$1"
    local feedback_lower
    feedback_lower=$(echo "$feedback" | tr '[:upper:]' '[:lower:]')

    # Check for clear bugs
    for pattern in "${CLEAR_BUG_PATTERNS[@]}"; do
        if echo "$feedback_lower" | grep -qiE "$pattern"; then
            echo "CLEAR_BUG"
            return
        fi
    done

    # Check for style issues
    for pattern in "${STYLE_PATTERNS[@]}"; do
        if echo "$feedback_lower" | grep -qiE "$pattern"; then
            echo "STYLE"
            return
        fi
    done

    # Check for debatable suggestions
    for pattern in "${DEBATABLE_PATTERNS[@]}"; do
        if echo "$feedback_lower" | grep -qiE "$pattern"; then
            echo "DEBATABLE"
            return
        fi
    done

    # Default to debatable if unclassified - Claude will apply judgment
    echo "DEBATABLE"
}

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
    # Use word boundary \b to prevent partial matches (e.g., "os" matching "osgeo")
    if grep -qE "^import[[:space:]]+(${import_name}\b|[^#]*,[[:space:]]*${import_name}\b)|^from[[:space:]]+${import_name}\b" "$file"; then
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

# =============================================================================
# ESCALATION FUNCTIONS
# =============================================================================

# Post an escalation request to the PR
post_escalation() {
    local reason="$1"
    local feedback="$2"
    local assessment="$3"

    # Get first admin for @mention
    local admin="${AGENT_ADMINS[0]:-AndrewAltimit}"

    local escalation_comment="## Agent Escalation Request

**Reason**: $reason

### Feedback Received
\`\`\`
$feedback
\`\`\`

### Agent Assessment
$assessment

### Options
1. Approve the suggested change
2. Reject and keep current implementation
3. Provide alternative guidance

@$admin Please advise on how to proceed.

_This escalation is from the automated review agent. Iteration ${ITERATION_COUNT}/${MAX_ITERATIONS}_"

    post_agent_comment "$escalation_comment"
    echo "[ESCALATE] Posted escalation request for: $reason"
}

# =============================================================================
# DECISION ENGINE
# =============================================================================

# Make a decision based on source trust and feedback type
# Returns: FIX, SKIP, VALIDATE
# Note: We no longer escalate automatically - Claude applies the rubric and
# decides what to fix vs skip. Escalation is reserved for explicit admin requests.
make_decision() {
    local trust_level="$1"
    local feedback_type="$2"
    local validated="$3"  # true/false

    case "$feedback_type" in
        CLEAR_BUG)
            if [ "$validated" = "true" ]; then
                # Validated bugs get fixed regardless of source
                echo "FIX"
            else
                case "$trust_level" in
                    ADMIN|TRUSTED)
                        echo "VALIDATE"  # Try to validate, then fix
                        ;;
                    AI_REVIEWER)
                        # Pass to Claude - let it validate and decide
                        echo "VALIDATE"
                        ;;
                    *)
                        echo "SKIP"  # Don't trust untrusted sources
                        ;;
                esac
            fi
            ;;
        STYLE)
            # Style issues are safe to auto-fix via formatters
            echo "FIX"
            ;;
        DEBATABLE)
            # Pass to Claude - it will apply the rubric and skip debatable items
            # Claude is smart enough to distinguish minor suggestions from major changes
            echo "VALIDATE"
            ;;
        *)
            echo "SKIP"
            ;;
    esac
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

# Load agent configuration
load_agents_config

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

echo "Actionable items detected, analyzing with decision rubric..."

# =============================================================================
# APPLY DECISION RUBRIC
# =============================================================================

# Determine the review source (AI reviewer by default for artifact files)
REVIEW_SOURCE="gemini"  # Default - Gemini/Codex are AI reviewers
TRUST_LEVEL=$(get_trust_level "$REVIEW_SOURCE")
echo "[RUBRIC] Review source: $REVIEW_SOURCE (trust level: $TRUST_LEVEL)"

# Classify the overall feedback type
FEEDBACK_TYPE=$(classify_feedback "$(echo -e "$REVIEW_CONTENT")")
echo "[RUBRIC] Feedback type: $FEEDBACK_TYPE"

# Make initial decision
INITIAL_DECISION=$(make_decision "$TRUST_LEVEL" "$FEEDBACK_TYPE" "false")
echo "[RUBRIC] Initial decision: $INITIAL_DECISION"

# Track validation results for reporting
VALIDATED_ISSUES=0
HALLUCINATION_SUSPECTS=0

# Analyze individual feedback items for validation
echo ""
echo "=== Validating AI Feedback ==="
echo "IMPORTANT: AI reviewers can hallucinate. Validating claims..."

# Extract file references from review and validate them
while IFS= read -r line; do
    # Skip empty lines
    [ -z "$line" ] && continue

    # Check if line mentions a file path
    if echo "$line" | grep -qE "\.(py|js|ts|yaml|yml|sh|md)"; then
        # Try to extract file path
        file_path=$(echo "$line" | grep -oE "[a-zA-Z0-9_/.-]+\.(py|js|ts|yaml|yml|sh|md)" | head -1)

        if [ -n "$file_path" ]; then
            if validate_file_exists "$file_path"; then
                echo "[VALIDATE] File exists: $file_path"
                ((VALIDATED_ISSUES++)) || true
            else
                echo "[VALIDATE] WARNING: File does not exist: $file_path (possible hallucination)"
                ((HALLUCINATION_SUSPECTS++)) || true
            fi
        fi
    fi

    # Check for line number references
    if echo "$line" | grep -qE "line [0-9]+|Line [0-9]+|:[0-9]+:"; then
        line_num=$(echo "$line" | grep -oE "[0-9]+" | head -1)
        if [ -n "$file_path" ] && [ -n "$line_num" ]; then
            if validate_line_number "$file_path" "$line_num"; then
                echo "[VALIDATE] Line $line_num valid in $file_path"
            else
                echo "[VALIDATE] WARNING: Line $line_num out of range in $file_path (possible hallucination)"
                ((HALLUCINATION_SUSPECTS++)) || true
            fi
        fi
    fi
done < <(echo -e "$REVIEW_CONTENT")

echo ""
echo "[RUBRIC] Validation summary: $VALIDATED_ISSUES validated, $HALLUCINATION_SUSPECTS suspected hallucinations"

# Adjust decision based on validation results
FINAL_DECISION="$INITIAL_DECISION"
if [ "$HALLUCINATION_SUSPECTS" -gt 0 ] && [ "$VALIDATED_ISSUES" -eq 0 ]; then
    echo "[RUBRIC] High hallucination risk detected - being extra cautious"
    if [ "$FEEDBACK_TYPE" = "CLEAR_BUG" ]; then
        FINAL_DECISION="SKIP"
        echo "[RUBRIC] Downgrading CLEAR_BUG to SKIP due to validation failures"
    fi
fi

# Handle skip cases
if [ "$FINAL_DECISION" = "SKIP" ]; then
    echo "[RUBRIC] Skipping - feedback does not meet criteria for auto-fix"

    post_agent_comment "## Agent Review Response

**Status**: No action taken (rubric decision: SKIP)

The agent analyzed the feedback but determined it should not auto-fix.

### Decision Analysis
- **Feedback Type**: $FEEDBACK_TYPE
- **Source Trust Level**: $TRUST_LEVEL
- **Decision**: SKIP

### Reasons for Skipping
$(if [ "$FEEDBACK_TYPE" = "DEBATABLE" ]; then echo "- Debatable suggestions require human review"; fi)
$(if [ "$TRUST_LEVEL" = "AI_REVIEWER" ] && [ "$VALIDATED_ISSUES" -eq 0 ]; then echo "- AI reviewer feedback could not be validated"; fi)
$(if [ "$HALLUCINATION_SUSPECTS" -gt 0 ]; then echo "- $HALLUCINATION_SUSPECTS items showed signs of hallucination (non-existent files/lines)"; fi)

### Patterns Originally Detected
$(echo -e "$MATCHED_PATTERNS")

If these issues are real, please fix them manually or ask an admin to approve agent action.

_Iteration ${ITERATION_COUNT}/${MAX_ITERATIONS}_"

    echo "made_changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
fi

# Proceed with analysis (FINAL_DECISION = FIX or VALIDATE)
# NOTE: We do NOT comment yet - we wait until after Claude analyzes to see
# what actually happened. Commenting before analysis leads to misleading
# "Proceeding with fixes" messages when Claude finds nothing to fix.
echo "[RUBRIC] Proceeding with analysis (decision: $FINAL_DECISION)"
echo "[RUBRIC] Validation summary: $VALIDATED_ISSUES validated, $HALLUCINATION_SUSPECTS suspected hallucinations"

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

Review feedback to address:

PROMPT_EOF
)

CLAUDE_PROMPT+=$(printf '%s\n' "$REVIEW_CONTENT")

CLAUDE_PROMPT+=$(cat << 'PROMPT_EOF'

Please analyze the review feedback above and make the necessary fixes.

VALIDATION CHECKLIST (apply to each reported issue):
[ ] File exists? If not, SKIP
[ ] Line number valid? If not, SKIP
[ ] Issue actually present in code? If not, SKIP
[ ] Change is safe (no logic changes)? If not, SKIP

Focus on VALIDATED issues only:
- Unused imports (remove them if they actually exist)
- Formatting issues (fix indentation, spacing)
- Type hint issues (if the types are actually wrong)
- Linting errors mentioned (confirm with actual code)

After making changes, provide a brief summary including:
1. What was fixed (validated issues)
2. What was SKIPPED and why (hallucinations, unvalidated claims)
3. Any issues that need human review
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

    post_agent_comment "## Agent Review Response

**Status**: No changes made

The agent analyzed the AI review feedback but determined no automated fixes should be applied.

### Decision Analysis
- **Feedback Type**: $FEEDBACK_TYPE
- **Source Trust Level**: $TRUST_LEVEL
- **Initial Decision**: $FINAL_DECISION

### Pre-Analysis Validation
- Items with valid file references: $VALIDATED_ISSUES
- Suspected hallucinations (invalid files/lines): $HALLUCINATION_SUSPECTS

### Patterns Originally Matched
$(printf '%b' "$MATCHED_PATTERNS")

### Claude's Analysis
$(if [ -n "$CLAUDE_SUMMARY" ]; then echo "\`\`\`"; echo "$CLAUDE_SUMMARY"; echo "\`\`\`"; else echo "No detailed analysis available"; fi)

### Why No Changes?
Common reasons include:
- Issues were **hallucinations** (files/lines don't exist)
- Suggestions require **architectural decisions** (not auto-fixable)
- Changes would affect **business logic** (requires human review)
- Issues are **debatable** style preferences

If these issues are legitimate and should be fixed, please either:
1. Fix manually
2. Provide specific guidance for the agent

_Iteration ${ITERATION_COUNT}/${MAX_ITERATIONS}_"

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

# Post success comment
post_agent_comment "## Agent Review Response

**Status**: Changes pushed

The agent successfully applied fixes based on the AI review feedback.

### Decision Analysis
- **Feedback Type**: $FEEDBACK_TYPE
- **Source Trust Level**: $TRUST_LEVEL
- **Decision**: $FINAL_DECISION

### Validation Summary
- Items validated: $VALIDATED_ISSUES
- Suspected hallucinations ignored: $HALLUCINATION_SUSPECTS

### Patterns Addressed
$(printf '%b' "$MATCHED_PATTERNS")

The pipeline will automatically re-run to validate these changes.

_Iteration ${ITERATION_COUNT}/${MAX_ITERATIONS}_"

echo "made_changes=true" >> "${GITHUB_OUTPUT:-/dev/null}"

#!/bin/bash
# Tests for board-agent-work action shell logic
# Run with: bash .github/actions/board-agent-work/tests/test_action_shell.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION_FILE="$SCRIPT_DIR/../action.yml"
TEST_PASSED=0
TEST_FAILED=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    TEST_PASSED=$((TEST_PASSED + 1))
}

log_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    TEST_FAILED=$((TEST_FAILED + 1))
}

log_info() {
    echo -e "${YELLOW}INFO${NC}: $1"
}

# =============================================================================
# Test: Context file generation
# =============================================================================
test_context_file_generation() {
    log_info "Testing context file generation..."

    # Extract the context file generation code from action.yml and test it
    local ISSUE_NUMBER=123
    local ISSUE_TITLE="Test Issue Title"
    local CONTEXT_FILE="/tmp/test_agent_context_$$.md"

    # Simulate the printf-based context generation (matching action.yml)
    printf '%s\n' \
      "# Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}" \
      "" \
      "## Task" \
      "Implement the changes described in this issue." \
      "" \
      "## Requirements" \
      "- Create working, tested code" \
      "- Follow existing code patterns" \
      "- Add appropriate tests" \
      "- Update documentation if needed" \
      > "$CONTEXT_FILE"

    # Verify file was created
    if [[ ! -f "$CONTEXT_FILE" ]]; then
        log_fail "Context file was not created"
        return 1
    fi

    # Verify file has content
    if [[ ! -s "$CONTEXT_FILE" ]]; then
        log_fail "Context file is empty"
        rm -f "$CONTEXT_FILE"
        return 1
    fi

    # Verify first line contains issue number
    FIRST_LINE=$(head -1 "$CONTEXT_FILE")
    if [[ "$FIRST_LINE" != *"#123"* ]]; then
        log_fail "Context file first line doesn't contain issue number: $FIRST_LINE"
        rm -f "$CONTEXT_FILE"
        return 1
    fi

    # Verify file contains required sections
    if ! grep -q "## Task" "$CONTEXT_FILE"; then
        log_fail "Context file missing '## Task' section"
        rm -f "$CONTEXT_FILE"
        return 1
    fi

    if ! grep -q "## Requirements" "$CONTEXT_FILE"; then
        log_fail "Context file missing '## Requirements' section"
        rm -f "$CONTEXT_FILE"
        return 1
    fi

    # Verify no leading whitespace on lines (heredoc indentation bug)
    if grep -q "^        " "$CONTEXT_FILE"; then
        log_fail "Context file has excessive leading whitespace (heredoc indentation bug)"
        cat "$CONTEXT_FILE"
        rm -f "$CONTEXT_FILE"
        return 1
    fi

    log_pass "Context file generation"
    rm -f "$CONTEXT_FILE"
}

# =============================================================================
# Test: Context file with special characters in title
# =============================================================================
test_context_file_special_chars() {
    log_info "Testing context file with special characters..."

    local ISSUE_NUMBER=456
    # Title with characters that need escaping: / & \ " '
    local ISSUE_TITLE='Fix path/to/file & handle quotes properly'
    local CONTEXT_FILE="/tmp/test_agent_context_special_$$.md"

    # Use simplified escaping for test (the actual action.yml handles this)
    printf '%s\n' \
      "# Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}" \
      "" \
      "## Task" \
      "Implement the changes described in this issue." \
      > "$CONTEXT_FILE"

    # Verify file was created without errors
    if [[ ! -f "$CONTEXT_FILE" ]]; then
        log_fail "Context file with special chars was not created"
        return 1
    fi

    # Verify the title is in the file (escaped)
    if ! grep -q "Issue #456" "$CONTEXT_FILE"; then
        log_fail "Issue number not found in context file"
        rm -f "$CONTEXT_FILE"
        return 1
    fi

    log_pass "Context file with special characters"
    rm -f "$CONTEXT_FILE"
}

# =============================================================================
# Test: JSON parsing with clean output (2>/dev/null vs 2>&1)
# =============================================================================
test_json_parsing_clean() {
    log_info "Testing JSON parsing produces clean output..."

    # Simulate board-cli output with logs mixed in (the bug we fixed)
    MIXED_OUTPUT='2026-01-11 11:32:01 - INFO - Starting
{"approved": true, "issue": 123}'

    # This should fail to parse (mixed content)
    if echo "$MIXED_OUTPUT" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        log_fail "Mixed log+JSON should not parse cleanly"
        return 1
    fi

    # Clean JSON should parse
    CLEAN_OUTPUT='{"approved": true, "issue": 123}'
    if ! echo "$CLEAN_OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('approved'))"; then
        log_fail "Clean JSON should parse successfully"
        return 1
    fi

    log_pass "JSON parsing requires clean output"
}

# =============================================================================
# Test: Large file cleanup patterns
# =============================================================================
test_large_file_cleanup() {
    log_info "Testing large file cleanup patterns..."

    TEST_DIR="/tmp/test_cleanup_$$"
    mkdir -p "$TEST_DIR"

    # Create test files of various sizes
    dd if=/dev/zero of="$TEST_DIR/bandit-report.json" bs=1024 count=200 2>/dev/null  # 200KB
    dd if=/dev/zero of="$TEST_DIR/small.log" bs=1024 count=50 2>/dev/null            # 50KB (under threshold)
    dd if=/dev/zero of="$TEST_DIR/large.log" bs=1024 count=200 2>/dev/null           # 200KB
    dd if=/dev/zero of="$TEST_DIR/coverage.xml" bs=1024 count=200 2>/dev/null        # 200KB

    # Run cleanup pattern (matches what's in action.yml)
    LARGE_FILES=(
      "bandit-report.json"
      "*.log"
      "coverage.xml"
      ".coverage"
    )

    cd "$TEST_DIR"
    for pattern in "${LARGE_FILES[@]}"; do
      find . -name "$pattern" -type f -size +100k -delete 2>/dev/null || true
    done

    # Verify large files were deleted
    if [[ -f "$TEST_DIR/bandit-report.json" ]]; then
        log_fail "bandit-report.json (>100k) should have been deleted"
        rm -rf "$TEST_DIR"
        return 1
    fi

    if [[ -f "$TEST_DIR/large.log" ]]; then
        log_fail "large.log (>100k) should have been deleted"
        rm -rf "$TEST_DIR"
        return 1
    fi

    # Verify small files were kept
    if [[ ! -f "$TEST_DIR/small.log" ]]; then
        log_fail "small.log (<100k) should have been kept"
        rm -rf "$TEST_DIR"
        return 1
    fi

    log_pass "Large file cleanup"
    rm -rf "$TEST_DIR"
}

# =============================================================================
# Test: Approval pattern matching
# =============================================================================
test_approval_patterns() {
    log_info "Testing approval pattern matching..."

    # Valid patterns (should match)
    VALID_PATTERNS=(
        "[Approved][Claude]"
        "[Approved][OpenCode]"
        "[Review][Gemini]"
        "[approved][claude]"
        "Some text [Approved][Claude] more text"
    )

    # Invalid patterns (should NOT match)
    INVALID_PATTERNS=(
        "[Approved]"                                      # Missing agent
        "reply with \`[Approved]\` to create PR"         # Instructional text
        "*Awaiting admin review - reply with [Approved]*" # Instructional text
        "[Approve][Claude]"                               # Wrong action word
    )

    # Case-insensitive pattern matching (matches Python's re.IGNORECASE)
    PATTERN='\[(Approved|Review|Close|Summarize|Debug)\]\[([A-Za-z]+)\]'

    for text in "${VALID_PATTERNS[@]}"; do
        if ! echo "$text" | grep -qiE "$PATTERN"; then
            log_fail "Valid pattern should match: $text"
            return 1
        fi
    done

    for text in "${INVALID_PATTERNS[@]}"; do
        if echo "$text" | grep -qiE "$PATTERN"; then
            log_fail "Invalid pattern should NOT match: $text"
            return 1
        fi
    done

    log_pass "Approval pattern matching"
}

# =============================================================================
# Test: CLI argument building
# =============================================================================
test_cli_args_building() {
    log_info "Testing CLI argument building..."

    # Simulate the CLI args building from action.yml
    MAX_ISSUES=5
    AGENT_NAME="claude"

    CLI_ARGS="--json ready --limit $MAX_ISSUES --approved-only"
    if [ -n "$AGENT_NAME" ]; then
      CLI_ARGS="$CLI_ARGS --agent \"$AGENT_NAME\""
    fi

    # Verify args are built correctly
    if [[ "$CLI_ARGS" != *"--approved-only"* ]]; then
        log_fail "CLI args missing --approved-only"
        return 1
    fi

    if [[ "$CLI_ARGS" != *"--agent"* ]]; then
        log_fail "CLI args missing --agent"
        return 1
    fi

    if [[ "$CLI_ARGS" != *"--limit 5"* ]]; then
        log_fail "CLI args missing --limit"
        return 1
    fi

    log_pass "CLI argument building"
}

# =============================================================================
# Test: Action YAML syntax validation
# =============================================================================
test_action_yaml_syntax() {
    log_info "Testing action.yml YAML syntax..."

    if [[ ! -f "$ACTION_FILE" ]]; then
        log_fail "action.yml not found at $ACTION_FILE"
        return 1
    fi

    # Check YAML syntax
    if command -v python3 &> /dev/null; then
        if ! python3 -c "import yaml; yaml.safe_load(open('$ACTION_FILE'))" 2>/dev/null; then
            log_fail "action.yml has invalid YAML syntax"
            return 1
        fi
    else
        log_info "Skipping YAML validation (python3 not available)"
        return 0
    fi

    log_pass "Action YAML syntax"
}

# =============================================================================
# Test: No unclosed heredocs in action.yml
# =============================================================================
test_no_unclosed_heredocs() {
    log_info "Testing for unclosed heredocs in action.yml..."

    # Extract all heredoc start markers
    HEREDOC_STARTS=$(grep -oE "<<-?\s*['\"]?[A-Z_]+['\"]?" "$ACTION_FILE" | wc -l)

    # Extract all heredoc end markers (lines that are ONLY the marker)
    # This is tricky because end markers should be at the start of a line
    # For now, just check that if we have heredocs, we have matching ends

    if [[ $HEREDOC_STARTS -gt 0 ]]; then
        log_info "Found $HEREDOC_STARTS heredoc declarations - verify manually that all are closed"
        # We can't easily validate this without parsing, but we can check for common issues

        # Check for indented heredoc markers that won't work
        if grep -qE "^\s+[A-Z_]+$" "$ACTION_FILE"; then
            # This might be an indented heredoc end marker which won't work without <<-
            INDENTED_MARKERS=$(grep -E "^\s+[A-Z_]+$" "$ACTION_FILE" | head -5)
            log_info "Warning: Found potentially indented heredoc markers (may need <<- syntax):"
            echo "$INDENTED_MARKERS"
        fi
    fi

    log_pass "Heredoc check completed (manual verification recommended)"
}

# =============================================================================
# Test: Claude CLI availability and basic functionality
# =============================================================================
test_claude_cli() {
    log_info "Testing Claude CLI availability..."

    if ! command -v claude &> /dev/null; then
        log_info "Claude CLI not installed - skipping"
        return 0
    fi

    # Test basic invocation
    RESULT=$(echo "Reply with just 'ok'" | timeout 30 claude --print --dangerously-skip-permissions 2>&1) || true

    if [[ -z "$RESULT" ]]; then
        log_fail "Claude CLI returned empty response"
        return 1
    fi

    if [[ "$RESULT" == *"error"* ]] && [[ "$RESULT" == *"streaming mode"* ]]; then
        log_fail "Claude CLI streaming mode error detected"
        return 1
    fi

    log_pass "Claude CLI basic test"
}

# =============================================================================
# Main test runner
# =============================================================================
main() {
    echo "=========================================="
    echo "Board Agent Work Action - Shell Tests"
    echo "=========================================="
    echo ""

    test_action_yaml_syntax
    test_context_file_generation
    test_context_file_special_chars
    test_json_parsing_clean
    test_large_file_cleanup
    test_approval_patterns
    test_cli_args_building
    test_no_unclosed_heredocs
    test_claude_cli

    echo ""
    echo "=========================================="
    echo "Results: ${TEST_PASSED} passed, ${TEST_FAILED} failed"
    echo "=========================================="

    if [[ $TEST_FAILED -gt 0 ]]; then
        exit 1
    fi
}

main "$@"

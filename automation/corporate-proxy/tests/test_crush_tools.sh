#!/bin/bash
# Comprehensive test suite for Crush CLI tool calls
set -e

echo "========================================"
echo "CRUSH COMPREHENSIVE TOOL TEST SUITE"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_file="$3"
    local expected_content="$4"

    echo -e "\n${YELLOW}Test: $test_name${NC}"
    echo "Command: $test_command"

    # Create test directory
    TEST_DIR=$(mktemp -d /tmp/crush-test-XXXXXX)
    LOG_DIR="$TEST_DIR/logs"
    mkdir -p "$LOG_DIR"

    # Run the command
    if docker run --rm \
        --user "$(id -u):$(id -g)" \
        -v "$TEST_DIR:/workspace" \
        -v "$LOG_DIR:/tmp/logs" \
        -e HOME=/tmp \
        -e OPENROUTER_API_KEY="test-secret-token-123" \
        -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
        crush-corporate:latest bash -c "cd /workspace && /usr/local/bin/crush.bin run '$test_command'" 2>&1 | tee "$LOG_DIR/output.log" > /dev/null; then

        # Check if expected file exists
        if [ -n "$expected_file" ]; then
            if [ -f "$TEST_DIR/$expected_file" ]; then
                if [ -n "$expected_content" ]; then
                    # Check content if specified
                    actual_content=$(cat "$TEST_DIR/$expected_file")
                    if [[ "$actual_content" == *"$expected_content"* ]]; then
                        echo -e "${GREEN}✅ PASSED${NC}: File created with expected content"
                        TESTS_PASSED=$((TESTS_PASSED + 1))
                    else
                        echo -e "${RED}❌ FAILED${NC}: File created but content doesn't match"
                        echo "Expected: $expected_content"
                        echo "Got: $actual_content"
                        TESTS_FAILED=$((TESTS_FAILED + 1))
                    fi
                else
                    echo -e "${GREEN}✅ PASSED${NC}: File created"
                    TESTS_PASSED=$((TESTS_PASSED + 1))
                fi
            else
                echo -e "${RED}❌ FAILED${NC}: Expected file not created"
                echo "Directory contents:"
                ls -la "$TEST_DIR/"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
        else
            # No file expected, just check command executed
            if grep -q "Error\|Failed\|Invalid" "$LOG_DIR/output.log"; then
                echo -e "${RED}❌ FAILED${NC}: Command execution failed"
                tail -10 "$LOG_DIR/output.log"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            else
                echo -e "${GREEN}✅ PASSED${NC}: Command executed"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            fi
        fi
    else
        echo -e "${RED}❌ FAILED${NC}: Docker command failed"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Cleanup
    rm -rf "$TEST_DIR"
}

# Services should already be running in the container
echo "Note: Services are started automatically inside the container"

echo -e "\n${YELLOW}Running Crush Tool Tests...${NC}"

# Test 1: Write command with single quotes
run_test "Write with single quotes" \
    "write 'hello.txt' with 'Hello from Crush'" \
    "hello.txt" \
    "Hello from Crush"

# Test 2: Write command with double quotes
run_test "Write with double quotes" \
    'write "test.md" with "# Test Markdown"' \
    "test.md" \
    "# Test Markdown"

# Test 3: Write command without quotes
run_test "Write without quotes" \
    "write config.json with {}" \
    "config.json" \
    "{}"

# Test 4: Create file alternative syntax
run_test "Create file syntax" \
    "create a file named data.txt with sample data" \
    "data.txt" \
    "sample data"

# Test 5: View/Read command (creates README first)
echo -e "\n${YELLOW}Preparing for view test...${NC}"
TEST_DIR=$(mktemp -d /tmp/crush-view-XXXXXX)
echo "This is a README file" > "$TEST_DIR/README.md"
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    crush-corporate:latest bash -c "cd /workspace && /usr/local/bin/crush.bin run 'view README.md'" 2>&1 | grep -q "README" && {
    echo -e "${GREEN}✅ PASSED${NC}: View command works"
    TESTS_PASSED=$((TESTS_PASSED + 1))
} || {
    echo -e "${RED}❌ FAILED${NC}: View command failed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}
rm -rf "$TEST_DIR"

# Test 6: Run/Execute command
run_test "Run ls command" \
    "run 'ls -la'" \
    "" \
    ""

# Test 7: Multiple word content
run_test "Write with multiple words" \
    "write story.txt with Once upon a time in a galaxy far away" \
    "story.txt" \
    "Once upon a time"

# Test 8: Special characters in filename
run_test "Special characters in filename" \
    "write my-file_v2.txt with version 2 content" \
    "my-file_v2.txt" \
    "version 2"

# Test 9: Nested directory creation (might fail, testing behavior)
run_test "Nested directory file" \
    "write docs/readme.md with documentation" \
    "docs/readme.md" \
    "documentation"

# Test 10: JSON content
run_test "JSON content" \
    'write package.json with {"name":"test","version":"1.0.0"}' \
    "package.json" \
    '"name":"test"'

# Summary
echo -e "\n========================================"
echo -e "TEST SUMMARY"
echo -e "========================================"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo -e "Total: $((TESTS_PASSED + TESTS_FAILED))"

# Cleanup services
pkill -f "mock_api" || true
pkill -f "translation_wrapper" || true

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}Some tests failed!${NC}"
    exit 1
fi

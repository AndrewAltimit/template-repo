#!/bin/bash
# Comprehensive test suite for OpenCode CLI tool calls
set -e

echo "========================================"
echo "OPENCODE COMPREHENSIVE TOOL TEST SUITE"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
    local check_type="${5:-file}"  # file, output, or none

    echo -e "\n${YELLOW}Test: $test_name${NC}"
    echo "Command: $test_command"

    # Create test directory
    TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
    LOG_DIR="$TEST_DIR/logs"
    mkdir -p "$LOG_DIR"

    # For read/edit tests, create initial files
    if [[ "$test_name" == *"Read"* ]] || [[ "$test_name" == *"Edit"* ]]; then
        echo "Initial content for testing" > "$TEST_DIR/test.txt"
        echo "# README" > "$TEST_DIR/README.md"
        mkdir -p "$TEST_DIR/src"
        echo "function test() { return 42; }" > "$TEST_DIR/src/index.js"
    fi

    # Run the command
    OUTPUT=$(docker run --rm \
        --user "$(id -u):$(id -g)" \
        -v "$TEST_DIR:/workspace" \
        -v "$LOG_DIR:/tmp/logs" \
        -e HOME=/tmp \
        -e OPENROUTER_API_KEY="test-secret-token-123" \
        -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
        opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run '$test_command'" 2>&1 | tee "$LOG_DIR/output.log")

    # Check results based on type
    case "$check_type" in
        "file")
            if [ -f "$TEST_DIR/$expected_file" ]; then
                if [ -n "$expected_content" ]; then
                    actual_content=$(cat "$TEST_DIR/$expected_file")
                    if [[ "$actual_content" == *"$expected_content"* ]]; then
                        echo -e "${GREEN}✅ PASSED${NC}: File created/modified with expected content"
                        TESTS_PASSED=$((TESTS_PASSED + 1))
                    else
                        echo -e "${RED}❌ FAILED${NC}: Content doesn't match"
                        echo "Expected to contain: $expected_content"
                        echo "Got: $actual_content"
                        TESTS_FAILED=$((TESTS_FAILED + 1))
                    fi
                else
                    echo -e "${GREEN}✅ PASSED${NC}: File created/modified"
                    TESTS_PASSED=$((TESTS_PASSED + 1))
                fi
            else
                echo -e "${RED}❌ FAILED${NC}: Expected file not found"
                ls -la "$TEST_DIR/"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
            ;;
        "output")
            if [[ "$OUTPUT" == *"$expected_content"* ]]; then
                echo -e "${GREEN}✅ PASSED${NC}: Output contains expected text"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            else
                echo -e "${RED}❌ FAILED${NC}: Output doesn't contain expected text"
                echo "Expected: $expected_content"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
            ;;
        "none"|*)
            if [[ "$OUTPUT" == *"Invalid Tool"* ]] || [[ "$OUTPUT" == *"Error"* ]]; then
                echo -e "${RED}❌ FAILED${NC}: Command failed with error"
                echo "$OUTPUT" | grep -i "invalid\|error" | head -3
                TESTS_FAILED=$((TESTS_FAILED + 1))
            else
                echo -e "${GREEN}✅ PASSED${NC}: Command executed"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            fi
            ;;
    esac

    # Cleanup
    rm -rf "$TEST_DIR"
}

# Start services with fixed mock API
echo "Starting mock services with OpenCode-specific API..."
pkill -f "mock_api" || true
pkill -f "translation_wrapper" || true
sleep 1

# Start the fixed services
./opencode/scripts/start-services-fixed.sh > /dev/null 2>&1 &
sleep 3

echo -e "\n${BLUE}=== WRITE TOOL TESTS ===${NC}"

# Test 1: Basic Write
run_test "Write - Basic syntax" \
    "Write a file called test.txt with Hello OpenCode" \
    "test.txt" \
    "Hello OpenCode"

# Test 2: Write with quotes
run_test "Write - With quotes" \
    'Write a file named "config.json" with content "{}"' \
    "config.json" \
    "{}"

# Test 3: Create file (alternative syntax)
run_test "Write - Create syntax" \
    "Create a new file data.csv with header,value" \
    "data.csv" \
    "header,value"

# Test 4: Write markdown
run_test "Write - Markdown file" \
    "Write README.md with # Project Title" \
    "README.md" \
    "# Project Title"

# Test 5: Write with path
run_test "Write - With extension" \
    "Write script.sh with #!/bin/bash" \
    "script.sh" \
    "#!/bin/bash"

echo -e "\n${BLUE}=== READ TOOL TESTS ===${NC}"

# Test 6: Read file
run_test "Read - Basic file" \
    "Read test.txt" \
    "" \
    "Initial content" \
    "output"

# Test 7: View file (alternative)
run_test "Read - View syntax" \
    "View README.md" \
    "" \
    "README" \
    "output"

# Test 8: Show file content
run_test "Read - Show syntax" \
    "Show the contents of test.txt" \
    "" \
    "Initial content" \
    "output"

echo -e "\n${BLUE}=== BASH TOOL TESTS ===${NC}"

# Test 9: Basic bash command
run_test "Bash - List files" \
    "Run ls -la" \
    "" \
    "" \
    "none"

# Test 10: Bash with echo
run_test "Bash - Echo command" \
    "Execute echo Hello World" \
    "" \
    "" \
    "none"

# Test 11: Create directory
run_test "Bash - Make directory" \
    "Run mkdir testdir" \
    "testdir" \
    "" \
    "file"

echo -e "\n${BLUE}=== EDIT TOOL TESTS ===${NC}"

# Test 12: Edit file
run_test "Edit - Modify content" \
    "Edit test.txt and change Initial to Modified" \
    "test.txt" \
    "Modified content" \
    "file"

# Test 13: Update file
run_test "Edit - Update syntax" \
    "Update README.md by adding a description" \
    "README.md" \
    "" \
    "file"

echo -e "\n${BLUE}=== GREP TOOL TESTS ===${NC}"

# Test 14: Search in files
run_test "Grep - Search pattern" \
    "Search for function in all js files" \
    "" \
    "" \
    "none"

# Test 15: Find in files
run_test "Grep - Find syntax" \
    "Find TODO in all files" \
    "" \
    "" \
    "none"

echo -e "\n${BLUE}=== LIST TOOL TESTS ===${NC}"

# Test 16: List directory
run_test "List - Current directory" \
    "List files in current directory" \
    "" \
    "" \
    "none"

# Test 17: List with path
run_test "List - Specific path" \
    "List the contents of /workspace" \
    "" \
    "" \
    "none"

echo -e "\n${BLUE}=== COMPLEX SCENARIOS ===${NC}"

# Test 18: Multiple operations
run_test "Complex - Write and verify" \
    "Write app.js with console.log('Hello') and then show me the file" \
    "app.js" \
    "console.log" \
    "file"

# Test 19: Code file creation
run_test "Complex - Python script" \
    "Create a Python file main.py with def main(): print('test')" \
    "main.py" \
    "def main" \
    "file"

# Test 20: JSON configuration
run_test "Complex - Package.json" \
    'Write package.json with {"name":"test-app","version":"1.0.0","main":"index.js"}' \
    "package.json" \
    '"name":"test-app"' \
    "file"

# Summary
echo -e "\n========================================"
echo -e "TEST SUMMARY"
echo -e "========================================"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo -e "Total: $((TESTS_PASSED + TESTS_FAILED))"

# Cleanup services
echo -e "\nCleaning up services..."
pkill -f "mock_api" || true
pkill -f "translation_wrapper" || true

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All OpenCode tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}⚠️  Some OpenCode tests failed!${NC}"
    exit 1
fi

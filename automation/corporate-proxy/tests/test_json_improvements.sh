#!/bin/bash
# Test JSON handling improvements

set -e

echo "========================================"
echo "TESTING ENHANCED JSON HANDLING"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Change to project root
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Ensure v2 API is running
echo -e "\n${BLUE}=== Starting Enhanced API ===${NC}"
pkill -f structured_tool_api || true
python3 shared/services/structured_tool_api_v2.py > /tmp/api_v2.log 2>&1 &
API_PID=$!
sleep 2

# Function to test tool detection
test_tool_detection() {
    local test_name="$1"
    local message="$2"
    local expected_tool="$3"
    local expected_in_args="$4"

    echo -e "\n${BLUE}Test: ${test_name}${NC}"
    echo "Message: $message"

    RESPONSE=$(curl -s -X POST http://localhost:8054/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{\"messages\": [{\"role\": \"user\", \"content\": \"$message\"}], \"tools\": [{\"type\": \"function\", \"function\": {\"name\": \"$expected_tool\"}}]}")

    if echo "$RESPONSE" | grep -q "\"name\":\"$expected_tool\"" && echo "$RESPONSE" | grep -q "$expected_in_args"; then
        echo -e "${GREEN}✅ PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "Response: $RESPONSE" | head -2
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo -e "\n${BLUE}=== Testing Write Tool with JSON ===${NC}"

# Test 1: Simple JSON
test_tool_detection \
    "Simple JSON object" \
    "Write config.json with {\\\"debug\\\":true}" \
    "write" \
    "config.json"

# Test 2: Complex nested JSON
test_tool_detection \
    "Nested JSON" \
    "Write package.json with {\\\"name\\\":\\\"test\\\",\\\"version\\\":\\\"1.0.0\\\",\\\"scripts\\\":{\\\"test\\\":\\\"jest\\\"}}" \
    "write" \
    "package.json"

# Test 3: JSON with special characters
test_tool_detection \
    "JSON with special chars" \
    "Write data.json with {\\\"message\\\":\\\"Hello, World!\\\",\\\"path\\\":\\\"/usr/bin\\\"}" \
    "write" \
    "data.json"

# Test 4: Array JSON
test_tool_detection \
    "JSON array" \
    "Write list.json with [\\\"item1\\\",\\\"item2\\\",\\\"item3\\\"]" \
    "write" \
    "list.json"

# Test 5: Mixed content
test_tool_detection \
    "Mixed JSON and text" \
    "Write readme.txt with This is text before JSON: {\\\"key\\\":\\\"value\\\"} and after" \
    "write" \
    "readme.txt"

echo -e "\n${BLUE}=== Testing Other Tools ===${NC}"

# Test 6: Read with path
test_tool_detection \
    "Read command" \
    "Read /etc/passwd" \
    "read" \
    "/etc/passwd"

# Test 7: Bash with complex command
test_tool_detection \
    "Complex bash" \
    "Run ls -la | grep json" \
    "bash" \
    "ls -la | grep json"

# Test 8: List directory
test_tool_detection \
    "List command" \
    "List /tmp" \
    "list" \
    "/tmp"

echo -e "\n${BLUE}=== Testing Edge Cases ===${NC}"

# Test 9: File path with spaces
test_tool_detection \
    "Path with spaces" \
    "Write my file.txt with content here" \
    "write" \
    "my file.txt"

# Test 10: Very long JSON
LONG_JSON="{\\\"a\\\":1,\\\"b\\\":2,\\\"c\\\":3,\\\"d\\\":4,\\\"e\\\":5,\\\"f\\\":6,\\\"g\\\":7,\\\"h\\\":8}"
test_tool_detection \
    "Long JSON" \
    "Write big.json with $LONG_JSON" \
    "write" \
    "big.json"

# Cleanup
kill $API_PID 2>/dev/null || true

# Summary
echo -e "\n========================================"
echo -e "${BLUE}JSON HANDLING TEST SUMMARY${NC}"
echo -e "========================================"
echo ""
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL))
    echo -e "Success Rate: ${YELLOW}${SUCCESS_RATE}%${NC}"

    if [ $SUCCESS_RATE -ge 90 ]; then
        echo -e "\n${GREEN}🎉 Excellent! JSON handling greatly improved!${NC}"
    elif [ $SUCCESS_RATE -ge 75 ]; then
        echo -e "\n${YELLOW}⚠️ Good progress, some edge cases remain${NC}"
    else
        echo -e "\n${RED}❌ JSON handling needs more work${NC}"
    fi
fi

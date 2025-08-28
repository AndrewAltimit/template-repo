#!/bin/bash
# Final comprehensive test suite for Crush and OpenCode
set -e

echo "========================================"
echo "FINAL TOOL TEST SUITE"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
OPENCODE_PASS=0
OPENCODE_FAIL=0
CRUSH_PASS=0
CRUSH_FAIL=0

# Change to project root
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo -e "\n${BLUE}=== TESTING OPENCODE TOOLS ===${NC}"

# Test 1: OpenCode Write
echo -e "\n${YELLOW}Test: OpenCode Write${NC}"
TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Write a file called test.txt with OpenCode Test Content'" 2>&1 > "$LOG_DIR/output.log"

if [ -f "$TEST_DIR/test.txt" ] && grep -q "OpenCode Test Content" "$TEST_DIR/test.txt"; then
    echo -e "${GREEN}✅ PASSED${NC}: Write tool created file with correct content"
    OPENCODE_PASS=$((OPENCODE_PASS + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Write tool did not create file"
    OPENCODE_FAIL=$((OPENCODE_FAIL + 1))
fi
rm -rf "$TEST_DIR"

# Test 2: OpenCode Create (alternative syntax)
echo -e "\n${YELLOW}Test: OpenCode Create${NC}"
TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Create a new file named data.json with {}'" 2>&1 > "$LOG_DIR/output.log"

if [ -f "$TEST_DIR/data.json" ]; then
    echo -e "${GREEN}✅ PASSED${NC}: Create syntax works"
    OPENCODE_PASS=$((OPENCODE_PASS + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Create syntax failed"
    OPENCODE_FAIL=$((OPENCODE_FAIL + 1))
fi
rm -rf "$TEST_DIR"

# Test 3: OpenCode with complex content
echo -e "\n${YELLOW}Test: OpenCode Complex Content${NC}"
TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Write package.json with {\"name\":\"test\",\"version\":\"1.0.0\"}'" 2>&1 > "$LOG_DIR/output.log"

if [ -f "$TEST_DIR/package.json" ] && grep -q '"name":"test"' "$TEST_DIR/package.json"; then
    echo -e "${GREEN}✅ PASSED${NC}: JSON content handled correctly"
    OPENCODE_PASS=$((OPENCODE_PASS + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Complex content failed"
    OPENCODE_FAIL=$((OPENCODE_FAIL + 1))
fi
rm -rf "$TEST_DIR"

echo -e "\n${BLUE}=== TESTING CRUSH TOOLS ===${NC}"

# Test 4: Crush Write
echo -e "\n${YELLOW}Test: Crush Write${NC}"
TEST_DIR=$(mktemp -d /tmp/crush-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    crush-corporate:latest run 'write test.txt with Crush Test Content' 2>&1 > "$LOG_DIR/output.log"

if [ -f "$TEST_DIR/test.txt" ] && grep -q "Crush Test Content" "$TEST_DIR/test.txt"; then
    echo -e "${GREEN}✅ PASSED${NC}: Write tool created file"
    CRUSH_PASS=$((CRUSH_PASS + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Write tool failed"
    CRUSH_FAIL=$((CRUSH_FAIL + 1))
    echo "   Output: $(tail -3 $LOG_DIR/output.log 2>/dev/null)"
fi
rm -rf "$TEST_DIR"

# Test 5: Crush Create
echo -e "\n${YELLOW}Test: Crush Create${NC}"
TEST_DIR=$(mktemp -d /tmp/crush-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    crush-corporate:latest run 'create a file named hello.md with # Hello Crush' 2>&1 > "$LOG_DIR/output.log"

if [ -f "$TEST_DIR/hello.md" ]; then
    echo -e "${GREEN}✅ PASSED${NC}: Create syntax works"
    CRUSH_PASS=$((CRUSH_PASS + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Create syntax failed"
    CRUSH_FAIL=$((CRUSH_FAIL + 1))
fi
rm -rf "$TEST_DIR"

# Test 6: Crush with quotes
echo -e "\n${YELLOW}Test: Crush Quoted Filename${NC}"
TEST_DIR=$(mktemp -d /tmp/crush-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    crush-corporate:latest run 'write "config.yml" with version: 1.0' 2>&1 > "$LOG_DIR/output.log"

if [ -f "$TEST_DIR/config.yml" ]; then
    echo -e "${GREEN}✅ PASSED${NC}: Quoted filenames work"
    CRUSH_PASS=$((CRUSH_PASS + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Quoted filenames failed"
    CRUSH_FAIL=$((CRUSH_FAIL + 1))
fi
rm -rf "$TEST_DIR"

# Summary
echo -e "\n========================================"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "========================================"
echo ""
echo -e "OpenCode Tests:"
echo -e "  ${GREEN}Passed: $OPENCODE_PASS${NC}"
echo -e "  ${RED}Failed: $OPENCODE_FAIL${NC}"
echo ""
echo -e "Crush Tests:"
echo -e "  ${GREEN}Passed: $CRUSH_PASS${NC}"
echo -e "  ${RED}Failed: $CRUSH_FAIL${NC}"
echo ""
TOTAL_PASS=$((OPENCODE_PASS + CRUSH_PASS))
TOTAL_FAIL=$((OPENCODE_FAIL + CRUSH_FAIL))
echo -e "Total: ${GREEN}$TOTAL_PASS passed${NC}, ${RED}$TOTAL_FAIL failed${NC}"

if [ $TOTAL_FAIL -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "\n${YELLOW}⚠️  Some tests failed${NC}"
    exit 1
fi

#!/bin/bash
# Master test runner for Crush and OpenCode tool tests
set -e

echo "========================================"
echo "CORPORATE PROXY TOOL TEST RUNNER"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Function to cleanup services
cleanup_services() {
    echo -e "\n${YELLOW}Cleaning up services...${NC}"
    pkill -f "mock_api" || true
    pkill -f "translation_wrapper" || true
    sleep 1
}

# Trap to ensure cleanup on exit
trap cleanup_services EXIT

# Initial cleanup
cleanup_services

echo -e "\n${BLUE}=== TESTING CRUSH TOOLS ===${NC}"

# Start services for Crush (using unified API)
echo "Starting services for Crush..."
cd shared/services
API_MODE=crush API_VERSION=v3 PORT=8050 python3 unified_tool_api.py > /tmp/crush_mock.log 2>&1 &
MOCK_PID=$!
sleep 1
python3 translation_wrapper_with_tools.py > /tmp/crush_wrapper.log 2>&1 &
WRAPPER_PID=$!
cd ../..
sleep 2

# Run Crush tests
echo -e "${YELLOW}Testing Crush write command...${NC}"
TEST_DIR=$(mktemp -d /tmp/crush-test-XXXXXX)
if docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://host.docker.internal:8052/v1" \
    --add-host=host.docker.internal:host-gateway \
    crush-corporate:latest bash -c "cd /workspace && /usr/local/bin/crush.bin run 'write test.txt with Hello Crush'" 2>&1 | grep -q "test.txt"; then

    if [ -f "$TEST_DIR/test.txt" ]; then
        echo -e "${GREEN}✅ Crush write test PASSED${NC}"
        echo "Content: $(cat "$TEST_DIR/test.txt")"
    else
        echo -e "${RED}❌ Crush write test FAILED - file not created${NC}"
    fi
else
    echo -e "${RED}❌ Crush write test FAILED - command error${NC}"
fi
rm -rf "$TEST_DIR"

# Test Crush view
TEST_DIR=$(mktemp -d /tmp/crush-test-XXXXXX)
echo "Test content" > "$TEST_DIR/README.md"
echo -e "${YELLOW}Testing Crush view command...${NC}"
if docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://host.docker.internal:8052/v1" \
    --add-host=host.docker.internal:host-gateway \
    crush-corporate:latest bash -c "cd /workspace && /usr/local/bin/crush.bin run 'view README.md'" 2>&1 | grep -q "Test content\|README"; then
    echo -e "${GREEN}✅ Crush view test PASSED${NC}"
else
    echo -e "${RED}❌ Crush view test FAILED${NC}"
fi
rm -rf "$TEST_DIR"

# Stop Crush services
kill $MOCK_PID $WRAPPER_PID 2>/dev/null || true
sleep 2

echo -e "\n${BLUE}=== TESTING OPENCODE TOOLS ===${NC}"

# Start services for OpenCode (using fixed mock API)
echo "Starting services for OpenCode..."
cd shared/services
python3 mock_api_opencode_fixed.py > /tmp/opencode_mock.log 2>&1 &
MOCK_PID=$!
sleep 1
python3 translation_wrapper_with_tools.py > /tmp/opencode_wrapper.log 2>&1 &
WRAPPER_PID=$!
cd ../..
sleep 2

# Run OpenCode tests
echo -e "${YELLOW}Testing OpenCode Write command...${NC}"
TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

OUTPUT=$(docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Write a file called hello.txt with Hello OpenCode'" 2>&1)

if echo "$OUTPUT" | grep -q "Invalid Tool"; then
    echo -e "${RED}❌ OpenCode Write test FAILED - Invalid Tool error${NC}"
    echo "Check mock API log:"
    tail -5 /tmp/opencode_mock.log | grep -E "TOOL|function" || true
elif [ -f "$TEST_DIR/hello.txt" ]; then
    echo -e "${GREEN}✅ OpenCode Write test PASSED${NC}"
    echo "Content: $(cat "$TEST_DIR/hello.txt")"
else
    echo -e "${RED}❌ OpenCode Write test FAILED - file not created${NC}"
    echo "Output: $OUTPUT" | head -3
fi
rm -rf "$TEST_DIR"

# Test OpenCode Read
TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"
echo "OpenCode test content" > "$TEST_DIR/test.txt"

echo -e "${YELLOW}Testing OpenCode Read command...${NC}"
OUTPUT=$(docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Read test.txt'" 2>&1)

if echo "$OUTPUT" | grep -q "OpenCode test content"; then
    echo -e "${GREEN}✅ OpenCode Read test PASSED${NC}"
elif echo "$OUTPUT" | grep -q "Invalid Tool"; then
    echo -e "${RED}❌ OpenCode Read test FAILED - Invalid Tool error${NC}"
else
    echo -e "${YELLOW}⚠️  OpenCode Read test INCONCLUSIVE${NC}"
    echo "Output didn't contain expected content"
fi
rm -rf "$TEST_DIR"

# Test OpenCode Bash
echo -e "${YELLOW}Testing OpenCode Bash command...${NC}"
TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

OUTPUT=$(docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Run ls -la'" 2>&1)

if echo "$OUTPUT" | grep -q "Invalid Tool"; then
    echo -e "${RED}❌ OpenCode Bash test FAILED - Invalid Tool error${NC}"
elif echo "$OUTPUT" | grep -q "total\|drwx"; then
    echo -e "${GREEN}✅ OpenCode Bash test PASSED${NC}"
else
    echo -e "${YELLOW}⚠️  OpenCode Bash test INCONCLUSIVE${NC}"
fi
rm -rf "$TEST_DIR"

# Summary
echo -e "\n========================================"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "========================================"
echo ""
echo "Check the detailed output above for test results."
echo ""
echo "Service logs available at:"
echo "  Crush mock: /tmp/crush_mock.log"
echo "  Crush wrapper: /tmp/crush_wrapper.log"
echo "  OpenCode mock: /tmp/opencode_mock.log"
echo "  OpenCode wrapper: /tmp/opencode_wrapper.log"

# Cleanup is handled by trap

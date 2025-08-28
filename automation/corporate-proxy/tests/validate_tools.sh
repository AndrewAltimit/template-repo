#!/bin/bash
# Quick validation test for both Crush and OpenCode tools
set -e

echo "========================================"
echo "TOOL VALIDATION TEST"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Change to project root
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Cleanup function
cleanup() {
    pkill -f "mock_api" || true
    pkill -f "translation_wrapper" || true
}
trap cleanup EXIT

echo -e "\n${YELLOW}=== VALIDATING OPENCODE ===${NC}"

# Start OpenCode services
cleanup
cd shared/services
python3 mock_api_opencode_fixed.py > /tmp/opencode_mock.log 2>&1 &
sleep 1
python3 translation_wrapper_with_tools.py > /tmp/opencode_wrapper.log 2>&1 &
sleep 2
cd ../..

# Test OpenCode Write
echo "Testing OpenCode Write..."
TEST_DIR=$(mktemp -d /tmp/opencode-validate-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && timeout 10 /usr/local/bin/opencode.bin run 'Write test.txt with validation test'" 2>&1 | tee "$LOG_DIR/output.log" > /dev/null

if [ -f "$TEST_DIR/test.txt" ]; then
    echo -e "${GREEN}✅ OpenCode Write: WORKING${NC}"
    echo "   Content: $(cat "$TEST_DIR/test.txt")"
else
    echo -e "${RED}❌ OpenCode Write: NOT WORKING${NC}"
    echo "   Check log: tail /tmp/opencode_mock.log"
fi
rm -rf "$TEST_DIR"

echo -e "\n${YELLOW}=== VALIDATING CRUSH ===${NC}"

# Start Crush services
cleanup
cd shared/services
API_MODE=crush API_VERSION=v3 PORT=8050 python3 unified_tool_api.py > /tmp/crush_mock.log 2>&1 &
sleep 1
UPSTREAM_URL=http://localhost:8050/api/v1/AI/GenAIExplorationLab/Models \
LISTEN_PORT=8052 \
python3 translation_wrapper_with_tools.py > /tmp/crush_wrapper.log 2>&1 &
sleep 2
cd ../..

# Test Crush Write
echo "Testing Crush Write..."
TEST_DIR=$(mktemp -d /tmp/crush-validate-XXXXXX)

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://host.docker.internal:8052/v1" \
    --add-host=host.docker.internal:host-gateway \
    crush-corporate:latest bash -c "cd /workspace && timeout 10 /usr/local/bin/crush.bin run 'write validation.txt with crush validation test'" 2>&1 | tee "$TEST_DIR/output.log" > /dev/null

if [ -f "$TEST_DIR/validation.txt" ]; then
    echo -e "${GREEN}✅ Crush Write: WORKING${NC}"
    echo "   Content: $(cat "$TEST_DIR/validation.txt")"
else
    echo -e "${RED}❌ Crush Write: NOT WORKING${NC}"
    echo "   Check log: tail /tmp/crush_mock.log"
    echo "   Output:"
    tail -5 "$TEST_DIR/output.log" 2>/dev/null || true
fi
rm -rf "$TEST_DIR"

echo -e "\n========================================"
echo "VALIDATION COMPLETE"
echo "========================================"

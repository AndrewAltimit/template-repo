#!/bin/bash
set -e

echo "========================================"
echo "Testing OpenCode with Log Capture"
echo "========================================"

# Create test and log directories
TEST_DIR=$(mktemp -d /tmp/opencode-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"
echo "Log directory: $LOG_DIR"

# Test OpenCode
echo ""
echo "Running OpenCode with log volume mount..."
echo "========================================"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Create a file called output.txt with the content Hello from OpenCode'"

echo ""
echo "Checking results..."
echo "========================================"

# Check if file was created
if [ -f "$TEST_DIR/output.txt" ]; then
    echo "✅ SUCCESS: File created!"
    echo "Content: $(cat output.txt)"
else
    echo "❌ FAILED: File not created in /workspace"

    # Check if it was created in /tmp instead
    if docker run --rm opencode-corporate:latest ls /tmp/output.txt 2>/dev/null; then
        echo "⚠️  File was created in /tmp instead of /workspace"
    fi
fi

# Check logs
echo ""
echo "Mock API Logs (tool detection):"
echo "================================"
if [ -f "$LOG_DIR/mock_api.log" ]; then
    grep -E "(TOOL DETECTED|tool_calls|Matched tool)" "$LOG_DIR/mock_api.log" | tail -10 || echo "No tool detection found"
else
    echo "No mock_api.log found"
fi

echo ""
echo "Translation Wrapper Logs:"
echo "========================="
if [ -f "$LOG_DIR/translation_wrapper.log" ]; then
    grep -E "(Company API response.*tool_calls|Tool calls detected)" "$LOG_DIR/translation_wrapper.log" | tail -10 || echo "No tool calls found"
else
    echo "No translation_wrapper.log found"
fi

echo ""
echo "Test complete. Logs saved in: $LOG_DIR"

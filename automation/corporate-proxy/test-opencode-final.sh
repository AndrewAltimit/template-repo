#!/bin/bash
set -e

echo "========================================"
echo "Final OpenCode Test"
echo "========================================"

# Create test directory
TEST_DIR=$(mktemp -d /tmp/opencode-final-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"
echo "Test directory: $TEST_DIR"

# Run OpenCode
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Write a file called test.txt with Hello World'" 2>&1 | tee opencode.log

# Check results
echo ""
echo "Checking for file..."
if [ -f "$TEST_DIR/test.txt" ]; then
    echo "✅ SUCCESS: File created by OpenCode!"
    echo "Content: $(cat $TEST_DIR/test.txt)"
else
    echo "❌ FAILED: File not created"
fi

echo ""
echo "Mock API log (last tool call):"
if [ -f "$LOG_DIR/mock_api.log" ]; then
    grep -A5 "TOOL DETECTED\|OpenCode format" "$LOG_DIR/mock_api.log" | tail -10
fi

echo ""
echo "Directory contents:"
ls -la "$TEST_DIR"

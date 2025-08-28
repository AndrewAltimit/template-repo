#!/bin/bash
set -e

echo "========================================"
echo "OpenCode Final Fixed Test"
echo "========================================"

# Create test directory
TEST_DIR=$(mktemp -d /tmp/opencode-final-fixed-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"
echo "Test directory: $TEST_DIR"

# Run OpenCode with the updated container
echo "Running OpenCode with fixed container..."
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Write a file called hello.txt with content Hello OpenCode Fixed'" 2>&1 | tee "$LOG_DIR/opencode.log"

# Check results
echo ""
echo "Checking for created file..."
if [ -f "$TEST_DIR/hello.txt" ]; then
    echo "✅ SUCCESS: File created by OpenCode!"
    echo "Content: $(cat $TEST_DIR/hello.txt)"
else
    echo "❌ FAILED: File not created"
    echo ""
    echo "Checking logs for issues..."
    if [ -f "$LOG_DIR/mock_api.log" ]; then
        echo "Mock API log (tool detection):"
        grep -E "TOOL|function|arguments" "$LOG_DIR/mock_api.log" | tail -10
    fi
    echo ""
    echo "OpenCode output (errors):"
    grep -i "invalid\|error" "$LOG_DIR/opencode.log" | head -5 || echo "No error messages found"
fi

echo ""
echo "Directory contents:"
ls -la "$TEST_DIR/"

echo ""
echo "Test complete!"

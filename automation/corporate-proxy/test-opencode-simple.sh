#!/bin/bash
set -e

echo "========================================"
echo "Simple OpenCode Test"
echo "========================================"

# Create test directory
TEST_DIR=$(mktemp -d /tmp/opencode-simple-XXXXXX)
echo "Test directory: $TEST_DIR"

# Run OpenCode
echo "Running OpenCode..."
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Create a file called test.txt with Hello World'" 2>&1 | tail -10

# Check results
echo ""
echo "Checking for file..."
if [ -f "$TEST_DIR/test.txt" ]; then
    echo "✅ File created: $(cat $TEST_DIR/test.txt)"
else
    echo "❌ File not found"
    echo "Directory contents:"
    ls -la "$TEST_DIR"
fi

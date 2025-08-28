#!/bin/bash
set -e

echo "========================================"
echo "Testing Crush Tool Execution"
echo "========================================"

# Create test directory
TEST_DIR=$(mktemp -d /tmp/crush-final-test-XXXXXX)
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"

# Test 1: Create file
echo ""
echo "Test 1: Create a file with write tool"
echo "========================================"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    crush-corporate:latest run "Create a file called test.txt with the content 'Hello from Crush'" 2>/dev/null

if [ -f "$TEST_DIR/test.txt" ]; then
    echo "✅ SUCCESS: File created!"
    echo "Content: $(cat test.txt)"
else
    echo "❌ FAILED: File not created"
fi

# Test 2: List files
echo ""
echo "Test 2: List files with ls tool"
echo "========================================"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    crush-corporate:latest run "List the files in the current directory" 2>/dev/null

echo ""
echo "Test complete. Directory: $TEST_DIR"

#!/bin/bash
set -e

echo "========================================"
echo "Debug Container Tool Execution Test"
echo "========================================"

# Create test directory
TEST_DIR=$(mktemp -d /tmp/tool-debug-XXXXXX)
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"

# Test with Crush
echo ""
echo "Testing Crush with debugging..."
echo "========================================"

# Run Crush and capture logs
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    -e FLASK_DEBUG="false" \
    crush-corporate:latest run "Create a file called test.txt with content hello" 2>&1 | tee crush.log

echo ""
echo "Checking if file was created..."
if [ -f "$TEST_DIR/test.txt" ]; then
    echo "✓ File created successfully!"
    echo "Content: $(cat test.txt)"
else
    echo "✗ File not created"
    echo ""
    echo "Container logs:"
    cat crush.log
    echo ""
    echo "Mock API logs from container:"
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        -v "$TEST_DIR:/workspace" \
        -e HOME=/tmp \
        crush-corporate:latest bash -c "cat /tmp/logs/mock_api.log 2>/dev/null || echo 'No mock API log found'"
fi

echo ""
echo "Test complete. Logs saved in: $TEST_DIR"

#!/bin/bash
set -e

echo "========================================"
echo "Testing Crush with Log Volume Mount"
echo "========================================"

# Create test and log directories
TEST_DIR=$(mktemp -d /tmp/crush-test-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"
echo "Log directory: $LOG_DIR"

# Run Crush container with log volume mounted
echo ""
echo "Running Crush with mounted log volume..."
echo "Command: 'Create a file called output.txt'"
echo "========================================"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    -e FLASK_DEBUG="false" \
    crush-corporate:latest run "Create a file called output.txt"

echo ""
echo "Container finished. Checking results..."
echo "========================================"

# Check if file was created
if [ -f "$TEST_DIR/output.txt" ]; then
    echo "✓ File created!"
    echo "Content: $(cat output.txt)"
else
    echo "✗ File not created"
fi

# Check logs
echo ""
echo "Mock API Logs:"
echo "=============="
if [ -f "$LOG_DIR/mock_api.log" ]; then
    grep -E "(Analyzing message|Matched tool|No tool patterns|TOOL DETECTED|Last message)" "$LOG_DIR/mock_api.log" | tail -20
else
    echo "No mock_api.log found"
fi

echo ""
echo "Translation Wrapper Logs:"
echo "========================"
if [ -f "$LOG_DIR/translation_wrapper.log" ]; then
    grep -E "(Full request data|Messages count|Message [0-9]+:|Tools provided)" "$LOG_DIR/translation_wrapper.log" | tail -30
else
    echo "No translation_wrapper.log found"
fi

echo ""
echo "Test complete. All logs saved in: $LOG_DIR"

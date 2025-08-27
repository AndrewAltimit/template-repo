#!/bin/bash
# Test script to verify tool execution works with the new tool-enabled services

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "==================================="
echo "Testing Tool Execution for Corporate Proxy"
echo "==================================="
echo ""

# Create a test directory
TEST_DIR=$(mktemp -d -t corporate-proxy-tools-test-XXXXXX)
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"
echo ""

# Test Crush with various tools
echo "Testing Crush tool execution..."
echo "--------------------------------"

# Test 1: ls command
echo "Test 1: List files"
echo "hello" > test.txt
"$SCRIPT_DIR/crush/scripts/run.sh" run "List files in the current directory"
echo ""

# Test 2: view command
echo "Test 2: View file"
"$SCRIPT_DIR/crush/scripts/run.sh" run "View the file test.txt"
echo ""

# Test 3: write command
echo "Test 3: Write file"
"$SCRIPT_DIR/crush/scripts/run.sh" run "Create a file called output.txt with the content 'Testing tool execution'"
if [ -f "output.txt" ]; then
    echo "✓ Crush successfully created file via tool"
    echo "  Content: $(cat output.txt)"
else
    echo "✗ Crush failed to execute write tool"
fi
echo ""

# Clean up for OpenCode test
rm -f output.txt

# Test OpenCode with tools
echo "Testing OpenCode tool execution..."
echo "-----------------------------------"

# Test 1: ls command
echo "Test 1: List files"
"$SCRIPT_DIR/opencode/scripts/run.sh" run "List files in the current directory"
echo ""

# Test 2: view command
echo "Test 2: View file"
"$SCRIPT_DIR/opencode/scripts/run.sh" run "View the file test.txt"
echo ""

# Test 3: write command
echo "Test 3: Write file"
"$SCRIPT_DIR/opencode/scripts/run.sh" run "Create a file called output.txt with the content 'Testing OpenCode tools'"
if [ -f "output.txt" ]; then
    echo "✓ OpenCode successfully created file via tool"
    echo "  Content: $(cat output.txt)"
else
    echo "✗ OpenCode failed to execute write tool"
fi
echo ""

echo "==================================="
echo "Test Results:"
echo "==================================="
ls -la "$TEST_DIR"
echo ""

# Cleanup
cd /tmp
rm -rf "$TEST_DIR"

echo "Test directory cleaned up."
echo ""
echo "Note: If tools are hanging, check /tmp/logs/mock_api.log and /tmp/logs/translation_wrapper.log in the containers"

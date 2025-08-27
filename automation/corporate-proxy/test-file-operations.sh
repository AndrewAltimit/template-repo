#!/bin/bash
# Test script to verify file operations work correctly with corporate proxy patches

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "==================================="
echo "Testing File Operations for Corporate Proxy"
echo "==================================="
echo ""

# Create a test directory
TEST_DIR=$(mktemp -d -t corporate-proxy-test-XXXXXX)
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"
echo ""

# Test Crush
echo "Testing Crush file operations..."
echo "--------------------------------"
cat > test_crush.txt << 'EOF'
Create a file called hello.txt with the content "Hello from Crush"
EOF

"$SCRIPT_DIR/crush/scripts/run.sh" run "$(cat test_crush.txt)"

if [ -f "hello.txt" ]; then
    echo "✓ Crush successfully created file"
    echo "  Content: $(cat hello.txt)"
else
    echo "✗ Crush failed to create file"
fi
echo ""

# Clean up for OpenCode test
rm -f hello.txt

# Test OpenCode
echo "Testing OpenCode file operations..."
echo "-----------------------------------"
cat > test_opencode.txt << 'EOF'
Create a file called hello.txt with the content "Hello from OpenCode"
EOF

"$SCRIPT_DIR/opencode/scripts/run.sh" run "$(cat test_opencode.txt)"

if [ -f "hello.txt" ]; then
    echo "✓ OpenCode successfully created file"
    echo "  Content: $(cat hello.txt)"
else
    echo "✗ OpenCode failed to create file"
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

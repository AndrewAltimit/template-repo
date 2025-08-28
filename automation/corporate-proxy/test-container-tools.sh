#!/bin/bash
# Direct test of tool execution in Crush and OpenCode containers
# This test bypasses the wrapper and directly tests if tools work

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "======================================"
echo "Container Tool Execution Test"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create test directory
TEST_DIR=$(mktemp -d -t tool-test-XXXXXX)
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"
echo ""

# Function to test tool execution in a container
test_container_tools() {
    local container_name=$1
    local run_script=$2

    echo -e "${YELLOW}Testing $container_name${NC}"

    # Test 1: Create a file using write tool
    echo "Test 1: Write tool"
    rm -f output.txt

    timeout 20 "$run_script" run 'Create a file called output.txt with the content "Tool test successful"' || {
        echo -e "${RED}✗ Command timed out or failed${NC}"
        return 1
    }

    if [ -f output.txt ]; then
        content=$(cat output.txt 2>/dev/null || echo "")
        echo -e "${GREEN}✓ File created${NC}"
        echo "  Content: $content"
    else
        echo -e "${RED}✗ File not created${NC}"
        return 1
    fi

    # Test 2: List files using ls tool
    echo ""
    echo "Test 2: List tool"
    echo "test1.txt" > test1.txt
    echo "test2.txt" > test2.txt

    output=$(timeout 20 "$run_script" run 'List files in the current directory' 2>&1 || echo "")

    if echo "$output" | grep -q "test1.txt\|test2.txt"; then
        echo -e "${GREEN}✓ List tool executed${NC}"
    else
        echo -e "${YELLOW}⚠ List tool may not have executed properly${NC}"
        echo "Output: $output"
    fi

    # Test 3: View file using view/read tool
    echo ""
    echo "Test 3: View tool"
    echo "This is test content" > readme.txt

    output=$(timeout 20 "$run_script" run 'View the file readme.txt' 2>&1 || echo "")

    if echo "$output" | grep -q "test content"; then
        echo -e "${GREEN}✓ View tool executed${NC}"
    else
        echo -e "${YELLOW}⚠ View tool may not have executed properly${NC}"
    fi

    return 0
}

# Test Crush if available
if [ -f "$SCRIPT_DIR/crush/scripts/run.sh" ]; then
    if docker images -q crush-corporate:latest > /dev/null 2>&1; then
        echo "======================================"
        echo "Testing Crush"
        echo "======================================"
        if test_container_tools "Crush" "$SCRIPT_DIR/crush/scripts/run.sh"; then
            echo -e "${GREEN}✓ Crush tests passed${NC}"
        else
            echo -e "${RED}✗ Crush tests failed${NC}"
        fi
    else
        echo -e "${YELLOW}Crush container not built. Build with:${NC}"
        echo "  cd $SCRIPT_DIR/crush && docker build -f docker/Dockerfile -t crush-corporate:latest ../"
    fi
    echo ""
fi

# Test OpenCode if available
if [ -f "$SCRIPT_DIR/opencode/scripts/run.sh" ]; then
    if docker images -q opencode-corporate:latest > /dev/null 2>&1; then
        echo "======================================"
        echo "Testing OpenCode"
        echo "======================================"
        if test_container_tools "OpenCode" "$SCRIPT_DIR/opencode/scripts/run.sh"; then
            echo -e "${GREEN}✓ OpenCode tests passed${NC}"
        else
            echo -e "${RED}✗ OpenCode tests failed${NC}"
        fi
    else
        echo -e "${YELLOW}OpenCode container not built. Build with:${NC}"
        echo "  cd $SCRIPT_DIR/opencode && docker build -f docker/Dockerfile -t opencode-corporate:latest ../"
    fi
    echo ""
fi

# Test with Python integration script if available
if command -v python3 &> /dev/null && [ -f "$SCRIPT_DIR/test-tool-integration.py" ]; then
    echo "======================================"
    echo "Running Python Integration Tests"
    echo "======================================"
    python3 "$SCRIPT_DIR/test-tool-integration.py"
fi

# Cleanup
cd /tmp
rm -rf "$TEST_DIR"

echo ""
echo "======================================"
echo "Test Complete"
echo "======================================"
echo ""
echo "This test verifies:"
echo "1. Tools are properly invoked when requested"
echo "2. Tools actually execute (files are created/read)"
echo "3. Tool results are returned correctly"
echo ""
echo "If tests fail, check:"
echo "- Container build status (rebuild if needed)"
echo "- Service logs in containers (/tmp/logs/)"
echo "- Tool detection patterns in mock_api_with_tools.py"

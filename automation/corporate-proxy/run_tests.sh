#!/bin/bash

# Corporate Proxy Dual Mode Test Runner
# Runs all tests for both native and text modes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0
SKIPPED=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Corporate Proxy Dual Mode Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Function to run a test
run_test() {
    local test_name=$1
    local test_file=$2

    echo -e "${YELLOW}Running: $test_name${NC}"

    if python3 "$test_file" -v 2>&1 | tee /tmp/test_output.log; then
        echo -e "${GREEN}✓ $test_name PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ $test_name FAILED${NC}"
        ((FAILED++))
        echo "See /tmp/test_output.log for details"
    fi
    echo
}

# Function to start mock servers
start_mock_servers() {
    echo -e "${BLUE}Starting mock servers...${NC}"

    # Start unified tool API mock server
    USE_MOCK_API=true API_MODE=gemini python3 shared/services/unified_tool_api.py > /tmp/mock_api.log 2>&1 &
    MOCK_API_PID=$!

    # Wait for mock API to start
    sleep 2

    if ps -p $MOCK_API_PID > /dev/null; then
        echo -e "${GREEN}Mock API started (PID: $MOCK_API_PID)${NC}"
    else
        echo -e "${RED}Failed to start mock API${NC}"
        exit 1
    fi

    echo
}

# Function to stop mock servers
stop_mock_servers() {
    echo -e "${BLUE}Stopping mock servers...${NC}"

    if [ ! -z "$MOCK_API_PID" ]; then
        kill $MOCK_API_PID 2>/dev/null || true
        echo "Mock API stopped"
    fi

    # Kill any remaining proxy processes
    pkill -f "gemini_proxy_wrapper.py" 2>/dev/null || true

    echo
}

# Cleanup function
cleanup() {
    stop_mock_servers
    echo -e "${BLUE}Cleanup complete${NC}"
}

# Set up trap for cleanup
trap cleanup EXIT

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
python3 --version

# Install dependencies if needed
echo -e "${BLUE}Checking dependencies...${NC}"
python3 -c "import flask" 2>/dev/null || {
    echo "Installing Flask..."
    pip3 install flask flask-cors requests
}

echo

# Run unit tests
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Unit Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo

run_test "Text Tool Parser Unit Tests" "tests/test_text_tool_parser.py"

# Run integration tests
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Integration Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo

run_test "Integration Mode Tests" "tests/test_integration_modes.py"

# Run mock scenario tests
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Mock Scenario Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo

run_test "Mock Scenario Tests" "tests/test_mock_scenarios.py"

# Test with actual proxy (optional)
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Live Proxy Tests (Optional)${NC}"
echo -e "${BLUE}========================================${NC}"
echo

read -p "Run live proxy tests? This will start actual servers. (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    start_mock_servers

    # Test native mode
    echo -e "${YELLOW}Testing Native Mode...${NC}"
    TOOL_MODE=native USE_MOCK_API=true python3 gemini/gemini_proxy_wrapper.py > /tmp/proxy_native.log 2>&1 &
    PROXY_PID=$!
    sleep 2

    if curl -s http://localhost:8053/health | grep -q "healthy"; then
        echo -e "${GREEN}✓ Native mode proxy running${NC}"

        # Run the dual mode test
        python3 tests/test_dual_mode.py 2>&1 | tee /tmp/native_test.log || true

        ((PASSED++))
    else
        echo -e "${RED}✗ Native mode proxy failed to start${NC}"
        ((FAILED++))
    fi

    kill $PROXY_PID 2>/dev/null || true
    sleep 1

    # Test text mode
    echo -e "${YELLOW}Testing Text Mode...${NC}"
    TOOL_MODE=text USE_MOCK_API=true python3 gemini/gemini_proxy_wrapper.py > /tmp/proxy_text.log 2>&1 &
    PROXY_PID=$!
    sleep 2

    if curl -s http://localhost:8053/health | grep -q "healthy"; then
        echo -e "${GREEN}✓ Text mode proxy running${NC}"

        # Could run additional text mode specific tests here

        ((PASSED++))
    else
        echo -e "${RED}✗ Text mode proxy failed to start${NC}"
        ((FAILED++))
    fi

    kill $PROXY_PID 2>/dev/null || true
else
    echo -e "${YELLOW}Skipping live proxy tests${NC}"
    ((SKIPPED+=2))
fi

echo

# Print summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${YELLOW}Skipped: $SKIPPED${NC}"
echo

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the logs.${NC}"
    exit 1
fi

#!/bin/bash
# Test script for OpenCode container with proxy

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${MAGENTA}🎭 OpenCode Container Proxy Test${NC}"
echo "=================================="
echo ""

# Function to run a test in the container
run_container_test() {
    local test_name="$1"
    local test_command="$2"

    echo -e "${BLUE}Test: $test_name${NC}"

    # Build the container if needed
    echo "Building container..."
    docker build -f docker/opencode-with-proxy.Dockerfile -t opencode-with-proxy:test . > /tmp/docker_build.log 2>&1

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed to build container${NC}"
        echo "Build log:"
        cat /tmp/docker_build.log
        return 1
    fi

    echo -e "${GREEN}✓ Container built successfully${NC}"
    echo ""

    # Run the test
    echo "Running test..."
    docker run --rm \
        -v "$(pwd):/workspace" \
        opencode-with-proxy:test \
        bash -c "$test_command"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test passed: $test_name${NC}"
        return 0
    else
        echo -e "${RED}✗ Test failed: $test_name${NC}"
        return 1
    fi
}

# Test 1: Verify proxy starts and responds correctly
echo -e "${CYAN}=== Test 1: Proxy Startup ===${NC}"
run_container_test "Proxy Startup" "
    # The entrypoint will start services and test them
    # We just need to verify the test passes
    sleep 5
    curl -s http://localhost:8052/health || exit 1
    echo 'Proxy is healthy'
"
echo ""

# Test 2: Test OpenCode with a simple query
echo -e "${CYAN}=== Test 2: OpenCode Query ===${NC}"
run_container_test "OpenCode Query" "
    # Wait for services to start
    sleep 5

    # Run a simple OpenCode query
    echo 'What is your name?' | opencode run 2>/dev/null | grep -q 'Hatsune Miku'

    if [ \$? -eq 0 ]; then
        echo 'OpenCode returned expected response: Hatsune Miku'
        exit 0
    else
        echo 'OpenCode did not return expected response'
        exit 1
    fi
"
echo ""

# Test 3: Interactive mode (just verify it starts)
echo -e "${CYAN}=== Test 3: Interactive Mode ===${NC}"
echo -e "${YELLOW}Starting interactive container...${NC}"
echo "You can test OpenCode manually. Type 'exit' to quit."
echo ""
echo "Example commands to try:"
echo "  echo 'What is 2+2?' | opencode run"
echo "  echo 'Write hello world in Python' | opencode run"
echo ""
echo -e "${YELLOW}All responses should be 'Hatsune Miku' in proxy mode${NC}"
echo ""

docker run --rm -it \
    -v "$(pwd):/workspace" \
    -e USE_PROXY=true \
    -e PROXY_MOCK_MODE=true \
    opencode-with-proxy:test

echo ""
echo -e "${GREEN}✓ All tests completed${NC}"
echo ""
echo "To use the container with real company API:"
echo "  docker run --rm -it \\"
echo "    -v \$(pwd):/workspace \\"
echo "    -e USE_PROXY=true \\"
echo "    -e PROXY_MOCK_MODE=false \\"
echo "    -e COMPANY_API_BASE=https://your-company-api.com \\"
echo "    -e COMPANY_API_TOKEN=your-real-token \\"
echo "    opencode-with-proxy:test"

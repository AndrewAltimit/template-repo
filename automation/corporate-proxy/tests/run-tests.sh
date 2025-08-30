#!/bin/bash
set -e
set -u
set -o pipefail

# Initialize PID variables to avoid unbound variable errors with set -u
GEMINI_PID=""
API_PID=""
SERVER_PID=""

# Cleanup function to ensure background processes are killed
# shellcheck disable=SC2317  # Function is called by trap
cleanup() {
    # Kill any background processes we started
    # Using 2>/dev/null to suppress errors if processes don't exist
    if [ -n "$GEMINI_PID" ]; then
        kill "$GEMINI_PID" 2>/dev/null || true
    fi
    if [ -n "$API_PID" ]; then
        kill "$API_PID" 2>/dev/null || true
    fi
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    # Also cleanup any stray processes by name
    pkill -f unified_tool_api 2>/dev/null || true
    pkill -f gemini_proxy_wrapper 2>/dev/null || true
}

# Set up trap to ensure cleanup on script exit (normal or abnormal)
trap cleanup EXIT INT TERM

# Unified test runner for corporate proxy tools
# Usage: ./run-tests.sh [OPTIONS]
# Options:
#   --all          Run all tests
#   --crush        Test Crush functionality
#   --opencode     Test OpenCode functionality
#   --gemini       Test Gemini functionality
#   --api          Test API endpoints
#   --integration  Run integration tests
#   --quick        Run quick smoke tests

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Parse arguments
TEST_TYPE="${1:-quick}"

echo "=========================================="
echo "Corporate Proxy Test Suite"
echo "Test Type: ${TEST_TYPE}"
echo "=========================================="
echo ""

# Function to run test and report result
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Running ${test_name}... "
    if eval "${test_command}" > /tmp/test_output.log 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Output from failed test:"
        echo "  ----------------------"
        sed 's/^/  /' < /tmp/test_output.log  # Indent output for readability
        echo "  ----------------------"
        return 1
    fi
}

# Track test results
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Quick smoke tests
run_quick_tests() {
    echo "Running quick smoke tests..."
    echo ""

    # Test unified API starts
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "Unified API startup" "python automation/corporate-proxy/shared/services/unified_tool_api.py &"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Test basic health check
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "API health check" "curl -fsS http://localhost:8080/health"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Cleanup is handled by trap function
}

# Crush-specific tests
run_crush_tests() {
    echo "Running Crush tests..."
    echo ""

    # Test Crush API with proper environment
    TESTS_RUN=$((TESTS_RUN + 1))
    if API_MODE=crush run_test "Crush API mode" "python -c \"import os; assert os.getenv('API_MODE') == 'crush'\""; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Test Crush Docker build
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "Crush Docker build" "docker-compose build crush-proxy"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# OpenCode-specific tests
run_opencode_tests() {
    echo "Running OpenCode tests..."
    echo ""

    # Test OpenCode API with proper environment
    TESTS_RUN=$((TESTS_RUN + 1))
    if API_MODE=opencode run_test "OpenCode API mode" "python -c \"import os; assert os.getenv('API_MODE') == 'opencode'\""; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Test OpenCode Docker build
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "OpenCode Docker build" "docker-compose build opencode-proxy"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Gemini-specific tests
run_gemini_tests() {
    echo "Running Gemini tests..."
    echo ""

    # Test Gemini API with proper environment
    TESTS_RUN=$((TESTS_RUN + 1))
    if API_MODE=gemini run_test "Gemini API mode" "python -c \"import os; assert os.getenv('API_MODE') == 'gemini'\""; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Test Gemini Docker build
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "Gemini Docker build" "docker-compose build gemini-proxy"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Start Gemini proxy (includes tool support)
    echo "Starting Gemini proxy with tool support..."
    GEMINI_PROXY_PORT=8053 USE_MOCK_API=true python automation/corporate-proxy/gemini/gemini_proxy_wrapper.py > /tmp/gemini_proxy.log 2>&1 &
    GEMINI_PID=$!

    # Start unified API for Gemini
    API_MODE=gemini API_VERSION=v3 PORT=8050 python automation/corporate-proxy/shared/services/unified_tool_api.py > /tmp/gemini_api.log 2>&1 &
    API_PID=$!

    # Use centralized health check utility
    echo "Waiting for services to be ready..."
    if python automation/corporate-proxy/shared/services/health_check.py localhost:8050 localhost:8053; then
        echo "✅ Services ready"
    else
        echo "❌ Services failed to start"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi

    # Test Gemini tools
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "Gemini tool tests" "python automation/corporate-proxy/tests/test_gemini_tools.py"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Cleanup is handled by trap function
}

# API endpoint tests
run_api_tests() {
    echo "Running API endpoint tests..."
    echo ""

    # Start test server
    API_MODE=crush PORT=8090 python automation/corporate-proxy/shared/services/unified_tool_api.py > /tmp/api_server.log 2>&1 &
    SERVER_PID=$!

    # Use centralized health check utility
    echo "Waiting for API server to be ready..."
    if python automation/corporate-proxy/shared/services/health_check.py localhost:8090; then
        echo "✅ API server ready"
    else
        echo "❌ API server failed to start"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi

    # Test endpoints
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "GET /tools" "curl -fsS http://localhost:8090/tools"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "POST /execute" "curl -fsS -X POST http://localhost:8090/execute -H 'Content-Type: application/json' -d '{\"tool\":\"view\",\"parameters\":{\"filePath\":\"test.py\"}}'"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "POST /chat/completions" "curl -fsS -X POST http://localhost:8090/chat/completions -H 'Content-Type: application/json' -d '{\"messages\":[{\"role\":\"user\",\"content\":\"test\"}]}'"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Cleanup is handled by trap function
}

# Integration tests
run_integration_tests() {
    echo "Running integration tests..."
    echo ""

    # Test Docker Compose up
    TESTS_RUN=$((TESTS_RUN + 1))
    if run_test "Docker Compose services" "docker-compose up -d crush-proxy opencode-proxy && sleep 5 && docker-compose ps | grep -E 'crush-proxy|opencode-proxy'"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Clean up
    docker-compose down 2>/dev/null || true
}

# Main test execution
case "${TEST_TYPE}" in
    --quick)
        run_quick_tests
        ;;
    --crush)
        run_crush_tests
        ;;
    --opencode)
        run_opencode_tests
        ;;
    --gemini)
        run_gemini_tests
        ;;
    --api)
        run_api_tests
        ;;
    --integration)
        run_integration_tests
        ;;
    --all)
        run_quick_tests
        echo ""
        run_crush_tests
        echo ""
        run_opencode_tests
        echo ""
        run_gemini_tests
        echo ""
        run_api_tests
        echo ""
        run_integration_tests
        ;;
    *)
        echo "Usage: $0 [--all|--crush|--opencode|--gemini|--api|--integration|--quick]"
        echo ""
        echo "Options:"
        echo "  --all          Run all tests"
        echo "  --crush        Test Crush functionality"
        echo "  --opencode     Test OpenCode functionality"
        echo "  --gemini       Test Gemini functionality"
        echo "  --api          Test API endpoints"
        echo "  --integration  Run integration tests"
        echo "  --quick        Run quick smoke tests (default)"
        exit 1
        ;;
esac

# Print summary
echo ""
echo "=========================================="
echo "Test Results Summary"
echo "=========================================="
echo -e "Tests Run:    ${TESTS_RUN}"
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi

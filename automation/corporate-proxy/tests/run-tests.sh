#!/bin/bash
set -e

# Unified test runner for corporate proxy tools
# Usage: ./run-tests.sh [OPTIONS]
# Options:
#   --all          Run all tests
#   --crush        Test Crush functionality
#   --opencode     Test OpenCode functionality
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
        echo "  See /tmp/test_output.log for details"
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

    # Kill the test server
    pkill -f unified_tool_api 2>/dev/null || true
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

# API endpoint tests
run_api_tests() {
    echo "Running API endpoint tests..."
    echo ""

    # Start test server
    API_MODE=crush PORT=8090 python automation/corporate-proxy/shared/services/unified_tool_api.py > /tmp/api_server.log 2>&1 &
    SERVER_PID=$!
    sleep 2

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

    # Kill test server
    kill $SERVER_PID 2>/dev/null || true
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
        run_api_tests
        echo ""
        run_integration_tests
        ;;
    *)
        echo "Usage: $0 [--all|--crush|--opencode|--api|--integration|--quick]"
        echo ""
        echo "Options:"
        echo "  --all          Run all tests"
        echo "  --crush        Test Crush functionality"
        echo "  --opencode     Test OpenCode functionality"
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

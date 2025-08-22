#!/bin/bash
# start_proxy_services.sh - Start proxy services inside a container
# This script can be used by any container to start the mock/proxy services

set -e

# Configuration from environment variables
MOCK_MODE=${PROXY_MOCK_MODE:-true}
COMPANY_API_BASE=${COMPANY_API_BASE:-http://localhost:8050}
COMPANY_API_TOKEN=${COMPANY_API_TOKEN:-test-secret-token-123}
LOG_DIR=${LOG_DIR:-/tmp}

# Colors for output (if terminal supports it)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

echo -e "${BLUE}Starting Proxy Services${NC}"
echo "================================"

# Function to check if a service is running
check_service() {
    local port=$1
    local service_name=$2

    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $service_name already running on port $port"
        return 0
    else
        return 1
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0

    echo -n "Waiting for $service_name to be ready"
    while [ $attempt -lt $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e " ${RED}✗${NC}"
    echo "Failed to start $service_name after $max_attempts seconds"
    return 1
}

# Start Mock Company API (if in mock mode)
if [ "$MOCK_MODE" = "true" ]; then
    if ! check_service 8050 "Mock Company API"; then
        echo "Starting Mock Company API..."
        python /workspace/automation/proxy/mock_company_api.py > $LOG_DIR/mock_api.log 2>&1 &
        MOCK_PID=$!
        echo "Mock API PID: $MOCK_PID"

        if ! wait_for_service 8050 "Mock Company API"; then
            echo -e "${RED}Failed to start Mock Company API${NC}"
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}Mock mode disabled - using real company API at $COMPANY_API_BASE${NC}"
fi

# Start API Translation Wrapper
if ! check_service 8052 "API Translation Wrapper"; then
    echo "Starting API Translation Wrapper..."

    # Export environment variables for the wrapper
    export WRAPPER_MOCK_MODE=$MOCK_MODE
    export COMPANY_API_BASE=$COMPANY_API_BASE
    export COMPANY_API_TOKEN=$COMPANY_API_TOKEN

    python /workspace/automation/proxy/api_translation_wrapper.py > $LOG_DIR/wrapper.log 2>&1 &
    WRAPPER_PID=$!
    echo "Translation Wrapper PID: $WRAPPER_PID"

    if ! wait_for_service 8052 "API Translation Wrapper"; then
        echo -e "${RED}Failed to start API Translation Wrapper${NC}"
        exit 1
    fi
fi

# Save PIDs for cleanup
if [ -n "$MOCK_PID" ] || [ -n "$WRAPPER_PID" ]; then
    echo "$MOCK_PID" > $LOG_DIR/mock_api.pid
    echo "$WRAPPER_PID" > $LOG_DIR/wrapper.pid
fi

echo ""
echo -e "${GREEN}✓ All services started successfully${NC}"
echo ""
echo "Services:"
echo "  Mock Company API:      http://localhost:8050"
echo "  Translation Wrapper:   http://localhost:8052"
echo ""
echo "Logs:"
echo "  Mock API:     $LOG_DIR/mock_api.log"
echo "  Wrapper:      $LOG_DIR/wrapper.log"
echo ""
echo "OpenCode endpoint: http://localhost:8052/v1"
echo "================================"

# Keep the script running if KEEP_RUNNING is set
if [ "$KEEP_RUNNING" = "true" ]; then
    echo "Keeping services running... Press Ctrl+C to stop"
    trap "echo 'Stopping services...'; kill $MOCK_PID $WRAPPER_PID 2>/dev/null; exit" INT TERM
    wait
fi

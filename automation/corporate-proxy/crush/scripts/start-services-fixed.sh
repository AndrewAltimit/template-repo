#!/bin/bash
set -e

echo "=========================================="
echo "Starting Crush Corporate Services (FIXED)"
echo "=========================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up services..."
    # shellcheck disable=SC2046
    kill $(jobs -p) 2>/dev/null || true
}

# Only trap if we're running interactively
if [ $# -eq 0 ]; then
    trap cleanup EXIT INT TERM
fi

# Create log directory
mkdir -p /tmp/logs

# Start mock Company API with tool support (runs on port 8050)
echo "Starting mock Company API with tool support on port 8050..."
if [ -f /app/mock_api_with_tools_v2.py ]; then
    echo "Using v2 mock API with enhanced pattern matching"
    FLASK_DEBUG=false MOCK_API_PORT=8050 python /app/mock_api_with_tools_v2.py > /tmp/logs/mock_api.log 2>&1 &
    MOCK_PID=$!
else
    echo "Using basic mock API"
    python /app/mock_api.py > /tmp/logs/mock_api.log 2>&1 &
    MOCK_PID=$!
fi

# Start translation wrapper with tool support (runs on port 8052)
echo "Starting translation wrapper on port 8052..."
if [ -f /app/translation_wrapper_with_tools.py ]; then
    python /app/translation_wrapper_with_tools.py > /tmp/logs/translation_wrapper.log 2>&1 &
    WRAPPER_PID=$!
else
    python /app/translation_wrapper.py > /tmp/logs/translation_wrapper.log 2>&1 &
    WRAPPER_PID=$!
fi

# Wait for services to be ready with proper health checks
echo "Waiting for services to be ready..."
MAX_WAIT=30
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    MOCK_READY=false
    WRAPPER_READY=false

    # Check mock API
    if curl -fsS http://localhost:8050/health > /dev/null 2>&1; then
        MOCK_READY=true
    fi

    # Check wrapper
    if curl -fsS http://localhost:8052/health > /dev/null 2>&1; then
        WRAPPER_READY=true
    fi

    if [ "$MOCK_READY" = true ] && [ "$WRAPPER_READY" = true ]; then
        echo "✓ All services are ready!"
        break
    fi

    sleep 1
    WAITED=$((WAITED + 1))

    # Show progress
    if [ $((WAITED % 5)) -eq 0 ]; then
        echo "  Still waiting... ($WAITED/$MAX_WAIT seconds)"
    fi
done

if [ $WAITED -eq $MAX_WAIT ]; then
    echo "✗ Services failed to start in time"
    echo "Check logs:"
    echo "  - /tmp/logs/mock_api.log"
    echo "  - /tmp/logs/translation_wrapper.log"
    exit 1
fi

echo ""
echo "=========================================="
echo "All services started successfully!"
echo "=========================================="
echo ""

# CRITICAL FIX: Use exec "$@" to properly handle Docker CMD
if [ $# -gt 0 ]; then
    # If arguments provided, execute them (replacing this script)
    exec "$@"
else
    # Otherwise, start Crush in interactive mode
    echo "Launching Crush interactive session..."
    exec crush
fi

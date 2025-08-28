#!/bin/bash
set -e

echo "=========================================="
echo "Starting Crush Corporate Services"
echo "=========================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up services..."
    # shellcheck disable=SC2046
    kill $(jobs -p) 2>/dev/null || true
    exit
}

trap cleanup EXIT INT TERM

# Create log directory
mkdir -p /tmp/logs

# Start mock Company API with tool support (runs on port 8050)
echo "Starting mock Company API with tool support on port 8050..."
# Try the tool-enabled versions in order: v2, v1, basic
if [ -f /app/mock_api_with_tools_v2.py ]; then
    echo "Using v2 mock API with enhanced pattern matching and debug logging"
    FLASK_DEBUG=false MOCK_API_PORT=8050 python /app/mock_api_with_tools_v2.py > /tmp/logs/mock_api.log 2>&1 &
elif [ -f /app/mock_api_with_tools.py ]; then
    echo "Using v1 mock API with tool support"
    python /app/mock_api_with_tools.py > /tmp/logs/mock_api.log 2>&1 &
else
    echo "Using basic mock API"
    python /app/mock_api.py > /tmp/logs/mock_api.log 2>&1 &
fi

# Wait for mock API to be ready
echo "Waiting for mock API to be ready..."
for i in {1..30}; do
    if curl -fsS http://localhost:8050/health > /dev/null; then
        echo "✓ Mock API is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "✗ Mock API failed to start"
        echo "Check logs at /tmp/logs/mock_api.log"
        exit 1
    fi
    sleep 1
done

# Start translation wrapper with tool support (runs on port 8052)
echo "Starting translation wrapper with tool support on port 8052..."
# Try the tool-enabled version first, fall back to basic if not available
if [ -f /app/translation_wrapper_with_tools.py ]; then
    python /app/translation_wrapper_with_tools.py > /tmp/logs/translation_wrapper.log 2>&1 &
else
    python /app/translation_wrapper.py > /tmp/logs/translation_wrapper.log 2>&1 &
fi

# Wait for wrapper to be ready
echo "Waiting for translation wrapper to be ready..."
for i in {1..30}; do
    if curl -fsS http://localhost:8052/health > /dev/null; then
        echo "✓ Translation wrapper is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "✗ Translation wrapper failed to start"
        echo "Check logs at /tmp/logs/translation_wrapper.log"
        exit 1
    fi
    sleep 1
done

echo ""
echo "=========================================="
echo "All services started successfully!"
echo "=========================================="
echo ""
echo "Services running:"
echo "  - Mock Company API: http://localhost:8050"
echo "  - Translation Wrapper: http://localhost:8052"
echo ""
echo "Service logs:"
echo "  - /tmp/logs/mock_api.log"
echo "  - /tmp/logs/translation_wrapper.log"
echo ""
echo "Starting Crush..."
echo "=========================================="
echo ""

# Keep services running and execute command if provided
if [ $# -gt 0 ]; then
    # If arguments are provided, run crush with them
    crush "$@"
    cleanup
else
    # Otherwise, start Crush in interactive mode
    echo "Launching Crush interactive session..."
    echo ""
    exec crush
fi

#!/bin/bash
set -e

echo "=========================================="
echo "Starting Crush Corporate Services"
echo "=========================================="
echo ""

# Check if mock mode is enabled (default to true for backward compatibility)
USE_MOCK_API="${USE_MOCK_API:-true}"

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

# Only start and wait for mock API if USE_MOCK_API is true
if [ "$USE_MOCK_API" = "true" ]; then
    # Start unified tool API (runs on port 8050)
    echo "Starting unified tool API on port 8050..."
    API_MODE=crush API_VERSION=v3 PORT=8050 python /app/unified_tool_api.py > /tmp/logs/mock_api.log 2>&1 &

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
else
    echo "Mock API disabled (USE_MOCK_API=$USE_MOCK_API)"
fi

# Start translation wrapper (runs on port 8052)
echo "Starting translation wrapper on port 8052..."
python /app/translation_wrapper.py > /tmp/logs/translation_wrapper.log 2>&1 &

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
if [ "$USE_MOCK_API" = "true" ]; then
    echo "  - Mock Company API: http://localhost:8050"
fi
echo "  - Translation Wrapper: http://localhost:8052"
echo ""
echo "Service logs:"
if [ "$USE_MOCK_API" = "true" ]; then
    echo "  - /tmp/logs/mock_api.log"
fi
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

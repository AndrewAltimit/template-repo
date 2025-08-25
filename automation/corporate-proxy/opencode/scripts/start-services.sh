#!/bin/bash
set -e

echo "=========================================="
echo "Starting OpenCode Corporate Services"
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

# Start mock Company API (runs on port 8050)
echo "Starting mock Company API on port 8050..."
python3 /app/mock_api.py > /tmp/logs/mock_api.log 2>&1 &

# Give the service a moment to start before checking
sleep 1

# Wait for mock API to be ready
echo "Waiting for mock API to be ready..."
for i in {1..30}; do
    if curl -fsS http://localhost:8050/health > /dev/null 2>&1; then
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

# Start translation wrapper (runs on port 8052)
echo "Starting translation wrapper on port 8052..."
python3 /app/translation_wrapper.py > /tmp/logs/translation_wrapper.log 2>&1 &

# Give the service a moment to start before checking
sleep 1

# Wait for wrapper to be ready
echo "Waiting for translation wrapper to be ready..."
for i in {1..30}; do
    if curl -fsS http://localhost:8052/health > /dev/null 2>&1; then
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
echo "OpenCode environment ready"
echo "=========================================="
echo ""

# Execute command if provided, otherwise start bash
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec bash
fi

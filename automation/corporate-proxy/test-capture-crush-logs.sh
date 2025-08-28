#!/bin/bash
set -e

echo "========================================"
echo "Capturing Crush Container Logs"
echo "========================================"

# Create test directory
TEST_DIR=$(mktemp -d /tmp/crush-logs-XXXXXX)
cd "$TEST_DIR"
echo "Test directory: $TEST_DIR"

# Run Crush container with message
echo "Running Crush with: 'Create a file called output.txt'"
echo "========================================"

# Run container and wait for it to complete
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    -e FLASK_DEBUG="false" \
    --name crush-test-$$ \
    crush-corporate:latest run "Create a file called output.txt" &

CONTAINER_PID=$!

# Wait for container to complete or timeout
for i in {1..10}; do
    if ! kill -0 $CONTAINER_PID 2>/dev/null; then
        break
    fi
    if [ "$i" -eq 10 ]; then
        echo "Container still running after 10 seconds, checking logs..."
    fi
    sleep 1
done

# Try to get logs from the container before it exits
echo ""
echo "Attempting to capture container logs..."
docker exec crush-test-$$ cat /tmp/logs/mock_api.log 2>/dev/null || echo "Could not get mock_api.log"
echo ""
docker exec crush-test-$$ cat /tmp/logs/translation_wrapper.log 2>/dev/null || echo "Could not get wrapper.log"

# Wait for container to finish
wait $CONTAINER_PID 2>/dev/null || true

echo ""
echo "Checking if file was created..."
if [ -f "$TEST_DIR/output.txt" ]; then
    echo "✓ File created!"
    echo "Content: $(cat output.txt)"
else
    echo "✗ File not created"
fi

echo ""
echo "Test complete. Logs in: $TEST_DIR"

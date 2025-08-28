#!/bin/bash
# Start mock API and translation services for OpenCode testing (FIXED VERSION)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
SHARED_DIR="$PROJECT_ROOT/automation/corporate-proxy/shared"
LOG_DIR="/tmp/opencode-logs"

echo "========================================"
echo "Starting OpenCode Corporate Proxy Services (FIXED)"
echo "========================================"

# Create log directory
mkdir -p "$LOG_DIR"

# Kill any existing services
pkill -f "mock_api_opencode_fixed.py" || true
pkill -f "translation_wrapper_with_tools.py" || true
sleep 1

# Start mock Company API on port 8050 (FIXED version)
echo "Starting fixed mock Company API on port 8050..."
cd "$SHARED_DIR/services"
python3 mock_api_opencode_fixed.py > "$LOG_DIR/mock_api.log" 2>&1 &
MOCK_PID=$!
echo "Mock API PID: $MOCK_PID"

# Wait for mock API to be ready
echo -n "Waiting for mock API to be ready..."
for i in {1..10}; do
    if curl -s http://localhost:8050/health > /dev/null; then
        echo " Ready!"
        break
    fi
    echo -n "."
    sleep 1
done

# Start translation wrapper on port 8052
echo "Starting translation wrapper on port 8052..."
cd "$SHARED_DIR/services"
UPSTREAM_URL=http://localhost:8050/api/v1/AI/GenAIExplorationLab/Models \
LISTEN_PORT=8052 \
python3 translation_wrapper_with_tools.py > "$LOG_DIR/translation.log" 2>&1 &
WRAPPER_PID=$!
echo "Translation wrapper PID: $WRAPPER_PID"

# Wait for translation wrapper
echo -n "Waiting for translation wrapper to be ready..."
for i in {1..10}; do
    if curl -s http://localhost:8052/health > /dev/null; then
        echo " Ready!"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "Services started successfully!"
echo "Mock API logs: $LOG_DIR/mock_api.log"
echo "Translation logs: $LOG_DIR/translation.log"
echo ""
echo "To test directly:"
echo "  curl -X POST http://localhost:8052/v1/chat/completions \\"
echo "    -H 'Authorization: Bearer test-secret-token-123' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Write a file called test.txt\"}], \"model\": \"gpt-4\"}'"
echo ""
echo "To stop services: pkill -f 'mock_api_opencode_fixed.py|translation_wrapper'"

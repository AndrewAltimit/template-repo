#!/bin/bash
# Run script for Company OpenCode with TUI support

set -e

IMAGE_NAME="opencode-company-tui:latest"
CONTAINER_NAME="opencode-company-tui"

echo "============================================"
echo "Starting Company OpenCode with TUI Support"
echo "============================================"

# Check if image exists
if ! docker images | grep -q "opencode-company-tui"; then
    echo "❌ Image not found. Building it first..."
    ./automation/proxy/build-company-tui.sh
fi

# Stop and remove existing container if it exists
if docker ps -a | grep -q "$CONTAINER_NAME"; then
    echo "Stopping existing container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# Get port configuration from environment or use defaults
MOCK_API_PORT=${MOCK_API_PORT:-8050}
WRAPPER_PORT=${WRAPPER_PORT:-8052}

# Check if ports are already in use
check_port() {
    local port=$1
    if lsof -i :"$port" 2>/dev/null | grep -q LISTEN; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Port mapping options
PORT_MAPPING=""

# Check mock API port
if check_port "$MOCK_API_PORT"; then
    echo "⚠️  Port $MOCK_API_PORT is already in use (likely by a mock API running on host)"
    echo "   Skipping port mapping for $MOCK_API_PORT - container will use internal mock API"
else
    PORT_MAPPING="$PORT_MAPPING -p $MOCK_API_PORT:$MOCK_API_PORT"
    echo "✅ Port $MOCK_API_PORT is free - will map container port"
fi

# Check wrapper port
if check_port "$WRAPPER_PORT"; then
    echo "⚠️  Port $WRAPPER_PORT is already in use"
    echo "   Skipping port mapping for $WRAPPER_PORT - container will use internal wrapper"
else
    PORT_MAPPING="$PORT_MAPPING -p $WRAPPER_PORT:$WRAPPER_PORT"
    echo "✅ Port $WRAPPER_PORT is free - will map container port"
fi

echo ""
echo "Starting container..."
echo "Mock services will auto-start in the container."
echo ""

# Run the container interactively with mock mode and auto-start enabled
# shellcheck disable=SC2086
docker run -it \
    --name "$CONTAINER_NAME" \
    --rm \
    -e COMPANY_MOCK_MODE="true" \
    -e COMPANY_AUTO_START="true" \
    -e COMPANY_API_BASE="http://localhost:$MOCK_API_PORT" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e OPENROUTER_API_KEY="sk-company-mock-api-key-123" \
    -e MOCK_API_PORT="$MOCK_API_PORT" \
    -e WRAPPER_PORT="$WRAPPER_PORT" \
    $PORT_MAPPING \
    -v "$(pwd):/workspace/project" \
    "$IMAGE_NAME"

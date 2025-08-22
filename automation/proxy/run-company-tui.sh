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

# Check if ports are already in use
check_port() {
    local port=$1
    if lsof -i :$port 2>/dev/null | grep -q LISTEN; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Port mapping options
PORT_MAPPING=""

# Check port 8050
if check_port 8050; then
    echo "⚠️  Port 8050 is already in use (likely by a mock API running on host)"
    echo "   Skipping port mapping for 8050 - container will use internal mock API"
else
    PORT_MAPPING="$PORT_MAPPING -p 8050:8050"
    echo "✅ Port 8050 is free - will map container port"
fi

# Check port 8052
if check_port 8052; then
    echo "⚠️  Port 8052 is already in use"
    echo "   Skipping port mapping for 8052 - container will use internal wrapper"
else
    PORT_MAPPING="$PORT_MAPPING -p 8052:8052"
    echo "✅ Port 8052 is free - will map container port"
fi

echo ""
echo "Starting container..."
echo "Mock services will auto-start in the container."
echo ""

# Run the container interactively with mock mode and auto-start enabled
docker run -it \
    --name "$CONTAINER_NAME" \
    --rm \
    -e COMPANY_MOCK_MODE="true" \
    -e COMPANY_AUTO_START="true" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e OPENROUTER_API_KEY="sk-company-mock-api-key-123" \
    $PORT_MAPPING \
    -v "$(pwd):/workspace/project" \
    "$IMAGE_NAME"

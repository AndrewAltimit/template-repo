#!/bin/bash
# Run Company OpenCode in production mode (no mock services)

set -e

IMAGE_NAME="opencode-company-tui:latest"
CONTAINER_NAME="opencode-company-production"

echo "============================================"
echo "Starting Company OpenCode (Production Mode)"
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

# Get API credentials
if [ -z "$COMPANY_API_BASE" ]; then
    echo "Enter Company API Base URL (e.g., https://your-company-api-gateway.example.com):"
    read -r COMPANY_API_BASE
fi

if [ -z "$COMPANY_API_TOKEN" ]; then
    echo "Enter Company API Token:"
    read -rs COMPANY_API_TOKEN
    echo ""
fi

echo ""
echo "Starting container in production mode..."
echo "Mock services will NOT be started."
echo "Using API: $COMPANY_API_BASE"
echo ""

# Run the container interactively WITHOUT mock mode
docker run -it \
    --name "$CONTAINER_NAME" \
    --rm \
    -e COMPANY_MOCK_MODE="false" \
    -e COMPANY_API_BASE="$COMPANY_API_BASE" \
    -e COMPANY_API_TOKEN="$COMPANY_API_TOKEN" \
    -e OPENROUTER_API_KEY="$COMPANY_API_TOKEN" \
    -v "$(pwd):/workspace/project" \
    "$IMAGE_NAME"

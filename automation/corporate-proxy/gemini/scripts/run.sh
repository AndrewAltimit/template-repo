#!/bin/bash

# Run script for Gemini CLI Corporate Proxy Container
set -e

# Directory variables not currently needed but may be used in future
# SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# GEMINI_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Running Gemini CLI Corporate Proxy"
echo "=========================================="

# Configuration
IMAGE_NAME="${IMAGE_NAME:-gemini-corporate-proxy}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
CONTAINER_NAME="${CONTAINER_NAME:-gemini-proxy}"

# Container run mode
RUN_MODE="${1:-interactive}"

# Check if image exists
if ! docker image inspect "$FULL_IMAGE" &> /dev/null; then
    echo "❌ Image $FULL_IMAGE not found. Please run ./scripts/build.sh first"
    exit 1
fi

# Stop any existing container with the same name
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# Prepare volume mounts
WORKSPACE_DIR="${WORKSPACE_DIR:-$(pwd)}"
echo "Mounting workspace: $WORKSPACE_DIR"

# Run based on mode
case "$RUN_MODE" in
    interactive|shell)
        echo "Starting Gemini CLI with corporate proxy..."
        echo "Services will start, then Gemini CLI will launch automatically."
        echo ""
        docker run -it --rm \
            --name "$CONTAINER_NAME" \
            -v "$WORKSPACE_DIR:/workspace" \
            -p 8050:8050 \
            -p 8052:8052 \
            -p 8053:8053 \
            "$FULL_IMAGE" \
            interactive
        ;;

    test)
        echo "Running test mode..."
        docker run -it --rm \
            --name "$CONTAINER_NAME" \
            "$FULL_IMAGE" \
            test
        ;;

    daemon|background)
        echo "Starting in background mode..."
        docker run -d \
            --name "$CONTAINER_NAME" \
            -v "$WORKSPACE_DIR:/workspace" \
            -p 8050:8050 \
            -p 8052:8052 \
            -p 8053:8053 \
            "$FULL_IMAGE" \
            daemon

        echo ""
        echo "Container started in background: $CONTAINER_NAME"
        echo ""
        echo "To check logs:"
        echo "  docker logs -f $CONTAINER_NAME"
        echo ""
        echo "To enter the container:"
        echo "  docker exec -it $CONTAINER_NAME bash"
        echo ""
        echo "To run Gemini CLI:"
        echo "  docker exec -it $CONTAINER_NAME gemini"
        echo ""
        echo "To stop:"
        echo "  docker stop $CONTAINER_NAME"
        ;;

    *)
        echo "Usage: $0 [interactive|test|daemon]"
        echo ""
        echo "Modes:"
        echo "  interactive - Start container with bash shell (default)"
        echo "  test        - Run tests and exit"
        echo "  daemon      - Run in background with services"
        exit 1
        ;;
esac

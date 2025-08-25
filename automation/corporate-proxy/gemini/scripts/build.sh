#!/bin/bash

# Build script for Gemini CLI Corporate Proxy Container
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEMINI_DIR="$(dirname "$SCRIPT_DIR")"
CORPORATE_PROXY_DIR="$(dirname "$GEMINI_DIR")"

echo "=========================================="
echo "Building Gemini CLI Corporate Proxy Container"
echo "=========================================="

# Configuration
IMAGE_NAME="${IMAGE_NAME:-gemini-corporate-proxy}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
GEMINI_VERSION="${GEMINI_VERSION:-HEAD}"

echo "Configuration:"
echo "  Image: $FULL_IMAGE"
echo "  Gemini Version: $GEMINI_VERSION"
echo "  Build Context: $CORPORATE_PROXY_DIR"
echo ""

# Check Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Build the container
echo "Building Docker image..."
cd "$CORPORATE_PROXY_DIR"

if docker build \
    -f gemini/docker/Dockerfile \
    --build-arg GEMINI_VERSION="$GEMINI_VERSION" \
    --build-arg USER_ID="$(id -u)" \
    --build-arg GROUP_ID="$(id -g)" \
    -t "$FULL_IMAGE" \
    .; then
    echo ""
    echo "=========================================="
    echo "✅ Build Complete!"
    echo "=========================================="
    echo ""
    echo "Image built: $FULL_IMAGE"
    echo ""
    echo "To run the container:"
    echo "  ./scripts/run.sh"
    echo ""
    echo "Or manually:"
    echo "  docker run -it --rm $FULL_IMAGE"
    echo ""
else
    echo ""
    echo "❌ Build failed!"
    exit 1
fi

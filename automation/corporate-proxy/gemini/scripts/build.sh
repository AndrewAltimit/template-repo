#!/bin/bash

# Build script for Gemini CLI Corporate Proxy Container
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEMINI_DIR="$(dirname "$SCRIPT_DIR")"
CORPORATE_PROXY_DIR="$(dirname "$GEMINI_DIR")"

# Source common functions
source "$CORPORATE_PROXY_DIR/shared/scripts/common-functions.sh"

print_header "Building Gemini CLI Corporate Proxy Container"

# Detect container runtime
detect_container_runtime

# Auto-detect architecture
detect_architecture

# Check if buildx is available
check_buildx

# Configuration
IMAGE_NAME="${IMAGE_NAME:-gemini-corporate-proxy}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
GEMINI_VERSION="${GEMINI_VERSION:-HEAD}"

echo "Configuration:"
echo "  Image: $FULL_IMAGE"
echo "  Gemini Version: $GEMINI_VERSION"
echo "  Target Architecture: $TARGETARCH"
echo "  Build Context: $CORPORATE_PROXY_DIR"
echo ""

# Build the container
print_info "Building Docker image..."
cd "$CORPORATE_PROXY_DIR"

if container_build \
    --platform "linux/${TARGETARCH}" \
    -f gemini/docker/Dockerfile \
    --build-arg GEMINI_VERSION="$GEMINI_VERSION" \
    --build-arg USER_ID="$(id -u)" \
    --build-arg GROUP_ID="$(id -g)" \
    -t "$FULL_IMAGE" \
    .; then
    print_header "✅ Build Complete!"
    echo ""
    echo "Image built: $FULL_IMAGE"
    echo "Architecture: $TARGETARCH"
    echo "Runtime: $CONTAINER_RUNTIME"
    echo ""
    echo "To run the container:"
    echo "  ./scripts/run.sh"
    echo ""
    echo "Or manually:"
    echo "  $CONTAINER_RUNTIME run -it --rm $FULL_IMAGE"
    echo ""
else
    print_error "Build failed!"
    exit 1
fi
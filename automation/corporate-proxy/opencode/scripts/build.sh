#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck disable=SC1091  # File exists at runtime
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Building OpenCode Corporate Integration"

# Detect container runtime
detect_container_runtime

# Auto-detect architecture
detect_architecture

# Check if buildx is available
check_buildx

print_info "Target architecture: $TARGETARCH"

# Navigate to OpenCode directory for relative Dockerfile path
cd "$SCRIPT_DIR/.."

# Get repository root for build context
REPO_ROOT="$(cd "$CORPORATE_PROXY_ROOT/../.." && pwd)"

# Build the Docker image
print_info "Building Docker image for $TARGETARCH..."
print_info "Using build context: $REPO_ROOT"
if container_build \
    --platform "linux/${TARGETARCH}" \
    --pull \
    -f "$SCRIPT_DIR/../docker/Dockerfile" \
    -t opencode-corporate:latest \
    --build-arg SERVICES_DIR="$SERVICES_DIR" \
    "$REPO_ROOT"; then
    print_info "Build successful!"
    echo ""
    echo "Runtime: $CONTAINER_RUNTIME"
    echo "Architecture: $TARGETARCH"
    echo ""
    echo "To run with mock services:"
    echo "  ./scripts/run.sh"
    echo ""
    echo "To run with production API:"
    echo "  ./scripts/run-production.sh"
else
    print_error "Build failed!"
    exit 1
fi

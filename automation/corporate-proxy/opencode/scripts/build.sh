#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck disable=SC1091  # File exists at runtime
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Building OpenCode Corporate Integration"

# Check Docker
check_docker

# Navigate to OpenCode directory
cd "$SCRIPT_DIR/.."

# Build the Docker image
print_info "Building Docker image..."
if docker build --pull \
    -f docker/Dockerfile \
    -t opencode-corporate:latest \
    --build-arg SERVICES_DIR="$SERVICES_DIR" \
    "$CORPORATE_PROXY_ROOT"; then
    print_info "Build successful!"
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

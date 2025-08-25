#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Running Crush with Mock Services"

# Check Docker
check_docker

# Get host user and group IDs for proper file permissions
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

# Clean up any existing container
cleanup_container "crush-corporate"

# Run the container
print_info "Starting Crush with mock services..."
docker run -it --rm \
    --name crush-corporate \
    -v "$(pwd):/workspace" \
    -u "${USER_ID}:${GROUP_ID}" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    crush-corporate:latest "$@"

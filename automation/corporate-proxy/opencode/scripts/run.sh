#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Running OpenCode with Mock Services"

# Check Docker
check_docker

# Get host user and group IDs for proper file permissions
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# Build if needed
build_if_needed "opencode-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

# Clean up any existing container
cleanup_container "opencode-corporate"

# Run the container and launch OpenCode directly
print_info "Starting OpenCode with mock services..."
if [ $# -gt 0 ]; then
    # If arguments provided, pass them to opencode
    docker run -it --rm \
        --name opencode-corporate \
        -v "$(pwd):/workspace" \
        -u "${USER_ID}:${GROUP_ID}" \
        -e COMPANY_API_BASE="http://localhost:8050" \
        -e COMPANY_API_TOKEN="test-secret-token-123" \
        -e WRAPPER_PORT="8052" \
        -e MOCK_API_PORT="8050" \
        -e OPENROUTER_API_KEY="test-secret-token-123" \
        -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
        opencode-corporate:latest bash -c "cd /workspace && opencode $*"
else
    # No arguments - launch OpenCode TUI in current directory
    docker run -it --rm \
        --name opencode-corporate \
        -v "$(pwd):/workspace" \
        -u "${USER_ID}:${GROUP_ID}" \
        -e COMPANY_API_BASE="http://localhost:8050" \
        -e COMPANY_API_TOKEN="test-secret-token-123" \
        -e WRAPPER_PORT="8052" \
        -e MOCK_API_PORT="8050" \
        -e OPENROUTER_API_KEY="test-secret-token-123" \
        -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
        opencode-corporate:latest bash -c "cd /workspace && opencode ."
fi

#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing Crush Non-Interactive"

# Check Docker
check_docker

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

# Clean up any existing container
cleanup_container "crush-corporate-test"

# Run the container without -it flag for testing
print_info "Starting Crush with mock services (non-interactive)..."

# Run container with Crush command directly (start-services.sh will handle it)
# Don't mount current directory to avoid permission issues
docker run --rm \
    --name crush-corporate-test \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    crush-corporate:latest run "say hello"

#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Running OpenCode with Production Company API"

# Check Docker
check_docker

# Check required environment variables
if ! check_env_vars "COMPANY_API_BASE" "COMPANY_API_TOKEN"; then
    echo ""
    echo "Please set the required environment variables:"
    echo "  export COMPANY_API_BASE='https://your-company-api-endpoint'"
    echo "  export COMPANY_API_TOKEN='your-token'"
    exit 1
fi

# Build if needed
build_if_needed "opencode-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

# Clean up any existing container
cleanup_container "opencode-corporate-prod"

print_info "Using Company API: $COMPANY_API_BASE"

# Run the container with production settings
docker run -it --rm \
    --name opencode-corporate-prod \
    -v "$(pwd):/workspace" \
    -e COMPANY_API_BASE="$COMPANY_API_BASE" \
    -e COMPANY_API_TOKEN="$COMPANY_API_TOKEN" \
    -e WRAPPER_PORT="8052" \
    opencode-corporate:latest "$@"

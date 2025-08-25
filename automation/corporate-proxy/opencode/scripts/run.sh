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

# Run the container
print_info "Starting OpenCode with mock services..."

# Prepare command based on arguments
if [ $# -eq 0 ]; then
    # No arguments - launch OpenCode TUI
    print_info "Launching OpenCode TUI..."
    OPENCODE_CMD="opencode ."
elif [ "$1" = "run" ]; then
    # OpenCode run command with message
    shift  # Remove 'run' from arguments
    print_info "Running OpenCode with message: $*"
    OPENCODE_CMD="opencode run \"$*\""
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    # Show help
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Options:"
    echo "  (no arguments)    Launch OpenCode TUI"
    echo "  run <message>     Run OpenCode with a message"
    echo "  --version         Show OpenCode version"
    echo "  --help, -h        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Launch TUI"
    echo "  $0 run 'say hello'    # Run with message"
    echo "  $0 --version          # Show version"
    exit 0
else
    # Pass all arguments directly to opencode
    OPENCODE_CMD="opencode $*"
fi

# Run Docker container with the prepared command
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
    opencode-corporate:latest bash -c "cd /workspace && $OPENCODE_CMD"

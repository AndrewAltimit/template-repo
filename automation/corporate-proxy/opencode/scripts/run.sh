#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Running OpenCode with Mock Services"

# Check Docker
check_docker

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
    OPENCODE_ARGS=("opencode" ".")
elif [ "$1" = "run" ]; then
    # Explicit run command
    shift  # Remove 'run' from arguments
    print_info "Running OpenCode with message: $*"
    OPENCODE_ARGS=("opencode" "run" "$*")
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    # Show help
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Options:"
    echo "  (no arguments)        Launch OpenCode TUI"
    echo "  <message>             Run OpenCode with a message"
    echo "  run <message>         Explicitly run with a message"
    echo "  --version             Show OpenCode version"
    echo "  --help, -h            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Launch TUI"
    echo "  $0 'say hello'        # Run with message"
    echo "  $0 run 'say hello'    # Explicitly run with message"
    echo "  $0 --version          # Show version"
    exit 0
elif [ "$1" = "--version" ]; then
    # Pass version flag to opencode
    OPENCODE_ARGS=("opencode" "--version")
else
    # Assume any other arguments are a message to run
    print_info "Running OpenCode with message: $*"
    OPENCODE_ARGS=("opencode" "run" "$*")
fi

# Run Docker container with the prepared command
# Run with host user's UID to ensure proper file permissions
# Detect if we have a TTY
if [ -t 0 ]; then
    TTY_FLAG="-it"
else
    TTY_FLAG=""
fi

# shellcheck disable=SC2086
container_run $TTY_FLAG --rm \
    --name opencode-corporate \
    --user "$(id -u):$(id -g)" \
    -v "$(pwd):/workspace:rw" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e TERM="${TERM:-xterm-256color}" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e WRAPPER_PORT="8052" \
    -e MOCK_API_PORT="8050" \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest "${OPENCODE_ARGS[@]}"

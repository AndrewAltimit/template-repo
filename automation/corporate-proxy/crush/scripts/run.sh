#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Running Crush with Mock Services"

# Check Docker
check_docker

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

# Clean up any existing container
cleanup_container "crush-corporate"

# Prepare command based on arguments
if [ $# -eq 0 ]; then
    # No arguments - launch interactive shell (no args to container)
    print_info "Launching interactive shell with Crush..."
    # Run the container
    print_info "Starting Crush with mock services..."

    # Detect if we have a TTY
    if [ -t 0 ]; then
        TTY_FLAG="-it"
    else
        TTY_FLAG=""
    fi

    # Run with host user's UID to ensure proper file permissions
    # Don't pass any arguments - start-services.sh will run interactively
    # shellcheck disable=SC2086
    container_run $TTY_FLAG --rm \
        --name crush-corporate \
        --user "$(id -u):$(id -g)" \
        -v "$(pwd):/workspace:rw" \
        -e HOME=/tmp \
        -e USER="$(whoami)" \
        -e TERM="${TERM:-xterm-256color}" \
        -e COMPANY_API_BASE="http://localhost:8050" \
        -e COMPANY_API_TOKEN="test-secret-token-123" \
        -e WRAPPER_PORT="8052" \
        -e MOCK_API_PORT="8050" \
        crush-corporate:latest
elif [ "$1" = "run" ]; then
    # Explicit run command
    shift  # Remove 'run' from arguments
    print_info "Running Crush with message: $*"
    CONTAINER_CMD=("run" "$*")
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    # Show help
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Options:"
    echo "  (no arguments)        Launch interactive shell"
    echo "  <message>             Run Crush with a message"
    echo "  run <message>         Explicitly run with a message"
    echo "  --help, -h            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Launch interactive shell"
    echo "  $0 'say hello'        # Run with message"
    echo "  $0 run 'say hello'    # Explicitly run with message"
    exit 0
else
    # Assume any other arguments are a message to run
    print_info "Running Crush with message: $*"
    CONTAINER_CMD=("run" "$*")
fi

# For non-interactive modes, run with command
if [ -n "${CONTAINER_CMD+x}" ]; then
    # Run the container
    print_info "Starting Crush with mock services..."

    # Detect if we have a TTY
    if [ -t 0 ]; then
        TTY_FLAG="-it"
    else
        TTY_FLAG=""
    fi

    # Run with host user's UID to ensure proper file permissions
    # shellcheck disable=SC2086
    container_run $TTY_FLAG --rm \
        --name crush-corporate \
        --user "$(id -u):$(id -g)" \
        -v "$(pwd):/workspace:rw" \
        -e HOME=/tmp \
        -e USER="$(whoami)" \
        -e TERM="${TERM:-xterm-256color}" \
        -e COMPANY_API_BASE="http://localhost:8050" \
        -e COMPANY_API_TOKEN="test-secret-token-123" \
        -e WRAPPER_PORT="8052" \
        -e MOCK_API_PORT="8050" \
        crush-corporate:latest "${CONTAINER_CMD[@]}"
fi

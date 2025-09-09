#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Running Gemini CLI with Mock Services"

# Check Docker
check_docker

# Configuration
IMAGE_NAME="${IMAGE_NAME:-gemini-corporate-proxy}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
CONTAINER_NAME="${CONTAINER_NAME:-gemini-corporate}"

# Build if needed
build_if_needed "$FULL_IMAGE" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

# Clean up any existing container
cleanup_container "$CONTAINER_NAME"

# Prepare command based on arguments
if [ $# -eq 0 ]; then
    # No arguments - launch interactive shell
    print_info "Launching interactive shell with Gemini CLI..."
    # Container will run start-services.sh in interactive mode
    CONTAINER_CMD=()
elif [ "$1" = "run" ]; then
    # Explicit run command
    shift  # Remove 'run' from arguments
    print_info "Running Gemini with prompt: $*"
    CONTAINER_CMD=("run" "$*")
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    # Show help
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Options:"
    echo "  (no arguments)        Launch interactive shell"
    echo "  <prompt>              Run Gemini with a prompt"
    echo "  run <prompt>          Explicitly run with a prompt"
    echo "  test                  Run test mode"
    echo "  daemon                Run in background mode"
    echo "  --help, -h            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Launch interactive shell"
    echo "  $0 'explain git'      # Run with prompt"
    echo "  $0 run 'explain git'  # Explicitly run with prompt"
    echo "  $0 test               # Run tests"
    echo "  $0 daemon             # Run in background"
    exit 0
elif [ "$1" = "test" ]; then
    # Test mode
    print_info "Running test mode..."
    CONTAINER_CMD=("test")
elif [ "$1" = "daemon" ] || [ "$1" = "background" ]; then
    # Daemon mode
    print_info "Starting in background mode..."
    DAEMON_MODE="true"
    CONTAINER_CMD=("daemon")
else
    # Assume any other arguments are a prompt to run
    print_info "Running Gemini with prompt: $*"
    CONTAINER_CMD=("run" "$*")
fi

# Prepare volume mounts
WORKSPACE_DIR="${WORKSPACE_DIR:-$(pwd)}"
print_info "Mounting workspace: $WORKSPACE_DIR"

# Detect if we have a TTY
if [ -t 0 ]; then
    TTY_FLAG="-it"
else
    TTY_FLAG=""
fi

# Common Docker run arguments
DOCKER_ARGS=(
    --name "$CONTAINER_NAME"
    --user "$(id -u):$(id -g)"
    -v "$WORKSPACE_DIR:/workspace:rw"
    -e HOME=/tmp
    -e USER="$(whoami)"
    -e TERM="${TERM:-xterm-256color}"
    -e COMPANY_API_BASE="http://localhost:8050"
    -e COMPANY_API_TOKEN="test-secret-token-123"
    -e WRAPPER_PORT="8052"
    -e MOCK_API_PORT="8050"
    -e GEMINI_API_KEY="test-secret-token-123"
    -e GEMINI_API_BASE="http://localhost:8053/v1"
    -p 8050:8050
    -p 8052:8052
    -p 8053:8053
)

# Run container based on mode
if [ "${DAEMON_MODE:-false}" = "true" ]; then
    # Background mode
    container_run -d \
        "${DOCKER_ARGS[@]}" \
        "$FULL_IMAGE" \
        "${CONTAINER_CMD[@]}"

    echo ""
    print_success "Container started in background: $CONTAINER_NAME"
    echo ""
    echo "To check logs:"
    echo "  $CONTAINER_RUNTIME logs -f $CONTAINER_NAME"
    echo ""
    echo "To enter the container:"
    echo "  $CONTAINER_RUNTIME exec -it $CONTAINER_NAME bash"
    echo ""
    echo "To run Gemini CLI:"
    echo "  $CONTAINER_RUNTIME exec -it $CONTAINER_NAME gemini"
    echo ""
    echo "To stop:"
    echo "  $CONTAINER_RUNTIME stop $CONTAINER_NAME"
else
    # Interactive/test mode
    # shellcheck disable=SC2086
    container_run $TTY_FLAG --rm \
        "${DOCKER_ARGS[@]}" \
        "$FULL_IMAGE" \
        "${CONTAINER_CMD[@]}"
fi

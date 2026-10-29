#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Starting OpenCode Interactive Session"

# Check container runtime
check_docker

# Build if needed
build_if_needed "opencode-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT/../.."

print_info "Starting interactive shell with OpenCode environment..."
print_info "The image entrypoint starts the mock Company API and translation wrapper"
print_info "Then use 'opencode' for the TUI or 'opencode run \"your question\"' for one-off queries"

# Run interactive session with host user's UID for proper file permissions.
# The entrypoint (start-services.sh) starts the services and then the shell.
container_run --rm -it \
    --user "$(id -u):$(id -g)" \
    -v "$(pwd):/workspace:rw" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    opencode-corporate:latest bash

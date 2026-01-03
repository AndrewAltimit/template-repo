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
build_if_needed "opencode-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Starting interactive shell with OpenCode environment..."
print_info "Services will start automatically inside the container"
print_info "Use '/usr/local/bin/opencode' to run OpenCode"
print_info "Or 'opencode run \"your question\"' for one-off queries"

# Run interactive session with host user's UID for proper file permissions
container_run --rm -it \
    --user "$(id -u):$(id -g)" \
    -v "$(pwd):/workspace:rw" \
    -e HOME=/tmp \
    -e USER="$(whoami)" \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c '
        # Start services
        echo "Starting mock API service..."
        python /app/mock_api.py > /dev/null 2>&1 &

        echo "Starting translation wrapper..."
        python /app/translation_wrapper.py > /dev/null 2>&1 &

        # Wait for services with health checks
        echo "Waiting for services to start..."
        for i in {1..30}; do
            if curl -fsS http://localhost:8050/health > /dev/null; then
                echo "✓ Mock API is ready"
                break
            fi
            if [ $i -eq 30 ]; then
                echo "✗ Mock API failed to start"
                exit 1
            fi
            sleep 1
        done

        for i in {1..30}; do
            if curl -fsS http://localhost:8052/health > /dev/null; then
                echo "✓ Translation wrapper is ready"
                break
            fi
            if [ $i -eq 30 ]; then
                echo "✗ Translation wrapper failed to start"
                exit 1
            fi
            sleep 1
        done

        echo ""
        echo "Services ready! You can now use OpenCode:"
        echo "  opencode ask \"your question\""
        echo "  opencode generate \"code request\""
        echo ""

        # Start interactive shell
        cd /workspace
        exec bash
    '

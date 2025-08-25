#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Starting OpenCode Interactive Session"

# Build if needed
build_if_needed "opencode-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Starting interactive OpenCode session..."
print_info "Services will start automatically inside the container"
print_info "Use 'opencode ask \"your question\"' to test"

# Run interactive session
docker run --rm -it \
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
            if curl -s http://localhost:8050/health > /dev/null 2>&1; then
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
            if curl -s http://localhost:8052/health > /dev/null 2>&1; then
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

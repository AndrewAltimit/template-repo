#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing OpenCode with Corporate Proxy"

# Build if needed
build_if_needed "opencode-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Running OpenCode with mock corporate API..."

# Run OpenCode with our proxy
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://localhost:8052/v1" \
    opencode-corporate:latest bash -c '
        # Start services
        python /app/mock_api.py > /dev/null 2>&1 &
        python /app/translation_wrapper.py > /dev/null 2>&1 &

        # Wait for services to start with health checks
        echo "Waiting for mock API to be ready..."
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

        echo "Waiting for translation wrapper to be ready..."
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

        # Test OpenCode
        echo "=== Testing OpenCode CLI ==="
        cd /workspace

        echo "Running OpenCode with a simple prompt..."
        opencode ask "Say Hello from OpenCode Corporate Integration" 2>&1 | tail -n 20
    '

print_success "OpenCode test completed!"

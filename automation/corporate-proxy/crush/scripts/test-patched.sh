#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing Crush with Patched Provider Validation"

# Build with the new patched Dockerfile
print_info "Building patched Crush container..."
build_if_needed "crush-corporate:patched" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Running Crush with bypassed validation..."

# Run with patched solution
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -e NO_COLOR=1 \
    -e CRUSH_NO_SPINNER=1 \
    -e CI=1 \
    -t \
    crush-corporate:patched bash -c '
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

        # Test the patched Crush
        echo "=== Testing Crush with bypassed validation ==="
        cd /workspace

        echo "Running Crush with a simple prompt..."
        # The wrapper script sets the environment variables to disable spinner
        # But we also set them at container level for extra safety
        crush run "Say Hello from Crush Corporate Integration"
    '

print_success "Test completed!"

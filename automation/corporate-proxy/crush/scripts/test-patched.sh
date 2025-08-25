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
    crush-corporate:patched bash -c '
        # Start services
        python /app/mock_api.py > /dev/null 2>&1 &
        python /app/translation_wrapper.py > /dev/null 2>&1 &

        # Wait for services to start
        sleep 3

        # Test the patched Crush
        echo "=== Testing Crush with bypassed validation ==="
        cd /workspace

        echo "Running Crush with a simple prompt..."
        # Filter out the TTY error message while preserving the actual output
        crush run "Say Hello from Crush Corporate Integration" 2>&1 | grep -v "Error running spinner"
    '

print_success "Test completed!"

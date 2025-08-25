#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing with Config in Working Directory"

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Testing with config in working directory..."

# Run with config in working directory
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    crush-corporate:latest bash -c '
        # Copy config to working directory
        cp /root/.config/crush/crush.json /workspace/.crush.json

        # Start services in background
        python /app/mock_api.py > /dev/null 2>&1 &
        python /app/translation_wrapper.py > /dev/null 2>&1 &

        # Wait for services
        sleep 3

        # Check if config is there
        echo "=== Config files in working directory ==="
        ls -la /workspace/

        # Try running crush
        echo ""
        echo "=== Running crush ==="
        cd /workspace
        crush run "Say Hello from Crush Corporate Integration" 2>&1
    '

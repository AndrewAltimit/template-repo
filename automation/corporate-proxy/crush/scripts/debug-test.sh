#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Debug Test - Crush Config Loading"

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Testing config loading with debug mode..."

# Run with debug to see what's happening
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    crush-corporate:latest bash -c '
        echo "=== Checking config files ==="
        ls -la /root/.config/crush/
        echo ""
        echo "=== Config content ==="
        cat /root/.config/crush/crush.json
        echo ""
        echo "=== Testing crush with debug ==="
        crush -d run "test" 2>&1 | head -50
    '

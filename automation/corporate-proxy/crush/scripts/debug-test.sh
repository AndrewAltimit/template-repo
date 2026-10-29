#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Debug Test - Crush Config Loading"

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT/../.."

print_info "Checking the config baked into the image..."

# Inspect only: bypass the entrypoint so no services start
docker run --rm --entrypoint bash crush-corporate:latest -c '
    echo "=== Crush config (copied to ~/.config/crush/crush.json on first run) ==="
    cat /app/crush-config.json
'

print_info "Testing crush with debug output against the mock services..."

# The entrypoint (start-services.sh) starts the mock API and translation
# wrapper, then passes these arguments to crush.
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    crush-corporate:latest -d run "test" 2>&1 | head -50

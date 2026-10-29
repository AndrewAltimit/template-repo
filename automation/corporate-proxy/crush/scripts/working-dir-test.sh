#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing with Config in Working Directory"

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT/../.."

print_info "Testing with config in working directory..."

# Put the config in /workspace as .crush.json (the project-level config file),
# then hand off to the entrypoint, which starts the mock API and translation
# wrapper and runs crush with the given arguments.
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    --entrypoint bash \
    crush-corporate:latest -c '
        cp /app/crush-config.json /workspace/.crush.json

        echo "=== Config files in working directory ==="
        ls -la /workspace/

        echo ""
        echo "=== Running crush ==="
        cd /workspace
        exec /app/start-services.sh run "Say Hello from Crush Corporate Integration"
    '

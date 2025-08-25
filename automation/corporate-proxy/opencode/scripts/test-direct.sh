#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing OpenCode API Translation Directly"

# Build if needed
build_if_needed "opencode-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Testing direct API call to translation wrapper..."

# Test the translation wrapper directly
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    opencode-corporate:latest bash -c '
        # Start mock API in background
        python /app/mock_api.py > /dev/null 2>&1 &

        # Start translation wrapper in background
        python /app/translation_wrapper.py > /dev/null 2>&1 &

        # Wait for services to start
        sleep 3

        # Test direct API call
        echo "=== Testing direct API call ==="
        curl -s -X POST http://localhost:8052/v1/chat/completions \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer test-secret-token-123" \
            -d "{
                \"model\": \"openrouter/anthropic/claude-3.5-sonnet\",
                \"messages\": [{\"role\": \"user\", \"content\": \"Say hello from OpenCode Corporate Integration\"}],
                \"max_tokens\": 100
            }" | python -m json.tool | grep -o "\"content\":.*" | head -1
    '

print_success "Direct API test completed!"

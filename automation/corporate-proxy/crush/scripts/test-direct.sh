#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing Crush API Integration Directly"

# Check Docker
check_docker

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

print_info "Starting test container with services..."

# Start container with services in background
docker run -d --rm \
    --name crush-test-services \
    -p 8050:8050 \
    -p 8052:8052 \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    crush-corporate:latest

# Wait for services
wait_for_service "http://localhost:8050/health" 30 "Mock API"
wait_for_service "http://localhost:8052/health" 30 "Translation Wrapper"

print_info "Testing translation layer..."

# Test the API directly
RESPONSE=$(curl -s -X POST http://localhost:8052/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer test-secret-token-123" \
    -d '{
        "model": "company/claude-3.5-sonnet",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Say hello"}
        ],
        "max_tokens": 100
    }')

echo "Response from API:"
echo "$RESPONSE" | jq -r '.choices[0].message.content' 2>/dev/null || echo "$RESPONSE"

# Cleanup
print_info "Cleaning up..."
docker stop crush-test-services

print_header "Test Complete"
echo "Expected output: 'Hatsune Miku' (from mock API)"

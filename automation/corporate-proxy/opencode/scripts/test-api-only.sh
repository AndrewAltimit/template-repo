#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing OpenCode API Translation Layer"

print_info "Starting services in Docker..."

# Run a simple Python container with our services
docker run --rm \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -v "$SCRIPT_DIR/../../shared/services:/app:ro" \
    python:3.11-alpine sh -c '
        # Install dependencies
        pip install --quiet flask flask-cors requests

        # Start mock API in background
        python /app/mock_api.py > /dev/null 2>&1 &

        # Start translation wrapper in background
        python /app/translation_wrapper.py > /dev/null 2>&1 &

        # Wait for services to start
        sleep 3

        # Test direct API call
        echo "=== Testing OpenCode API translation ==="
        echo "Sending request to translation wrapper..."

        # Use Python to make the request and parse JSON
        python -c "
import requests
import json

response = requests.post(
    \"http://localhost:8052/v1/chat/completions\",
    headers={
        \"Content-Type\": \"application/json\",
        \"Authorization\": \"Bearer test-secret-token-123\"
    },
    json={
        \"model\": \"openrouter/anthropic/claude-3.5-sonnet\",
        \"messages\": [{\"role\": \"user\", \"content\": \"Say hello from OpenCode Corporate Integration\"}],
        \"max_tokens\": 100
    }
)

data = response.json()
if \"choices\" in data:
    print(\"Response:\", data[\"choices\"][0][\"message\"][\"content\"])
else:
    print(\"Error:\", data)
"
    '

print_success "API translation test completed!"

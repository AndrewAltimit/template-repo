#!/bin/bash
# Test script for the OpenCode proxy

echo "Testing OpenCode proxy..."

# Run the container with the proxy wrapper
docker run --rm \
    -e USE_PROXY=true \
    -e PROXY_MOCK_MODE=true \
    -v "$(pwd):/workspace" \
    openrouter-agents-proxy:test \
    bash -c '
        # Start the mock API
        python3 /workspace/automation/proxy/mock_company_api.py &
        MOCK_PID=$!

        # Wait for mock API
        sleep 2

        # Start the wrapper
        python3 /workspace/automation/proxy/api_translation_wrapper.py &
        WRAPPER_PID=$!

        # Wait for wrapper
        sleep 2

        # Test the proxy
        echo "Testing proxy endpoint..."
        curl -s -X POST http://localhost:8052/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"openrouter/anthropic/claude-3.5-sonnet\", \"messages\": [{\"role\": \"user\", \"content\": \"Test\"}]}" | \
            python3 -c "import sys, json; print(json.load(sys.stdin)[\"choices\"][0][\"message\"][\"content\"])"

        # Kill processes
        kill $MOCK_PID $WRAPPER_PID 2>/dev/null
    '

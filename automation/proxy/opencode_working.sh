#!/bin/bash
# Working OpenCode-like experience with proxy

echo "🚀 OpenCode Proxy Session"
echo "========================="
echo ""

MODE=${1:-interactive}

# Run in container with proxy
if [ -t 0 ]; then
    DOCKER_FLAGS="-it"
else
    DOCKER_FLAGS=""
fi

docker-compose run --rm $DOCKER_FLAGS openrouter-agents bash -c '
    # Install dependencies
    pip install --quiet --break-system-packages flask flask-cors requests

    # Start proxy services
    echo "🔧 Starting proxy services..."
    python /workspace/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
    python /workspace/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &

    # Wait for services
    sleep 3

    # Check if proxy is working
    if curl -s http://localhost:8052/health > /dev/null 2>&1; then
        echo "✅ Proxy is running!"
    else
        echo "❌ Proxy failed to start"
        exit 1
    fi

    echo ""
    echo "================================"
    echo "🎭 Proxy Mode Active"
    echo "All responses = \"Hatsune Miku\""
    echo "================================"
    echo ""

    if [ "'$MODE'" = "test" ]; then
        # Test mode - run a single query
        echo "Testing proxy with query: What is your name?"
        curl -s -X POST http://localhost:8052/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"claude-3.5-sonnet\", \"messages\": [{\"role\": \"user\", \"content\": \"What is your name?\"}]}" \
            | python -c "import sys, json; print(\"Response:\", json.load(sys.stdin)[\"choices\"][0][\"message\"][\"content\"])"
    else
        # Interactive mode - use Python wrapper
        echo "Starting interactive session..."
        echo "Type your questions and get responses!"
        echo "Type \"exit\" to quit"
        echo ""

        # Run the Python CLI wrapper
        python /workspace/automation/proxy/opencode_proxy_wrapper.py
    fi
'

echo ""
echo "Session ended."

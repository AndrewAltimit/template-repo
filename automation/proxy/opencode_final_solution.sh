#!/bin/bash
# Final solution for running OpenCode with company proxy

echo "🚀 OpenCode with Company Proxy - Final Solution"
echo "==============================================="
echo ""

# Check if services are already running on host
if curl -s http://localhost:8052/health > /dev/null 2>&1; then
    echo "✅ Proxy already running on host"
    PROXY_URL="http://host.docker.internal:8052/v1"
else
    echo "Starting proxy services in container..."
    PROXY_URL="http://localhost:8052/v1"
fi

# Run OpenCode in container
docker-compose run --rm \
    --add-host host.docker.internal:host-gateway \
    openrouter-agents bash -c "

    # If proxy not on host, start it in container
    if ! curl -s http://host.docker.internal:8052/health > /dev/null 2>&1; then
        echo '📦 Installing proxy dependencies...'
        pip install --quiet --break-system-packages flask flask-cors requests

        echo '🚀 Starting proxy services in container...'
        python /workspace/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
        python /workspace/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &
        sleep 3

        PROXY_URL='http://localhost:8052/v1'
    else
        PROXY_URL='http://host.docker.internal:8052/v1'
    fi

    echo '✅ Proxy available at: '\$PROXY_URL
    echo ''

    # Create a minimal config that hijacks OpenRouter
    cat > ~/.config/opencode/.opencode.json << EOF
{
  \"provider\": {
    \"openrouter\": {
      \"options\": {
        \"baseURL\": \"\$PROXY_URL\"
      }
    }
  }
}
EOF

    # Set environment to use "OpenRouter" (which now points to our proxy)
    export OPENROUTER_API_KEY=dummy-key-for-proxy

    echo '================================'
    echo '🎭 OpenCode Proxy Mode Active'
    echo 'All responses = \"Hatsune Miku\"'
    echo '================================'
    echo ''
    echo 'Run: opencode'
    echo 'Or: opencode run -q \"Your question\"'
    echo ''

    # Start interactive bash
    exec bash
" 2>&1 | grep -v "WARNING"

echo ""
echo "Session ended."

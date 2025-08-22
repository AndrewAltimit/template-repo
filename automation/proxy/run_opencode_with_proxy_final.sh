#!/bin/bash
# Final working script to run OpenCode with proxy

echo "🚀 OpenCode with Proxy Test"
echo "============================"
echo ""

# Check what mode we want
MODE=${1:-test}

if [ "$MODE" = "test" ]; then
    echo "Mode: Test proxy (quick verification)"
    echo ""

    # Quick test in container
    docker-compose run --rm python-ci bash -c "
        # Install deps
        pip install --quiet flask flask-cors requests

        # Start services
        python /app/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
        python /app/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &

        # Wait for startup
        sleep 3

        # Test the proxy
        echo '🧪 Testing proxy endpoint...'
        curl -s -X POST http://localhost:8052/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{\"model\": \"claude-3.5-sonnet\", \"messages\": [{\"role\": \"user\", \"content\": \"What is your name?\"}]}' \
            | python -c 'import sys, json; print(\"Response:\", json.load(sys.stdin)[\"choices\"][0][\"message\"][\"content\"])'

        echo ''
        echo 'If you see \"Hatsune Miku\" above, the proxy is working! ✅'
    " 2>&1 | grep -v "warning"

elif [ "$MODE" = "interactive" ]; then
    echo "Mode: Interactive OpenCode with proxy"
    echo ""

    # Interactive session with proxy
    docker-compose run --rm -it python-ci bash -c "
        # Install deps
        echo '📦 Installing dependencies...'
        pip install --quiet flask flask-cors requests

        # Install Node.js and npm if not present
        if ! command -v npm > /dev/null 2>&1; then
            echo '📦 Installing Node.js...'
            apt-get update > /dev/null 2>&1
            apt-get install -y nodejs npm > /dev/null 2>&1
        fi

        # Install OpenCode
        echo '📦 Installing OpenCode CLI...'
        npm install -g @sst/opencode

        # Start services
        python /app/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
        python /app/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &

        # Wait for startup
        sleep 3

        # Create config
        cat > /tmp/opencode-config.json << 'EOF'
{
  \"provider\": {
    \"company-ai\": {
      \"name\": \"Company AI\",
      \"api\": \"http://localhost:8052/v1\",
      \"env\": [\"COMPANY_API_KEY\"],
      \"models\": {
        \"claude-3.5-sonnet\": {
          \"name\": \"Claude 3.5 Sonnet\",
          \"limit\": {\"context\": 200000, \"output\": 8192}
        }
      },
      \"options\": {\"apiKey\": \"test\"}
    }
  },
  \"disabled_providers\": [\"openrouter\", \"anthropic\", \"openai\"],
  \"model\": \"company-ai/claude-3.5-sonnet\"
}
EOF

        export OPENCODE_CONFIG=/tmp/opencode-config.json
        export COMPANY_API_KEY=test

        echo '================================'
        echo 'Proxy is running!'
        echo 'All responses will be: Hatsune Miku'
        echo ''
        echo 'Starting OpenCode interactive session...'
        echo '================================'

        opencode
    "

else
    echo "Usage: $0 [test|interactive]"
    echo ""
    echo "  test         - Quick test of proxy (default)"
    echo "  interactive  - Interactive OpenCode session with proxy"
fi

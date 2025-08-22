#!/bin/bash
# Interactive OpenCode with proxy - using openrouter-agents container

echo "🚀 OpenCode Interactive Session with Proxy"
echo "=========================================="
echo ""
echo "📌 Mode: All responses will be 'Hatsune Miku'"
echo ""

# First, build the openrouter-agents container if needed
echo "🐳 Preparing container..."
docker-compose build openrouter-agents 2>/dev/null || true

# Run interactive session
docker-compose run --rm -it openrouter-agents bash -c '
    echo "📦 Installing proxy dependencies..."
    pip install --quiet --break-system-packages flask flask-cors requests

    echo "🚀 Starting proxy services..."

    # Start mock API
    python /workspace/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
    MOCK_PID=$!

    # Start translation wrapper
    python /workspace/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &
    WRAPPER_PID=$!

    # Wait for services
    sleep 3

    # Check services
    if curl -s http://localhost:8052/health > /dev/null 2>&1; then
        echo "✅ Proxy is running!"
    else
        echo "❌ Proxy failed to start"
        cat /tmp/wrapper.log 2>/dev/null | head -10
        exit 1
    fi

    # Create OpenCode config
    cat > /tmp/opencode-config.json << "EOF"
{
  "provider": {
    "company-ai": {
      "name": "Company AI",
      "api": "http://localhost:8052/v1",
      "env": ["COMPANY_API_KEY"],
      "models": {
        "claude-3.5-sonnet": {
          "name": "Claude 3.5 Sonnet",
          "attachment": true,
          "temperature": true,
          "tool_call": true,
          "limit": {"context": 200000, "output": 8192}
        }
      },
      "options": {"apiKey": "test"}
    }
  },
  "disabled_providers": ["openrouter", "anthropic", "openai"],
  "model": "company-ai/claude-3.5-sonnet"
}
EOF

    export OPENCODE_CONFIG=/tmp/opencode-config.json
    export COMPANY_API_KEY=test

    echo ""
    echo "================================"
    echo "🎭 Proxy Mode Active"
    echo "All responses = \"Hatsune Miku\""
    echo "================================"
    echo ""
    echo "Try: opencode run -q \"What is your name?\""
    echo "Or just type: opencode"
    echo ""

    # Start bash session
    exec bash
'

echo ""
echo "Session ended."

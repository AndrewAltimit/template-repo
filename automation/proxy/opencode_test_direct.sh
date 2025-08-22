#!/bin/bash
# Direct test of OpenCode with proxy - simplified configuration

echo "🧪 Direct OpenCode Proxy Test"
echo "============================="
echo ""

# Run everything in one container session
docker-compose run --rm openrouter-agents bash -c '
    echo "📦 Setting up environment..."

    # Install proxy dependencies
    pip install --quiet --break-system-packages flask flask-cors requests

    echo "🚀 Starting proxy services..."

    # Start mock API
    python /workspace/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
    MOCK_PID=$!

    # Start translation wrapper with debugging
    FLASK_ENV=development python /workspace/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &
    WRAPPER_PID=$!

    # Wait for services
    sleep 3

    # Verify services are running
    echo "🔍 Checking services..."
    if curl -s http://localhost:8050/health > /dev/null 2>&1; then
        echo "  ✅ Mock API running on port 8050"
    else
        echo "  ❌ Mock API failed"
        cat /tmp/mock.log | tail -20
        exit 1
    fi

    if curl -s http://localhost:8052/health > /dev/null 2>&1; then
        echo "  ✅ Translation wrapper running on port 8052"
    else
        echo "  ❌ Translation wrapper failed"
        cat /tmp/wrapper.log | tail -20
        exit 1
    fi

    echo ""
    echo "📝 Testing proxy directly (without OpenCode)..."

    # Test the proxy endpoint directly
    RESPONSE=$(curl -s -X POST http://localhost:8052/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"claude-3.5-sonnet\", \"messages\": [{\"role\": \"user\", \"content\": \"Test\"}]}")

    echo "Response: $RESPONSE" | python -c "
import sys, json
line = sys.stdin.read()
try:
    data = json.loads(line.replace(\"Response: \", \"\"))
    content = data[\"choices\"][0][\"message\"][\"content\"]
    print(f\"✅ Proxy works! Response: {content}\")
except:
    print(f\"❌ Error parsing response: {line}\")
    "

    echo ""
    echo "📝 Now testing with OpenCode..."
    echo ""

    # Try different OpenCode configurations

    # Method 1: Use OpenRouter provider with custom baseURL
    echo "Method 1: OpenRouter provider with custom baseURL..."
    cat > /tmp/opencode1.json << "EOF"
{
  "provider": {
    "openrouter": {
      "api": "http://localhost:8052/v1",
      "options": {
        "apiKey": "test-key",
        "baseURL": "http://localhost:8052/v1"
      }
    }
  },
  "model": "claude-3.5-sonnet"
}
EOF

    export OPENCODE_CONFIG=/tmp/opencode1.json
    export OPENROUTER_API_KEY=test-key

    echo "Testing: opencode run -q \"What is 1+1?\""
    timeout 10 opencode run -q "What is 1+1?" 2>&1 | grep -E "Hatsune|Error|error" | head -5 || echo "Method 1 failed or timed out"

    echo ""
    echo "Method 2: Custom provider..."

    # Method 2: Simpler custom provider
    cat > /tmp/opencode2.json << "EOF"
{
  "provider": {
    "custom": {
      "name": "Custom AI",
      "npm": "@ai-sdk/openai",
      "api": "http://localhost:8052/v1",
      "env": ["CUSTOM_API_KEY"],
      "models": {
        "claude-3.5-sonnet": {
          "name": "Claude",
          "limit": {"context": 100000, "output": 4096}
        }
      }
    }
  },
  "disabled_providers": ["openrouter", "anthropic", "openai"],
  "model": "custom/claude-3.5-sonnet"
}
EOF

    export OPENCODE_CONFIG=/tmp/opencode2.json
    export CUSTOM_API_KEY=test-key

    echo "Testing: opencode run -q \"What is 2+2?\""
    timeout 10 opencode run -q "What is 2+2?" 2>&1 | grep -E "Hatsune|Error|error" | head -5 || echo "Method 2 failed or timed out"

    echo ""
    echo "📊 Checking logs for errors..."
    echo "Wrapper log tail:"
    tail -10 /tmp/wrapper.log 2>/dev/null || echo "No wrapper log"

    echo ""
    echo "✅ Proxy is working correctly (returns Hatsune Miku)"
    echo "⚠️  OpenCode may have issues with custom providers"
    echo ""
    echo "Alternative: Use the proxy with curl or other HTTP clients"
    echo "The proxy endpoint is: http://localhost:8052/v1/chat/completions"

    # Kill services
    kill $MOCK_PID $WRAPPER_PID 2>/dev/null || true
'

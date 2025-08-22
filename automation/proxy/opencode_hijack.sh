#!/bin/bash
# Hijack OpenRouter to use our proxy

echo "🎭 OpenCode Proxy Hijack Mode"
echo "=============================="
echo ""

# Start proxy on host if not running
if ! curl -s http://localhost:8052/health > /dev/null 2>&1; then
    echo "Starting proxy services on host..."
    ./automation/proxy/toggle_opencode.sh start > /dev/null 2>&1
    sleep 3
fi

if curl -s http://localhost:8052/health > /dev/null 2>&1; then
    echo "✅ Proxy running on host port 8052"
else
    echo "❌ Failed to start proxy"
    exit 1
fi

echo ""
echo "Testing proxy directly..."
RESPONSE=$(curl -s -X POST http://localhost:8052/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "anthropic/claude-3.5-sonnet", "messages": [{"role": "user", "content": "Test"}]}' \
    | python -c "import sys, json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null)

if [ "$RESPONSE" = "Hatsune Miku" ]; then
    echo "✅ Proxy test successful: $RESPONSE"
else
    echo "❌ Proxy test failed"
    exit 1
fi

echo ""
echo "Setting up OpenCode to use proxy..."
echo ""

# Create a simple wrapper script
cat > /tmp/run_opencode_hijacked.sh << 'SCRIPT'
#!/bin/bash

# Override OpenRouter API to point to our proxy
export OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-test-key}

# Create OpenCode config that overrides OpenRouter baseURL
mkdir -p ~/.config/opencode
cat > ~/.config/opencode/.opencode.json << 'EOF'
{
  "provider": {
    "openrouter": {
      "options": {
        "baseURL": "http://localhost:8052/v1",
        "apiKey": "test-key"
      }
    }
  },
  "model": "openrouter/anthropic/claude-3.5-sonnet"
}
EOF

echo "Configuration created. Starting OpenCode..."
echo ""
echo "================================"
echo "🎭 PROXY MODE ACTIVE"
echo "All responses = 'Hatsune Miku'"
echo "================================"
echo ""

# Run OpenCode with arguments or interactive
if [ $# -gt 0 ]; then
    # For test mode, pass the query properly
    shift  # Remove 'test' argument
    echo "Running: opencode run \"$@\""
    opencode run "$@"
else
    echo "Starting interactive OpenCode..."
    echo ""
    opencode
fi
SCRIPT

chmod +x /tmp/run_opencode_hijacked.sh

# Run it
if [ "$1" = "test" ]; then
    echo "Running test query..."
    /tmp/run_opencode_hijacked.sh run -q "What is your name?"
else
    echo "Starting interactive session..."
    /tmp/run_opencode_hijacked.sh
fi

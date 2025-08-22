#!/bin/bash
# Test OpenCode with the proxy using proper configuration

echo "🔧 Testing Real OpenCode with Proxy"
echo "===================================="
echo ""

# First ensure npm package is installed
echo "📦 Ensuring @ai-sdk/openai-compatible is available..."
docker-compose run --rm openrouter-agents bash -c '
    npm list @ai-sdk/openai-compatible > /dev/null 2>&1 || npm install @ai-sdk/openai-compatible
' > /dev/null 2>&1

# Now run the actual test
docker-compose run --rm openrouter-agents bash -c '
    # Install proxy dependencies
    pip install --quiet --break-system-packages flask flask-cors requests

    # Start proxy services
    echo "🚀 Starting proxy services..."
    python /workspace/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
    MOCK_PID=$!

    python /workspace/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &
    WRAPPER_PID=$!

    # Wait for services
    sleep 3

    # Check services
    if ! curl -s http://localhost:8052/health > /dev/null 2>&1; then
        echo "❌ Proxy failed to start"
        cat /tmp/wrapper.log | tail -20
        exit 1
    fi

    echo "✅ Proxy is running"
    echo ""

    # Copy the working config
    cp /workspace/automation/proxy/opencode-config-working.json /tmp/opencode-config.json

    # Set environment variables
    export OPENCODE_CONFIG=/tmp/opencode-config.json
    export OPENROUTER_API_KEY=test-key-for-proxy

    echo "📝 Testing OpenCode with command: opencode run -q \"What is your name?\""
    echo "Expected: Should return \"Hatsune Miku\""
    echo ""

    # Run OpenCode with debug output
    timeout 15 opencode run -q "What is your name?" 2>&1 | tee /tmp/opencode.log | grep -E "Hatsune|Error|error|Provider" | head -10

    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 124 ]; then
        echo ""
        echo "⏱️  OpenCode timed out (15 seconds)"
        echo ""
        echo "Last logs from OpenCode:"
        tail -20 /tmp/opencode.log 2>/dev/null
        echo ""
        echo "Wrapper logs:"
        tail -10 /tmp/wrapper.log 2>/dev/null
    elif grep -q "Hatsune Miku" /tmp/opencode.log 2>/dev/null; then
        echo ""
        echo "✅ SUCCESS! OpenCode returned \"Hatsune Miku\""
        echo "The proxy is working with OpenCode!"
    else
        echo ""
        echo "❌ OpenCode did not return expected response"
        echo ""
        echo "OpenCode output:"
        cat /tmp/opencode.log 2>/dev/null | head -30
        echo ""
        echo "Wrapper logs:"
        tail -10 /tmp/wrapper.log 2>/dev/null
    fi

    # Cleanup
    kill $MOCK_PID $WRAPPER_PID 2>/dev/null || true
'

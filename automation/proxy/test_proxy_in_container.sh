#!/bin/bash
# Simple test of proxy services in a container

echo "Testing proxy services in container..."

# Create a test script that runs inside container
cat > /tmp/test_proxy.sh << 'EOF'
#!/bin/bash
set -e

echo "📦 Installing requirements..."
pip install --quiet flask flask-cors requests 2>/dev/null || pip3 install --quiet flask flask-cors requests

echo "🚀 Starting proxy services..."

# The volume mount puts files in /app not /workspace for python-ci container
# Start mock API in background
python3 /app/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &
MOCK_PID=$!

# Start translation wrapper in background
python3 /app/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &
WRAPPER_PID=$!

echo "⏳ Waiting for services to start..."
sleep 5

echo "🧪 Testing proxy endpoint..."

# First check if services are running
if curl -s http://localhost:8050/health > /dev/null 2>&1; then
    echo "✓ Mock API is running"
else
    echo "✗ Mock API failed to start"
    cat /tmp/mock.log 2>/dev/null || echo "No log file"
fi

if curl -s http://localhost:8052/health > /dev/null 2>&1; then
    echo "✓ Translation wrapper is running"
else
    echo "✗ Translation wrapper failed to start"
    cat /tmp/wrapper.log 2>/dev/null || echo "No log file"
fi

# Now test the actual endpoint
echo "Testing chat completion..."
RESPONSE=$(curl -s -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 50}')

if [ -n "$RESPONSE" ]; then
    echo "$RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print('Response:', data.get('choices', [{}])[0].get('message', {}).get('content', 'ERROR'))" 2>/dev/null || echo "Response parsing failed: $RESPONSE"
else
    echo "No response received"
fi

echo ""
echo "🛑 Stopping services..."
kill $MOCK_PID $WRAPPER_PID 2>/dev/null || true

echo "✅ Test complete!"
EOF

chmod +x /tmp/test_proxy.sh

# Run in the python-ci container which already exists
docker-compose run --rm \
  -v /tmp/test_proxy.sh:/tmp/test_proxy.sh \
  python-ci \
  bash /tmp/test_proxy.sh

rm -f /tmp/test_proxy.sh

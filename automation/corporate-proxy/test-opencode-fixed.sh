#!/bin/bash
set -e

echo "========================================"
echo "OpenCode Fixed Test"
echo "========================================"

# Start services using the fixed mock API
echo "Starting fixed services..."
./opencode/scripts/start-services-fixed.sh

sleep 2

# Create test directory
TEST_DIR=$(mktemp -d /tmp/opencode-fixed-XXXXXX)
LOG_DIR="$TEST_DIR/logs"
mkdir -p "$LOG_DIR"
echo "Test directory: $TEST_DIR"

# Copy mock API log for debugging
cp /tmp/opencode-logs/mock_api.log "$LOG_DIR/" 2>/dev/null || true

# Test 1: Test direct API with proper format
echo ""
echo "Test 1: Testing direct API with OpenAI format..."
curl -s -X POST http://localhost:8052/v1/chat/completions \
  -H "Authorization: Bearer test-secret-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write a file called test.txt with Hello World"}],
    "model": "gpt-4",
    "tools": [{
      "type": "function",
      "function": {
        "name": "write",
        "description": "Write to a file",
        "parameters": {
          "type": "object",
          "properties": {
            "filePath": {"type": "string"},
            "content": {"type": "string"}
          }
        }
      }
    }]
  }' | jq -r '.choices[0].message.tool_calls[0] | "Tool: \(.function.name), Args: \(.function.arguments)"' || echo "No tool call in response"

# Test 2: Run OpenCode with the fixed API
echo ""
echo "Test 2: Running OpenCode with fixed API..."
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$TEST_DIR:/workspace" \
    -v "$LOG_DIR:/tmp/logs" \
    -e HOME=/tmp \
    -e OPENROUTER_API_KEY="test-secret-token-123" \
    -e OPENROUTER_BASE_URL="http://host.docker.internal:8052/v1" \
    --add-host=host.docker.internal:host-gateway \
    opencode-corporate:latest bash -c "cd /workspace && /usr/local/bin/opencode.bin run 'Write a file called hello.txt with content Hello OpenCode'" 2>&1 | tee "$LOG_DIR/opencode.log"

# Check results
echo ""
echo "Checking for created files..."
if [ -f "$TEST_DIR/hello.txt" ]; then
    echo "✅ SUCCESS: File created by OpenCode!"
    echo "Content: $(cat $TEST_DIR/hello.txt)"
else
    echo "❌ FAILED: File not created"
    echo ""
    echo "Checking OpenCode log for errors..."
    grep -i "error\|invalid\|fail" "$LOG_DIR/opencode.log" | head -5 || true
fi

echo ""
echo "Mock API log (last 20 lines):"
tail -20 /tmp/opencode-logs/mock_api.log | grep -E "TOOL|Tool|tool_calls|function|ERROR" || echo "No relevant log entries"

echo ""
echo "Directory contents:"
ls -la "$TEST_DIR/"

# Cleanup
echo ""
echo "Stopping services..."
pkill -f "mock_api_opencode_fixed.py" || true
pkill -f "translation_wrapper_with_tools.py" || true

echo "Test complete!"

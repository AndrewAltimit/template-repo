#!/bin/bash
set -e

echo "========================================"
echo "Testing Direct API Call vs Container"
echo "========================================"

# Kill any existing services
lsof -i :8050 | grep -v PID | awk '{print $2}' | xargs -r kill 2>/dev/null || true
lsof -i :8052 | grep -v PID | awk '{print $2}' | xargs -r kill 2>/dev/null || true
sleep 1

# Start v2 mock API with debug logging
echo "Starting v2 mock API with debug logging..."
cd /home/miku/Documents/repos/template-repo/automation/corporate-proxy
FLASK_DEBUG=false python3 shared/services/mock_api_with_tools_v2.py > /tmp/mock_api.log 2>&1 &
MOCK_PID=$!

# Start translation wrapper
echo "Starting translation wrapper..."
python3 shared/services/translation_wrapper_with_tools.py > /tmp/wrapper.log 2>&1 &
WRAPPER_PID=$!

sleep 2

# Test 1: Direct API call to mock API
echo ""
echo "Test 1: Direct call to mock API (port 8050)"
echo "=========================================="
curl -s -X POST http://localhost:8050/api/v1/AI/GenAIExplorationLab/Models/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-secret-token-123" \
  -d '{"messages":[{"role":"user","content":"Create a file called output.txt"}],"tools":[{"type":"function","function":{"name":"write"}}]}' \
  | python3 -m json.tool | grep -A5 "tool_calls" || echo "No tool detected"

# Test 2: Call through translation wrapper
echo ""
echo "Test 2: Call through translation wrapper (port 8052)"
echo "=========================================="
curl -s -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"Create a file called output.txt"}],"tools":[{"type":"function","function":{"name":"write"}}]}' \
  | python3 -m json.tool | grep -A5 "tool_calls" || echo "No tool detected"

# Test 3: Simulate what Crush sends
echo ""
echo "Test 3: Simulating Crush request format"
echo "=========================================="
# Crush typically sends a system message followed by user message
curl -s -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "system", "content": "You are a helpful AI assistant"},
      {"role": "user", "content": "Create a file called output.txt"}
    ],
    "tools": [{"type": "function", "function": {"name": "write", "description": "Write to a file"}}],
    "stream": false
  }' \
  | python3 -m json.tool | grep -A5 "tool_calls" || echo "No tool detected"

echo ""
echo "Checking logs for pattern matching..."
echo "=========================================="
echo "Mock API log (last 20 lines):"
tail -20 /tmp/mock_api.log | grep -E "(Analyzing message|Matched tool|No tool patterns|TOOL DETECTED)" || true

echo ""
echo "Wrapper log (last 10 lines):"
tail -10 /tmp/wrapper.log | grep -E "(Received request|Forwarding|Company API response)" || true

# Cleanup
kill $MOCK_PID $WRAPPER_PID 2>/dev/null || true

echo ""
echo "Test complete"

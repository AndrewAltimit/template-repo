#!/bin/bash
# Test the tool call flow with mock requests
# This simulates what Crush/OpenCode would send and verifies the response format

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "======================================"
echo "Testing Tool Call Flow"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to pretty-print JSON
pretty_json() {
    python3 -m json.tool 2>/dev/null || cat
}

# Function to test tool call response
test_tool_call() {
    local service_name=$1
    local port=$2
    local endpoint=$3
    local request_body=$4

    echo -e "${YELLOW}Testing $service_name on port $port${NC}"
    echo "Request:"
    echo "$request_body" | pretty_json
    echo ""

    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer test-secret-token-123" \
        -d "$request_body" \
        "http://localhost:$port$endpoint")

    echo "Response:"
    echo "$response" | pretty_json
    echo ""

    # Check if response contains tool_calls
    if echo "$response" | grep -q "tool_calls"; then
        echo -e "${GREEN}✓ Tool call detected in response${NC}"

        # Extract tool name and arguments
        tool_name=$(echo "$response" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data['tool_calls'][0]['function']['name'])" 2>/dev/null || echo "unknown")
        tool_args=$(echo "$response" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data['tool_calls'][0]['function']['arguments'])" 2>/dev/null || echo "{}")

        echo "  Tool: $tool_name"
        echo "  Arguments: $tool_args"
        return 0
    else
        echo -e "${RED}✗ No tool call in response${NC}"
        return 1
    fi
}

# Test 1: Direct mock API with tools
echo "======================================"
echo "Test 1: Mock API with Tool Support"
echo "======================================"

# Start the mock API with tools
echo "Starting mock API with tool support..."
python3 "$SCRIPT_DIR/shared/services/mock_api_with_tools.py" > /tmp/mock_api_test.log 2>&1 &
MOCK_PID=$!

# Wait for service to start
sleep 3

# Prepare request with tools
request_with_tools='{
  "messages": [
    {"role": "user", "content": "Create a file called test.txt with the content Hello World"}
  ],
  "tools": [
    {
      "function": {
        "name": "write",
        "description": "Write content to a file",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"}
          },
          "required": ["file_path", "content"]
        }
      }
    }
  ],
  "max_tokens": 1000
}'

if test_tool_call "Mock API" 8050 "/api/v1/AI/GenAIExplorationLab/Models/test" "$request_with_tools"; then
    echo -e "${GREEN}✓ Mock API test passed${NC}"
else
    echo -e "${RED}✗ Mock API test failed${NC}"
fi

# Stop mock API
kill $MOCK_PID 2>/dev/null || true

echo ""
echo "======================================"
echo "Test 2: Translation Wrapper with Tools"
echo "======================================"

# Start both services
echo "Starting services..."
python3 "$SCRIPT_DIR/shared/services/mock_api_with_tools.py" > /tmp/mock_api_test.log 2>&1 &
MOCK_PID=$!
sleep 2

python3 "$SCRIPT_DIR/shared/services/translation_wrapper_with_tools.py" > /tmp/wrapper_test.log 2>&1 &
WRAPPER_PID=$!
sleep 2

# OpenAI format request
openai_request='{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "List files in the current directory"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "ls",
        "description": "List files",
        "parameters": {
          "type": "object",
          "properties": {
            "path": {"type": "string"}
          }
        }
      }
    }
  ],
  "max_tokens": 1000
}'

# Test translation wrapper
response=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$openai_request" \
    "http://localhost:8052/v1/chat/completions")

echo "OpenAI Format Response:"
echo "$response" | pretty_json
echo ""

# Check response format
if echo "$response" | grep -q "tool_calls"; then
    echo -e "${GREEN}✓ Translation wrapper returns proper OpenAI format with tool calls${NC}"
else
    echo -e "${RED}✗ Translation wrapper failed to return tool calls${NC}"
fi

# Cleanup
kill $MOCK_PID 2>/dev/null || true
kill $WRAPPER_PID 2>/dev/null || true

echo ""
echo "======================================"
echo "Test 3: Tool Parameter Extraction"
echo "======================================"

# Test the pattern matching for different tool requests
test_patterns() {
    local message=$1
    local expected_tool=$2

    echo "Testing: \"$message\""

    # Start mock API
    python3 "$SCRIPT_DIR/shared/services/mock_api_with_tools.py" > /tmp/mock_api_test.log 2>&1 &
    local pid=$!
    sleep 2

    request=$(cat <<EOF
{
  "messages": [{"role": "user", "content": "$message"}],
  "tools": [
    {"function": {"name": "ls"}},
    {"function": {"name": "view"}},
    {"function": {"name": "write"}},
    {"function": {"name": "bash"}},
    {"function": {"name": "grep"}},
    {"function": {"name": "edit"}}
  ]
}
EOF
)

    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer test-secret-token-123" \
        -d "$request" \
        "http://localhost:8050/api/v1/AI/GenAIExplorationLab/Models/test")

    detected_tool=$(echo "$response" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('tool_calls', [{}])[0].get('function', {}).get('name', 'none'))" 2>/dev/null || echo "error")

    if [ "$detected_tool" = "$expected_tool" ]; then
        echo -e "  ${GREEN}✓ Correctly detected: $detected_tool${NC}"
    else
        echo -e "  ${RED}✗ Expected $expected_tool but got $detected_tool${NC}"
    fi

    kill $pid 2>/dev/null || true
    sleep 1
}

test_patterns "List files in current directory" "ls"
test_patterns "Show me what files are here" "ls"
test_patterns "View the README.md file" "view"
test_patterns "Create a file called hello.txt with content Test" "write"
test_patterns "Run the command ls -la" "bash"
test_patterns "Search for TODO in all files" "grep"
test_patterns "Edit the config.json file" "edit"

echo ""
echo "======================================"
echo "Summary"
echo "======================================"
echo ""
echo "The tool call flow is working if:"
echo "1. Mock API returns tool_calls when it detects tool patterns"
echo "2. Translation wrapper properly forwards tools and converts responses"
echo "3. Pattern matching correctly identifies tool requests"
echo ""
echo "Check logs for details:"
echo "  /tmp/mock_api_test.log"
echo "  /tmp/wrapper_test.log"

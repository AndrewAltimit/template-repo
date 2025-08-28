# Corporate Proxy Tool Execution Fix

## Problem
Crush and OpenCode tools (ls, view, write, etc.) were not executing when used through the corporate proxy. The tools would display in white text (indicating they were being triggered) but then hang without executing.

## Root Cause Analysis

### Tool Execution Flow
1. **Normal Flow (with real API)**:
   - Crush/OpenCode sends available tools + messages to the API
   - API decides which tool to call and returns a `tool_call` response
   - Crush/OpenCode executes the tool locally
   - Crush/OpenCode sends tool results back to the API
   - API continues with the response

2. **Broken Flow (with corporate proxy)**:
   - Crush/OpenCode sends tools + messages to translation wrapper
   - Translation wrapper strips tools and only forwards messages
   - Mock API always returns "Hatsune Miku" (no tool calls)
   - Crush/OpenCode waits forever for a tool call that never comes
   - **Result: Hang**

### Specific Issues
1. **Mock API**: Always returned plain text, never tool calls
2. **Translation Wrapper**: Didn't forward tools or handle tool call responses
3. **Format Mismatch**: Company API format doesn't match OpenAI tool format

## Solution

### 1. Enhanced Mock API (`mock_api_with_tools.py`)
- Detects tool requests in messages using regex patterns
- Extracts tool parameters from natural language
- Returns properly formatted tool call responses
- Handles common tools: ls, view, write, bash, grep, edit

### 2. Enhanced Translation Wrapper (`translation_wrapper_with_tools.py`)
- Forwards tool definitions to the Company API
- Handles tool call responses from the API
- Converts tool results back to the expected format
- Supports both streaming and non-streaming responses

### 3. Smart Fallback in Start Scripts
Both services use a fallback mechanism:
```bash
if [ -f /app/mock_api_with_tools.py ]; then
    python /app/mock_api_with_tools.py > /tmp/logs/mock_api.log 2>&1 &
else
    python /app/mock_api.py > /tmp/logs/mock_api.log 2>&1 &
fi
```

This ensures backward compatibility while enabling tool support when available.

## Files Modified

### New Files
- `shared/services/mock_api_with_tools.py` - Mock API with tool detection
- `shared/services/translation_wrapper_with_tools.py` - Translation with tool support
- `test-tool-execution.sh` - Test script for tool execution

### Updated Files
- `crush/scripts/start-services.sh` - Use tool-enabled services
- `opencode/scripts/start-services.sh` - Use tool-enabled services
- `crush/docker/Dockerfile` - Copy new service files
- `opencode/docker/Dockerfile` - Copy new service files

## Tool Detection Logic

The mock API detects tool requests using patterns:
- **ls**: "list", "show files", "what files"
- **view**: "view", "read", "show", "cat" + filename
- **write**: "write", "create", "save" + filename
- **bash**: "run", "execute", "command"
- **grep**: "grep", "search", "find"
- **edit**: "edit", "modify", "change" + filename

## Testing

### Manual Testing
```bash
# Test tool execution
./automation/corporate-proxy/test-tool-execution.sh

# Test individual tools
./crush/scripts/run.sh run "List files in current directory"
./crush/scripts/run.sh run "Create a file called test.txt with content 'Hello'"
./crush/scripts/run.sh run "View README.md"

./opencode/scripts/run.sh run "Show me what files are here"
./opencode/scripts/run.sh run "Write 'Hello World' to hello.txt"
```

### Debugging
If tools still hang, check logs inside the container:
```bash
# In a running container
cat /tmp/logs/mock_api.log
cat /tmp/logs/translation_wrapper.log
```

## Response Format

### Tool Call Response (OpenAI Format)
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "toolu_123",
        "type": "function",
        "function": {
          "name": "write",
          "arguments": "{\"file_path\":\"test.txt\",\"content\":\"Hello\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

### Tool Result Format
```json
{
  "role": "tool",
  "content": "File created successfully",
  "tool_call_id": "toolu_123"
}
```

## Limitations

1. **Pattern Matching**: Tool detection uses regex patterns, not true AI understanding
2. **Parameter Extraction**: Simple heuristics for extracting parameters from natural language
3. **Mock Only**: This fix only works with the mock API, not real Company API
4. **Limited Tools**: Only common tools are detected (ls, view, write, bash, grep, edit)

## Future Improvements

1. **Real API Integration**: Extend Company API to support tool calls natively
2. **Better Detection**: Use NLP or a small model for better tool detection
3. **More Tools**: Add support for more Crush/OpenCode tools
4. **Tool Chaining**: Support multiple tool calls in sequence
5. **Error Handling**: Better error messages when tools fail

## Important Notes

- Both permission fixes (UID) and tool execution fixes are needed for full functionality
- The tool-enabled services are backward compatible with non-tool requests
- Logs are crucial for debugging - always check `/tmp/logs/` in containers
- The mock API now returns contextual responses instead of always "Hatsune Miku"

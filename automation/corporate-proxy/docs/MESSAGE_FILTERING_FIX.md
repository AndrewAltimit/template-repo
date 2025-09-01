# Message Filtering Fix for Company API Compatibility

## Problem

When OpenCode sends conversation history back to the company API, it includes `tool_calls` fields in assistant messages. The company API doesn't support these fields and rejects the request.

### Example of Rejected Request
```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [  // ❌ Company API doesn't support this
        {
          "id": "call_0",
          "type": "function",
          "function": {
            "name": "write",
            "arguments": "{\"filePath\":\"hello.md\",\"content\":\"hello\"}"
          }
        }
      ]
    }
  ]
}
```

## Root Cause

OpenCode follows the OpenAI API format which includes:
- `tool_calls` array in assistant messages when tools are invoked
- `cache_control` fields for optimization
- `tool` role for tool execution results

The company API only supports basic message formats with `role` and `content` fields.

## Solution Implemented

### Message Filtering Logic

The translation wrapper now filters messages before sending to the company API:

1. **Remove `tool_calls` field**: Strip from all assistant messages
2. **Convert empty content**: If a message has `tool_calls` but no content, generate descriptive text
3. **Convert tool messages**: Change `role: "tool"` to `role: "user"` with "Tool result: " prefix
4. **Remove cache_control**: Strip any cache optimization fields
5. **Handle system messages**: Extract separately (not in messages array)

### Transformation Examples

#### Before (from OpenCode):
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [{"function": {"name": "write"}}]
}
```

#### After (to Company API):
```json
{
  "role": "assistant",
  "content": "[Calling write tool]"
}
```

#### Tool Result Before:
```json
{
  "role": "tool",
  "content": "File written successfully"
}
```

#### Tool Result After:
```json
{
  "role": "user",
  "content": "Tool result: File written successfully"
}
```

## Implementation Details

The filtering happens in `translation_wrapper.py` when processing messages:

```python
# Filter out tool_calls from messages sent to company API
if "tool_calls" in msg:
    # Convert to text if no content
    content = msg.get("content", "")
    if not content and msg.get("tool_calls"):
        # Generate descriptive text
        tool_descriptions = []
        for tc in msg["tool_calls"]:
            if tc.get("function"):
                func = tc["function"]
                tool_descriptions.append(f"[Calling {func.get('name')} tool]")
        content = " ".join(tool_descriptions)

    # Add message without tool_calls field
    user_messages.append({"role": msg["role"], "content": content})
```

## Benefits

1. **Company API Compatibility**: Requests are now accepted without validation errors
2. **Conversation Preservation**: Tool invocations are represented as text
3. **Clean History**: No unsupported fields in message history
4. **Tool Context**: Users can still see what tools were called

## Testing

Comprehensive tests verify:
- Tool_calls are removed from assistant messages
- Empty content is replaced with tool descriptions
- Tool messages are converted to user messages
- System messages are handled separately
- Normal messages are preserved unchanged
- Complex conversations work correctly

## Result

The company API now accepts all requests from OpenCode, enabling:
- Proper conversation flow with tool usage
- Multiple rounds of tool invocations
- Clean message history without errors

# Streaming Tool Calls Fix for OpenCode Corporate Proxy

## Problem

The OpenCode corporate proxy was failing with type validation errors when processing streaming responses containing tool calls. The error indicated that each tool call in a streaming response's `delta` field was missing the required `index` field.

### Error Details
```
AI_TypeValidationError: Type validation failed
Error: Invalid input: expected number, received undefined
Path: ["choices",0,"delta","tool_calls",0,"index"]
```

## Root Cause

The OpenAI API specification requires different formats for tool calls in streaming vs non-streaming responses:

### Non-Streaming Format
```json
{
  "choices": [{
    "message": {
      "tool_calls": [
        {"id": "call_0", "type": "function", "function": {...}}
      ]
    }
  }]
}
```

### Streaming Format (SSE chunks)
```json
{
  "choices": [{
    "delta": {
      "tool_calls": [
        {"index": 0, "id": "call_0", "type": "function", "function": {...}}
      ]
    }
  }]
}
```

The key difference: **streaming tool calls require an `index` field**.

## Solution Implemented

### 1. Enhanced Tool Call Formatting
Updated `format_tool_calls_for_openai()` to accept a `streaming` parameter:
```python
def format_tool_calls_for_openai(tool_calls, streaming=False):
    formatted_calls = []
    for i, call in enumerate(tool_calls):
        formatted_call = {
            "id": f"call_{i}",
            "type": "function",
            "function": {...}
        }
        # Add index for streaming responses
        if streaming:
            formatted_call["index"] = i
        formatted_calls.append(formatted_call)
    return formatted_calls
```

### 2. Improved Streaming Response Generation
Changed streaming response to:
1. Send an initial chunk with the assistant role
2. Send each tool call as a separate chunk (proper SSE format)
3. Include the `index` field in each tool call
4. Send a final chunk with finish_reason

### 3. Proper SSE Chunk Sequencing
```python
# Initial chunk
{"delta": {"role": "assistant"}, "finish_reason": None}

# Tool call chunks (one per tool)
{"delta": {"tool_calls": [{"index": 0, "id": "call_0", ...}]}, "finish_reason": None}
{"delta": {"tool_calls": [{"index": 1, "id": "call_1", ...}]}, "finish_reason": None}

# Final chunk
{"delta": {}, "finish_reason": "tool_calls"}
```

## Benefits

1. **OpenCode Compatibility**: Streaming responses now pass OpenCode's type validation
2. **Proper SSE Format**: Each tool call is sent as a separate chunk per OpenAI spec
3. **Incremental Updates**: Clients can process tool calls as they arrive
4. **Error Prevention**: Index field ensures proper tool call ordering

## Testing

Added comprehensive tests in `test_streaming_tool_calls.py`:
- Verifies index field presence in streaming mode
- Confirms index field absence in non-streaming mode
- Validates SSE chunk structure
- Tests argument JSON encoding
- Handles edge cases (empty tool calls)

## Usage

The fix is automatic - the translation wrapper detects streaming mode and formats accordingly:
```python
# Automatically handled based on request
if data.get("stream", False):
    tool_calls = format_tool_calls_for_openai(parsed_calls, streaming=True)
else:
    tool_calls = format_tool_calls_for_openai(parsed_calls, streaming=False)
```

## Compatibility

This fix maintains backward compatibility:
- Non-streaming responses unchanged
- Streaming responses now conform to OpenAI API v1 specification
- Works with OpenCode, Continue.dev, and other OpenAI-compatible clients

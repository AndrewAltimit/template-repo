# OpenCode API Response Format Requirements

## Overview
The OpenCode CLI expects specific JSON response formats that must be strictly adhered to for proper functionality. This document outlines the exact format requirements for both standard responses and tool-enabled responses, compatible with the OpenRouter API format.

## Standard Response Format

### Basic Structure
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "qwen/qwen-2.5-coder-32b-instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "response text"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

### Required Fields
- **id**: Unique completion ID
- **object**: Always "chat.completion" for non-streaming responses
- **created**: Unix timestamp
- **model**: Model identifier used for the response
- **choices**: Array of response choices (usually just one)
  - **index**: Choice index (0 for single response)
  - **message**: The response message object
    - **role**: MUST be "assistant" for AI responses
    - **content**: The actual text response
  - **finish_reason**: Typically "stop" for completed responses
- **usage**: Token usage information
  - **prompt_tokens**: Input tokens
  - **completion_tokens**: Output tokens
  - **total_tokens**: Sum of input and output

## Tool Response Format

### Tool Call Response
When the model wants to call a tool:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "qwen/qwen-2.5-coder-32b-instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "tool_name",
              "arguments": "{\"param1\": \"value1\", \"param2\": \"value2\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15
  }
}
```

### Tool Result Format
When OpenCode CLI sends tool results back after execution:
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "tool execution result"
}
```

For error responses:
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "Error: Error message here"
}
```

## Streaming Response Format

For streaming responses, each chunk follows the Server-Sent Events (SSE) format:
```
data: {
  "id": "chatcmpl-123",
  "object": "chat.completion.chunk",
  "created": 1677652288,
  "model": "qwen/qwen-2.5-coder-32b-instruct",
  "choices": [
    {
      "index": 0,
      "delta": {
        "content": "chunk of text"
      },
      "finish_reason": null
    }
  ]
}

```

Last chunk has `"finish_reason": "stop"` and final chunk is:
```
data: [DONE]

```

### Tool Call Streaming
Tool calls in streaming mode arrive as deltas:
```
data: {
  "choices": [
    {
      "index": 0,
      "delta": {
        "tool_calls": [
          {
            "index": 0,
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "tool_name",
              "arguments": "{\"param"
            }
          }
        ]
      }
    }
  ]
}

```

## Common Issues and Solutions

### Issue 1: Incorrect Role
**Problem**: Using "model" instead of "assistant"
```json
// WRONG
"role": "model"

// CORRECT
"role": "assistant"
```

### Issue 2: Missing Usage Information
**Problem**: Not including token usage
```json
// WRONG
{
  "choices": [...],
  // Missing usage
}

// CORRECT
{
  "choices": [...],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

### Issue 3: Incorrect Tool Call Format
**Problem**: Using non-standard tool call structure
```json
// WRONG
"function_call": {"name": "tool", "parameters": {}}

// CORRECT
"tool_calls": [{
  "id": "call_123",
  "type": "function",
  "function": {
    "name": "tool",
    "arguments": "{\"param\": \"value\"}"
  }
}]
```

### Issue 4: Tool Arguments as Object
**Problem**: Passing arguments as object instead of JSON string
```json
// WRONG
"arguments": {"param": "value"}

// CORRECT
"arguments": "{\"param\": \"value\"}"
```

## Testing Response Format

Use the following curl command to test the proxy:
```bash
curl -X POST http://localhost:8054/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "model": "qwen/qwen-2.5-coder-32b-instruct",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }' | jq .
```

Expected response structure:
```json
{
  "id": "chatcmpl-xyz",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "qwen/qwen-2.5-coder-32b-instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "...response..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

## OpenRouter-Specific Considerations

### Model Names
OpenCode uses OpenRouter's model naming convention:
- Format: `provider/model-name`
- Example: `qwen/qwen-2.5-coder-32b-instruct`

### API Endpoints
- Chat Completions: `/v1/chat/completions`
- Models List: `/v1/models`
- Model Info: `/v1/models/{model_id}`

### Headers
Required headers for OpenRouter API:
- `Content-Type: application/json`
- `Authorization: Bearer YOUR_API_KEY`
- `HTTP-Referer` (optional but recommended)
- `X-Title` (optional, for tracking)

## Validation Checklist

- [ ] Response has `id`, `object`, `created`, `model` fields
- [ ] Response has `choices` array
- [ ] Each choice has `index`, `message`, and `finish_reason`
- [ ] Message has `role: "assistant"` and either `content` or `tool_calls`
- [ ] Response includes `usage` object with token counts
- [ ] Tool calls use `tool_calls` array format
- [ ] Tool arguments are JSON strings, not objects
- [ ] Tool responses use role `"tool"` with `tool_call_id`
- [ ] Streaming responses use SSE format with `data:` prefix
- [ ] Streaming ends with `data: [DONE]`
- [ ] Model names follow `provider/model` format

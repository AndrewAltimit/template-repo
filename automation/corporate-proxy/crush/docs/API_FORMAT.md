# Crush API Response Format Requirements

## Overview
The Crush CLI expects specific JSON response formats that must be strictly adhered to for proper functionality. This document outlines the exact format requirements for both standard responses and tool-enabled responses, compatible with the OpenRouter API format. Crush is optimized for speed and uses lightweight models for rapid code generation.

## Standard Response Format

### Basic Structure
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "deepseek/deepseek-chat",
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
  "model": "deepseek/deepseek-chat",
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
When Crush CLI sends tool results back after execution:
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

For streaming responses (optimized for speed), each chunk follows the Server-Sent Events (SSE) format:
```
data: {
  "id": "chatcmpl-123",
  "object": "chat.completion.chunk",
  "created": 1677652288,
  "model": "deepseek/deepseek-chat",
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

## Crush-Specific Optimizations

### Fast Model Selection
Crush prioritizes speed and uses these models:
- Primary: `deepseek/deepseek-chat` - Fast, efficient coding
- Fallback: `microsoft/phi-3-medium-128k-instruct` - Quick responses
- Alternative: `meta-llama/llama-3.1-8b-instruct` - Balanced performance

### Response Time Targets
- Initial response: < 500ms
- Complete simple code generation: < 2 seconds
- Code conversion tasks: < 3 seconds
- Explanation tasks: < 1.5 seconds

### Simplified Tool Usage
Crush focuses on essential tools for speed:
- File reading (cached for performance)
- Code writing (batched operations)
- Simple search (indexed for speed)

## Common Issues and Solutions

### Issue 1: Slow Response Times
**Problem**: Using heavyweight models
```json
// WRONG - Too slow for Crush
"model": "gpt-4-turbo-preview"

// CORRECT - Optimized for speed
"model": "deepseek/deepseek-chat"
```

### Issue 2: Excessive Token Usage
**Problem**: Verbose responses consuming too many tokens
```json
// WRONG
"content": "Let me explain this in detail with multiple examples..."

// CORRECT
"content": "```python\n# Direct solution\ndef solve(): return result\n```"
```

### Issue 3: Missing Streaming Support
**Problem**: Not supporting streaming for faster perceived response
```json
// WRONG - Waiting for complete response
"object": "chat.completion"

// CORRECT - Stream chunks as they arrive
"object": "chat.completion.chunk"
```

### Issue 4: Tool Overhead
**Problem**: Using tools when direct response is faster
```json
// WRONG - Tool call for simple task
"tool_calls": [{"function": {"name": "calculate_sum"}}]

// CORRECT - Direct response
"content": "The sum is 42"
```

## Testing Response Format

Use the following curl command to test the proxy:
```bash
curl -X POST http://localhost:8055/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "model": "deepseek/deepseek-chat",
    "messages": [
      {"role": "user", "content": "Write a quick Python hello world"}
    ],
    "stream": true
  }' --no-buffer
```

Expected streaming response:
```
data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1234567890,"model":"deepseek/deepseek-chat","choices":[{"index":0,"delta":{"content":"print"},"finish_reason":null}]}

data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1234567890,"model":"deepseek/deepseek-chat","choices":[{"index":0,"delta":{"content":"(\"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1234567890,"model":"deepseek/deepseek-chat","choices":[{"index":0,"delta":{"content":", World"},"finish_reason":null}]}

data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1234567890,"model":"deepseek/deepseek-chat","choices":[{"index":0,"delta":{"content":"!\")"},"finish_reason":null}]}

data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1234567890,"model":"deepseek/deepseek-chat","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]

```

## Performance Benchmarks

### Target Response Times
| Task Type | Target Time | Max Tokens |
|-----------|------------|------------|
| Simple code generation | < 2s | 500 |
| Code conversion | < 3s | 1000 |
| Quick explanation | < 1.5s | 300 |
| Error fix | < 2.5s | 600 |
| Unit test generation | < 2s | 400 |

### Model Performance Comparison
| Model | Avg Response | Quality | Cost |
|-------|-------------|---------|------|
| deepseek/deepseek-chat | 0.8s | Good | Low |
| microsoft/phi-3-medium | 1.2s | Good | Low |
| meta-llama/llama-3.1-8b | 1.0s | Good | Low |

## OpenRouter-Specific Considerations

### Model Names
Crush uses OpenRouter's fastest models:
- Format: `provider/model-name`
- Primary: `deepseek/deepseek-chat`
- Optimized for code generation speed

### API Endpoints
- Chat Completions: `/v1/chat/completions`
- Models List: `/v1/models`
- Model Info: `/v1/models/{model_id}`

### Headers
Required headers for OpenRouter API:
- `Content-Type: application/json`
- `Authorization: Bearer YOUR_API_KEY`
- `HTTP-Referer` (optional but recommended)
- `X-Title` (optional, set to "Crush" for tracking)

### Rate Limiting
Crush implements aggressive caching to minimize API calls:
- Response cache: 5 minutes for identical queries
- File content cache: Until modification
- Model list cache: 1 hour

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
- [ ] Response time meets performance targets (< 2s for most tasks)
- [ ] Token usage is optimized (< 1000 for most responses)
- [ ] Streaming is enabled for better perceived performance

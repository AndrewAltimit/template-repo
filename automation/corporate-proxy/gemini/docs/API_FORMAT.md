# Gemini API Response Format Requirements

## Overview
The Gemini CLI expects specific JSON response formats that must be strictly adhered to for proper functionality. This document outlines the exact format requirements for both standard responses and tool-enabled responses.

## Standard Response Format

### Basic Structure
```json
{
  "candidates": [
    {
      "content": {
        "parts": [{"text": "response text"}],
        "role": "model"
      },
      "finishReason": "STOP",
      "index": 0,
      "safetyRatings": []
    }
  ],
  "promptFeedback": {"safetyRatings": []},
  "usageMetadata": {
    "promptTokenCount": 10,
    "candidatesTokenCount": 20,
    "totalTokenCount": 30
  }
}
```

### Required Fields
- **candidates**: Array of response candidates (usually just one)
  - **content**: The response content object
    - **parts**: Array of content parts
      - **text**: The actual text response
    - **role**: MUST be "model" for AI responses
  - **finishReason**: Typically "STOP" for completed responses
  - **index**: Candidate index (0 for single response)
  - **safetyRatings**: Array (can be empty)
- **promptFeedback**: Feedback object with safetyRatings
- **usageMetadata**: Token usage information
  - **promptTokenCount**: Input tokens
  - **candidatesTokenCount**: Output tokens
  - **totalTokenCount**: Sum of input and output

## Tool Response Format

### Tool Call Response
When the model wants to call a tool:
```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "functionCall": {
              "name": "tool_name",
              "args": {  // Note: "args" not "arguments"
                "param1": "value1",
                "param2": "value2"
              },
              "id": "call_123"  // Optional but used by Gemini CLI for correlation
            }
          }
        ],
        "role": "model"
      },
      "finishReason": "STOP",
      "index": 0,
      "safetyRatings": []
    }
  ],
  "promptFeedback": {"safetyRatings": []},
  "usageMetadata": {
    "promptTokenCount": 10,
    "candidatesTokenCount": 5,
    "totalTokenCount": 15
  }
}
```

### Tool Result Format
When Gemini CLI sends tool results back after execution:
```json
{
  "contents": [
    {
      "role": "user",  // Always "user" for function responses in Gemini CLI
      "parts": [
        {
          "functionResponse": {
            "name": "tool_name",
            "id": "call_123",  // Should match the functionCall id
            "response": {
              "output": "tool execution result"  // Use "output" for successful results
            }
          }
        }
      ]
    }
  ]
}
```

For error responses:
```json
{
  "functionResponse": {
    "name": "tool_name",
    "id": "call_123",
    "response": {
      "error": "Error message here"  // Use "error" for failures
    }
  }
}
```

## Common Issues and Solutions

### Issue 1: Incorrect Role
**Problem**: Using "assistant" instead of "model"
```json
// WRONG
"role": "assistant"

// CORRECT
"role": "model"
```

### Issue 2: Missing Parts Array
**Problem**: Putting text directly in content
```json
// WRONG
"content": {"text": "response"}

// CORRECT
"content": {"parts": [{"text": "response"}], "role": "model"}
```

### Issue 3: Incorrect Tool Call Format
**Problem**: Using OpenAI-style function calls
```json
// WRONG
"function_call": {"name": "tool", "arguments": "{}"}

// CORRECT
"functionCall": {"name": "tool", "args": {}}
```

## Testing Response Format

Use the following curl command to test the proxy:
```bash
curl -X POST http://localhost:8053/v1/models/gemini-2.5-flash/generateContent \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "parts": [{"text": "Hello"}],
        "role": "user"
      }
    ]
  }' | jq .
```

Expected response structure:
```json
{
  "candidates": [
    {
      "content": {
        "parts": [{"text": "...response..."}],
        "role": "model"
      },
      "finishReason": "STOP",
      "index": 0,
      "safetyRatings": []
    }
  ],
  "promptFeedback": {"safetyRatings": []},
  "usageMetadata": {
    "promptTokenCount": 10,
    "candidatesTokenCount": 20,
    "totalTokenCount": 30
  }
}
```

## Streaming Response Format

For streaming responses, each chunk follows this format:
```json
{
  "candidates": [
    {
      "content": {
        "parts": [{"text": "chunk of text"}],
        "role": "model"
      },
      "finishReason": null,  // null until last chunk
      "index": 0
    }
  ]
}
```

Last chunk has `"finishReason": "STOP"`

## Validation Checklist

- [ ] Response has `candidates` array
- [ ] Each candidate has `content` object
- [ ] Content has `parts` array and `role: "model"`
- [ ] Parts contain either `text`, `functionCall`, or `functionResponse`
- [ ] Response includes `promptFeedback` object
- [ ] Response includes `usageMetadata` with token counts
- [ ] Tool calls use `functionCall` not `function_call`
- [ ] Tool arguments use `args` not `arguments`
- [ ] Function responses use role `"user"` not `"function"`
- [ ] Function responses include `id` for correlation with calls
- [ ] Success responses use `{"output": "..."}` format
- [ ] Error responses use `{"error": "..."}` format

# OpenCode Tool Execution Fix

## Problem Analysis

When the company sets `tool_call: false` in their OpenCode model configuration (because their API endpoints don't support native tools), OpenCode won't execute the parsed tool calls even though the translation wrapper correctly extracts and formats them.

## The Issue

1. **Company Configuration**: Sets `tool_call: false` in `company-override.json` because their endpoints don't support native tools
2. **Translation Wrapper**: Correctly parses tool calls from text and formats them as OpenAI tool_calls
3. **OpenCode**: Ignores tool_calls in the response because `tool_call: false` in model config

## Solution Options

### Option 1: Keep tool_call: true in OpenCode config (RECOMMENDED)
Even though the company API doesn't support tools, OpenCode needs `tool_call: true` to execute them.

**Fix in `automation/corporate-proxy/shared/patches/company-override.json`:**
```json
{
  "openrouter": {
    "models": {
      "openrouter/anthropic/claude-3.5-sonnet": {
        "tool_call": true,  // Keep this true for OpenCode to execute tools
        // ... rest of config
      }
    }
  }
}
```

The translation wrapper handles the mismatch:
- It knows the actual endpoint doesn't support tools (`supports_tools: false` in models.json)
- It parses tool calls from text
- It returns them in OpenAI format for OpenCode to execute

### Option 2: Force tool execution in wrapper
The wrapper could execute tools itself and return results, but this is complex and breaks OpenCode's execution model.

### Option 3: Use a hybrid approach
Set `tool_call: true` in OpenCode but `supports_tools: false` in the wrapper's models.json.

## Recommended Configuration

**In `company-override.json` (for OpenCode):**
```json
"tool_call": true  // OpenCode needs this to execute tools
```

**In `models.json` (for translation wrapper):**
```json
"supports_tools": false  // Wrapper uses text parsing
```

## Testing the Fix

1. Set `tool_call: true` in company-override.json
2. Set `supports_tools: false` in models.json
3. The wrapper will parse tools from text
4. OpenCode will execute the parsed tools

## Why This Works

- OpenCode sees `tool_call: true` and is willing to execute tools
- The wrapper sees `supports_tools: false` and parses tools from text
- The wrapper returns properly formatted tool_calls
- OpenCode executes them as if they came from a native tool-supporting API

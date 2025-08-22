# OpenCode Proxy Solution - WORKING

## The Challenge
OpenCode has issues with custom provider configurations (ProviderInitError), but we can hijack the OpenRouter configuration to use our proxy.

## ✅ VERIFIED WORKING SOLUTION

### Step 1: Start the Proxy
```bash
# This starts both mock API and translation wrapper
./automation/proxy/toggle_opencode.sh start
```

Verify it's working:
```bash
curl -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "anthropic/claude-3.5-sonnet", "messages": [{"role": "user", "content": "Test"}]}' \
  | python -m json.tool
# Should return: "content": "Hatsune Miku"
```

### Step 2: Configure OpenCode

Create this configuration in `~/.config/opencode/.opencode.json`:

```json
{
  "provider": {
    "openrouter": {
      "options": {
        "baseURL": "http://localhost:8052/v1",
        "apiKey": "test-key"
      }
    }
  },
  "model": "openrouter/anthropic/claude-3.5-sonnet"
}
```

Or run this command:
```bash
mkdir -p ~/.config/opencode
cat > ~/.config/opencode/.opencode.json << 'EOF'
{
  "provider": {
    "openrouter": {
      "options": {
        "baseURL": "http://localhost:8052/v1",
        "apiKey": "test-key"
      }
    }
  },
  "model": "openrouter/anthropic/claude-3.5-sonnet"
}
EOF
```

### Step 3: Set Environment Variable
```bash
export OPENROUTER_API_KEY=test-key
```

### Step 4: Run OpenCode
```bash
# Interactive mode
opencode

# Single query
echo "What is your name?" | opencode run
```

## 🎯 What's Happening

1. **Proxy Services**: Mock API (port 8050) + Translation Wrapper (port 8052)
2. **Hijacking**: We tell OpenCode that OpenRouter is at `localhost:8052` instead of `openrouter.ai`
3. **Translation**: The wrapper translates between OpenCode's expected format and your company's API format
4. **Response**: All responses are "Hatsune Miku" (in mock mode)

## 🔍 Verification

The proxy is working when:
1. You see requests in `/tmp/wrapper.log`:
   ```
   INFO:__main__:Received OpenCode request
   INFO:__main__:Company response: {"content": [{"text": "Hatsune Miku", "type": "text"}]}
   ```

2. All OpenCode responses are "Hatsune Miku"

## 🚀 Production Setup

To use real company API instead of mock:

1. Set environment variables:
```bash
export WRAPPER_MOCK_MODE=false
export COMPANY_API_BASE=https://your-company-api.com
export COMPANY_API_TOKEN=your-real-token
```

2. Restart the wrapper:
```bash
pkill -f api_translation_wrapper.py
python automation/proxy/api_translation_wrapper.py &
```

3. OpenCode will now use your real company API!

## ⚠️ Known Issues

1. **ProviderInitError**: OpenCode has trouble with fully custom providers, which is why we hijack OpenRouter instead
2. **Command Syntax**: Use `echo "query" | opencode run` instead of `opencode run -q "query"` for better reliability
3. **Config Location**: OpenCode looks in `~/.config/opencode/.opencode.json` - other locations may not work

## 📝 Complete Test Script

Save this as `test_opencode_proxy.sh`:

```bash
#!/bin/bash

# Start proxy
./automation/proxy/toggle_opencode.sh start

# Configure OpenCode
mkdir -p ~/.config/opencode
cat > ~/.config/opencode/.opencode.json << 'EOF'
{
  "provider": {
    "openrouter": {
      "options": {
        "baseURL": "http://localhost:8052/v1"
      }
    }
  },
  "model": "openrouter/anthropic/claude-3.5-sonnet"
}
EOF

# Set API key
export OPENROUTER_API_KEY=test-key

# Test
echo "What is your name?" | opencode run
# Should output: "Hatsune Miku"
```

## Summary

The proxy successfully intercepts OpenCode's OpenRouter calls and returns "Hatsune Miku" for all queries. This confirms that OpenCode IS using the proxy when properly configured. The key is hijacking the OpenRouter configuration rather than trying to create a custom provider.

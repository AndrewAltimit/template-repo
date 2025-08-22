# OpenCode Proxy Quick Start Guide

## 🚀 Fastest Way to Test

### 1. Start the proxy services on your host:
```bash
# This starts both mock API and translation wrapper
./automation/proxy/toggle_opencode.sh start
```

### 2. Test that the proxy is working:
```bash
# This should return "Hatsune Miku"
curl -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "Hello"}]}'
```

### 3. Configure OpenCode to use the proxy:

#### Option A: Use environment variables (simplest)
```bash
export OPENCODE_CONFIG=/path/to/automation/proxy/opencode-custom.jsonc
export COMPANY_API_KEY=mock-api-key-for-testing

# Now run OpenCode normally
opencode run -q "What is your name?"
# Should return: "Hatsune Miku"
```

#### Option B: Use the toggle script
```bash
# Switch to proxy mode
./automation/proxy/toggle_opencode.sh proxy

# Run OpenCode
opencode run -q "What is your name?"
# Should return: "Hatsune Miku"

# Switch back to OpenRouter
./automation/proxy/toggle_opencode.sh openrouter
```

## 🐳 Docker Usage

### Simple Container Test
```bash
# Test proxy services in container
./automation/proxy/test_proxy_in_container.sh
# Should show: "Response: Hatsune Miku"
```

### Run OpenCode in Container with Proxy

1. **Build the container** (if not already built):
```bash
docker-compose build openrouter-agents
```

2. **Run with proxy inside container**:
```bash
docker-compose run --rm openrouter-agents bash -c "
  # Install dependencies
  pip install flask flask-cors requests

  # Start proxy services
  python /workspace/automation/proxy/mock_company_api.py &
  python /workspace/automation/proxy/api_translation_wrapper.py &
  sleep 3

  # Test endpoint
  curl -X POST http://localhost:8052/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"claude-3.5-sonnet\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}'
"
```

## 🔧 Manual Testing

### Test Components Individually

1. **Test Mock Company API**:
```bash
curl -X POST http://localhost:8050/api/v1/AI/GenAIExplorationLab/Models/ai-coe-bedrock-claude35-sonnet-200k:analyze=null \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-secret-token-123" \
  -d '{"messages": [{"role": "user", "content": "Test"}]}'
```

2. **Test Translation Wrapper**:
```bash
curl -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "Test"}]}'
```

3. **Run comprehensive tests**:
```bash
python automation/proxy/test_opencode_proxy.py
```

## 📝 Key Files

- **Mock API**: `automation/proxy/mock_company_api.py` (Port 8050)
- **Translation Wrapper**: `automation/proxy/api_translation_wrapper.py` (Port 8052)
- **OpenCode Config**: `automation/proxy/opencode-custom.jsonc`
- **Toggle Script**: `automation/proxy/toggle_opencode.sh`
- **Test Suite**: `automation/proxy/test_opencode_proxy.py`

## ✅ Success Indicators

When everything is working correctly:

1. `curl http://localhost:8052/health` returns status: "healthy"
2. All API calls return "Hatsune Miku" as the response
3. OpenCode uses the custom provider configuration
4. No OpenRouter API calls are made (saves credits!)

## 🔄 Switching Modes

```bash
# Check current mode
./automation/proxy/toggle_opencode.sh status

# Switch to proxy (mock)
./automation/proxy/toggle_opencode.sh proxy

# Switch to OpenRouter (real)
./automation/proxy/toggle_opencode.sh openrouter

# Stop proxy services
./automation/proxy/toggle_opencode.sh stop
```

## 🚨 Troubleshooting

### Services not starting
```bash
# Check if ports are in use
lsof -i :8050
lsof -i :8052

# Kill any existing processes
pkill -f mock_company_api.py
pkill -f api_translation_wrapper.py

# Restart services
./automation/proxy/toggle_opencode.sh start
```

### OpenCode not using proxy
```bash
# Verify config is set
echo $OPENCODE_CONFIG

# Should point to: /path/to/automation/proxy/opencode-custom.jsonc
```

### Check logs
```bash
tail -f /tmp/mock_api.log
tail -f /tmp/wrapper.log
```

## 🎯 Production Setup

When ready to use real company API:

1. Set environment variables:
```bash
export WRAPPER_MOCK_MODE=false
export COMPANY_API_BASE=https://your-company-api.com
export COMPANY_API_TOKEN=your-real-token
```

2. Restart translation wrapper:
```bash
pkill -f api_translation_wrapper.py
python automation/proxy/api_translation_wrapper.py &
```

3. Test with OpenCode - should now use real API instead of mock!

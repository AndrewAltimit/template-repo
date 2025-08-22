# OpenCode Toggle Guide: Proxy vs OpenRouter

This guide explains how to easily switch OpenCode between using the company proxy (mock endpoints) and real OpenRouter endpoints.

## 🎯 Quick Start

### Check Current Status
```bash
./automation/proxy/toggle_opencode.sh status
```

### Switch to Company Proxy (Mock Mode)
```bash
./automation/proxy/toggle_opencode.sh proxy
```
- All responses will be "Hatsune Miku"
- Uses local translation wrapper
- Perfect for testing integration

### Switch to OpenRouter (Real Mode)
```bash
./automation/proxy/toggle_opencode.sh openrouter
```
- Uses real AI models
- Requires `OPENROUTER_API_KEY` environment variable
- Normal OpenCode behavior

## 🧪 Testing

### Test Mock Endpoints
```bash
# Run comprehensive test suite
python automation/proxy/test_opencode_proxy.py

# Quick API test
curl -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Test with OpenCode CLI
```bash
# After switching to proxy mode
./automation/proxy/toggle_opencode.sh proxy

# Run OpenCode - should return "Hatsune Miku"
./automation/proxy/opencode_wrapper.sh run -q "What is 2+2?"
```

## 📁 File Structure

```
automation/proxy/
├── mock_company_api.py         # Mock company API (always returns "Hatsune Miku")
├── api_translation_wrapper.py  # Translates between OpenCode and company formats
├── toggle_opencode.sh          # Main toggle script
├── opencode_wrapper.sh         # Wrapper to run OpenCode with correct config
├── test_opencode_proxy.py      # Test suite
├── test_integration.py         # Comprehensive integration tests
├── opencode-custom.jsonc       # Config for proxy mode
└── configs/
    ├── opencode-openrouter.jsonc  # Config for OpenRouter mode
    └── .current_config            # Stores current mode
```

## 🔧 How It Works

### Proxy Mode Architecture
```
OpenCode → Translation Wrapper (:8052) → Mock Company API (:8050)
         ← (OpenCode format)            ← (Company format)
```

1. **OpenCode** sends requests in OpenAI-compatible format
2. **Translation Wrapper** converts to company API format
3. **Mock Company API** always returns "Hatsune Miku"
4. Response flows back through translation layer

### Toggle Mechanism

The toggle script manages:
- Starting/stopping proxy services
- Setting environment variables
- Switching configuration files
- Maintaining state in `.current_config`

## 🐳 Docker Usage

### Start Services with Docker
```bash
# Start proxy services
docker-compose --profile proxy up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api-translation-wrapper
```

### Run OpenCode in Container
```bash
# Proxy mode
docker-compose run --rm \
  -e OPENCODE_CONFIG=/workspace/automation/proxy/opencode-custom.jsonc \
  -e COMPANY_API_KEY=mock-api-key-for-testing \
  openrouter-agents opencode run -q "Hello"

# OpenRouter mode
docker-compose run --rm \
  -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  openrouter-agents opencode run -q "Hello"
```

## 🔍 Verification

### In Proxy Mode
- **All responses**: "Hatsune Miku"
- **Services running**: Ports 8050 and 8052
- **Config**: Uses `opencode-custom.jsonc`

### In OpenRouter Mode
- **Real AI responses**: Actual model outputs
- **Services stopped**: No proxy services
- **Config**: Default OpenCode configuration

## 🛠️ Troubleshooting

### Services not starting
```bash
# Check if ports are in use
lsof -i :8050
lsof -i :8052

# Kill existing processes
pkill -f mock_company_api.py
pkill -f api_translation_wrapper.py

# Restart
./automation/proxy/toggle_opencode.sh start
```

### OpenCode not using proxy
```bash
# Verify environment variables
echo $OPENCODE_CONFIG
echo $COMPANY_API_KEY

# Re-source the toggle script
source ./automation/proxy/toggle_opencode.sh proxy
```

### Check logs
```bash
# View service logs
tail -f /tmp/mock_api.log
tail -f /tmp/wrapper.log

# Docker logs
docker-compose logs -f mock-company-api
docker-compose logs -f api-translation-wrapper
```

## 🚀 Production Setup

When ready for production with real company API:

1. **Update wrapper configuration**:
```bash
export WRAPPER_MOCK_MODE=false
export COMPANY_API_BASE=https://your-company-api.com
export COMPANY_API_TOKEN=your-real-token
```

2. **Update model mappings** in `api_translation_wrapper.py`:
```python
MODEL_MAPPING = {
    "claude-3.5-sonnet": "your-company-model-id",
    # Add more mappings
}
```

3. **Deploy with Docker**:
```bash
docker-compose --profile proxy up -d api-translation-wrapper
```

## 📊 Status Commands

```bash
# Full status
./automation/proxy/toggle_opencode.sh status

# Quick service check
curl http://localhost:8050/health  # Mock API
curl http://localhost:8052/health  # Translation wrapper

# Test current mode
./automation/proxy/toggle_opencode.sh test
```

## 🎉 Success Indicators

### Proxy Mode Working
✅ `toggle_opencode.sh status` shows services running
✅ All API calls return "Hatsune Miku"
✅ Test suite passes completely

### OpenRouter Mode Working
✅ No proxy services running
✅ Real AI responses from models
✅ OpenCode uses default configuration

## 💡 Tips

1. **Always verify mode** before testing:
   ```bash
   ./automation/proxy/toggle_opencode.sh status
   ```

2. **Use wrapper script** for consistent behavior:
   ```bash
   ./automation/proxy/opencode_wrapper.sh run -q "Your prompt"
   ```

3. **Monitor logs** during development:
   ```bash
   tail -f /tmp/wrapper.log
   ```

4. **Test after switching**:
   ```bash
   python automation/proxy/test_opencode_proxy.py
   ```

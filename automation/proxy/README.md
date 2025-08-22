# OpenCode Proxy System

> **🎭 Enhanced Version Available**: For an improved user experience with automatic service startup and cleaner interface, see the [Proxy Wrapper Documentation](../../docs/features/opencode-proxy-wrapper.md).

This directory contains a complete proxy solution that allows OpenCode to work with company internal AI APIs instead of OpenRouter.

## 🎯 Purpose

Many companies block OpenRouter but have their own AI API endpoints. This proxy system:
- Intercepts OpenCode's OpenRouter requests
- Translates them to your company's API format
- Returns responses that OpenCode understands
- Works both on host and in containers

## 📁 Files

| File | Description |
|------|-------------|
| `mock_company_api.py` | Mock server simulating company API (returns "Hatsune Miku") |
| `api_translation_wrapper.py` | Translates between OpenCode and company API formats |
| `container_entrypoint.sh` | Container startup script with auto-configuration |
| `run_opencode_container.sh` | Easy launcher for containerized OpenCode |
| `toggle_opencode.sh` | Host-based proxy toggle script |
| `test_container_proxy.sh` | Comprehensive container testing |
| `CONTAINER_SOLUTION.md` | Detailed container documentation |
| `OPENCODE_PROXY_SOLUTION.md` | Host-based solution documentation |

## 🚀 Quick Start

### Container Mode (Recommended)
```bash
# Interactive session with mock API
./automation/proxy/run_opencode_container.sh

# Single query with mock API
./automation/proxy/run_opencode_container.sh mock query "Your question"

# Use real company API
export COMPANY_API_BASE=https://your-api.com
export COMPANY_API_TOKEN=your-token
./automation/proxy/run_opencode_container.sh real interactive
```

### Host Mode
```bash
# Start proxy on host
./automation/proxy/toggle_opencode.sh start

# Configure OpenCode (creates opencode.json)
./automation/proxy/toggle_opencode.sh proxy

# Stop proxy
./automation/proxy/toggle_opencode.sh stop
```

## 🔧 How It Works

1. **Mock Company API** (Port 8050)
   - Simulates your company's API endpoint
   - Always returns "Hatsune Miku" for testing
   - Mimics exact company API format

2. **Translation Wrapper** (Port 8052)
   - Receives OpenCode's OpenRouter requests
   - Translates to company API format
   - Sends to mock or real company API
   - Translates response back to OpenAI format

3. **OpenCode Configuration**
   - Hijacks OpenRouter configuration
   - Points to localhost:8052 instead of openrouter.ai
   - OpenCode works normally, unaware of proxy

## 🎭 Testing

The system uses "Hatsune Miku" as the test response because:
- It's unique and immediately identifiable
- Confirms the proxy is intercepting requests
- Makes debugging straightforward

When you see "Hatsune Miku" in responses, the proxy is working correctly.

## 🔄 Switching Modes

### Mock Mode (Testing)
- `PROXY_MOCK_MODE=true` (default)
- All responses are "Hatsune Miku"
- No external API calls
- Perfect for testing setup

### Real Mode (Production)
- `PROXY_MOCK_MODE=false`
- Set `COMPANY_API_BASE` and `COMPANY_API_TOKEN`
- Uses actual company API
- Real AI responses

## 📦 Container Features

- Self-contained with all dependencies
- Auto-starts proxy services
- Auto-configures OpenCode
- Health checks and logging
- Easy deployment to any Docker environment

## 🛠️ Customization

### Adding Model Mappings
Edit `api_translation_wrapper.py`:
```python
MODEL_MAPPING = {
    "your-model": "company-endpoint",
    # Add more mappings
}
```

### Changing Response Format
Modify translation functions in `api_translation_wrapper.py`:
- `translate_request()` - Customize request translation
- `translate_response()` - Customize response translation

## 📝 Logs

- Mock API: `/tmp/mock_api.log`
- Translation Wrapper: `/tmp/wrapper.log`
- View in container: `cat /tmp/wrapper.log`

## 🚨 Troubleshooting

### "Hatsune Miku" not appearing
1. Check proxy is running: `curl http://localhost:8052/health`
2. Verify OpenCode config: `cat opencode.json`
3. Check logs: `tail -f /tmp/wrapper.log`

### Container won't start
1. Check Docker is running
2. Rebuild: `docker build -f docker/opencode-with-proxy.Dockerfile -t opencode-with-proxy:latest .`
3. Check ports 8050/8052 aren't in use

### Real API not working
1. Verify environment variables are set
2. Check network connectivity
3. Confirm API token is valid
4. Review wrapper logs for errors

## 🔒 Security

- API tokens via environment variables only
- No hardcoded credentials
- Services listen on localhost only
- Container runs as non-root user

## 📚 Documentation

- [Container Solution](./CONTAINER_SOLUTION.md) - Detailed container guide
- [Host Solution](./OPENCODE_PROXY_SOLUTION.md) - Running on host
- [API Wrapper](./api_translation_wrapper.py) - Translation logic

## ✅ Summary

This proxy system successfully enables OpenCode to work with company internal APIs by:
- Hijacking OpenRouter configuration (workaround for ProviderInitError)
- Translating between API formats
- Providing both mock and real modes
- Working in containers for portability

The solution is simple, portable, and ready for production use.

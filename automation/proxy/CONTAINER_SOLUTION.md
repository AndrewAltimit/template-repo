# OpenCode Container with Proxy Support - Complete Solution

## ✅ Working Solution

This solution packages OpenCode with an integrated proxy that allows it to work with your company's internal AI API instead of OpenRouter.

## 🚀 Quick Start

### 1. Build the Container
```bash
./automation/proxy/build-company-tui.sh
```

### 2. Run with Mock Mode (Testing)
```bash
# Interactive TUI mode (auto-starts)
./automation/proxy/run-company-tui.sh

# All responses will be "Hatsune Miku" in mock mode to verify the proxy is working
```

### 3. Run with Real Company API
```bash
export COMPANY_API_BASE=https://your-company-api.com
export COMPANY_API_TOKEN=your-real-token
./automation/proxy/run-company-production.sh
```

## 📦 What's Included

The container includes:
- **OpenCode CLI**: The official AI code assistant
- **Mock Company API**: Simulates your company's API for testing
- **API Translation Wrapper**: Translates between OpenCode and company API formats
- **Auto-configuration**: Automatically configures OpenCode to use the proxy

## 🔧 How It Works

1. **Proxy Services Start**: Mock API (port 8050) and Translation Wrapper (port 8052)
2. **OpenRouter Hijacking**: We configure OpenCode to think OpenRouter is at `localhost:8052`
3. **Request Translation**: The wrapper translates OpenCode's OpenAI-format requests to your company's format
4. **Response Translation**: Company responses are translated back to OpenAI format
5. **Seamless Integration**: OpenCode works normally, unaware it's using a proxy

## 🎯 Architecture

```
OpenCode CLI
    ↓ (OpenAI format request)
Translation Wrapper (port 8052)
    ↓ (Company format request)
Company API (Mock or Real)
    ↓ (Company format response)
Translation Wrapper
    ↓ (OpenAI format response)
OpenCode CLI
```

## 🔄 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_PROXY` | `true` | Enable/disable proxy mode |
| `PROXY_MOCK_MODE` | `true` | Use mock API (true) or real company API (false) |
| `COMPANY_API_BASE` | `http://localhost:8050` | Company API endpoint |
| `COMPANY_API_TOKEN` | `test-secret-token-123` | Authentication token |

## 📝 Testing

### Verify Proxy is Working
```bash
# Test returns "Hatsune Miku" in mock mode
docker run --rm opencode-with-proxy:latest \
  bash -c "echo 'What is your name?' | opencode run"
```

### Check Service Health
```bash
# Check if services are running
docker run --rm opencode-with-proxy:latest \
  bash -c "curl http://localhost:8052/health"
```

### View Logs
```bash
# Run interactive and check logs
docker run --rm -it opencode-with-proxy:latest
# Inside container:
cat /tmp/wrapper.log
cat /tmp/mock_api.log
```

## 🚢 Deployment in Other Containers

To add this proxy capability to any container:

1. **Copy the proxy scripts**:
```dockerfile
COPY automation/proxy/mock_company_api.py /workspace/
COPY automation/proxy/company_translation_wrapper.py /workspace/
```

2. **Install dependencies**:
```dockerfile
RUN pip3 install flask flask-cors requests
RUN npm install -g opencode-ai
```

3. **Use the entrypoint**:
```dockerfile
ENTRYPOINT ["/workspace/automation/proxy/container_entrypoint.sh"]
```

## 🐛 Troubleshooting

### OpenCode Not Using Proxy
- Check `/workspace/opencode.json` exists
- Verify `OPENROUTER_API_KEY` is set
- Ensure services are running on ports 8050 and 8052

### "Hatsune Miku" Not Appearing
- Verify `PROXY_MOCK_MODE=true`
- Check wrapper logs: `cat /tmp/wrapper.log`
- Test proxy directly: `curl http://localhost:8052/health`

### Real API Not Working
- Set `PROXY_MOCK_MODE=false`
- Verify `COMPANY_API_BASE` and `COMPANY_API_TOKEN`
- Check network connectivity to company API

## 🎭 Why "Hatsune Miku"?

We use "Hatsune Miku" as the test response because:
1. It's unique and immediately identifiable
2. It confirms the proxy is intercepting requests
3. It's unlikely to appear in normal API responses
4. It makes debugging easier - if you see "Hatsune Miku", the proxy is working!

## 📄 Files

- `docker/opencode-company-tui-working.Dockerfile` - Working container definition with TUI
- `automation/proxy/mock_company_api.py` - Mock company API server
- `automation/proxy/company_translation_wrapper.py` - Format translation layer
- `automation/proxy/test-company-tui.sh` - Testing script

## ✨ Features

- ✅ Zero configuration needed (works out of the box)
- ✅ Supports both mock and real company APIs
- ✅ Portable to any Docker environment
- ✅ Includes health checks and logging
- ✅ Graceful error handling
- ✅ Easy to debug with clear test responses

## 🔐 Security Notes

- API tokens are passed via environment variables
- No credentials are hardcoded
- Mock mode uses fake tokens for testing
- Services only listen on localhost within container

## 📚 Additional Resources

- [Company Translation Wrapper](./company_translation_wrapper.py)
- [Mock Company API](./mock_company_api.py)

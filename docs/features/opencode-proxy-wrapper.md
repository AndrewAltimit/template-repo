# OpenCode Proxy Wrapper

This document describes the enhanced proxy wrapper system for OpenCode that provides a cleaner interface and better user experience when using corporate AI APIs.

## Overview

The proxy wrapper is an improvement over the basic proxy system. It:
- Shows a clear banner indicating which models work through the proxy
- Automatically starts proxy services when needed
- Provides a seamless experience without showing unavailable models
- Works with the existing OpenCode binary (no source compilation needed)

## Architecture

```
┌─────────────────────────────────────┐
│         OpenCode CLI                │
│   (sees only proxy models)          │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│    opencode-proxy-wrapper.sh        │
│  (starts services & configures)     │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│   API Translation Wrapper           │
│        (Port 8052)                  │
│  Translates OpenAI → Company API    │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│     Mock Company API                │
│        (Port 8050)                  │
│   Returns "Hatsune Miku" (testing)  │
└─────────────────────────────────────┘
```

## Components

### 1. Docker Image (`openrouter-agents-proxy.Dockerfile`)
- Based on `node:20-slim` for compatibility
- Includes both OpenCode and Crush binaries
- Installs proxy dependencies (Flask, requests)
- Creates wrapper script at `/usr/local/bin/opencode`
- Real OpenCode binary at `/usr/local/bin/opencode.real`

### 2. Wrapper Script (`opencode-proxy-wrapper.sh`)
- Displays clear banner showing available models
- Automatically starts Mock API and Translation Wrapper
- Configures OpenCode to use proxy
- Handles service health checks
- Provides clean error messages

### 3. Wrapper Entry Point
The `/usr/local/bin/opencode` script checks `USE_PROXY` environment variable:
- If `true`: Runs the proxy wrapper
- If `false`: Runs OpenCode directly

## Usage

### Building the Image

```bash
# Build the proxy-enabled image
docker build -f docker/openrouter-agents-proxy.Dockerfile -t openrouter-agents-proxy:latest .
```

### Running with Proxy (Default)

```bash
# Interactive mode with proxy
docker run --rm -it \
    -v "$(pwd):/workspace" \
    openrouter-agents-proxy:latest

# The container will:
# 1. Display available models banner
# 2. Start proxy services automatically
# 3. Launch OpenCode with proxy configuration
```

### Running without Proxy

```bash
# Disable proxy and use standard OpenRouter
docker run --rm -it \
    -e USE_PROXY=false \
    -e OPENROUTER_API_KEY=your-key \
    -v "$(pwd):/workspace" \
    openrouter-agents-proxy:latest
```

### Testing the Proxy

```bash
# Run the test script
./automation/proxy/test-proxy.sh

# Expected output: "Hatsune Miku"
```

## Available Models

When running with the proxy, only these models work:

| Model ID | Description |
|----------|-------------|
| `openrouter/anthropic/claude-3.5-sonnet` | Claude 3.5 Sonnet (Default) |
| `openrouter/anthropic/claude-3-opus` | Claude 3 Opus |
| `openrouter/openai/gpt-4` | GPT-4 |

**Note**: OpenCode may still display other models in its list, but only the above three will work through the company proxy. All other models will fall back to Claude 3.5 Sonnet.

## Configuration

### Environment Variables

- `USE_PROXY`: Enable/disable proxy mode (default: `true`)
- `PROXY_MOCK_MODE`: Use mock API for testing (default: `true`)
- `COMPANY_API_BASE`: Real company API endpoint (when mock mode is disabled)
- `COMPANY_API_TOKEN`: Authentication token for company API

### Files

- **OpenCode Config**: `/home/node/.config/opencode/.opencode.json`
  ```json
  {
    "provider": {
      "openrouter": {
        "options": {
          "baseURL": "http://localhost:8052/v1",
          "apiKey": "proxy-key"
        }
      }
    },
    "model": "openrouter/anthropic/claude-3.5-sonnet"
  }
  ```

## Troubleshooting

### Issue: Services fail to start

**Solution**: Check if ports 8050 and 8052 are already in use:
```bash
netstat -tulpn | grep -E "8050|8052"
```

### Issue: "Module not found" errors

**Solution**: Ensure the image was built with proxy requirements:
```bash
docker exec <container> pip list | grep -E "flask|requests"
```

### Issue: OpenCode shows many models but only 3 work

**Expected behavior**: This is a known limitation. OpenCode has hardcoded model lists that cannot be overridden. The proxy handles unmapped models by routing them to the default (Claude 3.5 Sonnet).

## Improvements Over Basic Proxy

1. **Better UX**: Clear banner showing which models work
2. **Automatic Setup**: Services start automatically
3. **Clean Interface**: Wrapper script provides helpful messages
4. **No Source Building**: Uses existing OpenCode binary
5. **Easy Testing**: Simple test script included

## Future Enhancements

- [ ] Build OpenCode from source to show only proxy models
- [ ] Add model selection menu
- [ ] Support for additional models through company API
- [ ] Real-time proxy status monitoring
- [ ] Automatic fallback to direct OpenRouter if proxy fails

## Related Documentation

- [OpenCode Proxy (Basic)](opencode-proxy.md) - Original proxy implementation
- [API Translation Wrapper](../../automation/proxy/README.md) - Detailed proxy documentation
- [OpenCode Models Issue](../../automation/proxy/OPENCODE_MODELS_ISSUE.md) - Why models can't be hidden

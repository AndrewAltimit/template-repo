# OpenCode Company Proxy Feature

## Overview

The OpenCode Proxy is a sophisticated solution that enables OpenCode AI CLI to work with corporate/internal AI APIs instead of OpenRouter. This is essential for organizations that:
- Have OpenRouter blocked by corporate firewalls
- Run their own AI infrastructure
- Need to route requests through internal API gateways
- Want to use OpenCode with custom AI endpoints

## How It Works

### Architecture

```
OpenCode CLI
    ↓ (OpenAI-format request)
Translation Wrapper (port 8052)
    ↓ (Company-format request)
Company API or Mock (port 8050)
    ↓ (Company-format response)
Translation Wrapper
    ↓ (OpenAI-format response)
OpenCode CLI
```

### Key Components

1. **API Translation Wrapper** (`automation/proxy/api_translation_wrapper.py`)
   - Translates between OpenCode's expected OpenAI format and your company's API format
   - Handles model mapping and fallback logic
   - Provides health check and model listing endpoints

2. **Mock Company API** (`automation/proxy/mock_company_api.py`)
   - Simulates your company's API for testing
   - Returns "Hatsune Miku" for all requests (verification)
   - Mimics exact company API authentication and format

3. **Container Integration** (`docker/opencode-with-proxy.Dockerfile`)
   - Self-contained Docker image with all dependencies
   - Auto-starts proxy services
   - Configures OpenCode automatically

## Quick Start

### Using Docker (Recommended)

```bash
# Build and run with mock API (testing)
./automation/proxy/run_opencode_container.sh

# Single query with mock API
./automation/proxy/run_opencode_container.sh mock query "What is 2+2?"

# Use with real company API
export COMPANY_API_BASE=https://your-company-api.com
export COMPANY_API_TOKEN=your-token
./automation/proxy/run_opencode_container.sh real interactive
```

### Manual Setup (Host)

```bash
# Start proxy services
./automation/proxy/toggle_opencode.sh start

# Configure OpenCode
./automation/proxy/toggle_opencode.sh proxy

# Stop proxy
./automation/proxy/toggle_opencode.sh stop
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_PROXY` | `true` | Enable/disable proxy mode |
| `PROXY_MOCK_MODE` | `true` | Use mock API (`true`) or real company API (`false`) |
| `COMPANY_API_BASE` | `http://localhost:8050` | Your company's API endpoint |
| `COMPANY_API_TOKEN` | `test-secret-token-123` | Authentication token for company API |
| `OPENROUTER_API_KEY` | `test-key` | Dummy key (proxy doesn't use it) |

### Model Mapping

The proxy maps OpenCode model requests to your company's API endpoints:

```python
# Primary supported models
"openrouter/anthropic/claude-3.5-sonnet" → "ai-coe-bedrock-claude35-sonnet-200k"
"openrouter/anthropic/claude-3-opus" → "ai-coe-bedrock-claude3-opus"
"openrouter/openai/gpt-4" → "ai-coe-openai-gpt4"

# Unmapped models → Default (Claude 3.5 Sonnet)
"openrouter/openai/gpt-5" → "ai-coe-bedrock-claude35-sonnet-200k"
```

## Important Behavior

### Model Fallback

**ALL models work through the proxy**, even those not explicitly mapped:
- Supported models use their specific endpoints
- Unsupported models fall back to Claude 3.5 Sonnet
- No errors - graceful handling of any model selection

### OpenCode Model List

OpenCode shows many OpenRouter models in its UI, but:
- This is a cosmetic issue (hardcoded in OpenCode)
- Only 3 models are properly mapped to company endpoints
- All other models use the default fallback
- The proxy still intercepts and handles all requests

### Verification

In mock mode, all responses are "Hatsune Miku":
- This unique response confirms the proxy is active
- Easy to verify routing is working correctly
- Helps debug configuration issues

## Technical Details

### Request Translation

1. **OpenCode → Company Format**:
   - Extracts messages and system prompts
   - Maps model names to company endpoints
   - Converts to company's expected JSON structure
   - Adds required headers and authentication

2. **Company → OpenCode Format**:
   - Extracts response content
   - Builds OpenAI-compatible response structure
   - Handles streaming and tokens
   - Maintains conversation context

### Proxy Hijacking

The proxy works by hijacking OpenRouter configuration:
```json
{
  "provider": {
    "openrouter": {
      "options": {
        "baseURL": "http://localhost:8052/v1"
      }
    }
  }
}
```

OpenCode thinks it's talking to OpenRouter, but requests go to our proxy.

## Troubleshooting

### "Hatsune Miku" not appearing
- Check proxy is running: `curl http://localhost:8052/health`
- Verify OpenCode config: `cat opencode.json`
- Check logs: `tail -f /tmp/wrapper.log`

### Container issues
- Rebuild: `docker build -f docker/opencode-with-proxy.Dockerfile -t opencode-with-proxy:latest .`
- Check ports 8050/8052 aren't in use: `lsof -i :8050`
- Verify Docker is running: `docker ps`

### Real API not working
- Verify environment variables are set correctly
- Check network connectivity to company API
- Confirm API token is valid and not expired
- Review wrapper logs for specific errors

## Advanced Usage

### Custom Model Mappings

Edit `automation/proxy/api_translation_wrapper.py`:
```python
MODEL_MAPPING = {
    "your-model": "company-endpoint",
    # Add more mappings
}
```

### Response Format Customization

Modify translation functions:
- `translate_to_company_format()` - Request transformation
- `translate_from_company_format()` - Response transformation

### Adding New Company API Formats

1. Update request builder in `translate_to_company_format()`
2. Update response parser in `translate_from_company_format()`
3. Adjust headers and authentication as needed

## Files Reference

| File | Purpose |
|------|---------|
| `automation/proxy/api_translation_wrapper.py` | Main proxy service |
| `automation/proxy/mock_company_api.py` | Mock API for testing |
| `automation/proxy/container_entrypoint.sh` | Container startup script |
| `automation/proxy/run_opencode_container.sh` | Easy launcher script |
| `docker/opencode-with-proxy.Dockerfile` | Container definition |
| `automation/proxy/README.md` | Quick reference guide |
| `automation/proxy/CONTAINER_SOLUTION.md` | Container details |
| `automation/proxy/OPENCODE_MODELS_ISSUE.md` | Model list limitation |

## Security Considerations

- API tokens via environment variables only
- No hardcoded credentials in code
- Services bind to localhost only (not exposed externally)
- Container runs as non-root user
- Mock mode for safe testing without real API access

## Future Improvements

1. **Custom Provider Support**: Contribute to OpenCode to properly support custom providers
2. **Model Filtering**: Build a UI wrapper that filters displayed models
3. **Multiple Backends**: Support routing to different company APIs based on model
4. **Caching**: Add response caching for frequently used prompts
5. **Metrics**: Add usage tracking and monitoring

## Summary

The OpenCode Proxy successfully enables OpenCode to work with internal company APIs by:
- Intercepting all OpenRouter traffic
- Translating between API formats
- Providing graceful fallback for all models
- Working seamlessly in Docker containers
- Offering both mock and production modes

This solution is production-ready and actively used for AI development with corporate API endpoints.

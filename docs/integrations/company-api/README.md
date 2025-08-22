# Company API Integration for OpenCode

This documentation describes how to configure OpenCode to use your company's internal AI API endpoint instead of OpenRouter.

## Overview

Since OpenCode supports custom API endpoints through its provider configuration, we've created an **API Translation Wrapper** that:
1. Accepts requests in the format OpenCode expects
2. Translates them to your company's API format
3. Forwards to your company's AI endpoint
4. Translates responses back to OpenCode's expected format

## Architecture

```
OpenCode → Translation Wrapper → Company API
         ←                     ←
```

The translation wrapper acts as a bridge, making your company's API compatible with OpenCode without requiring any modifications to OpenCode itself.

## Components

### 1. Mock Company API (`mock_company_api.py`)
- **Purpose**: Testing endpoint that mimics your company's API format
- **Port**: 8050
- **Response**: Always returns "Hatsune Miku" for testing
- **Auth**: Bearer token authentication

### 2. API Translation Wrapper (`api_translation_wrapper.py`)
- **Purpose**: Translates between OpenCode and company API formats
- **Port**: 8052
- **Modes**: Mock (testing) or Production (real API)
- **Endpoints**:
  - `/v1/chat/completions` - Main chat endpoint
  - `/v1/models` - List available models
  - `/health` - Health check

### 3. OpenCode Configuration (`opencode-custom.jsonc`)
- Custom provider configuration pointing to the translation wrapper
- Disables default providers (OpenRouter, Anthropic, OpenAI)
- Maps models to company endpoints

## Quick Start

### 1. Start Services with Docker

```bash
# Start both mock API and translation wrapper
docker-compose --profile proxy up -d

# Or start individually
docker-compose up -d mock-company-api
docker-compose up -d api-translation-wrapper
```

### 2. Test the Integration

```bash
# Run the test script
python automation/proxy/test_integration.py
```

This will test:
- Direct mock API connection
- Translation wrapper functionality
- Streaming support
- OpenCode integration (if installed)

### 3. Configure OpenCode

Use the custom configuration file:

```bash
# Set environment variable
export OPENCODE_CONFIG=/path/to/automation/proxy/opencode-custom.jsonc
export COMPANY_API_KEY=mock-api-key-for-testing

# Run OpenCode
opencode run -q "Hello, who are you?"
```

## Configuration

### Environment Variables

#### For Translation Wrapper:
- `WRAPPER_MOCK_MODE`: Set to `true` for testing, `false` for production
- `COMPANY_API_BASE`: Base URL of company API (default: `http://localhost:8050`)
- `COMPANY_API_TOKEN`: Authentication token for company API

#### For Production:
```bash
export WRAPPER_MOCK_MODE=false
export COMPANY_API_BASE=https://aigateway-prod.apps-1.gp-1-prod.openshift.cignacloud.com
export COMPANY_API_TOKEN=your-real-token-here
```

### Model Mapping

Edit `MODEL_MAPPING` in `api_translation_wrapper.py` to map OpenCode model IDs to company endpoints:

```python
MODEL_MAPPING = {
    "claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "gpt-4": "ai-coe-openai-gpt4:analyze=null",
    # Add more mappings as needed
}
```

## API Format Translation

### OpenCode Request Format
```json
{
  "model": "claude-3.5-sonnet",
  "messages": [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello"}
  ],
  "max_tokens": 1000,
  "temperature": 0.7
}
```

### Company API Format
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "system": "You are helpful",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "max_tokens": 1000,
  "temperature": 0.7
}
```

The wrapper handles this translation automatically.

## Testing

### Manual Testing

1. Test mock API directly:
```bash
curl -X POST http://localhost:8050/api/v1/AI/GenAIExplorationLab/Models/ai-coe-bedrock-claude35-sonnet-200k:analyze=null \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-secret-token-123" \
  -d '{
    "anthropic_version": "bedrock-2023-05-31",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

2. Test translation wrapper:
```bash
curl -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3.5-sonnet",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

### Automated Testing

Run the comprehensive test suite:
```bash
python automation/proxy/test_integration.py
```

## Production Deployment

### 1. Update Configuration

Set production environment variables:
```bash
export WRAPPER_MOCK_MODE=false
export COMPANY_API_BASE=https://your-company-api.com
export COMPANY_API_TOKEN=your-production-token
```

### 2. Deploy with Docker

```bash
# Build and deploy
docker-compose --profile proxy build
docker-compose --profile proxy up -d api-translation-wrapper
```

### 3. Configure OpenCode Container

For the containerized OpenCode:
```bash
docker-compose run --rm openrouter-agents \
  -e OPENCODE_CONFIG=/workspace/automation/proxy/opencode-custom.jsonc \
  -e COMPANY_API_KEY=your-api-key \
  opencode run -q "Your prompt here"
```

## Troubleshooting

### Issue: OpenCode not using custom endpoint
- Verify `OPENCODE_CONFIG` environment variable is set
- Check that disabled_providers includes "openrouter"
- Ensure the translation wrapper is running

### Issue: Authentication errors
- Verify `COMPANY_API_TOKEN` is correct
- Check Bearer token format in headers
- Ensure token has necessary permissions

### Issue: Model not found
- Check MODEL_MAPPING in translation wrapper
- Verify model ID in OpenCode configuration
- Ensure company API supports the requested model

### Issue: Response format errors
- Check translation logic in wrapper
- Verify company API response format
- Enable debug logging to see raw responses

## Security Considerations

1. **API Keys**: Never commit real API keys to the repository
2. **Network Isolation**: Use Docker networks to isolate services
3. **HTTPS**: Use HTTPS for production deployments
4. **Token Rotation**: Regularly rotate API tokens
5. **Access Control**: Limit wrapper access to authorized services only

## Adding New Models

To add support for new models:

1. Update `MODEL_MAPPING` in `api_translation_wrapper.py`
2. Add model configuration in `opencode-custom.jsonc`
3. Test with mock endpoint first
4. Deploy to production after verification

## Monitoring

The wrapper provides health checks and logging:

```bash
# Check health
curl http://localhost:8052/health

# View logs
docker-compose logs -f api-translation-wrapper
```

## Future Enhancements

- [ ] Add caching layer for repeated requests
- [ ] Implement request/response logging for audit
- [ ] Add metrics collection (latency, usage)
- [ ] Support for multiple company API endpoints
- [ ] Automatic retry with exponential backoff
- [ ] Request rate limiting
- [ ] Response streaming optimization

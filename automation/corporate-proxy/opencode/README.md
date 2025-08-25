# OpenCode Corporate Proxy Integration

## Overview

This integration allows OpenCode CLI to work with corporate AI services by translating between OpenRouter/OpenAI API format and Company's Bedrock-based format.

## Architecture

```
OpenCode CLI → OpenRouter API → Translation Wrapper → Company Bedrock API
                            ↓
                        Mock API (for testing outside corporate network)
```

## Quick Start

### Testing the API Translation Layer

The simplest test to verify the proxy is working:

```bash
cd automation/corporate-proxy/opencode
./scripts/test-api-only.sh
```

This will:
1. Start the mock Company API service
2. Start the translation wrapper
3. Send a test request and verify the response

Expected output: `Response: Hatsune Miku`

### Using with OpenCode CLI

If you have OpenCode installed locally, you can use it with the proxy:

```bash
# Set environment variables to point to the proxy
export OPENROUTER_API_KEY="your-key-or-test-token"
export OPENROUTER_BASE_URL="http://localhost:8052/v1"

# Start the proxy services
docker run -d --name opencode-proxy \
    -p 8050:8050 -p 8052:8052 \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    -v "$PWD/../shared/services:/app:ro" \
    python:3.11-alpine sh -c '
        pip install --quiet flask flask-cors requests &&
        python /app/mock_api.py &
        python /app/translation_wrapper.py &
        sleep infinity
    '

# Now use OpenCode normally
opencode ask "Write a Python function to calculate fibonacci"

# Stop the proxy when done
docker stop opencode-proxy && docker rm opencode-proxy
```

## Production Deployment

For production use with real Company API:

```bash
export COMPANY_API_BASE="https://bedrock.internal.company.com"
export COMPANY_API_TOKEN="your-actual-company-token"
export OPENROUTER_API_KEY="your-openrouter-key"
export OPENROUTER_BASE_URL="http://localhost:8052/v1"

# Start the translation wrapper (no mock API needed)
docker run -d --name opencode-proxy \
    -p 8052:8052 \
    -e COMPANY_API_BASE="$COMPANY_API_BASE" \
    -e COMPANY_API_TOKEN="$COMPANY_API_TOKEN" \
    -v "$PWD/../shared/services:/app:ro" \
    python:3.11-alpine sh -c '
        pip install --quiet flask flask-cors requests &&
        python /app/translation_wrapper.py
    '
```

## Model Mapping

The translation wrapper automatically maps OpenRouter model names to Company endpoints:

| OpenRouter Model | Company Endpoint |
|------------------|------------------|
| openrouter/anthropic/claude-3.5-sonnet | ai-coe-bedrock-claude35-sonnet-200k:analyze=null |
| openrouter/anthropic/claude-3-opus | ai-coe-bedrock-claude3-opus:analyze=null |
| openrouter/openai/gpt-4 | ai-coe-bedrock-gpt4:analyze=null |
| gpt-4 | ai-coe-bedrock-claude35-sonnet-200k:analyze=null |
| gpt-3.5-turbo | ai-coe-bedrock-claude3-opus:analyze=null |

## Directory Structure

```
opencode/
├── config/
│   └── opencode-config.json    # OpenCode configuration (if needed)
├── docker/
│   ├── Dockerfile              # Full OpenCode build (complex)
│   └── Dockerfile-simple       # Simple container (recommended)
├── scripts/
│   ├── test-api-only.sh       # Test translation layer only
│   ├── test-direct.sh          # Test direct API calls
│   ├── test-opencode.sh       # Test with OpenCode CLI
│   └── run-interactive.sh      # Interactive session
└── README.md                   # This file
```

## Shared Services

This integration uses shared services from `automation/corporate-proxy/shared/`:
- `translation_wrapper.py` - Converts between API formats
- `mock_api.py` - Mock Company API for testing
- `common-functions.sh` - Bash utilities

## Troubleshooting

### API Translation Issues
- Verify services are running: `docker ps`
- Check ports 8050 (mock) and 8052 (wrapper) are accessible
- Test API directly: `./scripts/test-api-only.sh`

### Model Not Found
- Ensure model name is in the mapping table
- Check `shared/services/translation_wrapper.py` for supported models

### Connection Refused
- Make sure Docker is running
- Verify no other services are using ports 8050/8052
- Check firewall settings

## Security Notes

- API tokens are passed via environment variables
- Never commit real tokens to the repository
- Mock API only returns test responses
- All prompts stay within corporate network in production

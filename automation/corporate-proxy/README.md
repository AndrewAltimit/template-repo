# Corporate AI Proxy Solutions

This directory contains proxy integrations that enable popular AI development tools to work with corporate AI services behind firewalls or with custom authentication.

## Overview

Many AI development tools (OpenCode, Crush, etc.) are designed to work with public AI APIs like OpenAI or Anthropic. In corporate environments, AI services are often:
- Behind firewalls with custom authentication
- Using different API formats (e.g., AWS Bedrock)
- Subject to compliance and security requirements

These proxy solutions act as translation layers, allowing developers to use their favorite AI tools while complying with corporate policies.

## Architecture

```
AI Tool → Standard API Format → Translation Proxy → Corporate AI Service
                            ↓
                    Mock Service (for testing)
```

## Integrated Tools

### 1. Crush CLI
- **Directory**: `crush/`
- **Status**: ✅ Fully working with Catwalk bypass
- **Test**: `cd crush && ./scripts/test-patched.sh`
- Bypasses provider validation to work with custom endpoints

### 2. OpenCode CLI
- **Directory**: `opencode/`
- **Status**: ✅ API translation working
- **Test**: `cd opencode && ./scripts/test-api-only.sh`
- Translates OpenRouter API calls to corporate format

## Shared Components

The `shared/` directory contains reusable components:

### Services
- `translation_wrapper.py` - Converts between OpenAI/OpenRouter and corporate API formats
- `mock_api.py` - Simulates corporate API responses for testing

### Scripts
- `common-functions.sh` - Bash utilities for consistent output and Docker operations

## Quick Start

### Testing with Mock Services

Both integrations can be tested without corporate network access:

```bash
# Test Crush
cd crush
./scripts/test-patched.sh
# Expected: "Hatsune Miku"

# Test OpenCode
cd opencode
./scripts/test-api-only.sh
# Expected: "Response: Hatsune Miku"
```

### Production Deployment

Set environment variables for your corporate API:

```bash
export COMPANY_API_BASE="https://bedrock.internal.company.com"
export COMPANY_API_TOKEN="your-actual-token"
```

Then run the proxy containers with these credentials.

## Model Mapping

The translation layer maps standard model names to corporate endpoints:

| Standard Model | Corporate Endpoint |
|----------------|-------------------|
| gpt-4 | ai-coe-bedrock-claude35-sonnet-200k |
| gpt-3.5-turbo | ai-coe-bedrock-claude3-opus |
| claude-3.5-sonnet | ai-coe-bedrock-claude35-sonnet-200k |

## Security Considerations

- **Credentials**: Use environment variables, never hardcode
- **Network**: Proxy runs locally, minimizing attack surface
- **Logging**: Sensitive data is not logged
- **Testing**: Mock services prevent accidental data exposure

## Adding New Tools

To integrate a new AI tool:

1. Create a directory under `corporate-proxy/`
2. Use shared services for API translation
3. Create Docker container for isolation
4. Add test scripts following existing patterns
5. Document model mappings and configuration

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure 8050-8052 are available
2. **Docker permissions**: User must be in docker group
3. **Model not found**: Check model mapping in translation_wrapper.py
4. **Connection refused**: Verify Docker daemon is running

### Debug Mode

Enable debug output:
```bash
export DEBUG=1
# Run your test script
```

## Contributing

When adding new integrations:
- Follow the existing directory structure
- Reuse shared components
- Include comprehensive test scripts
- Document all environment variables
- Test with both mock and real services

## License

Part of the template-repo project. See repository root for license information.

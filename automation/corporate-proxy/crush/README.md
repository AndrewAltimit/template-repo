# Crush Corporate Proxy Integration

## Overview

This integration allows the Crush CLI tool to work with corporate AI services by translating between OpenAI API format and Company's Bedrock-based format. It includes a patched solution to bypass Crush's provider validation requirements.

## Architecture

```
Crush CLI → OpenAI API → Translation Wrapper → Company Bedrock API
                    ↓
                Mock API (for testing outside corporate network)
```

## Key Components

1. **Translation Wrapper** (`shared/services/translation_wrapper.py`)
   - Converts OpenAI API calls to Company Bedrock format
   - Handles streaming responses
   - Maps model names appropriately

2. **Mock API** (`shared/services/mock_api.py`)
   - Simulates Company API responses for testing
   - Returns "Hatsune Miku" as test response
   - Used when outside corporate network

3. **Crush Wrapper** (`scripts/crush-wrapper.sh`)
   - **Bypasses Catwalk provider validation**
   - Creates fake provider cache
   - Configures environment properly

4. **Docker Container** (`docker/Dockerfile`)
   - Alpine-based for minimal size
   - Includes patched solution
   - Runs all services together

## Quick Start

### Testing with Mock API

```bash
# Test the patched solution
./scripts/test-patched.sh

# Test API translation directly
./scripts/test-direct.sh

# Run interactive Crush session
./scripts/run-interactive.sh
```

### Production Use

Inside the corporate network:
```bash
export COMPANY_API_BASE="https://bedrock.internal.company.com"
export COMPANY_API_TOKEN="your-actual-token"
docker-compose up crush-corporate
```

## Configuration

The configuration file (`config/crush-config.json`) uses OpenAI as the provider:
```json
{
  "providers": {
    "openai": {
      "id": "openai",
      "name": "OpenAI (Company Proxy)",
      "base_url": "http://localhost:8052/v1",
      "type": "openai",
      "api_key": "test-secret-token-123"
    }
  },
  "models": {
    "large": {
      "model": "gpt-4",
      "provider": "openai"
    },
    "small": {
      "model": "gpt-3.5-turbo",
      "provider": "openai"
    }
  }
}
```

## The Catwalk Problem and Solution

### Problem
Crush validates all providers against a centralized list from the Catwalk service. Custom providers are rejected, preventing corporate proxy usage.

### Solution
We implemented a wrapper script (`scripts/crush-wrapper.sh`) that creates a fake provider cache, bypassing the Catwalk validation. The wrapper:
- Creates a fake `providers.json` cache file
- Sets environment variables to force cache usage
- Transparently launches the actual Crush binary

### Important: Solution Fragility

**Warning**: This bypass solution relies on Crush's internal implementation details and is inherently fragile:

1. **Cache Path Dependency**: The solution assumes Crush stores its cache in `~/.local/share/crush`. If Crush changes this location in a future update, the bypass will fail.

2. **Environment Variable Dependency**: We rely on the `CATWALK_URL` environment variable to force cache usage. If Crush changes how it handles provider validation or removes this override mechanism, the bypass will break.

3. **Internal API Changes**: The structure of the `providers.json` cache file mimics Crush's internal format. Changes to this format will require updating our fake cache generation.

4. **Version Sensitivity**: The solution is tested with Crush v0.8.0-nightly. Major version updates may introduce breaking changes.

#### Mitigation Strategies

While this fragility is acceptable for an internal corporate tool, consider these strategies:

- **Version Pinning**: Always use a specific Crush version in the Dockerfile
- **Automated Testing**: The test scripts help detect when the bypass breaks
- **Fallback Options**: Keep OpenCode as an alternative if Crush bypass fails
- **Monitor Updates**: Check Crush release notes for validation changes

#### Long-term Solution

The ideal solution would be for Crush to officially support custom provider configuration without Catwalk validation, or to allow disabling provider validation entirely for corporate use cases.

## Model Mapping

| Crush Model | Company Endpoint |
|-------------|------------------|
| gpt-4 | ai-coe-bedrock-claude35-sonnet-200k:analyze=null |
| gpt-3.5-turbo | ai-coe-bedrock-claude3-opus:analyze=null |
| company/claude-3.5-sonnet | ai-coe-bedrock-claude35-sonnet-200k:analyze=null |
| company/gpt-4 | ai-coe-bedrock-gpt4:analyze=null |

## Directory Structure

```
crush/
├── config/
│   └── crush-config.json      # Crush configuration
├── docker/
│   └── Dockerfile             # Container with patched solution
├── scripts/
│   ├── crush-wrapper.sh      # Bypass validation wrapper
│   ├── start-services.sh     # Service startup script
│   ├── test-patched.sh       # Test patched solution
│   ├── test-direct.sh        # Test API directly
│   └── run-interactive.sh    # Interactive session
├── ANALYSIS.md               # Deep dive into Catwalk issue
├── PATCHED_SOLUTION.md       # Bypass solution details
└── README.md                 # This file
```

## Shared Services

This integration uses shared services from `automation/corporate-proxy/shared/`:
- Translation wrapper for API conversion
- Mock API for testing
- Common bash functions for scripts

## Troubleshooting

### "No providers configured" Error
This should be resolved by the patched solution. If it persists:
1. Check that the wrapper script is being used
2. Verify the provider cache is created
3. Ensure CATWALK_URL is set to force cache usage

### API Connection Issues
1. Verify services are running: `docker logs crush-corporate`
2. Check ports 8050 (mock) and 8052 (wrapper) are accessible
3. Test API directly: `./scripts/test-direct.sh`

### Model Not Found
Ensure the model name matches one in the configuration. Use `company/` prefix for custom models.

## Security Notes

- API tokens are passed via environment variables
- Never commit real tokens to the repository
- Mock API only returns test responses
- All prompts stay within corporate network in production

## Future Enhancements

1. Support for more AI providers
2. Response caching for common queries
3. Usage analytics and monitoring
4. Dynamic model discovery
5. Automatic Crush updates with validation

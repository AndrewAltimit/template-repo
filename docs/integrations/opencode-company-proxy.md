# OpenCode Company Proxy Integration

## Overview

This integration customizes [OpenCode](https://github.com/sst/opencode) to work with internal company AI APIs through a translation proxy, allowing organizations to use their own AI infrastructure while maintaining OpenCode's user experience.

## Architecture

The integration uses a three-tier architecture:

```
OpenCode (patched) → Translation Wrapper (port 8052) → Company API (port 8050)
```

### Components

1. **OpenCode Container** (`opencode-company-tui`)
   - Patched version of OpenCode with limited model selection
   - Configured to use translation wrapper endpoint
   - Includes TUI support for interactive mode

2. **Translation Wrapper** (`company_translation_wrapper.py`)
   - Translates between OpenAI format and company-specific Bedrock format
   - Handles authentication and model mapping
   - Provides streaming simulation (buffered responses)

3. **Mock API** (`mock_company_api.py`)
   - Simulates company API for testing outside corporate network
   - Returns test responses for development
   - Validates request/response format

## Usage

### Quick Start with Mock Services

**Note: This integration has been superseded by a more comprehensive solution.**

Please use the new corporate proxy integration:
```bash
# Build the new container
cd automation/corporate-proxy/opencode
./scripts/build.sh

# Run with auto-starting mock services
./scripts/run.sh
```

For complete documentation, see:
- `/automation/corporate-proxy/opencode/README.md` - OpenCode integration
- `/automation/corporate-proxy/shared/docs/ARCHITECTURE.md` - Architecture details

The container automatically:
- Starts mock Company API on port 8050
- Starts translation wrapper on port 8052
- Configures OpenCode to use the wrapper
- Provides interactive TUI interface

### Production Mode

For use with real company APIs:

```bash
# Set company credentials
export COMPANY_API_BASE="https://your-company-api-gateway"
export COMPANY_API_TOKEN="your-token"

# Run in production mode (new approach)
cd automation/corporate-proxy/opencode
./scripts/run-production.sh
```

### Available Commands

- `opencode` - Interactive TUI mode
- `opencode serve` - Headless server mode
- `opencode run "prompt"` - Single command mode
- `opencode models` - List available models

## Company API Format

The translation wrapper handles conversion between OpenAI and company-specific formats:

### Company Request Format
```json
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1000,
    "system": "System prompt",
    "messages": [
        {"role": "user", "content": "Message"}
    ]
}
```

### OpenAI Format (from OpenCode)
```json
{
    "model": "company/claude-3.5-sonnet",
    "messages": [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Message"}
    ],
    "max_tokens": 1000,
    "stream": false
}
```

## Model Configuration

The integration limits available models to organization-specific options:

- `company/claude-3.5-sonnet` - Claude 3.5 Sonnet
- `company/claude-3-opus` - Claude 3 Opus
- `company/gpt-4` - GPT-4

Model configuration is defined in `automation/corporate-proxy/opencode/docker/patches/company-override.json`.

## Technical Details

### Build Process

1. Clones OpenCode source
2. Patches TypeScript files to limit models
3. Compiles with Bun to create binary
4. Builds TUI separately (Go binary)
5. Packages in container with Python services

### Key Files

- `automation/corporate-proxy/opencode/docker/Dockerfile` - Container definition
- `automation/corporate-proxy/opencode/docker/patches/company-override.json` - Model configuration
- `automation/corporate-proxy/shared/services/translation_wrapper.py` - API translator
- `automation/corporate-proxy/shared/services/mock_api.py` - Mock service (new)
- ~~`automation/proxy/`~~ - Legacy scripts (deprecated, use `/automation/corporate-proxy/` instead)

### Environment Variables

- `COMPANY_MOCK_MODE` - Enable mock services (true/false)
- `COMPANY_AUTO_START` - Auto-start OpenCode TUI (true/false)
- `COMPANY_API_BASE` - Company API endpoint
- `COMPANY_API_TOKEN` - Authentication token
- `OPENROUTER_API_KEY` - API key for OpenCode
- `MOCK_API_PORT` - Mock API port (default: 8050)
- `WRAPPER_PORT` - Translation wrapper port (default: 8052)

## Limitations

1. **Streaming**: Responses are buffered, not truly streamed
2. **Tool Calling**: Not supported in company API format
3. **Model Naming**: Uses simplified names, not full paths

## Troubleshooting

### Config File Errors
- OpenCode doesn't use config files in this setup
- API endpoint is hardcoded in models configuration

### Connection Issues
- Ensure mock services are running (check with `ps aux`)
- Verify ports 8050 and 8052 are available
- Check logs in `/tmp/mock_api.log` and `/tmp/wrapper.log`

### TUI Not Working
- TUI binary is included at `/home/bun/.cache/opencode/tui/`
- Ensure terminal supports interactive mode (TTY)

## Future Improvements

- True streaming support when company API supports it
- Additional model support as needed
- Configuration management for multiple environments
- CI/CD pipeline for automated builds

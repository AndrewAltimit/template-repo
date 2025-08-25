# Gemini CLI Corporate Proxy Integration

This integration enables Gemini CLI to work within corporate environments by providing a proxy layer that translates between Gemini's API format and corporate API endpoints.

## Features

### 1. Full Containerization
- Gemini CLI runs in a Docker container (contrary to official documentation stating it cannot be containerized)
- Multi-stage build for optimized image size
- Runs as non-root user for enhanced security
- All dependencies included - no local installation required

### 2. Corporate Proxy Integration
- Transparent API translation between Gemini and corporate formats
- Mock mode for testing and validation
- Configurable endpoints via environment variables
- Support for corporate authentication tokens

### 3. Optimized User Experience
- **Auto-launch**: Container starts directly in Gemini CLI
- **No authentication prompts**: Pre-configured with API key authentication
- **Quick launcher script**: Simple `./gemini` command from the gemini directory
- **Multiple run modes**: Interactive, test, and daemon modes

## Quick Start

```bash
# Build the container
./scripts/build.sh

# Run in interactive mode (default)
./gemini
# or
./scripts/run.sh

# Run tests
./scripts/run.sh test

# Run in background (daemon mode)
./scripts/run.sh daemon
```

## Architecture

The integration consists of three main components:

1. **Mock API Service** (Port 8050)
   - Simulates corporate API responses
   - Returns test data in development mode
   - Configurable for production endpoints

2. **Gemini Proxy Wrapper** (Port 8053)
   - Translates Gemini API requests to corporate format
   - Handles response transformation
   - Manages authentication headers

3. **Gemini CLI** (Patched)
   - Bundle modified to use local proxy
   - Authentication pre-configured
   - API endpoint redirection via sed patches

## Configuration

### Environment Variables

```bash
# API Configuration
COMPANY_API_BASE=http://localhost:8050  # Corporate API endpoint
COMPANY_API_TOKEN=your-token-here        # Authentication token
USE_MOCK_API=true                        # Enable mock mode for testing

# Proxy Ports
GEMINI_PROXY_PORT=8053
MOCK_API_PORT=8050
```

### Production Deployment

For production use, update the environment variables in the Dockerfile:

```dockerfile
ENV COMPANY_API_BASE="https://your-corporate-api.com"
ENV COMPANY_API_TOKEN="production-token"
ENV USE_MOCK_API=false
```

## Technical Implementation

### Key Achievements

1. **Containerization Success**: Proved Gemini CLI can be containerized by using Node.js bundle directly
2. **API Validation Bypass**: Patched bundle to redirect Google API calls to local proxy
3. **Authentication Automation**: Pre-configured settings.json eliminates auth prompts
4. **Corporate Integration**: Follows same pattern as OpenCode and Crush integrations

### File Structure

```
gemini/
├── docker/
│   └── Dockerfile           # Multi-stage container build
├── scripts/
│   ├── build.sh            # Build container image
│   ├── run.sh              # Run container with options
│   └── gemini-wrapper.sh   # Container entrypoint script
├── config/
│   └── gemini-config.json  # Gemini configuration
├── patches/                # Bundle modification patches
│   ├── api-redirect.patch
│   └── auth-bypass.patch
├── gemini_proxy_wrapper.py # Main proxy service
├── gemini                  # Quick launcher script
└── README.md              # This file
```

## Testing

The test suite validates:
- Service health checks
- API proxy functionality
- Gemini CLI integration
- Mock response verification

Run tests with:
```bash
./scripts/run.sh test
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: The container runs as non-root user. Ensure mounted directories have appropriate permissions.

2. **API Connection Failed**: Check that proxy services are running:
   ```bash
   docker logs gemini-proxy
   ```

3. **Authentication Issues**: Verify GEMINI_API_KEY environment variable is set (dummy value for proxy mode).

## Security Considerations

- Container runs as non-root user (appuser)
- API tokens managed via environment variables
- TLS verification disabled only for local proxy communication
- No credentials stored in image

## Future Enhancements

- [ ] Add support for streaming responses
- [ ] Implement response caching
- [ ] Add metrics and monitoring
- [ ] Support for multiple corporate API backends

## Related Documentation

- [OpenCode Integration](../opencode/README.md)
- [Crush Integration](../crush/README.md)
- [Corporate Proxy Overview](../README.md)

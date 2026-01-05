# Gemini MCP Server

> A Model Context Protocol server for Google Gemini AI integration, providing second opinions, code validation, and AI-assisted code review.

## Validation Status

| Component | Status | Description |
|-----------|--------|-------------|
| AI Consultation | Validated | Code review and second opinions |
| Conversation History | Validated | Context maintained across queries |
| Container Mode | Validated | Docker-based execution |
| Rate Limiting | Validated | Built-in API quota management |

**Scope**: This server provides AI consultation via Google's Gemini API. Best suited for **code review tasks** - tool use capabilities are limited compared to other AI agents.

**Note on Tool Use**: The Gemini CLI currently has limited tool use capabilities. For interactive code generation or complex multi-step tasks, consider using OpenCode, Crush, or Codex instead. Gemini excels at code review and validation.

## Quick Start

```bash
# Set API key (free tier available)
export GOOGLE_API_KEY="your-api-key-here"  # Get from https://aistudio.google.com/app/apikey

# Using docker-compose
docker-compose up -d mcp-gemini

# Or run directly
python -m mcp_gemini.server --mode http

# Test health
curl http://localhost:8006/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_gemini` | Get AI assistance for review/validation | `query` (required), `context`, `comparison_mode`, `force` |
| `clear_gemini_history` | Clear conversation history | None |
| `gemini_status` | Get integration status | None |
| `toggle_gemini_auto_consult` | Control auto-consultation | `enable` |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GOOGLE_API_KEY` | - | **Required**: Google AI Studio API key |
| `GEMINI_ENABLED` | `true` | Enable/disable integration |
| `GEMINI_TIMEOUT` | `60` | Request timeout (seconds) |
| `GEMINI_RATE_LIMIT` | `2` | Delay between requests (seconds) |
| `GEMINI_MAX_CONTEXT` | `4000` | Maximum context length |
| `GEMINI_AUTO_CONSULT` | `true` | Auto-consultation on uncertainty |
| `GEMINI_USE_CONTAINER` | `true` | Use Docker container |
| `GEMINI_INCLUDE_HISTORY` | `true` | Include conversation history |
| `GEMINI_MAX_HISTORY` | `10` | Maximum history entries |

### API Key Setup

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Free tier: 60 requests/min, 1,500 requests/day
3. Set `GOOGLE_API_KEY` environment variable or add to `.env`

## Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| Container (default) | Runs in Docker with host auth | Production |
| Host | Direct Python execution | Development |
| Corporate Proxy | `automation/corporate-proxy/gemini/` | Enterprise |

## Docker Support

```bash
# Build container
./automation/corporate-proxy/gemini/scripts/build.sh

# Start server
docker-compose up -d mcp-gemini

# View logs
docker-compose logs -f mcp-gemini
```

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "gemini": {
      "command": "python",
      "args": ["-m", "mcp_gemini.server", "--mode", "stdio"]
    }
  }
}
```

## Testing

```bash
# Test server
python tools/mcp/mcp_gemini/scripts/test_server.py

# Test container mode
python tools/mcp/mcp_gemini/scripts/test_container.py

# Health check
curl -s http://localhost:8006/health | jq
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| API key error | Missing `GOOGLE_API_KEY` | Set env var or add to `.env` |
| Container not found | Image not built | Run `./automation/corporate-proxy/gemini/scripts/build.sh` |
| Timeout errors | Complex query or slow network | Increase `GEMINI_TIMEOUT` |
| Rate limit errors | Too many requests | Increase `GEMINI_RATE_LIMIT` |

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Limited tool use | Cannot execute complex multi-step tasks | Use for review only; use OpenCode/Crush for generation |
| Container auth | Requires host auth mounted | Build container with auth |
| Rate limits | Free tier has daily limits | Upgrade plan if needed |

## Best Practices

1. **Use for Code Review**: Gemini excels at reviewing and validating code
2. **Clear History**: Clear conversation history when switching contexts
3. **Provide Context**: Include relevant code for better responses
4. **Rate Limiting**: Respect limits to avoid quota issues

## Security

- API key stored in environment variable (not hardcoded)
- Container runs with non-root user
- Consultation logs can be disabled for sensitive code
- Sandbox mode available for testing

## License

Part of the template-repo project. See repository LICENSE file.

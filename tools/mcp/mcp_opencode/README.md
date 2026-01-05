# OpenCode MCP Server

> A Model Context Protocol server for AI-powered code assistance using OpenRouter, supporting code generation, refactoring, review, and explanation.

## Validation Status

| Component | Status | Description |
|-----------|--------|-------------|
| Code Generation | Validated | Generate new code from descriptions |
| Code Refactoring | Validated | Improve existing code structure |
| Code Review | Validated | Analyze code for issues |
| Code Explanation | Validated | Explain code functionality |

**Scope**: This server provides AI-powered code assistance via OpenRouter API. It supports both STDIO (local process) and HTTP (remote/cross-machine) transport modes.

## Transport Modes

**STDIO Mode** (Default for Claude Code):
- For local use on the same machine as the client
- Automatically managed by Claude via `.mcp.json`
- No manual startup required

**HTTP Mode** (Port 8014):
- For cross-machine access or containerized deployment
- Runs as a persistent network service

## Quick Start

```bash
# Set your API key
export OPENROUTER_API_KEY="your-api-key-here"

# STDIO mode - automatically started by Claude
# Just use the tools directly

# HTTP mode - start manually
python -m mcp_opencode.server --mode http

# Test health (HTTP mode)
curl http://localhost:8014/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_opencode` | Main consultation tool | `query` (required), `context`, `mode`, `comparison_mode`, `force` |
| `clear_opencode_history` | Clear conversation history | None |
| `opencode_status` | Get integration status | None |
| `toggle_opencode_auto_consult` | Control auto-consultation | `enable` |

### Consultation Modes

| Mode | Description |
|------|-------------|
| `quick` (default) | General queries without specific formatting |
| `generate` | Focused code generation with optional context |
| `refactor` | Refactor and improve existing code |
| `review` | Code review and analysis |
| `explain` | Explain code functionality |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OPENROUTER_API_KEY` | - | **Required**: OpenRouter API key |
| `OPENCODE_MODEL` | `qwen/qwen-2.5-coder-32b-instruct` | Model to use |
| `OPENCODE_ENABLED` | `true` | Enable/disable the server |
| `OPENCODE_TIMEOUT` | `300` | Request timeout (seconds) |
| `OPENCODE_MAX_CONTEXT` | `8000` | Maximum context length |
| `OPENCODE_LOG_GENERATIONS` | `true` | Log all generations |
| `OPENCODE_INCLUDE_HISTORY` | `true` | Include conversation history |
| `OPENCODE_MAX_HISTORY` | `5` | Maximum history entries |

### Configuration File

Create `opencode-config.json` in your project root:

```json
{
  "enabled": true,
  "timeout": 300,
  "max_context_length": 8000,
  "quiet_mode": true
}
```

## Docker Support

```bash
# Using docker-compose
docker-compose up -d mcp-opencode

# Or using the container
docker-compose run --rm openrouter-agents python -m mcp_opencode.server
```

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "opencode": {
      "command": "python",
      "args": ["-m", "mcp_opencode.server", "--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
```

## Testing

```bash
# Run the test script
python tools/mcp/mcp_opencode/scripts/test_server.py

# Health check (HTTP mode)
curl -s http://localhost:8014/health | jq
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| API key error | Missing `OPENROUTER_API_KEY` | Set environment variable |
| Server won't start | Port 8014 in use | Change port or stop conflicting service |
| Timeout errors | Complex request or slow network | Increase `OPENCODE_TIMEOUT` |
| Container issues | openrouter-agents not running | Start container with docker-compose |

## Integration with Claude

Once configured, tools are available as:
- `mcp__opencode__consult_opencode` - Main consultation tool
- `mcp__opencode__clear_opencode_history` - Clear history
- `mcp__opencode__opencode_status` - Get status
- `mcp__opencode__toggle_opencode_auto_consult` - Control auto-consultation

## License

Part of the template-repo project. See repository LICENSE file.

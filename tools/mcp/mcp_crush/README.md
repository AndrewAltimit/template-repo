# Crush MCP Server

> A Model Context Protocol server for AI-powered code generation and conversion using OpenRouter.

## Overview

This MCP server provides:
- Code generation with multiple modes
- Code explanation and analysis
- Code conversion between languages
- State management with conversation history

## Transport Modes

**STDIO Mode** (Default for Claude Code):
- For local use on the same machine as the client
- Automatically managed by Claude via `.mcp.json`
- No manual startup required

**HTTP Mode** (Port 8015):
- For cross-machine access or containerized deployment
- Runs as a persistent network service
- Useful when the server needs to run on a different machine

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY` - **Required**: Your OpenRouter API key
- `CRUSH_ENABLED` - Enable/disable the server (default: true)
- `CRUSH_TIMEOUT` - Request timeout in seconds (default: 300)
- `CRUSH_MAX_PROMPT` - Maximum prompt length (default: 4000)
- `CRUSH_LOG_GENERATIONS` - Log all generations (default: true)
- `CRUSH_INCLUDE_HISTORY` - Include conversation history (default: true)
- `CRUSH_MAX_HISTORY` - Maximum history entries (default: 5)

### Configuration File

You can also create `crush-config.json` in your project root:

```json
{
  "enabled": true,
  "timeout": 300,
  "max_prompt_length": 4000,
  "quiet_mode": true
}
```

## Running the Server

### STDIO Mode (Local Process)

For Claude Code and local MCP clients, the server is automatically started via `.mcp.json`. No manual startup needed - just use the tools:

```python
# Claude automatically starts the server when you use it
result = mcp__crush__consult_crush(query="Convert this to TypeScript...")
```

### HTTP Mode (Remote/Cross-Machine)

For running on a different machine or in a container:

```bash
# Set your API key
export OPENROUTER_API_KEY="your-api-key-here"

# Start HTTP server on port 8015
python -m mcp_crush.server --mode http

# The server will be available at http://localhost:8015
```

### Manual STDIO Mode

For testing or development:

```bash
# Run in stdio mode manually
python -m mcp_crush.server --mode stdio
```

### Docker

```bash
# Using docker-compose
docker-compose up -d mcp-crush

# Or run directly
docker run -p 8015:8015 -e OPENROUTER_API_KEY="your-key" mcp-crush
```

## Available Tools

### consult_crush

Consult Crush for code generation, explanation, conversion, or general queries.

**Parameters:**
- `query` (required): The coding question, task, or code to consult about
- `context`: Additional context or target language for conversion
- `mode`: Consultation mode (default: "quick")
  - **quick** (default): General queries without specific formatting
  - **generate**: Focused code generation with optional context
  - **explain**: Explain code functionality
  - **convert**: Convert code between languages
- `comparison_mode`: Compare with previous Claude response (default: true)
- `force`: Force consultation even if disabled (default: false)

### clear_crush_history

Clear the conversation history.

### crush_status

Get server status and statistics.

### toggle_crush_auto_consult

Toggle automatic consultation on uncertainty detection.

**Parameters:**
- `enable`: Enable or disable auto-consultation

## Testing

```bash
# Run the test script
python tools/mcp/mcp_crush/scripts/test_server.py

# Or use curl for manual testing
curl http://localhost:8015/health
curl http://localhost:8015/mcp/tools
```

## Integration with Claude

Once the server is running, it will be available as MCP tools in Claude:
- `mcp__crush__consult_crush` - Main consultation tool with multiple modes
- `mcp__crush__clear_crush_history` - Clear conversation history
- `mcp__crush__crush_status` - Get status and statistics
- `mcp__crush__toggle_crush_auto_consult` - Control auto-consultation

## Troubleshooting

1. **Server won't start**: Check that port 8015 is not in use
2. **API errors**: Ensure OPENROUTER_API_KEY is set correctly
3. **Container issues**: Make sure the openrouter-agents container is running
4. **Timeout errors**: Increase CRUSH_TIMEOUT for complex tasks

## License

Part of the template-repo project. See repository LICENSE file.

# OpenCode MCP Server

The OpenCode MCP Server provides AI-powered code generation using OpenCode, supporting both STDIO (local process) and HTTP (remote/cross-machine) transports.

## Overview

This MCP server wraps the OpenCode CLI agent to provide:
- Code generation with context and history
- Code refactoring
- Code review and analysis
- Multi-language support
- State management with conversation history

## Transport Modes

**STDIO Mode** (Default for Claude Code):
- For local use on the same machine as the client
- Automatically managed by Claude via `.mcp.json`
- No manual startup required

**HTTP Mode** (Port 8014):
- For cross-machine access or containerized deployment
- Runs as a persistent network service
- Useful when the server needs to run on a different machine

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY` - **Required**: Your OpenRouter API key
- `OPENCODE_ENABLED` - Enable/disable the server (default: true)
- `OPENCODE_MODEL` - Model to use (default: qwen/qwen-2.5-coder-32b-instruct)
- `OPENCODE_TIMEOUT` - Request timeout in seconds (default: 300)
- `OPENCODE_MAX_CONTEXT` - Maximum context length (default: 8000)
- `OPENCODE_LOG_GENERATIONS` - Log all generations (default: true)
- `OPENCODE_INCLUDE_HISTORY` - Include conversation history (default: true)
- `OPENCODE_MAX_HISTORY` - Maximum history entries (default: 5)

### Configuration File

You can also create `opencode-config.json` in your project root:

```json
{
  "enabled": true,
  "model": "qwen/qwen-2.5-coder-32b-instruct",
  "timeout": 300,
  "max_context_length": 8000
}
```

## Running the Server

### STDIO Mode (Local Process)

For Claude Code and local MCP clients, the server is automatically started via `.mcp.json`. No manual startup needed - just use the tools:

```python
# Claude automatically starts the server when you use it
result = mcp__opencode__consult_opencode(query="Write a Python function...")
```

### HTTP Mode (Remote/Cross-Machine)

For running on a different machine or in a container:

```bash
# Set your API key
export OPENROUTER_API_KEY="your-api-key-here"

# Start HTTP server on port 8014
python -m tools.mcp.opencode.server --mode http

# The server will be available at http://localhost:8014
```

### Manual STDIO Mode

For testing or development:

```bash
# Run in stdio mode manually
python -m tools.mcp.opencode.server --mode stdio
```

### Docker

```bash
# Using docker-compose
docker-compose up -d mcp-opencode

# Or run directly
docker run -p 8014:8014 -e OPENROUTER_API_KEY="your-key" mcp-opencode
```

## Available Tools

### consult_opencode
Consult OpenCode for code generation, refactoring, review, or general queries.

Parameters:
- `query` (required): The coding question, task, or code to consult about
- `context`: Additional context or existing code
- `mode`: Consultation mode - "generate", "refactor", "review", "explain", or "quick" (default: "quick")
  - **quick** (default): General queries without specific formatting, handles any coding question
  - **generate**: Focused code generation with optional context
  - **refactor**: Refactor existing code with instructions
  - **review**: Review code and provide feedback
  - **explain**: Explain code functionality
- `comparison_mode`: Compare with previous Claude response (default: true)
- `force`: Force consultation even if disabled (default: false)

### clear_opencode_history
Clear the conversation history.

### opencode_status
Get server status and statistics.

### toggle_opencode_auto_consult
Toggle automatic OpenCode consultation on uncertainty detection.

Parameters:
- `enable`: Enable or disable auto-consultation

## Testing

```bash
# Run the test script
python tools/mcp/opencode/scripts/test_server.py

# Or use curl for manual testing
curl http://localhost:8014/health
curl http://localhost:8014/tools
```

## Integration with Claude

Once the server is running, it will be available as MCP tools in Claude:
- `mcp__opencode__consult_opencode` - Main consultation tool with multiple modes
- `mcp__opencode__clear_opencode_history` - Clear conversation history
- `mcp__opencode__opencode_status` - Get status and statistics
- `mcp__opencode__toggle_opencode_auto_consult` - Control auto-consultation

## Troubleshooting

1. **Server won't start**: Check that port 8014 is not in use
2. **API errors**: Ensure OPENROUTER_API_KEY is set correctly
3. **Container issues**: Make sure the openrouter-agents container is running
4. **Timeout errors**: Increase OPENCODE_TIMEOUT for complex tasks

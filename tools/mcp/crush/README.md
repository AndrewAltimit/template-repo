# Crush MCP Server

The Crush MCP Server provides fast AI-powered code generation using Crush, supporting both STDIO (local process) and HTTP (remote/cross-machine) transports.

## Overview

This MCP server wraps the Crush CLI agent to provide:
- Quick code generation with style preferences
- Code explanation and analysis
- Code conversion between languages
- State management with conversation history
- Fast response times for rapid iteration

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
python -m tools.mcp.crush.server --mode http

# The server will be available at http://localhost:8015
```

### Manual STDIO Mode

For testing or development:

```bash
# Run in stdio mode manually
python -m tools.mcp.crush.server --mode stdio
```

### Docker

```bash
# Using docker-compose
docker-compose up -d mcp-crush

# Or run directly
docker run -p 8015:8015 -e OPENROUTER_API_KEY="your-key" mcp-crush
```

## Available Tools

### quick_generate
Fast code generation with style preferences.

Parameters:
- `prompt` (required): The coding task or question
- `style`: Output style - "concise", "detailed", or "explained" (default: "concise")

### explain_code
Get explanations for existing code.

Parameters:
- `code` (required): The code to explain
- `focus`: Specific aspect to focus on (optional)

### convert_code
Convert code between programming languages.

Parameters:
- `code` (required): The code to convert
- `target_language` (required): Target programming language
- `preserve_comments`: Whether to preserve comments (default: true)

### clear_crush_history
Clear the conversation history.

### crush_status
Get server status and statistics.

## Testing

```bash
# Run the test script
python tools/mcp/crush/scripts/test_server.py

# Or use curl for manual testing
curl http://localhost:8015/health
curl http://localhost:8015/mcp/tools
```

## Integration with Claude

Once the server is running, it will be available as MCP tools in Claude:
- `mcp__crush__quick_generate`
- `mcp__crush__explain_code`
- `mcp__crush__convert_code`
- etc.

## Style Preferences

The `quick_generate` tool supports three styles:

1. **concise**: Minimal, focused code without extra explanation
2. **detailed**: Complete implementation with all edge cases
3. **explained**: Code with inline comments and explanations

## Troubleshooting

1. **Server won't start**: Check that port 8015 is not in use
2. **API errors**: Ensure OPENROUTER_API_KEY is set correctly
3. **Container issues**: Make sure the openrouter-agents container is running
4. **Timeout errors**: Crush is optimized for speed, but increase CRUSH_TIMEOUT if needed

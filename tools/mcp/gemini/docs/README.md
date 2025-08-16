# Gemini AI Integration MCP Server

The Gemini MCP Server provides integration with Google's Gemini AI for getting second opinions, code validation, and AI-assisted development workflows.

## Important Requirements

⚠️ **This server MUST run on the host system, not in a container!**

The Gemini CLI requires Docker access to function properly, which means it cannot run inside a container itself (would require Docker-in-Docker). Always launch this server directly on your host machine.

## Features

- **AI Consultation**: Get second opinions on code and technical decisions
- **Conversation History**: Maintain context across consultations
- **Auto-consultation**: Automatic AI consultation on uncertainty detection
- **Comparison Mode**: Compare responses with previous Claude outputs
- **Rate Limiting**: Built-in rate limiting to avoid API quota issues

## Available Tools

### consult_gemini

Get AI assistance from Gemini for code review, problem-solving, or validation.

**Parameters:**
- `query` (required): The question or code to consult Gemini about
- `context`: Additional context for the consultation
- `comparison_mode`: Compare with previous Claude response (default: true)
- `force`: Force consultation even if disabled (default: false)

**Example:**
```json
{
  "tool": "consult_gemini",
  "arguments": {
    "query": "Review this function for potential issues",
    "context": "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)",
    "comparison_mode": true
  }
}
```

### gemini_status

Get current status and statistics of the Gemini integration.

**Example:**
```json
{
  "tool": "gemini_status",
  "arguments": {}
}
```

### clear_gemini_history

Clear the conversation history to start fresh consultations.

**Example:**
```json
{
  "tool": "clear_gemini_history",
  "arguments": {}
}
```

### toggle_gemini_auto_consult

Enable or disable automatic Gemini consultation when uncertainty is detected.

**Parameters:**
- `enable`: true to enable, false to disable, omit to toggle

**Example:**
```json
{
  "tool": "toggle_gemini_auto_consult",
  "arguments": {"enable": true}
}
```

## Running the Server

### Prerequisites

1. **Gemini CLI**: Install the Gemini CLI tool and ensure it's in your PATH
2. **Authentication**: Configure Gemini CLI authentication

   **⚠️ IMPORTANT - Use Web Login for Free Tier!**
   - The Gemini CLI should use **Google web login (OAuth)** for authentication
   - This provides a **FREE TIER** with 60 requests/min, 1,000 requests/day, 4M tokens/day
   - **CAUTION**: Using API keys instead of web login will result in **charges** for usage
   - For single-maintainer projects, the free tier via web login is recommended

3. **Host System**: Must run on the host, not in a container

### stdio Mode (Recommended for Claude Desktop)

```bash
# Using the start script
./tools/mcp/gemini/scripts/start_server.sh --mode stdio

# Or directly
python -m tools.mcp.gemini.server --mode stdio
```

### HTTP Mode

```bash
# Using the start script
./tools/mcp/gemini/scripts/start_server.sh --mode http

# Or directly
python -m tools.mcp.gemini.server --mode http
```

The server will start on port 8006 by default.

## Configuration

### Environment Variables

Create a `.env` file in your project root or set these environment variables:

```bash
# Enable/disable Gemini integration
GEMINI_ENABLED=true

# Auto-consultation on uncertainty
GEMINI_AUTO_CONSULT=true

# Gemini CLI command (if not in PATH)
GEMINI_CLI_COMMAND=gemini

# Request timeout in seconds
GEMINI_TIMEOUT=60

# Rate limit delay between requests
GEMINI_RATE_LIMIT=2

# Maximum context length
GEMINI_MAX_CONTEXT=4000

# Log consultations
GEMINI_LOG_CONSULTATIONS=true

# Gemini model to use
GEMINI_MODEL=gemini-2.5-flash

# Sandbox mode for testing
GEMINI_SANDBOX=false

# Debug mode
GEMINI_DEBUG=false

# Include conversation history
GEMINI_INCLUDE_HISTORY=true

# Maximum history entries
GEMINI_MAX_HISTORY=10
```

### Configuration File

Create `gemini-config.json` in your project root:

```json
{
  "enabled": true,
  "auto_consult": true,
  "timeout": 60,
  "model": "gemini-2.5-flash",
  "max_context_length": 4000,
  "rate_limit_delay": 2
}
```

## Integration with Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "gemini": {
      "command": "python",
      "args": [
        "-m",
        "tools.mcp.gemini.server",
        "--mode", "stdio",
        "--project-root", "/path/to/your/project"
      ]
    }
  }
}
```

## Testing

Run the test script to verify the server is working:

```bash
# Must run on host system
python tools/mcp/gemini/scripts/test_server.py
```

## Troubleshooting

### "Cannot run in container" Error

If you see this error, you're trying to run the server inside Docker. Exit the container and run on your host system.

### Gemini CLI Not Found

1. Install the Gemini CLI tool
2. Add it to your PATH
3. Or set `GEMINI_CLI_COMMAND` to the full path

### Authentication Issues

1. Run `gemini auth` to configure authentication
2. Use **Google web login** (OAuth) for free tier access
3. **AVOID using API keys** - they will incur charges
4. Check the Gemini CLI documentation

### Timeout Errors

1. Increase `GEMINI_TIMEOUT` for complex queries
2. Simplify your queries
3. Check network connectivity

## Best Practices

1. **Clear History Regularly**: Clear conversation history when switching contexts
2. **Provide Context**: Include relevant context for better AI responses
3. **Rate Limiting**: Respect rate limits to avoid API quota issues
4. **Error Handling**: Always handle potential timeout or API errors
5. **Comparison Mode**: Use comparison mode to get diverse perspectives

## Example Workflow

```python
# 1. Check status
status = await client.execute_tool("gemini_status")

# 2. Clear history for fresh start
await client.execute_tool("clear_gemini_history")

# 3. Consult about code
result = await client.execute_tool("consult_gemini", {
    "query": "Review this Python function for best practices",
    "context": "def process_data(data): return [x*2 for x in data if x > 0]"
})

# 4. Disable auto-consult if needed
await client.execute_tool("toggle_gemini_auto_consult", {"enable": False})
```

## Security Considerations

- Authentication is managed by the Gemini CLI (use web login for free tier)
- No credentials are stored in the MCP server
- **Cost consideration**: Web login provides free tier; API keys incur charges
- Consultation logs can be disabled for sensitive code
- Sandbox mode available for testing without API calls

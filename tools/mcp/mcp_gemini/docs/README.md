# Gemini AI Integration MCP Server

The Gemini MCP Server provides integration with Google's Gemini AI for getting second opinions, code validation, and AI-assisted development workflows.

## Important Requirements

The Gemini MCP server now supports both host and containerized execution:

- **Container mode (Default)**: Runs Gemini CLI in a Docker container with host authentication
- **Host mode**: Direct execution for development - `python -m mcp_gemini.server`
- **Container options**:
  - Corporate proxy version: `automation/corporate-proxy/gemini/`
  - Simple container: `tools/cli/containers/run_gemini_container.sh`

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

1. **Docker**: Required for container mode (default)
2. **Gemini CLI Authentication**: Configure Gemini CLI authentication on the host

   **API Key Required**
   - The Gemini MCP server now uses **Google AI Studio API keys** for authentication
   - This provides a **free tier** with 60 requests/min, 1,500 requests/day
   - Get your free API key at: https://aistudio.google.com/app/apikey
   - Set `GOOGLE_API_KEY` environment variable or add to `.env` file
   - For single-maintainer projects, the free tier is more than sufficient
   - Why we switched from OAuth: Better CI/CD reliability, no browser auth, explicit model selection

3. **Container Image**: Build the Gemini container if using container mode:
   ```bash
   ./automation/corporate-proxy/gemini/scripts/build.sh
   ```

### stdio Mode (Recommended for Claude Desktop)

```bash
# Using the start script
./tools/mcp/gemini/scripts/start_server.sh --mode stdio

# Or directly
python -m mcp_gemini.server --mode stdio
```

### HTTP Mode

```bash
# Using the start script
./tools/mcp/gemini/scripts/start_server.sh --mode http

# Or directly
python -m mcp_gemini.server --mode http
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

# Note: GEMINI_MODEL is optional - the CLI will use a default model if not specified
# Model selection works reliably with the API key authentication

# Sandbox mode for testing
GEMINI_SANDBOX=false

# Debug mode
GEMINI_DEBUG=false

# Include conversation history
GEMINI_INCLUDE_HISTORY=true

# Maximum history entries
GEMINI_MAX_HISTORY=10

# Container configuration
GEMINI_USE_CONTAINER=true  # Use Docker container for Gemini CLI
GEMINI_CONTAINER_IMAGE=gemini-corporate-proxy:latest
GEMINI_CONTAINER_SCRIPT=/workspace/automation/corporate-proxy/gemini/scripts/run.sh
GEMINI_YOLO_MODE=false  # Enable auto-approval for container mode
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
  "rate_limit_delay": 2,
  "use_container": true,
  "container_image": "gemini-corporate-proxy:latest",
  "yolo_mode": false
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
        "mcp_gemini.server",
        "--mode", "stdio",
        "--project-root", "/path/to/your/project"
      ]
    }
  }
}
```

## Testing

Run the test scripts to verify the server is working:

```bash
# Test basic server functionality
python tools/mcp/gemini/scripts/test_server.py

# Test container mode specifically
python tools/mcp/gemini/scripts/test_container.py
```

## Troubleshooting

### Container Image Not Found

If you see "Container image not found" error:
1. Build the container: `./automation/corporate-proxy/gemini/scripts/build.sh`
2. Or disable container mode: Set `GEMINI_USE_CONTAINER=false`

### Gemini CLI Not Found (Host Mode)

1. Install the Gemini CLI tool
2. Add it to your PATH
3. Or set `GEMINI_CLI_COMMAND` to the full path

### Authentication Issues

1. Ensure `GOOGLE_API_KEY` environment variable is set
2. Get your free API key from: https://aistudio.google.com/app/apikey
3. Add it to `.env` file or export it in your shell
4. The API key provides free tier access (1,500 requests/day)
5. Check the Gemini CLI documentation for model availability

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

- Authentication uses `GOOGLE_API_KEY` environment variable
- API keys should be stored in `.env` file (git-ignored)
- No credentials are hardcoded in the MCP server
- **Cost consideration**: Free tier available (1,500 requests/day, no credit card required)
- Consultation logs can be disabled for sensitive code
- Sandbox mode available for testing without API calls

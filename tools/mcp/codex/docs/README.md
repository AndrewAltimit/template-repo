# Codex MCP Server

MCP server for integrating OpenAI Codex for AI-powered code generation and assistance.

## Features

- **Code Generation**: Generate code from natural language descriptions
- **Code Completion**: Complete partial code snippets
- **Code Refactoring**: Improve existing code quality
- **Code Explanation**: Explain complex code segments
- **Interactive Mode**: Codex primarily operates in interactive mode

## Available Tools

### consult_codex
Consult Codex for code generation or assistance.

**Parameters:**
- `query` (string, required): The coding question or task
- `context` (string, optional): Additional context or existing code
- `mode` (string, optional): Consultation mode - "generate", "complete", "refactor", "explain", or "quick"
- `comparison_mode` (boolean, optional): Compare with previous responses (default: true)
- `force` (boolean, optional): Force consultation even if disabled

### clear_codex_history
Clear the Codex conversation history.

### codex_status
Get Codex integration status and statistics.

### toggle_codex_auto_consult
Toggle automatic Codex consultation.

**Parameters:**
- `enable` (boolean, optional): Enable or disable auto-consultation

## Configuration

The server can be configured through environment variables:

- `CODEX_ENABLED`: Enable/disable Codex integration (default: "true")
- `CODEX_AUTO_CONSULT`: Enable/disable automatic consultation (default: "true")
- `CODEX_AUTH_PATH`: Path to Codex auth file (default: "~/.codex/auth.json")
- `CODEX_TIMEOUT`: Timeout for operations in seconds (default: 300)
- `CODEX_MAX_CONTEXT`: Maximum context length (default: 8000)
- `CODEX_LOG_CONSULTATIONS`: Log consultation details (default: "true")
- `CODEX_INCLUDE_HISTORY`: Include conversation history (default: "true")
- `CODEX_MAX_HISTORY`: Maximum history entries (default: 5)

## Usage

### Starting the Server

**Standalone (HTTP mode):**
```bash
python -m tools.mcp.codex.server --mode http --port 8021
```

**Standalone (STDIO mode):**
```bash
python -m tools.mcp.codex.server --mode stdio
```

**Via Docker Compose:**
```bash
docker-compose up mcp-codex
```

### Client Usage

```python
from tools.mcp.codex.client import CodexClient

client = CodexClient(port=8021)

# Consult Codex
result = await client.consult_codex(
    query="Write a Python function to sort a list",
    mode="generate"
)

# Get status
status = await client.get_status()

# Clear history
await client.clear_history()
```

## Authentication

Codex requires authentication via the Codex CLI:

1. Install Codex CLI: `npm install -g @openai/codex`
2. Authenticate: `codex auth`
3. Auth file created at: `~/.codex/auth.json`

## Testing

Run the test script to verify the server is working:

```bash
# Start the server first
python -m tools.mcp.codex.server --mode http

# In another terminal
python tools/mcp/codex/scripts/test_server.py
```

## Docker Support

The Codex MCP server can run in a Docker container with proper auth mounting:

```dockerfile
# See docker/mcp-codex.Dockerfile
```

Mount the auth directory when running:
```bash
docker run -v ~/.codex:/home/user/.codex:ro mcp-codex
```

## Notes

- Codex CLI primarily operates in interactive mode
- Authentication is required via the host's `~/.codex/auth.json`
- The server provides structured responses indicating how to use Codex interactively
- For actual code generation, use the Codex CLI directly or through the agent scripts

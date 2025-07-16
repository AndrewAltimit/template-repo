# MCP Servers Documentation

This project uses multiple Model Context Protocol (MCP) servers to provide various development tools while maintaining the container-first philosophy.

## Architecture Overview

The MCP functionality is split across two servers:

1. **Main MCP Server** - Containerized, runs all tools that don't require host access
2. **Gemini MCP Server** - Host-only, provides Gemini AI integration

This separation ensures that most tools benefit from containerization while tools requiring Docker access (like Gemini CLI) can still function properly.

## Main MCP Server (Port 8005)

The main MCP server runs in a Docker container and provides code quality and content creation tools.

### Starting the Server

```bash
# Start via Docker Compose (recommended)
docker-compose up -d mcp-server

# View logs
docker-compose logs -f mcp-server

# Test health
curl http://localhost:8005/health
```

### Available Tools

#### Code Quality Tools
- **format_check** - Check code formatting for Python, JavaScript, TypeScript, Go, and Rust
- **lint** - Run static code analysis with configurable linting rules

#### Content Creation Tools
- **create_manim_animation** - Create mathematical and technical animations using Manim
- **compile_latex** - Compile LaTeX documents to PDF, DVI, or PostScript formats

### API Endpoints

- `GET /` - Server information and available tools
- `GET /health` - Health check endpoint
- `POST /tools/execute` - Execute a specific tool
- `GET /tools` - List all available tools with descriptions

## Gemini MCP Server (Port 8006)

The Gemini MCP server provides AI assistance through the Gemini CLI. It **must run on the host system** because the Gemini CLI requires Docker access.

### Container Detection

The server includes automatic container detection and will immediately exit with an error message if someone attempts to run it in a container:

```bash
# This will fail with a helpful error message
docker-compose run gemini-mcp-server
```

### Starting the Server

```bash
# Must run on host system
python3 tools/mcp/gemini_mcp_server.py

# Or use the helper script
./scripts/start-gemini-mcp.sh

# Test health
curl http://localhost:8006/health
```

### Available Tools

#### AI Integration Tools
- **consult_gemini** - Get AI assistance for technical questions, code reviews, and recommendations
  - Parameters:
    - `prompt` (required): The question or code to analyze
    - `context` (optional): Additional context as a dictionary
    - `max_retries` (optional): Maximum retry attempts (default: 3)

- **clear_gemini_history** - Clear conversation history for fresh responses
  - No parameters required
  - Returns the number of cleared entries

### API Endpoints

- `GET /` - Server information
- `GET /health` - Health check endpoint
- `POST /tools/consult_gemini` - Consult Gemini AI
- `POST /tools/clear_gemini_history` - Clear conversation history
- `GET /mcp/tools` - List available MCP tools

### Example Usage

```python
import requests

# Consult Gemini
response = requests.post(
    "http://localhost:8006/tools/consult_gemini",
    json={
        "prompt": "What are the best practices for Python async programming?",
        "context": {"project": "web-api"}
    }
)
result = response.json()
print(result["response"])

# Clear history
response = requests.post("http://localhost:8006/tools/clear_gemini_history")
print(f"Cleared {response.json()['cleared_count']} entries")
```

## Configuration

Both servers are configured in `.mcp.json`:

```json
{
  "mcpServers": {
    "local-tools": {
      "name": "Local MCP Tools",
      "url": "http://localhost:8005",
      "tools": { /* ... */ }
    },
    "gemini-tools": {
      "name": "Gemini MCP Server",
      "url": "http://localhost:8006",
      "note": "Must run on host system, not in container",
      "tools": { /* ... */ }
    }
  }
}
```

## Testing

Test scripts are provided for both servers:

```bash
# Test main MCP server
python3 scripts/test-mcp-server.py

# Test Gemini MCP server
python3 scripts/test-gemini-mcp-server.py

# Test container detection
./scripts/test-gemini-container-exit.sh
```

## Troubleshooting

### Main MCP Server Issues

1. **Port 8005 already in use**
   ```bash
   # Find process using port
   sudo lsof -i :8005
   # Stop the container
   docker-compose down mcp-server
   ```

2. **Container permission issues**
   ```bash
   ./scripts/fix-runner-permissions.sh
   ```

### Gemini MCP Server Issues

1. **"Cannot run in container" error**
   - This is expected behavior
   - Run the server directly on the host system

2. **Gemini CLI not found**
   - Install Gemini CLI: `npm install -g @google/gemini-cli`
   - Authenticate: Run `gemini` command once

3. **Port 8006 already in use**
   ```bash
   # Check for existing process
   ps aux | grep gemini_mcp_server
   # Kill if needed
   kill $(cat /tmp/gemini-mcp.pid)
   ```

## Development Notes

- The main MCP server can be extended with new tools by adding methods to the `MCPTools` class
- The Gemini MCP server uses the existing `GeminiIntegration` class from `tools/gemini/`
- Both servers use FastAPI for the HTTP API
- Container detection is performed immediately on startup for the Gemini server
- All tools return JSON responses with consistent error handling

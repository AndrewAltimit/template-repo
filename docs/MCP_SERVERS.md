# MCP Servers Documentation

This project uses multiple Model Context Protocol (MCP) servers to provide various development tools while maintaining the container-first philosophy.

## Architecture Overview

The MCP functionality is split across three servers:

1. **Main MCP Server** (Port 8005) - Containerized, runs code quality, content creation, and Gaea2 terrain generation tools
2. **Gemini MCP Server** (Port 8006) - Host-only, provides Gemini AI integration (requires Docker access)
3. **Gaea2 MCP Server** (Port 8007) - Windows host-only, provides Gaea2 CLI automation (requires Gaea2 installation)

This separation ensures that most tools benefit from containerization while tools requiring host system access (Gemini CLI, Gaea2 executable) can function properly on their respective platforms.

## Main MCP Server (Port 8005)

The main MCP server runs in a Docker container and provides code quality, content creation, and Gaea2 terrain generation tools.

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

#### Gaea2 Terrain Generation Tools (185 nodes supported)
- **create_gaea2_project** - Create custom terrain projects with automatic validation and error correction
  - Supports all 185 documented Gaea2 nodes across 9 categories
  - Automatic validation and fix built-in by default
  - Adds missing Export and coloring nodes automatically
  - Guarantees Gaea2-compatible output files

- **validate_and_fix_workflow** - Comprehensive validation and automatic repair of Gaea2 workflows
  - Multi-level validation (structure, nodes, properties, connections, patterns)
  - Automatic error recovery and fixing
  - Conservative and aggressive repair modes

- **analyze_workflow_patterns** - Pattern-based workflow analysis using knowledge from 31 real projects
  - Get intelligent node suggestions based on current workflow
  - Performance analysis and bottleneck detection
  - Similarity matching with known good patterns

- **repair_gaea2_project** - Repair damaged or invalid Gaea2 project files
  - Analyzes project health and identifies issues
  - Automatic fixing of common problems
  - Detailed error reports with fix suggestions

- **create_gaea2_from_template** - Create projects using professional workflow templates
  - Templates: basic_terrain, detailed_mountain, volcanic_terrain, desert_canyon
  - Pre-configured workflows for common terrain types
  - Customizable parameters

- **optimize_gaea2_properties** - Optimize node properties for performance or quality
  - Performance mode for faster rendering
  - Quality mode for best visual results
  - Intelligent property adjustments based on node type

- **suggest_gaea2_nodes** - Get intelligent node suggestions based on terrain type and context
  - Context-aware suggestions
  - Based on patterns from real projects
  - Considers existing workflow nodes

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

## Gaea2 MCP Server (Port 8007) - Windows Only

The Gaea2 MCP Server is a standalone server that provides all Gaea2 terrain generation capabilities plus CLI automation for running Gaea2 projects programmatically. It **must run on a Windows host** where Gaea2 is installed.

### Prerequisites

- Windows 10/11 with Gaea2 installed
- Python 3.8+ with aiohttp and aiofiles packages
- GAEA2_PATH environment variable set to Gaea.Swarm.exe location

### Starting the Server

```bash
# Set environment variable (Windows)
set GAEA2_PATH=C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe

# Start server using helper scripts
scripts\start-gaea2-mcp.bat

# Or run directly
python tools/mcp/gaea2_mcp_server.py

# Test health
curl http://localhost:8007/health
```

### Additional Features

Beyond the Gaea2 tools available in the main MCP server, the standalone server provides:

#### CLI Automation
- **run_gaea2_project** - Execute terrain generation via Gaea's command line interface
  - Pass variables to control terrain generation dynamically
  - Capture verbose output and parse results
  - Track execution history for debugging
  - Supports all Gaea.Swarm.exe command line options

- **analyze_execution_history** - Learn from previous terrain generation runs
  - View past executions and their results
  - Identify common errors or patterns
  - Optimize future runs based on history

### API Endpoints

- `GET /health` - Health check and Gaea2 path verification
- `GET /mcp/tools` - List available tools
- `POST /mcp/execute` - Execute a tool with parameters

### Example: Create and Run Terrain

```python
import requests

# Create terrain project
response = requests.post("http://localhost:8007/mcp/execute", json={
    "tool": "create_gaea2_project",
    "parameters": {
        "project_name": "mountain_terrain",
        "workflow": [...],  # Node definitions
        "auto_validate": True
    }
})

# Run the project with variables
response = requests.post("http://localhost:8007/mcp/execute", json={
    "tool": "run_gaea2_project",
    "parameters": {
        "project_path": "mountain_terrain.terrain",
        "verbose": True,
        "variables": {
            "erosion_strength": 0.5,
            "detail_level": 2
        }
    }
})
```

For complete Gaea2 MCP documentation, see:
- [Gaea2 MCP Overview](gaea2/README.md)
- [Gaea2 MCP Server Guide](gaea2/GAEA2_MCP_SERVER.md)
- [API Reference](gaea2/GAEA2_API_REFERENCE.md)

## Configuration

All three servers are configured in `.mcp.json`:

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
    },
    "gaea2-tools": {
      "name": "Gaea2 MCP Server",
      "url": "http://localhost:8007",
      "note": "Windows only, requires Gaea2 installation",
      "tools": { /* ... */ }
    }
  }
}
```

## Testing

Test scripts are provided for all servers:

```bash
# Test main MCP server
python3 scripts/test-mcp-server.py

# Test Gemini MCP server
python3 scripts/test-gemini-mcp-server.py

# Test Gaea2 MCP server (Windows only)
python3 scripts/test-gaea2-mcp-server.py

# Test container detection (Gemini)
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

### Gaea2 MCP Server Issues

1. **"Gaea2 executable not found"**
   - Verify GAEA2_PATH environment variable is set correctly
   - Check that Gaea.Swarm.exe exists at the specified location
   - Ensure you're running on Windows with Gaea2 installed

2. **"Server must run on Windows"**
   - The Gaea2 MCP server only works on Windows
   - Gaea2 is a Windows-only application
   - Use the main MCP server (port 8005) for Gaea2 project creation on other platforms

3. **Port 8007 already in use**
   ```cmd
   # Windows: Check for existing process
   netstat -an | findstr 8007
   # Kill the process if needed
   taskkill /F /PID <process_id>
   ```

## Development Notes

- The main MCP server can be extended with new tools by adding methods to the `MCPTools` class
- The Gemini MCP server uses the existing `GeminiIntegration` class from `tools/gemini/`
- The Gaea2 MCP server extends the main server with CLI automation capabilities
- All servers use FastAPI for the HTTP API
- Container detection is performed immediately on startup for Gemini and Gaea2 servers
- All tools return JSON responses with consistent error handling
- Gaea2 tools include automatic validation and error recovery by default

# MCP Servers Documentation

This project uses a modular architecture with multiple Model Context Protocol (MCP) servers, each specialized for specific functionality.

## Architecture Overview

The MCP functionality is split across four modular servers:

1. **Code Quality MCP Server** (Port 8010) - Containerized, provides code formatting and linting tools
2. **Content Creation MCP Server** (Port 8011) - Containerized, provides Manim animations and LaTeX compilation
3. **Gaea2 MCP Server** (Port 8007) - Containerized, provides terrain generation and workflow management
4. **Gemini MCP Server** (Port 8006) - Host-only, provides Gemini AI integration (requires Docker access)

This modular architecture ensures better separation of concerns, easier maintenance, and the ability to scale individual services independently.

## Code Quality MCP Server (Port 8010)

The code quality server provides formatting and linting tools for multiple programming languages.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker-compose up -d mcp-code-quality

# Or run locally for development
python -m tools.mcp.code_quality.server

# View logs
docker-compose logs -f mcp-code-quality

# Test health
curl http://localhost:8010/health
```

### Available Tools

- **format_check** - Check code formatting for Python, JavaScript, TypeScript, Go, and Rust
- **lint** - Run static code analysis with configurable linting rules
- **autoformat** - Automatically format code files

### Configuration

See `tools/mcp/code_quality/docs/README.md` for detailed configuration options.

## Content Creation MCP Server (Port 8011)

The content creation server provides tools for creating animations and compiling documents.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker-compose up -d mcp-content-creation

# Or run locally for development
python -m tools.mcp.content_creation.server

# View logs
docker-compose logs -f mcp-content-creation

# Test health
curl http://localhost:8011/health
```

### Available Tools

- **create_manim_animation** - Create mathematical and technical animations using Manim
- **compile_latex** - Compile LaTeX documents to PDF, DVI, or PostScript formats
- **render_tikz** - Render TikZ diagrams as standalone images

### Configuration

Output directory is configured via the `MCP_OUTPUT_DIR` environment variable (defaults to `/tmp/mcp-content-output` in container).

See `tools/mcp/content_creation/docs/README.md` for detailed documentation.

## Gaea2 MCP Server (Port 8007)

The Gaea2 server provides comprehensive terrain generation capabilities with support for all 185 documented Gaea2 nodes.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker-compose up -d mcp-gaea2

# Or run locally for development
python -m tools.mcp.gaea2.server

# For remote server deployment (e.g., on Windows with Gaea2 installed)
# Set GAEA2_REMOTE_URL environment variable to point to the remote server
export GAEA2_REMOTE_URL=http://remote-server:8007

# View logs
docker-compose logs -f mcp-gaea2

# Test health
curl http://localhost:8007/health
```

### Available Tools

#### Terrain Generation Tools (185 nodes supported)
- **create_gaea2_project** - Create custom terrain projects with automatic validation
- **create_gaea2_from_template** - Use professional workflow templates
- **validate_and_fix_workflow** - Comprehensive validation and automatic repair
- **analyze_workflow_patterns** - Pattern-based analysis using real project knowledge
- **optimize_gaea2_properties** - Optimize for performance or quality
- **suggest_gaea2_nodes** - Get intelligent node suggestions
- **repair_gaea2_project** - Repair damaged project files

#### CLI Automation (when running on Windows with Gaea2)
- **run_gaea2_project** - Execute terrain generation via CLI
- **analyze_execution_history** - Learn from previous runs

### Configuration

- For containerized deployment: Works out of the box
- For Windows deployment with CLI features: Set `GAEA2_PATH` environment variable
- See `tools/mcp/gaea2/docs/README.md` for complete documentation

## Gemini MCP Server (Port 8006)

The Gemini server provides AI assistance through the Gemini CLI. It **must run on the host system** because it requires Docker access.

### Starting the Server

```bash
# Must run on host system (not in container)
python -m tools.mcp.gemini.server

# Or use HTTP mode
python -m tools.mcp.gemini.server --mode http

# Or use the helper script
./tools/mcp/gemini/scripts/start_server.sh

# Test health
curl http://localhost:8006/health
```

### Available Tools

- **consult_gemini** - Get AI assistance for technical questions
- **clear_gemini_history** - Clear conversation history
- **gemini_status** - Get integration status
- **toggle_gemini_auto_consult** - Control auto-consultation

### Container Detection

The server includes automatic container detection and will exit with an error if run in a container:

```bash
# This will fail with a helpful error message
docker-compose run --rm python-ci python -m tools.mcp.gemini.server
```

See `tools/mcp/gemini/docs/README.md` for detailed documentation.

## Unified Testing

Test all servers at once:

```bash
# Test all running servers
python scripts/mcp/test_all_servers.py

# Quick connectivity test only
python scripts/mcp/test_all_servers.py --quick

# Test individual servers
python tools/mcp/code_quality/scripts/test_server.py
python tools/mcp/content_creation/scripts/test_server.py
python tools/mcp/gaea2/scripts/test_server.py
python tools/mcp/gemini/scripts/test_server.py
```

## Configuration

The modular servers are configured in `.mcp.json`:

```json
{
  "mcpServers": {
    "code-quality": {
      "name": "Code Quality MCP Server",
      "url": "http://localhost:8010"
    },
    "content-creation": {
      "name": "Content Creation MCP Server",
      "url": "http://localhost:8011"
    },
    "gaea2": {
      "name": "Gaea2 MCP Server",
      "url": "${GAEA2_REMOTE_URL:-http://localhost:8007}"
    },
    "gemini": {
      "name": "Gemini MCP Server",
      "url": "http://localhost:8006",
      "note": "Must run on host system"
    }
  }
}
```

## Client Usage

The `main.py` client can target specific servers:

```python
# Target a specific server
export MCP_SERVER_NAME=gaea2
python main.py

# Or use the server URL directly
export MCP_SERVER_URL=http://localhost:8007
python main.py
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using a port (e.g., 8010)
sudo lsof -i :8010

# Stop specific container
docker-compose down mcp-code-quality
```

### Container Permission Issues

```bash
./scripts/fix-runner-permissions.sh
```

### Gemini Server Issues

1. **"Cannot run in container" error** - Run on host system
2. **Gemini CLI not found** - Install with `npm install -g @google/gemini-cli`

### Gaea2 Windows CLI Features

1. **Set GAEA2_PATH** environment variable to Gaea.Swarm.exe location
2. **Ensure Windows host** for CLI automation features

## Development Notes

- Each server extends `BaseMCPServer` from `tools/mcp/core/`
- Servers can run standalone or via Docker Compose
- All servers provide consistent JSON API responses
- Use the modular architecture to add new specialized servers
- Follow the container-first philosophy except where technically impossible (Gemini)

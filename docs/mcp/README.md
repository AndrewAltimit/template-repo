# MCP (Model Context Protocol) Servers

This repository contains a modular collection of MCP servers that provide various development and content creation tools. Each server is specialized for specific functionality and can be run independently.

## Available MCP Servers

### 1. Code Quality MCP Server (Port 8010)
**Location**: `tools/mcp/code_quality/`
**Documentation**: [Code Quality MCP Documentation](../../tools/mcp/code_quality/docs/README.md)

Provides code formatting and linting tools for multiple languages:
- Format checking (Python, JavaScript, TypeScript, Go, Rust)
- Linting with various tools (flake8, pylint, eslint, etc.)
- Auto-formatting capabilities

### 2. Content Creation MCP Server (Port 8011)
**Location**: `tools/mcp/content_creation/`
**Documentation**: [Content Creation MCP Documentation](../../tools/mcp/content_creation/docs/README.md)

Tools for creating mathematical animations and documents:
- Manim animations (mathematical visualizations)
- LaTeX document compilation (PDF, DVI, PS)
- TikZ diagram rendering

### 3. Gemini AI Integration MCP Server (Port 8006)
**Location**: `tools/mcp/gemini/`
**Documentation**: [Gemini MCP Documentation](../../tools/mcp/gemini/docs/README.md)

AI integration for second opinions and code validation:
- Gemini AI consultations
- Conversation history management
- Auto-consultation on uncertainty detection

**⚠️ Important**: Must run on host system (not in container)

### 4. Gaea2 Terrain Generation MCP Server (Port 8007)
**Location**: `tools/mcp/gaea2/`
**Documentation**: [Gaea2 MCP Documentation](../gaea2/README.md) | [Full Documentation Index](../gaea2/INDEX.md)

Comprehensive terrain generation with Gaea2:
- Support for all 185 Gaea2 nodes
- Intelligent validation and error correction
- Professional terrain templates
- CLI automation (Windows only)
- Project repair capabilities

## Configuration and Transport

### HTTP Streamable Transport

MCP servers can use HTTP transport for remote deployment. For detailed configuration and troubleshooting:
- **[MCP Server Modes: STDIO vs HTTP](STDIO_VS_HTTP_MODES.md)** - Complete guide for MCP server modes and HTTP implementation
- **[MCP Specification](https://modelcontextprotocol.io/specification/2025-06-18)** - Official protocol specification

### Configuration File (.mcp.json)

All MCP servers are configured in the `.mcp.json` file at the project root. HTTP servers use the following format:

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "http://host:port/messages"
    }
  }
}
```

## Architecture Overview

```
tools/mcp/
├── core/                    # Shared utilities and base classes
│   ├── base_server.py      # Base MCP server class
│   ├── http_bridge.py      # HTTP bridge for remote servers
│   └── utils.py            # Common utilities
│
├── code_quality/           # Code quality tools
├── content_creation/       # Manim & LaTeX tools
├── gemini/                 # AI integration
└── gaea2/                  # Terrain generation
```

## Running MCP Servers

Each server can run in two modes:

### HTTP Mode
For web API access and integration with other services:
```bash
python -m tools.mcp.<server_name>.server --mode http
```

### stdio Mode
For Claude Desktop integration:
```bash
python -m tools.mcp.<server_name>.server --mode stdio
```

## Claude Desktop Configuration

Add the desired servers to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "code-quality": {
      "command": "python",
      "args": ["-m", "tools.mcp.code_quality.server", "--mode", "stdio"]
    },
    "content-creation": {
      "command": "python",
      "args": ["-m", "tools.mcp.content_creation.server", "--mode", "stdio"]
    },
    "gemini": {
      "command": "python",
      "args": ["-m", "tools.mcp.gemini.server", "--mode", "stdio"]
    },
    "gaea2": {
      "command": "python",
      "args": ["-m", "tools.mcp.gaea2.server", "--mode", "stdio"]
    }
  }
}
```

## Docker Support

Most servers can run in Docker containers. Example compose configuration:

```yaml
version: '3.8'

services:
  mcp-code-quality:
    build:
      context: .
      dockerfile: docker/mcp-code-quality.Dockerfile
    ports:
      - "8010:8010"
    volumes:
      - ./output:/app/output

  mcp-content-creation:
    build:
      context: .
      dockerfile: docker/mcp-content.Dockerfile
    ports:
      - "8011:8011"
    volumes:
      - ./output:/app/output

  # Note: Gemini must run on host
  # Note: Gaea2 CLI features require Windows host
```

## Development

### Creating a New MCP Server

1. Create a new directory under `tools/mcp/`
2. Inherit from `BaseMCPServer` in `core/base_server.py`
3. Implement the `get_tools()` method
4. Add tool implementation methods
5. Create documentation in `docs/README.md`
6. Add tests in `scripts/test_server.py`

### Testing

Each server includes test scripts:
```bash
python tools/mcp/<server_name>/scripts/test_server.py
```

Test all servers:
```bash
python scripts/mcp/test_all_servers.py
```


## Common Issues

### Port Conflicts
Each server uses a different port:
- Code Quality: 8010
- Content Creation: 8011
- Gemini: 8006
- Gaea2: 8007

### Container Restrictions
- **Gemini**: Cannot run in container (needs Docker access)
- **Gaea2 CLI**: Requires Windows host with Gaea2 installed

### Missing Dependencies
Each server has specific requirements. Check the server's documentation for installation instructions.

## Contributing

When contributing to MCP servers:

1. Follow the modular structure
2. Add comprehensive documentation
3. Include test scripts
4. Update this overview if adding new servers
5. Ensure backward compatibility when possible

## License

See repository LICENSE file.

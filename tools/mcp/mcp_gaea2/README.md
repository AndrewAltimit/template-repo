# Gaea2 MCP Server (Rust)

> A Model Context Protocol server for Gaea2 terrain generation, providing project creation, validation, optimization, and CLI automation for professional terrain workflows.

## Overview

This MCP server provides:
- Custom terrain project creation from nodes and connections
- 11 pre-built professional templates (mountain, volcanic, canyon, coastal, arctic, etc.)
- Workflow validation with automatic error correction
- Intelligent node suggestions based on context
- Property optimization for performance or quality
- CLI automation for Gaea.Swarm.exe execution (Windows)
- Project file management (listing, download, repair)

**Note**: This server was migrated from Python to Rust as part of the mcp-core-rust framework migration.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode (default for remote deployment)
./target/release/mcp-gaea2 --mode standalone --port 8007

# Run in STDIO mode (for Claude Code)
./target/release/mcp-gaea2 --mode stdio

# Test health
curl http://localhost:8007/health
```

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `create_gaea2_project` | Create custom terrain from nodes/connections | `project_name`, `nodes`, `connections` |
| `create_gaea2_from_template` | Create project from template | `template_name`, `project_name` |
| `validate_and_fix_workflow` | Validate and auto-fix workflow | `nodes`, `connections`, `strict_mode` |
| `suggest_gaea2_nodes` | Get intelligent node suggestions | `current_nodes`, `context` |
| `optimize_gaea2_properties` | Optimize properties for mode | `nodes`, `mode` |
| `analyze_workflow_patterns` | Analyze patterns and suggest improvements | `nodes`, `connections` |
| `run_gaea2_project` | Execute project via CLI | `project_path`, `resolution`, `seed` |
| `download_gaea2_project` | Download project as base64 | `project_path` |
| `list_gaea2_projects` | List projects in directory | `directory` |
| `list_gaea2_templates` | List available templates | None |
| `analyze_execution_history` | Debug/monitor executions | `limit` |
| `repair_gaea2_project` | Repair project file | `project_path`, `create_backup` |

## Available Templates

| Template | Description | Nodes |
|----------|-------------|-------|
| `basic_terrain` | Simple mountain with erosion | 4 |
| `detailed_mountain` | Multi-stage erosion with details | 6 |
| `volcanic_terrain` | Volcano with thermal effects | 5 |
| `desert_canyon` | Canyon with sandstone layers | 5 |
| `mountain_range` | Alpine with snow caps | 6 |
| `volcanic_island` | Island with coastal features | 6 |
| `canyon_system` | Complex canyon with rivers | 6 |
| `coastal_cliffs` | Dramatic cliffs with erosion | 6 |
| `river_valley` | Valley with floodplains | 6 |
| `arctic_terrain` | Glaciers and permafrost | 6 |
| `modular_portal_terrain` | Modular with portal nodes | 5 |

## Node Categories

| Category | Examples | Count |
|----------|----------|-------|
| **Primitive** | Perlin, Voronoi, Cellular, Gradient | 14 |
| **Terrain** | Mountain, Volcano, Canyon, Island | 18 |
| **Modify** | Erosion2, Blur, Warp, Terrace | 21 |
| **Surface** | Details, Rockmap, Sediment | 10 |
| **Simulate** | Erosion2, Rivers, Snow, Glacier | 16 |
| **Derive** | Slope, Curvature, Normal, Height | 10 |
| **Colorize** | QuickColor, Satmaps, Mixer | 8 |
| **Output** | Output, Export, Unity | 4 |
| **Utility** | Combine, Portal, Switch | 18 |

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8000]
--gaea-path <PATH>    Path to Gaea.Swarm.exe (or GAEA2_PATH env)
--output-dir <DIR>    Output directory [default: /app/output/gaea2]
--log-level <LEVEL>   Log level [default: info]
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GAEA2_PATH` | Path to Gaea.Swarm.exe executable |
| `GAEA2_OUTPUT_DIR` | Directory for generated terrain files |

## Transport Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **standalone** | Full MCP server with HTTP transport | Production, Docker |
| **stdio** | STDIO transport for direct integration | Claude Code, local MCP |
| **server** | REST API only (no MCP protocol) | Microservices |
| **client** | MCP proxy to REST backend | Horizontal scaling |

## Remote Deployment

Gaea2 requires a Windows machine with Gaea2 installed. This server is designed to run on that remote machine:

- **Default Address**: `192.168.0.152:8007`
- **Requirements**: Windows, Gaea2 2.2.6.0+, Gaea.Swarm.exe

```bash
# On Windows remote machine
.\mcp-gaea2.exe --mode standalone --port 8007 --gaea-path "C:\Program Files\Gaea2\Gaea.Swarm.exe"
```

## Docker Support

### Using docker-compose

```bash
# Start the MCP server
docker compose up -d mcp-gaea2

# View logs
docker compose logs -f mcp-gaea2

# Test health
curl http://localhost:8007/health
```

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "gaea2": {
      "command": "mcp-gaea2",
      "args": ["--mode", "stdio"]
    }
  }
}
```

Or for remote HTTP mode:

```json
{
  "mcpServers": {
    "gaea2": {
      "url": "http://192.168.0.152:8007"
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_gaea2

# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Run tests
cargo test

# Run clippy
cargo clippy -- -D warnings

# Format code
cargo fmt
```

## Project Structure

```
tools/mcp/mcp_gaea2/
|-- Cargo.toml          # Package configuration
|-- Cargo.lock          # Dependency lock file
|-- README.md           # This file
+-- src/
    |-- main.rs         # CLI entry point
    |-- server.rs       # MCP tools implementation
    |-- types.rs        # Data types and models
    |-- config.rs       # Configuration
    |-- schema.rs       # Node type definitions
    |-- templates.rs    # Pre-built templates
    |-- validation.rs   # Workflow validation
    |-- generation.rs   # Project file generation
    +-- cli.rs          # Gaea.Swarm CLI automation
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## Example Usage

### Create Project from Template

```bash
curl -X POST http://localhost:8007/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "create_gaea2_from_template",
    "arguments": {
      "template_name": "detailed_mountain",
      "project_name": "my_terrain"
    }
  }'
```

### Create Custom Workflow

```bash
curl -X POST http://localhost:8007/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "create_gaea2_project",
    "arguments": {
      "project_name": "custom_terrain",
      "nodes": [
        {"id": 100, "type": "Mountain", "name": "Base"},
        {"id": 101, "type": "Erosion2", "name": "Erosion"},
        {"id": 102, "type": "Output", "name": "Output"}
      ],
      "connections": [
        {"from_node": 100, "to_node": 101},
        {"from_node": 101, "to_node": 102}
      ]
    }
  }'
```

### Validate Workflow

```bash
curl -X POST http://localhost:8007/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "validate_and_fix_workflow",
    "arguments": {
      "nodes": [{"type": "Mountain"}, {"type": "Output"}],
      "connections": [{"from_node": 100, "to_node": 101}]
    }
  }'
```

## Testing

```bash
# Run unit tests
cargo test

# Test with output
cargo test -- --nocapture

# Test HTTP endpoints (after starting server)
curl http://localhost:8007/health
curl http://localhost:8007/mcp/tools

# List templates
curl -X POST http://localhost:8007/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "list_gaea2_templates", "arguments": {}}'
```

## Validation Features

The validation system checks:
- **Node types**: Against 100+ valid Gaea2 node types
- **Connections**: Source/target existence, port compatibility
- **Properties**: Type constraints, value ranges
- **Structure**: DAG validation (no cycles)
- **Completeness**: Missing output nodes, unconnected nodes (strict mode)

Auto-fixes include:
- Invalid node type suggestions
- Missing seed values for generators
- Removed invalid connections
- Position normalization

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~20ms |
| Project creation | ~5ms |
| Validation | ~2ms |
| Template load | ~1ms |

## Gaea2 File Format

The server generates `.terrain` files compatible with Gaea2 2.2.6.0:

```json
{
  "$id": "1",
  "Assets": { ... },
  "Metadata": {
    "Name": "project_name",
    "Version": "2.2.6.0",
    "DateCreated": "2024-01-01 00:00:00Z"
  }
}
```

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime
- [serde](https://serde.rs/) - Serialization
- [tracing](https://tracing.rs/) - Logging
- [chrono](https://docs.rs/chrono/) - Date/time handling

## Related Documentation

- [MCP Architecture](../../../docs/mcp/README.md)
- [Gaea2 Documentation](https://quadspinner.com/Gaea/)
- [MCP Core Rust](../mcp_core_rust/README.md)

## License

Part of the template-repo project. See repository LICENSE file.

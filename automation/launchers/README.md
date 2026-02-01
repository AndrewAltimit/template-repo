# Automation Launchers

Centralized launcher scripts for various services and tools in the repository.

## Directory Structure

```
launchers/
├── windows/             # Windows-specific launchers
├── linux/               # Linux/Mac launchers
└── README.md            # This file
```

## Virtual Character Server

> **Note**: The Virtual Character MCP Server has been migrated from Python to Rust.
> For running the server, use Docker Compose or the pre-built binary from GitHub releases.

### Running via Docker Compose (Recommended)

```bash
# STDIO mode (for MCP clients)
docker compose --profile virtual-character run --rm -T mcp-virtual-character mcp-virtual-character --mode stdio

# HTTP mode (standalone server)
docker compose --profile virtual-character up mcp-virtual-character
```

The HTTP server will be available at `http://localhost:8025`.

### Running the Binary Directly

Download the pre-built binary from [GitHub Releases](https://github.com/AndrewAltimit/template-repo/releases), then:

```bash
# STDIO mode
./mcp-virtual-character --mode stdio

# HTTP mode
./mcp-virtual-character --mode standalone --port 8025
```

### Configuration

The server accepts these parameters:
- `--mode`: `stdio` or `standalone` (default: stdio)
- `--port`: Server port for standalone mode (default: 8025)
- `--host`: Bind address for standalone mode (default: 0.0.0.0)
- `--log-level`: Log level (default: info)

### Features

- VRChat OSC protocol support for avatar control
- VRCEmote system for gesture wheel control
- PAD emotion model for smooth expression interpolation
- Mock backend for testing without VRChat

## Adding New Launchers

When adding new launcher scripts:

1. Create a subdirectory for your service
2. Add platform-specific launchers as needed
3. Update this README with usage instructions
4. Consider adding:
   - Dependency checks
   - Configuration validation
   - Error handling
   - Auto-restart capabilities

## Best Practices

- Use descriptive names for launcher scripts
- Include configuration options as parameters
- Add help/usage information
- Check dependencies before starting
- Provide clear error messages
- Support both interactive and non-interactive modes

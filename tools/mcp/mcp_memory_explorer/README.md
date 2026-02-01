# Memory Explorer MCP Server (Rust)

> A Model Context Protocol server for game memory exploration and reverse engineering, built in Rust with Windows memory API support for process memory access.

## Overview

This MCP server provides:
- Process listing and attachment
- Memory reading with multiple data type interpretations
- Pattern scanning with wildcard support
- Value searching for game variables (health, position, etc.)
- Pointer chain resolution for dynamic addresses
- Memory watching for change detection
- Module listing with base addresses

**Note**: This server was migrated from Python (pymem) to Rust for improved performance and native Windows API access. Most operations require Windows; on other platforms, only process listing is available.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-memory-explorer --mode standalone --port 8025

# Run in STDIO mode (for Claude Code)
./target/release/mcp-memory-explorer --mode stdio

# Test health
curl http://localhost:8025/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_processes` | List running processes | `filter` (optional) |
| `attach_process` | Attach to a process by name | `process_name` (required) |
| `detach_process` | Detach from current process | None |
| `get_modules` | List loaded modules (DLLs) | None |
| `read_memory` | Read memory at address | `address` (required), `type`, `size` |
| `dump_memory` | Hex dump with ASCII | `address` (required), `size` |
| `scan_pattern` | Search for byte patterns | `pattern` (required), `module`, `return_all`, `max_results` |
| `find_value` | Search for specific values | `value` (required), `type`, `module`, `max_results` |
| `resolve_pointer` | Follow pointer chain | `base` (required), `offsets` (required) |
| `watch_address` | Monitor an address | `label` (required), `address` (required), `type`, `size` |
| `read_watches` | Read all watched addresses | None |
| `remove_watch` | Remove a watch | `label` (required) |
| `get_status` | Get explorer status | None |

### Supported Data Types

- `bytes` - Raw bytes as hex
- `int32`, `int64`, `uint32`, `uint64` - Integers
- `float`, `double` - Floating point
- `string` - Null-terminated string
- `pointer` - 64-bit pointer
- `vector3`, `vector4` - 3D/4D float vectors
- `matrix4x4` - 4x4 transformation matrix

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8025]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

## Transport Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **standalone** | Full MCP server with HTTP transport | Production, Docker |
| **stdio** | STDIO transport for direct integration | Claude Code, local MCP clients |
| **server** | REST API only (no MCP protocol) | Microservices |
| **client** | MCP proxy to REST backend | Horizontal scaling |

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "memory-explorer": {
      "command": "mcp-memory-explorer",
      "args": ["--mode", "stdio"]
    }
  }
}
```

## Example Session

```
# Find and attach to the game
> list_processes filter="NMS"
{"processes": [{"name": "NMS.exe", "pid": 12345}]}

> attach_process process_name="NMS.exe"
{"attached": true, "pid": 12345, "base_address": "0x7FF6A1B20000"}

# Find the main module
> get_modules
[{"name": "NMS.exe", "base_address": "0x7FF6A1B20000", "size_mb": 150.5}, ...]

# Scan for a pattern (e.g., camera matrix access)
> scan_pattern pattern="F3 0F 10 ?? ?? ?? ?? ?? F3 0F 11"
{"count": 3, "results": [{"address": "0x7FF6A1C45678"}]}

# Read a matrix at an address
> read_memory address="0x7FF6A1C45678" type="matrix4x4"
{"value": [[1.0, 0.0, 0.0, 0.0], ...]}

# Watch the player position
> watch_address label="player_x" address="0x7FF6A1D00100" type="float"
{"label": "player_x", "value": 1234.56}

# Check for changes
> read_watches
[{"label": "player_x", "value": 1235.78, "changed": true}]
```

## Building from Source

```bash
cd tools/mcp/mcp_memory_explorer

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
tools/mcp/mcp_memory_explorer/
+-- Cargo.toml          # Package configuration
+-- Cargo.lock          # Dependency lock file
+-- README.md           # This file
+-- src/
    +-- main.rs         # CLI entry point
    +-- server.rs       # MCP tools implementation
    +-- explorer.rs     # Memory exploration engine
    +-- types.rs        # Data types
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## Architecture

### Memory Access (Windows)

The server uses native Windows APIs for memory operations:
- `OpenProcess` - Open process handle with full access
- `ReadProcessMemory` - Read memory from target process
- `VirtualQueryEx` - Query memory region information
- `CreateToolhelp32Snapshot` - Enumerate processes and modules

### Pattern Scanning

Pattern scanning supports wildcards (`??`) for matching any byte:
```
"48 8B 05 ?? ?? ?? ?? 48 85 C0"
```
This finds instructions with variable offsets while matching the fixed bytes.

### Cross-Platform Support

| Feature | Windows | Linux/macOS |
|---------|---------|-------------|
| Process listing | Full | Full |
| Process attachment | Full | Stub (error) |
| Memory reading | Full | Stub (error) |
| Pattern scanning | Full | Stub (error) |

## Reverse Engineering Tips

### Finding Camera/View Matrices

1. Look for patterns that access 16 consecutive floats (64 bytes)
2. Common patterns: `F3 0F 10` (movss), `F3 0F 11` (movss store)
3. View matrices often have identity-like values initially

### Finding Player Position

1. Use `find_value` with your current X coordinate as a float
2. Move the player and search again to narrow down
3. Once found, use `watch_address` to monitor

### Signature Scanning

1. Find the code that accesses the data in a disassembler
2. Extract unique byte sequences around the access
3. Use `??` for bytes that may change (addresses, offsets)

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~10ms |
| Process attachment | ~50-100ms |
| Module enumeration | ~10-50ms |
| Pattern scan (100MB module) | ~500ms-2s |
| Memory read | <1ms |

## Security Note

This tool requires administrator privileges on Windows and can read any process memory. Use responsibly and only on games/software you have permission to analyze.

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [windows](https://github.com/microsoft/windows-rs) - Windows API bindings
- [sysinfo](https://github.com/GuillaumeGomez/sysinfo) - Cross-platform process listing
- [tokio](https://tokio.rs/) - Async runtime

## License

Part of the template-repo project. See repository LICENSE file.

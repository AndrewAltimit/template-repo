# Memory Explorer MCP Server

MCP server for game memory exploration and reverse engineering. Designed to help AI assistants explore game memory to find structures, patterns, and data locations.

## Features

- **Process Management**: List and attach to running processes
- **Memory Reading**: Read various data types (integers, floats, strings, vectors, matrices)
- **Pattern Scanning**: Search for byte patterns with wildcards
- **Value Search**: Find specific values in memory (useful for health, position, etc.)
- **Pointer Resolution**: Follow pointer chains to find dynamic addresses
- **Memory Watching**: Monitor addresses for changes over time
- **Module Listing**: View loaded DLLs and their base addresses

## Requirements

- Windows (uses Windows memory APIs via pymem)
- Python 3.11+
- Administrator privileges (required for process memory access)

## Installation

```bash
cd tools/mcp/mcp_memory_explorer
pip install -e .
```

## Usage

### Running the Server

```bash
# Run as a module
python -m mcp_memory_explorer

# Or directly
python src/mcp_memory_explorer/server.py
```

### MCP Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "memory-explorer": {
      "command": "python",
      "args": ["-m", "mcp_memory_explorer"],
      "cwd": "tools/mcp/mcp_memory_explorer/src"
    }
  }
}
```

## Available Tools

### Process Management

- `list_processes` - List running processes (optionally filter by name)
- `attach_process` - Attach to a process by name (e.g., "NMS.exe")
- `detach_process` - Detach from current process
- `get_status` - Get current attachment status

### Memory Reading

- `read_memory` - Read memory with various type interpretations:
  - `bytes` - Raw bytes as hex
  - `int32`, `int64`, `uint32`, `uint64` - Integers
  - `float`, `double` - Floating point
  - `string` - Null-terminated string
  - `pointer` - 64-bit pointer
  - `vector3`, `vector4` - 3D/4D vectors
  - `matrix4x4` - 4x4 transformation matrix

- `dump_memory` - Hex dump with ASCII representation

### Searching

- `scan_pattern` - Search for byte patterns with wildcards
  - Example: `"48 8B 05 ?? ?? ?? ?? 48 85 C0"`
  - Use `??` for wildcard bytes

- `find_value` - Search for specific numeric values

### Pointer Operations

- `resolve_pointer` - Follow a pointer chain
  - Example: base="NMS.exe", offsets=[0x1000, 0x20, 0x8]

### Watching

- `watch_address` - Add an address to monitor
- `read_watches` - Read all watched values
- `remove_watch` - Remove a watch

### Module Information

- `get_modules` - List all loaded DLLs with base addresses

## Example Session

```
# Find and attach to the game
> list_processes filter="NMS"
[{"name": "NMS.exe", "pid": 12345}]

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

## Security Note

This tool requires administrator privileges and can read any process memory. Use responsibly and only on games/software you have permission to analyze.

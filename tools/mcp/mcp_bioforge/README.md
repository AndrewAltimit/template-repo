# BioForge MCP Server (Rust)

> A Model Context Protocol server for the BioForge biological automation platform -- liquid handling, thermal control, plate imaging, colony counting, and protocol management with safety enforcement.

## Overview

This MCP server provides:
- Liquid handling: dispense, aspirate, and mix operations with volume tracking
- Thermal control: temperature setting, heat shock sequences, and long-duration incubation
- Imaging: plate capture with multiple illumination modes and colony counting
- Protocol management: load and validate saved protocol TOML files
- Safety enforcement: all actuator operations validated through `SafetyEnforcer`
- Human-in-the-loop gates for critical steps
- Emergency stop capability

**Phase 2**: Tools validate all inputs through `bioforge-safety` before returning mock responses. Real hardware drivers will be wired in subsequent phases.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in STDIO mode (for Claude Code)
./target/release/mcp-bioforge --mode stdio --config-dir /path/to/config

# Run in standalone HTTP mode
./target/release/mcp-bioforge --mode standalone --port 8030 --config-dir /path/to/config

# Test health
curl http://localhost:8030/health
```

### Prerequisites

- Configuration directory containing `safety_limits.toml` and `hardware.toml`
- Default config path: `./config` (relative to working directory)
- Config files define safety limits, workspace bounds, and hardware parameters

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `dispense` | Dispense precise volume to target well | `target`, `volume_ul`, `reagent`, `flow_rate` |
| `aspirate` | Aspirate from a source container | `source`, `volume_ul`, `flow_rate` |
| `mix` | Aspirate/dispense cycles to mix contents | `target`, `volume_ul`, `cycles`, `flow_rate` |
| `move_to` | Move gantry to absolute position | `x_mm`, `y_mm`, `z_mm` |
| `set_temperature` | Set thermal zone to target temperature | `zone`, `target_c`, `hold_seconds` |
| `heat_shock` | Atomic ramp-hold-return temperature sequence | `ramp_to_c`, `hold_s`, `return_to_c` |
| `incubate` | Long-duration temperature hold with monitoring | `zone`, `target_c`, `duration_hours` |
| `capture_plate_image` | Capture plate image (white, UV, dark field) | `plate_id`, `lighting_mode` |
| `count_colonies` | Colony counting pipeline on captured image | `plate_id`, `image_id` |
| `load_protocol` | Load and validate a protocol TOML file | `protocol_id` |
| `get_system_status` | Get sensor readings, actuator states, inventory | None |
| `request_human_action` | Pause for human intervention | `description`, `timeout_min` |
| `emergency_stop` | Halt all actuators and safe the system | None |

### Example: Dispense

```json
{
  "tool": "dispense",
  "arguments": {
    "target": "plate_1:A1",
    "volume_ul": 50.0,
    "reagent": "LB_broth"
  }
}
```

### Example: Heat Shock

```json
{
  "tool": "heat_shock",
  "arguments": {
    "ramp_to_c": 42.0,
    "hold_s": 45,
    "return_to_c": 4.0
  }
}
```

## Safety Enforcement

All actuator operations pass through `SafetyEnforcer` from the `bioforge-safety` crate:
- **Rate limiting** -- prevents commands faster than hardware can safely execute
- **Actuator interval** -- enforces minimum time between consecutive actuator calls
- **Volume validation** -- rejects volumes outside safe range, tracks cumulative dispensed volume
- **Position validation** -- ensures gantry stays within workspace bounds
- **Temperature validation** -- rejects temperatures outside safe operating range
- **Incubation limits** -- caps maximum incubation duration
- **Heat shock hold limits** -- prevents excessively long thermal exposures
- **Flow rate validation** -- ensures pump speeds stay within safe limits
- **Mix cycle limits** -- caps maximum aspirate/dispense cycles

## Configuration

### CLI Arguments

```
--mode <MODE>           Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>           Port to listen on [default: 8030]
--config-dir <PATH>     Path to config directory with safety_limits.toml and hardware.toml [default: config]
--log-level <LEVEL>     Log level [default: info]
```

### Config Files

The `--config-dir` must contain:
- `safety_limits.toml` -- temperature ranges, volume limits, rate limits, timing constraints
- `hardware.toml` -- motion bounds (x/y/z max), device parameters

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
    "bioforge": {
      "command": "mcp-bioforge",
      "args": ["--mode", "stdio", "--config-dir", "/path/to/bioforge/config"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_bioforge

# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Run clippy
cargo clippy -- -D warnings

# Format code
cargo fmt
```

## Project Structure

```
tools/mcp/mcp_bioforge/
├── Cargo.toml          # Package configuration
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point, config loading
    └── tools.rs        # MCP tool implementations (13 tools)
```

Depends on library crates from `packages/bioforge/`:
- `bioforge-types` -- shared types, config structs, error definitions
- `bioforge-safety` -- SafetyEnforcer, WorkspaceBounds
- `bioforge-hal` -- hardware abstraction layer
- `bioforge-protocol` -- protocol parsing and validation
- `bioforge-vision` -- imaging and colony counting

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [bioforge-*](../../../packages/bioforge/) - BioForge library crates
- [tokio](https://tokio.rs/) - Async runtime
- [toml](https://github.com/toml-rs/toml) - Config file parsing
- [chrono](https://github.com/chronotope/chrono) - Timestamps

## License

Part of the template-repo project. See repository LICENSE file.

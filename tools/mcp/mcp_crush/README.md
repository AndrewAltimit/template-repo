# Crush MCP Server (Rust)

> A Model Context Protocol server for AI-powered code generation using Crush CLI via OpenRouter, built in Rust for performance and reliability.

## Overview

This MCP server provides:
- Quick code generation with multiple modes (generate, explain, convert, quick)
- Conversation history tracking for context continuity
- Local, container, and Docker execution modes
- Environment-based configuration

**Note**: This server was migrated from Python to Rust for improved performance and lower resource usage.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-crush --mode standalone --port 8015

# Run in STDIO mode (for Claude Code)
./target/release/mcp-crush --mode stdio

# Test health
curl http://localhost:8015/health
```

### Prerequisites

- Crush CLI installed locally, OR
- Docker with `openrouter-agents` service configured
- OpenRouter API key: Set `OPENROUTER_API_KEY` environment variable

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_crush` | Generate, explain, or convert code | `query` (required), `context`, `mode`, `comparison_mode`, `force` |
| `clear_crush_history` | Clear conversation history | None |
| `crush_status` | Get integration status and statistics | None |
| `toggle_crush_auto_consult` | Control auto-consultation | `enable` |

### Consultation Modes

| Mode | Description |
|------|-------------|
| `quick` | General code task with concise response (default) |
| `generate` | Generate detailed implementation from requirements |
| `explain` | Explain code functionality |
| `convert` | Convert code to another language (requires `context`) |

### Example Usage

```bash
# Get status
curl -X POST http://localhost:8015/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "crush_status", "arguments": {}}'

# Quick code generation
curl -X POST http://localhost:8015/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "consult_crush", "arguments": {"query": "Write a Python function to calculate fibonacci numbers", "mode": "quick"}}'

# Convert code
curl -X POST http://localhost:8015/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "consult_crush", "arguments": {"query": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)", "mode": "convert", "context": "Rust"}}'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CRUSH_ENABLED` | `true` | Enable/disable integration |
| `CRUSH_AUTO_CONSULT` | `true` | Enable auto-consultation |
| `OPENROUTER_API_KEY` | None | OpenRouter API key (required) |
| `CRUSH_TIMEOUT` | `300` | Timeout in seconds |
| `CRUSH_MAX_PROMPT` | `4000` | Maximum prompt length |
| `CRUSH_LOG_CONSULTATIONS` | `true` | Log all consultations |
| `CRUSH_INCLUDE_HISTORY` | `true` | Include history in prompts |
| `CRUSH_MAX_HISTORY` | `5` | Maximum history entries |
| `CRUSH_DOCKER_SERVICE` | `openrouter-agents` | Docker service name |
| `CRUSH_QUIET_MODE` | `true` | Suppress TTY features |

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8015]
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

## Execution Modes

The server automatically detects the best execution mode:

1. **Container Mode**: When running inside Docker, executes `crush` directly
2. **Local Mode**: When `crush` CLI is available locally
3. **Docker Mode**: Falls back to `docker compose run` with the configured service

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "crush": {
      "command": "mcp-crush",
      "args": ["--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "your-api-key"
      }
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "crush": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-crush", "mcp-crush", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_crush

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
tools/mcp/mcp_crush/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── crush.rs        # Crush CLI integration
    └── types.rs        # Data types and configuration
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## Testing

```bash
# Run unit tests
cargo test

# Test with output
cargo test -- --nocapture

# Test HTTP endpoints (after starting server)
curl http://localhost:8015/health
curl http://localhost:8015/mcp/tools
curl -X POST http://localhost:8015/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "crush_status", "arguments": {}}'
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "OPENROUTER_API_KEY not configured" | Missing API key | Set `OPENROUTER_API_KEY` environment variable |
| "Crush failed with exit code" | CLI error | Check Crush installation and API key |
| Timeout errors | Complex query | Increase `CRUSH_TIMEOUT` |
| Docker execution fails | Service not running | Start `openrouter-agents` service |

## Security

- API keys should be set via environment variables, not in config files
- Container mode provides isolation from host system
- Auth tokens are stored in user's home directory, not in code

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime
- [clap](https://clap.rs/) - CLI argument parsing
- [serde](https://serde.rs/) - Serialization

## License

Part of the template-repo project. See repository LICENSE file.

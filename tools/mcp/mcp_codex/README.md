# Codex MCP Server (Rust)

> A Model Context Protocol server for AI-powered code generation using OpenAI's Codex CLI, built in Rust for performance and reliability.

## Overview

This MCP server provides:
- Code generation with multiple modes (generate, complete, refactor, explain, quick)
- Conversation history tracking
- Environment-based configuration
- Docker containerized execution with sandbox support

**Note**: This server was migrated from Python to Rust for improved performance and lower resource usage.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-codex --mode standalone --port 8021

# Run in STDIO mode (for Claude Code)
./target/release/mcp-codex --mode stdio

# Test health
curl http://localhost:8021/health
```

### Prerequisites

- OpenAI Codex CLI installed: `npm install -g @openai/codex`
- Codex authentication: Run `codex auth` first

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_codex` | Generate, complete, refactor, or explain code | `query` (required), `context`, `mode`, `comparison_mode`, `force` |
| `clear_codex_history` | Clear conversation history | None |
| `codex_status` | Get integration status and statistics | None |
| `toggle_codex_auto_consult` | Control auto-consultation | `enable` |

### Consultation Modes

| Mode | Description |
|------|-------------|
| `quick` | General code task (default) |
| `generate` | Generate new code from requirements |
| `complete` | Complete partial code |
| `refactor` | Refactor existing code for quality |
| `explain` | Explain code functionality |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEX_ENABLED` | `true` | Enable/disable integration |
| `CODEX_AUTO_CONSULT` | `true` | Enable auto-consultation |
| `CODEX_AUTH_PATH` | `~/.codex/auth.json` | Path to auth file |
| `CODEX_TIMEOUT` | `300` | Timeout in seconds |
| `CODEX_MAX_CONTEXT` | `8000` | Maximum context length |
| `CODEX_LOG_CONSULTATIONS` | `true` | Log all consultations |
| `CODEX_INCLUDE_HISTORY` | `true` | Include history in prompts |
| `CODEX_MAX_HISTORY` | `5` | Maximum history entries |
| `CODEX_BYPASS_SANDBOX` | `false` | Bypass sandbox (containers only) |

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8021]
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

## Docker Support

### Using docker-compose

```bash
# Start the MCP server
docker compose up -d mcp-codex

# View logs
docker compose logs -f mcp-codex

# Test health
curl http://localhost:8021/health
```

### Building the Image

```bash
# Build with docker-compose
docker compose build mcp-codex

# Or build directly
docker build -f docker/codex.Dockerfile -t mcp-codex .
```

### Volume Mounts

The container requires access to Codex authentication:
- `~/.codex:/home/user/.codex:rw` - Auth token and session files

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "codex": {
      "command": "mcp-codex",
      "args": ["--mode", "stdio"]
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "codex": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-codex", "mcp-codex", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_codex

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
tools/mcp/mcp_codex/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── codex.rs        # Codex CLI integration
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
curl http://localhost:8021/health
curl http://localhost:8021/mcp/tools
curl -X POST http://localhost:8021/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "codex_status", "arguments": {}}'
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Codex CLI not available" | Codex not installed | Run `npm install -g @openai/codex` |
| "Authentication not found" | Not authenticated | Run `codex auth` on host |
| Timeout errors | Complex query | Increase `CODEX_TIMEOUT` |
| Container auth issues | Missing volume mount | Ensure `~/.codex` is mounted with `:rw` |

## Security

- Codex runs in sandbox mode by default (`--sandbox workspace-write`)
- `CODEX_BYPASS_SANDBOX` should only be enabled in already-sandboxed environments (containers)
- Auth tokens are stored in user's home directory, not in code
- Container runs as non-root user

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime
- [clap](https://clap.rs/) - CLI argument parsing
- [serde](https://serde.rs/) - Serialization

## License

Part of the template-repo project. See repository LICENSE file.

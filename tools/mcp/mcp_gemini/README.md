# Gemini MCP Server (Rust)

> A Model Context Protocol server for AI-powered second opinions and validation using Google's Gemini CLI, built in Rust for performance and reliability.

## Overview

This MCP server provides:
- Second opinion consultations via Gemini AI
- Conversation history tracking with context carry-over
- Rate limiting for API protection
- Container and direct CLI execution modes
- Environment-based configuration

**Note**: This server was migrated from Python to Rust for improved performance and lower resource usage.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-gemini --mode standalone --port 8006

# Run in STDIO mode (for Claude Code)
./target/release/mcp-gemini --mode stdio

# Test health
curl http://localhost:8006/health
```

### Prerequisites

- Gemini CLI installed: `npm install -g @google/gemini-cli`
- Gemini authentication: Run `gemini` interactively first, OR
- Google API key: Set `GOOGLE_API_KEY` or `GEMINI_API_KEY` environment variable

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_gemini` | Get second opinion from Gemini AI | `query` (required), `context`, `comparison_mode`, `force` |
| `clear_gemini_history` | Clear conversation history | None |
| `gemini_status` | Get integration status and statistics | None |
| `toggle_gemini_auto_consult` | Control auto-consultation | `enable` |

### Example Usage

```bash
# Get status
curl -X POST http://localhost:8006/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "gemini_status", "arguments": {}}'

# Consult Gemini
curl -X POST http://localhost:8006/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "consult_gemini", "arguments": {"query": "Review this code for security issues", "context": "def login(user, pass): ..."}}'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_ENABLED` | `true` | Enable/disable integration |
| `GEMINI_AUTO_CONSULT` | `true` | Enable auto-consultation |
| `GEMINI_CLI_COMMAND` | `gemini` | CLI command to use |
| `GEMINI_TIMEOUT` | `600` | Timeout in seconds |
| `GEMINI_RATE_LIMIT` | `2.0` | Delay between requests (seconds) |
| `GEMINI_MAX_CONTEXT` | `100000` | Maximum context length |
| `GEMINI_LOG_CONSULTATIONS` | `true` | Log all consultations |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` | Model to use |
| `GEMINI_INCLUDE_HISTORY` | `true` | Include history in prompts |
| `GEMINI_MAX_HISTORY` | `10` | Maximum history entries |
| `GEMINI_USE_CONTAINER` | `true` | Use Docker container mode |
| `GEMINI_CONTAINER_IMAGE` | `gemini-corporate-proxy:latest` | Container image |
| `GEMINI_YOLO_MODE` | `false` | Enable YOLO approval mode |
| `GOOGLE_API_KEY` | None | Google API key (alternative to OAuth) |
| `GEMINI_API_KEY` | None | Alias for `GOOGLE_API_KEY` |

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8006]
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
docker compose up -d mcp-gemini

# View logs
docker compose logs -f mcp-gemini

# Test health
curl http://localhost:8006/health
```

### Building the Image

```bash
# Build with docker-compose
docker compose build mcp-gemini

# Or build directly
docker build -f docker/mcp-gemini.Dockerfile -t mcp-gemini .
```

### Volume Mounts

For OAuth authentication, the container requires:
- `~/.gemini:/home/geminiuser/.gemini:ro` - Auth tokens and session files

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "gemini": {
      "command": "mcp-gemini",
      "args": ["--mode", "stdio"],
      "env": {
        "GOOGLE_API_KEY": "your-api-key"
      }
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "gemini": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-gemini", "mcp-gemini", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_gemini

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
tools/mcp/mcp_gemini/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── gemini.rs       # Gemini CLI integration
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
curl http://localhost:8006/health
curl http://localhost:8006/mcp/tools
curl -X POST http://localhost:8006/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "gemini_status", "arguments": {}}'
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Gemini CLI not available" | Gemini not installed | Run `npm install -g @google/gemini-cli` |
| "Authentication required" | Not authenticated | Run `gemini` interactively or set `GOOGLE_API_KEY` |
| Timeout errors | Complex query | Increase `GEMINI_TIMEOUT` |
| Container auth issues | Missing OAuth tokens | Ensure `~/.gemini` exists on host |
| Rate limit errors | Too many requests | Increase `GEMINI_RATE_LIMIT` delay |

## Security

- API keys should be set via environment variables, not in config files
- Container mode provides isolation from host system
- Rate limiting protects against API abuse
- Auth tokens are stored in user's home directory, not in code
- Container runs as non-root user

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime
- [clap](https://clap.rs/) - CLI argument parsing
- [serde](https://serde.rs/) - Serialization
- [regex](https://github.com/rust-lang/regex) - Pattern matching

## License

Part of the template-repo project. See repository LICENSE file.

# OpenCode MCP Server (Rust)

> A Model Context Protocol server for AI-powered code assistance via OpenRouter, built in Rust for performance and reliability.

## Overview

This MCP server provides:
- Code generation, refactoring, review, and explanation capabilities
- Multiple consultation modes (generate, refactor, review, explain, quick)
- Conversation history tracking for context continuity
- Direct OpenRouter API integration using Qwen Coder model
- Environment-based configuration

**Note**: This server was migrated from Python to Rust for improved performance and lower resource usage.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-opencode --mode standalone --port 8014

# Run in STDIO mode (for Claude Code)
./target/release/mcp-opencode --mode stdio

# Test health
curl http://localhost:8014/health
```

### Prerequisites

- OpenRouter API key: Set `OPENROUTER_API_KEY` environment variable

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_opencode` | Generate, refactor, review, or explain code | `query` (required), `context`, `mode`, `comparison_mode`, `force` |
| `clear_opencode_history` | Clear conversation history | None |
| `opencode_status` | Get integration status and statistics | None |
| `toggle_opencode_auto_consult` | Control auto-consultation | `enable` |

### Consultation Modes

| Mode | Description |
|------|-------------|
| `quick` | Quick response with concise answers (default) |
| `generate` | Generate clean, well-documented code from requirements |
| `refactor` | Suggest improvements for readability, performance, maintainability |
| `review` | Analyze code for bugs, security issues, performance problems |
| `explain` | Provide clear, detailed explanations of code |

### Example Usage

```bash
# Get status
curl -X POST http://localhost:8014/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "opencode_status", "arguments": {}}'

# Quick code generation
curl -X POST http://localhost:8014/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "consult_opencode", "arguments": {"query": "Write a Python function to merge two sorted lists", "mode": "quick"}}'

# Code review
curl -X POST http://localhost:8014/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "consult_opencode", "arguments": {"query": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)", "mode": "review"}}'

# Refactor with context
curl -X POST http://localhost:8014/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "consult_opencode", "arguments": {"query": "def sort(arr): ...", "mode": "refactor", "context": "optimize for large arrays"}}'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_ENABLED` | `true` | Enable/disable integration |
| `OPENCODE_AUTO_CONSULT` | `true` | Enable auto-consultation |
| `OPENROUTER_API_KEY` | None | OpenRouter API key (required) |
| `OPENCODE_MODEL` | `qwen/qwen-2.5-coder-32b-instruct` | Model to use |
| `OPENCODE_TIMEOUT` | `300` | Timeout in seconds |
| `OPENCODE_MAX_PROMPT` | `8000` | Maximum prompt length |
| `OPENCODE_LOG_CONSULTATIONS` | `true` | Log all consultations |
| `OPENCODE_INCLUDE_HISTORY` | `true` | Include history in prompts |
| `OPENCODE_MAX_HISTORY` | `5` | Maximum history entries |

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8014]
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
    "opencode": {
      "command": "mcp-opencode",
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
    "opencode": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-opencode", "mcp-opencode", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_opencode

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
tools/mcp/mcp_opencode/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── opencode.rs     # OpenRouter API integration
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
curl http://localhost:8014/health
curl http://localhost:8014/mcp/tools
curl -X POST http://localhost:8014/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "opencode_status", "arguments": {}}'
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "OPENROUTER_API_KEY not configured" | Missing API key | Set `OPENROUTER_API_KEY` environment variable |
| "API error (401)" | Invalid API key | Check your OpenRouter API key |
| Timeout errors | Complex query | Increase `OPENCODE_TIMEOUT` |
| Rate limiting | Too many requests | Add delay between requests |

## Security

- API keys should be set via environment variables, not in config files
- All API communication uses HTTPS
- Request headers include proper identification for rate limiting

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime
- [reqwest](https://docs.rs/reqwest/) - HTTP client
- [clap](https://clap.rs/) - CLI argument parsing
- [serde](https://serde.rs/) - Serialization

## License

Part of the template-repo project. See repository LICENSE file.

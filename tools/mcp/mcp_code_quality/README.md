# Code Quality MCP Server (Rust)

> A Model Context Protocol server for code quality operations, built in Rust. Provides format checking, linting, testing, type checking, security scanning, and dependency auditing with enterprise security features.

## Overview

This MCP server provides:
- Format checking and auto-formatting for multiple languages
- Code linting with various linters (ruff, flake8, eslint, golint, clippy)
- pytest test execution with coverage support
- Type checking with ty (Astral's fast type checker)
- Security scanning with bandit
- Dependency vulnerability auditing with pip-audit
- Markdown link validation with md-link-checker
- Enterprise security features: path validation, rate limiting, audit logging

**Note**: Migrated from Python to Rust for improved performance.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-code-quality --mode standalone --port 8010

# Run in STDIO mode (for Claude Code)
./target/release/mcp-code-quality --mode stdio

# Test health
curl http://localhost:8010/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `format_check` | Check code formatting | `path` (required), `language` |
| `lint` | Run code linting | `path` (required), `linter`, `config` |
| `autoformat` | Auto-format code | `path` (required), `language` |
| `run_tests` | Run pytest tests | `path`, `pattern`, `verbose`, `coverage`, `fail_fast`, `markers` |
| `type_check` | Run ty type checking | `path` (required), `config` |
| `security_scan` | Run bandit security analysis | `path` (required), `severity`, `confidence` |
| `audit_dependencies` | Check for vulnerabilities | `requirements_file` |
| `check_markdown_links` | Check markdown for broken links | `path` (required), `check_external`, `timeout`, `concurrent`, `ignore_patterns` |
| `get_status` | Get server status | None |
| `get_audit_log` | Get audit log entries | `limit`, `operation` |

### Example: Format Check

```json
{
  "tool": "format_check",
  "arguments": {
    "path": "/app/src",
    "language": "python"
  }
}
```

### Example: Run Linting

```json
{
  "tool": "lint",
  "arguments": {
    "path": "/app/src",
    "linter": "ruff"
  }
}
```

## Configuration

### CLI Arguments

```
--mode <MODE>           Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>           Port to listen on [default: 8010]
--timeout <SECS>        Timeout for subprocess operations [default: 600]
--allowed-paths <PATHS> Comma-separated allowed paths [default: /workspace,/app,/home]
--audit-log <PATH>      Audit log file path [default: /var/log/mcp-code-quality/audit.log]
--rate-limit <BOOL>     Enable rate limiting [default: true]
--log-level <LEVEL>     Log level [default: info]
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_CODE_QUALITY_TIMEOUT` | Subprocess timeout (seconds) | `600` |
| `MCP_CODE_QUALITY_ALLOWED_PATHS` | Comma-separated allowed paths | `/workspace,/app,/home` |
| `MCP_CODE_QUALITY_AUDIT_LOG` | Audit log file path | `/var/log/mcp-code-quality/audit.log` |
| `MCP_CODE_QUALITY_RATE_LIMIT` | Enable rate limiting | `true` |

## Security Features

### Path Allowlist Validation
Only paths within configured allowed directories can be operated on. This prevents access to sensitive system files.

### Rate Limiting
Operations are rate-limited to prevent DoS attacks:
- `format_check`: 100 calls/minute
- `lint`: 50 calls/minute
- `autoformat`: 50 calls/minute
- `run_tests`: 20 calls/minute
- `type_check`: 30 calls/minute
- `security_scan`: 20 calls/minute
- `audit_dependencies`: 10 calls/minute

### Audit Logging
All operations are logged with timestamps, paths, success status, and details for compliance review.

## Prerequisites

The server requires these external tools to be installed:

| Tool | Package | Purpose |
|------|---------|---------|
| `black` | pip install black | Python formatting |
| `ruff` | pip install ruff | Python linting |
| `flake8` | pip install flake8 | Python linting |
| `ty` | pip install ty | Python type checking |
| `pytest` | pip install pytest | Python testing |
| `bandit` | pip install bandit | Security scanning |
| `pip-audit` | pip install pip-audit | Dependency auditing |
| `prettier` | npm install prettier | JS/TS formatting |
| `eslint` | npm install eslint | JS/TS linting |
| `rustfmt` | cargo component | Rust formatting |
| `clippy` | cargo component | Rust linting |
| `gofmt` | go toolchain | Go formatting |
| `golint` | go install | Go linting |

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
    "code-quality": {
      "command": "mcp-code-quality",
      "args": ["--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_code_quality

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
tools/mcp/mcp_code_quality/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── engine.rs       # Code quality engine
    └── types.rs        # Data types
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## Response Format

### format_check Response

```json
{
  "success": true,
  "formatted": true,
  "output": "",
  "command": "black --check /app/src"
}
```

### lint Response

```json
{
  "success": true,
  "passed": false,
  "issues": ["src/main.py:10: E501 line too long"],
  "issue_count": 1,
  "command": "ruff check /app/src"
}
```

### security_scan Response

```json
{
  "success": true,
  "passed": false,
  "findings": [{"severity": "HIGH", "test_id": "B105", "issue_text": "..."}],
  "finding_count": 1,
  "command": "bandit -r /app/src --severity-level=low --confidence-level=low -f json"
}
```

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime with process support
- [dashmap](https://github.com/xacrimon/dashmap) - Concurrent HashMap for rate limiting
- [chrono](https://github.com/chronotope/chrono) - Date/time for audit logging

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~50ms |
| Format check | Depends on file size |
| Linting | Depends on codebase size |
| Rate limit check | <1ms |

## License

Part of the template-repo project. See repository LICENSE file.

# MCP Code Quality Server (Standalone HTTP)

> A standalone Rust HTTP server for code quality operations. Provides formatting, linting, testing, type checking, security scanning, and dependency auditing behind an Axum-based REST API with enterprise security features.

## Overview

This is the standalone HTTP backend for the code-quality MCP server. It exposes code quality tools as REST endpoints with built-in security:

- **Path allowlist validation** -- restricts operations to approved directories
- **Rate limiting** -- sliding-window per-operation throttling
- **Audit logging** -- JSON-structured compliance logging with rotation
- **Subprocess management** -- timeout-guarded command execution

This server is used inside Docker containers by the [MCP Code Quality server](../../mcp/mcp_code_quality/) which wraps it with the MCP protocol layer.

## Quick Start

```bash
# Build from source
cd tools/rust/mcp-code-quality
cargo build --release

# Start the HTTP server (default port 8010)
./target/release/mcp-code-quality

# Custom port and disabled rate limiting
./target/release/mcp-code-quality --port 9000 --no-rate-limit

# Test health
curl http://localhost:8010/health
```

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `format_check` | Check code formatting | `path` (required), `language` |
| `lint` | Run code linting | `path` (required), `linter`, `config` |
| `autoformat` | Auto-format code files | `path` (required), `language` |
| `run_tests` | Run pytest tests | `path`, `pattern`, `verbose`, `coverage`, `fail_fast`, `markers` |
| `type_check` | Run ty type checking | `path` (required), `strict`, `config` |
| `security_scan` | Run bandit security analysis | `path` (required), `severity`, `confidence` |
| `audit_dependencies` | Check for known vulnerabilities | `requirements_file` |
| `check_markdown_links` | Validate links in markdown | `path` (required), `check_external`, `timeout`, `concurrent_checks` |
| `get_status` | Get server status and tool versions | None |
| `get_audit_log` | Get recent audit log entries | `limit`, `operation` |

### Supported Languages and Linters

| Language | Format | Lint |
|----------|--------|------|
| Python | black | ruff, flake8 |
| JavaScript | prettier | eslint |
| TypeScript | prettier | eslint |
| Go | gofmt | golint |
| Rust | rustfmt | clippy |

## Configuration

### CLI Arguments

```
-p, --port <PORT>     Port to listen on [default: 8010]
    --host <HOST>     Host to bind to [default: 0.0.0.0]
    --no-rate-limit   Disable rate limiting
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_CODE_QUALITY_PORT` | `8010` | Server port |
| `MCP_CODE_QUALITY_HOST` | `0.0.0.0` | Bind address |
| `MCP_CODE_QUALITY_TIMEOUT` | `600` | Subprocess timeout (seconds) |
| `MCP_CODE_QUALITY_ALLOWED_PATHS` | `/workspace,/app,/home,/tmp` | Comma-separated allowed paths |
| `MCP_CODE_QUALITY_AUDIT_LOG` | `/var/log/mcp-code-quality/audit.log` | Audit log file path |
| `MCP_CODE_QUALITY_RATE_LIMIT` | `true` | Enable rate limiting |

## Security Features

### Path Allowlist

All file operations are validated against a configurable allowlist. Paths are canonicalized (symlinks resolved) before checking, preventing path traversal attacks.

### Rate Limiting

Per-operation sliding-window rate limits:

| Operation | Limit |
|-----------|-------|
| `format_check` | 100/min |
| `lint` | 50/min |
| `autoformat` | 50/min |
| `run_tests` | 20/min |
| `type_check` | 30/min |
| `security_scan` | 20/min |
| `audit_dependencies` | 10/min |

### Audit Logging

Every operation is logged as a JSON line with timestamp, path, success status, and details. Log rotation occurs at 10 MB. Falls back to `/tmp/mcp-code-quality-audit.log` if the primary path is not writable.

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tools/list` | GET | List available tools with schemas |
| `/tools/call` | POST | Execute a tool (MCP-style request) |
| `/format_check` | POST | Legacy: direct format check |
| `/lint` | POST | Legacy: direct lint |
| `/autoformat` | POST | Legacy: direct autoformat |
| `/run_tests` | POST | Legacy: direct test runner |
| `/type_check` | POST | Legacy: direct type check |
| `/security_scan` | POST | Legacy: direct security scan |
| `/audit_dependencies` | POST | Legacy: direct dependency audit |
| `/check_markdown_links` | POST | Legacy: direct link check |
| `/get_status` | GET | Legacy: direct status |
| `/get_audit_log` | POST | Legacy: direct audit log |

## Project Structure

```
tools/rust/mcp-code-quality/
├── Cargo.toml          # Package configuration
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point (clap)
    ├── server.rs       # Axum HTTP server and route handlers
    ├── config.rs       # Config from env vars, rate limit definitions
    ├── security.rs     # Path validation, rate limiting, audit logging
    ├── subprocess.rs   # Timeout-guarded command execution
    ├── error.rs        # Error types and MCP error responses
    └── tools/
        ├── mod.rs      # Tool type definitions (Language, Linter)
        ├── format.rs   # Format check and autoformat
        ├── lint.rs     # Lint, type check, security scan
        ├── test.rs     # Test runner, dependency audit, link check
        └── status.rs   # Server status and audit log retrieval
```

## Dependencies

- [axum](https://docs.rs/axum) - HTTP framework
- [tower-http](https://docs.rs/tower-http) - CORS middleware
- [tokio](https://tokio.rs/) - Async runtime with subprocess support
- [chrono](https://docs.rs/chrono) - Timestamps for audit logging
- [clap](https://docs.rs/clap) - CLI argument parsing

## License

Part of the template-repo project. See repository LICENSE file.

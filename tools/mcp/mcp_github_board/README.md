# GitHub Board MCP Server (Rust)

> A Model Context Protocol server for GitHub Projects v2 board operations -- work claims, dependency management, status tracking, and multi-agent coordination.

## Overview

This MCP server provides:
- Work queue management: query ready work, claim/release issues
- Status tracking: update issue status on GitHub Projects boards
- Dependency management: blocker relationships and parent-child links
- Multi-agent coordination: claim system prevents concurrent work on the same issue
- Session tracking: claims are tied to agent + session for renewability
- Board configuration and agent listing

Wraps the `board-manager` Rust CLI for all GitHub Projects v2 API operations. The CLI is auto-discovered from PATH, `~/.local/bin`, `~/.cargo/bin`, or local build paths.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in STDIO mode (for Claude Code)
./target/release/mcp-github-board --mode stdio

# Run in standalone HTTP mode
./target/release/mcp-github-board --mode standalone --port 8022

# Test health
curl http://localhost:8022/health
```

### Prerequisites

- `board-manager` CLI built and in PATH (from `tools/rust/board-manager/`)
- GitHub authentication configured (via `gh auth` or `GITHUB_TOKEN`)
- GitHub Projects v2 board configured in the repository

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `query_ready_work` | Get unblocked, unclaimed TODO issues | `agent_name`, `limit` |
| `claim_work` | Claim an issue for implementation | `issue_number`, `agent_name`, `session_id` |
| `renew_claim` | Extend claim duration for long tasks | `issue_number`, `agent_name`, `session_id` |
| `release_work` | Release claim on an issue | `issue_number`, `agent_name`, `reason` |
| `update_status` | Change issue status on the board | `issue_number`, `status` |
| `add_blocker` | Add blocking dependency between issues | `issue_number`, `blocker_number` |
| `mark_discovered_from` | Set parent-child relationship | `issue_number`, `parent_number` |
| `get_issue_details` | Get full issue details with metadata | `issue_number` |
| `get_dependency_graph` | Get blockers, blocked, parent, children | `issue_number` |
| `list_agents` | List enabled agents for this board | None |
| `get_board_config` | Get full board configuration | None |
| `board_status` | Get server initialization status | None |

### Status Values

The `update_status` tool accepts: `Todo`, `In Progress`, `Blocked`, `Done`, `Abandoned`.

### Release Reasons

The `release_work` tool accepts: `completed`, `blocked`, `abandoned`, `error`.

### Example: Claim Work

```json
{
  "tool": "claim_work",
  "arguments": {
    "issue_number": 42,
    "agent_name": "claude-code",
    "session_id": "session-abc123"
  }
}
```

### Example: Query Ready Work

```json
{
  "tool": "query_ready_work",
  "arguments": {
    "agent_name": "claude-code",
    "limit": 5
  }
}
```

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8022]
--log-level <LEVEL>   Log level [default: info]
```

### board-manager Discovery

The server auto-discovers the `board-manager` binary in this order:
1. `which board-manager` (PATH lookup)
2. `/usr/local/bin/board-manager`
3. `~/.local/bin/board-manager`
4. `~/.cargo/bin/board-manager`
5. `tools/rust/board-manager/target/release/board-manager` (relative)
6. `$CWD/tools/rust/board-manager/target/release/board-manager` (absolute)

All `board-manager` calls use `--format json` for structured output.

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
    "github-board": {
      "command": "mcp-github-board",
      "args": ["--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_github_board

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

Also build the required CLI dependency:

```bash
cd tools/rust/board-manager
cargo build --release
```

## Project Structure

```
tools/mcp/mcp_github_board/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    └── server.rs       # MCP tools + board-manager CLI wrapper
```

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime with process support
- [which](https://github.com/harryfei/which-rs) - Binary discovery in PATH
- [dirs](https://github.com/dirs-dev/dirs-rs) - Home directory resolution
- [board-manager](../../rust/board-manager/) - GitHub Projects v2 CLI (runtime dependency)

## License

Part of the template-repo project. See repository LICENSE file.

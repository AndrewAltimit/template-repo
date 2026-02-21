# AgentCore Memory MCP Server (Rust)

> A Model Context Protocol server for AI agent memory using ChromaDB vector database. Provides semantic search, fact storage, and session event tracking across multiple AI agents.

## Overview

This MCP server provides:
- Short-term memory via session events (goals, decisions, outcomes)
- Long-term memory via fact storage with namespace organization
- Semantic search across stored memories ranked by relevance
- In-memory LRU cache for repeated queries
- Predefined namespace hierarchy for multi-agent knowledge sharing
- Content sanitization before storage

**Note**: Migrated from Python to Rust for improved performance. Uses ChromaDB as the vector database backend (self-hosted, no cloud costs).

## Quick Start

```bash
# Build from source
cargo build --release

# Run in STDIO mode (for Claude Code)
./target/release/mcp-agentcore-memory --mode stdio

# Run in standalone HTTP mode
./target/release/mcp-agentcore-memory --mode standalone --port 8023

# Test health
curl http://localhost:8023/health
```

### Prerequisites

- ChromaDB instance running (default: `localhost:8000`)
- Start via Docker Compose: `docker compose up -d chromadb`

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `store_event` | Store a short-term session event | `content` (required), `actor_id` (required), `session_id` (required) |
| `store_facts` | Store facts/patterns for long-term retention | `facts` (required), `namespace` (required), `source` |
| `search_memories` | Semantic search across stored memories | `query` (required), `namespace` (required), `top_k` |
| `list_session_events` | List events from a specific session | `actor_id` (required), `session_id` (required), `limit` |
| `list_namespaces` | List available predefined namespaces | None |
| `memory_status` | Get ChromaDB connection status and cache stats | None |

### Example: Store Facts

```json
{
  "tool": "store_facts",
  "arguments": {
    "facts": ["Rust workspace uses resolver 2", "All MCP servers use mcp-core crate"],
    "namespace": "codebase/patterns",
    "source": "PR #42"
  }
}
```

### Example: Search Memories

```json
{
  "tool": "search_memories",
  "arguments": {
    "query": "how are MCP servers structured",
    "namespace": "codebase/architecture",
    "top_k": 5
  }
}
```

## Namespace Hierarchy

Memories are organized into predefined namespaces using `/` separators:

| Category | Namespaces |
|----------|------------|
| **Codebase** | `codebase/architecture`, `codebase/patterns`, `codebase/conventions`, `codebase/dependencies` |
| **Reviews** | `reviews/pr`, `reviews/issues` |
| **Preferences** | `preferences/user`, `preferences/project` |
| **Agents** | `agents/claude`, `agents/gemini`, `agents/opencode`, `agents/crush`, `agents/codex` |
| **Cross-Cutting** | `security/patterns`, `testing/patterns`, `performance/patterns` |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMADB_HOST` | `localhost` | ChromaDB server host |
| `CHROMADB_PORT` | `8000` | ChromaDB server port |
| `CHROMADB_COLLECTION` | `agent_memory` | Collection name prefix |

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8023]
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
    "agentcore-memory": {
      "command": "mcp-agentcore-memory",
      "args": ["--mode", "stdio"],
      "env": {
        "CHROMADB_HOST": "localhost",
        "CHROMADB_PORT": "8000"
      }
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_agentcore_memory

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
tools/mcp/mcp_agentcore_memory/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── client.rs       # ChromaDB HTTP client
    ├── cache.rs        # In-memory LRU cache
    ├── sanitize.rs     # Content sanitization
    └── types.rs        # Data types, config, namespace definitions
```

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime
- [reqwest](https://github.com/seanmonstar/reqwest) - HTTP client for ChromaDB API
- [chrono](https://github.com/chronotope/chrono) - Timestamps for events
- [sha2](https://github.com/RustCrypto/hashes) / [md5](https://github.com/stainless-steel/md5) - Content deduplication

## License

Part of the template-repo project. See repository LICENSE file.

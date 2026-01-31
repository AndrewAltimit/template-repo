# AgentCore Memory MCP Server

> This MCP server was converted from Python to Rust for improved performance
> and consistency with the project's container-first philosophy.
> See the MIT License in the repository root for licensing information.

A Model Context Protocol server for persistent AI agent memory using ChromaDB with semantic search capabilities.

## Overview

This MCP server provides persistent memory for AI agents, enabling:
- **Short-term memory**: Session-based events for conversation context
- **Long-term memory**: Facts and patterns stored indefinitely
- **Semantic search**: Find relevant memories by meaning, not just keywords

## Quick Start

### Using ChromaDB (Self-Hosted)

1. Start ChromaDB:
```bash
docker compose --profile memory-chromadb up -d
```

2. The MCP server will auto-connect when invoked via Claude Code.

## MCP Tools

### `store_event`
Store a short-term memory event.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | Content to remember |
| `actor_id` | string | Yes | Actor identifier (e.g., 'claude-code') |
| `session_id` | string | Yes | Session identifier |

### `store_facts`
Store facts for long-term retention.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `facts` | array | Yes | List of fact strings to store |
| `namespace` | string | Yes | Namespace for organization |
| `source` | string | No | Source attribution |

### `search_memories`
Search memories using semantic similarity.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `namespace` | string | Yes | Namespace to search |
| `top_k` | integer | No | Maximum results (default: 5) |

### `list_session_events`
List events from a specific session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `actor_id` | string | Yes | Actor identifier |
| `session_id` | string | Yes | Session identifier |
| `limit` | integer | No | Maximum events (default: 50) |

### `list_namespaces`
List available predefined namespaces.

### `memory_status`
Get provider status and info.

## Namespaces

Memories are organized into hierarchical namespaces:

| Category | Namespace | Purpose |
|----------|-----------|---------|
| Codebase | `codebase/patterns` | Code patterns and idioms |
| Codebase | `codebase/architecture` | Architectural decisions |
| Codebase | `codebase/conventions` | Coding conventions |
| Codebase | `codebase/dependencies` | Dependency information |
| Reviews | `reviews/pr` | PR review context |
| Reviews | `reviews/issues` | Issue context |
| Preferences | `preferences/user` | User preferences |
| Preferences | `preferences/project` | Project preferences |
| Agents | `agents/claude` | Claude-specific learnings |
| Agents | `agents/gemini` | Gemini-specific learnings |
| Agents | `agents/opencode` | OpenCode-specific learnings |
| Agents | `agents/crush` | Crush-specific learnings |
| Agents | `agents/codex` | Codex-specific learnings |

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CHROMADB_HOST` | ChromaDB host | `localhost` |
| `CHROMADB_PORT` | ChromaDB port | `8000` |
| `CHROMADB_COLLECTION` | Collection prefix | `agent_memory` |

## Building

```bash
cd tools/mcp/mcp_agentcore_memory
cargo build --release
```

The binary will be at `target/release/mcp-agentcore-memory`.

## Usage

```bash
# STDIO mode (for Claude Code)
./target/release/mcp-agentcore-memory --mode stdio

# Standalone HTTP mode
./target/release/mcp-agentcore-memory --mode standalone --port 8023

# Check health
curl http://localhost:8023/health

# List tools
curl http://localhost:8023/mcp/tools
```

## Security

- **Content Sanitization**: All content is scanned for secrets (API keys, tokens, passwords) before storage
- **Entropy Analysis**: High-entropy strings that look like secrets are redacted
- **No Secrets Policy**: Credentials are never stored in memory

### Blocked Patterns

The sanitizer detects and redacts:
- Generic secrets (`api_key=`, `secret=`, `password=`, `token=`)
- Private keys (`-----BEGIN.*PRIVATE KEY-----`)
- OpenAI/Stripe keys (`sk-`, `pk_`, `rk_`)
- AWS credentials (`AKIA...`, 40-char base64)
- GitHub tokens (`ghp_`, `gho_`, `github_pat_`)
- Slack tokens (`xox*-`)
- Anthropic keys (`sk-ant-`)
- OpenRouter keys (`sk-or-`)
- Bearer/Basic auth tokens
- Connection strings with passwords

## Architecture

```
+-----------------------------------------------------------+
|               MCP Server (agentcore-memory)                |
|                                                           |
|  Tools: store_event, store_facts, search_memories, etc.   |
|                          |                                |
|                          v                                |
|  +-----------------------------------------------------+  |
|  |             ChromaDB HTTP Client                    |  |
|  +-----------------------------------------------------+  |
|                          |                                |
|                          v                                |
|  +-----------------------------------------------------+  |
|  |              ChromaDB Server (Docker)               |  |
|  |              - Vector embeddings                    |  |
|  |              - Semantic search                      |  |
|  +-----------------------------------------------------+  |
+-----------------------------------------------------------+
```

## License

Part of the template-repo project. See repository LICENSE file.

# MCP Rust Core Migration Plan

**Branch**: `feat/mcp-core-rust`
**Author**: Claude Code
**Date**: 2026-01-26

## Executive Summary

This plan outlines the migration of MCP servers from Python to Rust, introducing a new `mcp_core_rust` workspace with three operational modes: standalone, server, and client. The goal is to maintain full HTTP compatibility with existing Python servers while gaining Rust's performance and safety benefits.

---

## 1. Current Architecture Analysis

### 1.1 Python MCP Core Structure

The existing Python infrastructure (`tools/mcp/mcp_core/`) provides:

```
BaseMCPServer (Abstract Base Class)
├── HTTP Transport (FastAPI + Uvicorn)
│   ├── /health - Health check
│   ├── /mcp/tools - List tools
│   ├── /mcp/execute - Execute tool (simple API)
│   ├── /messages - HTTP Stream Transport (MCP 2024-11-05)
│   └── /mcp - JSON-RPC endpoint
├── STDIO Transport (mcp.server.stdio)
└── Tool Registry (get_tools() -> Dict)
```

**Key Design Patterns**:
- Tool name = method name (reflection-based dispatch)
- JSON Schema for tool parameters
- Session management via `Mcp-Session-Id` header
- SSE streaming for long-running operations

### 1.2 Server Inventory (20 Total)

| Port | Server | Complexity | Migration Priority |
|------|--------|------------|-------------------|
| 8010 | code-quality | High (subprocess) | P2 |
| 8011 | content-creation | High (LaTeX/Manim) | P3 |
| 8014 | opencode | Low (API proxy) | P1 |
| 8015 | crush | Low (API proxy) | P1 |
| 8021 | codex | Low (API proxy) | P1 |
| 8022 | github-board | Medium | P2 |
| 8024 | reaction-search | Low (semantic) | P1 - Pilot |
| 8023 | agentcore-memory | Medium | P2 |
| Others | Various | Variable | P3+ |

---

## 2. Proposed Architecture

### 2.1 Three Operational Modes

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP Core Rust                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │   STANDALONE    │  │     SERVER      │  │     CLIENT      │     │
│  │    (default)    │  │   (REST only)   │  │  (MCP proxy)    │     │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤     │
│  │ MCP Protocol    │  │ REST API only   │  │ MCP Protocol    │     │
│  │ + Tool Impl     │  │ (no MCP)        │  │ -> REST Client  │     │
│  │ (All-in-one)    │  │                 │  │                 │     │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘     │
│           │                    │                    │               │
│           ▼                    ▼                    ▼               │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐      │
│  │ Claude Desktop │   │ Any REST       │   │ Claude Desktop │      │
│  │ or HTTP Client │   │ Consumer       │   │ (tools remote) │      │
│  └────────────────┘   └────────────────┘   └────────────────┘      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Mode Details**:

| Mode | CLI Flag | Use Case | Transport |
|------|----------|----------|-----------|
| **standalone** | `--mode standalone` | Default, full MCP server with tools | HTTP + STDIO |
| **server** | `--mode server` | Headless tool server (no MCP) | REST API only |
| **client** | `--mode client --backend URL` | MCP proxy to remote tools | HTTP + STDIO |

### 2.2 Workspace Structure

```
tools/mcp/mcp_core_rust/
├── Cargo.toml                    # Workspace root
├── crates/
│   ├── mcp-core/                 # Core abstractions
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── server.rs         # BaseMCPServer trait
│   │       ├── tool.rs           # Tool trait + registry
│   │       ├── transport/
│   │       │   ├── mod.rs
│   │       │   ├── http.rs       # Axum-based HTTP transport
│   │       │   ├── stdio.rs      # STDIO transport
│   │       │   └── rest.rs       # REST-only mode
│   │       ├── jsonrpc.rs        # JSON-RPC 2.0 handling
│   │       ├── session.rs        # Session management
│   │       └── error.rs          # Error types
│   │
│   ├── mcp-macros/               # Proc macros for tool registration
│   │   ├── Cargo.toml
│   │   └── src/
│   │       └── lib.rs            # #[mcp_tool], #[derive(MCPServer)]
│   │
│   ├── mcp-client/               # Client mode implementation
│   │   ├── Cargo.toml
│   │   └── src/
│   │       └── lib.rs            # REST client for proxying
│   │
│   └── mcp-testing/              # Test utilities
│       ├── Cargo.toml
│       └── src/
│           └── lib.rs            # Mock server, test client
│
└── servers/                      # Converted MCP servers
    └── reaction-search/          # Pilot server
        ├── Cargo.toml
        └── src/
            ├── main.rs
            ├── server.rs
            └── tools/
                ├── mod.rs
                ├── search.rs
                └── status.rs
```

### 2.3 Core Traits

```rust
// mcp-core/src/tool.rs

/// A single MCP tool with schema and execution
#[async_trait]
pub trait Tool: Send + Sync {
    /// Tool name (used in JSON-RPC)
    fn name(&self) -> &'static str;

    /// Tool description for discovery
    fn description(&self) -> &'static str;

    /// JSON Schema for parameters
    fn schema(&self) -> serde_json::Value;

    /// Execute the tool with given arguments
    async fn execute(&self, args: serde_json::Value) -> Result<ToolResult>;
}

/// Result of tool execution
pub struct ToolResult {
    pub content: Vec<Content>,
    pub is_error: bool,
}

pub enum Content {
    Text { text: String },
    Image { data: String, mime_type: String },
    Resource { uri: String, mime_type: String },
}
```

```rust
// mcp-core/src/server.rs

/// Base MCP server with tool registry
pub struct MCPServer {
    name: String,
    version: String,
    port: u16,
    tools: HashMap<String, Arc<dyn Tool>>,
    mode: ServerMode,
}

pub enum ServerMode {
    /// Full MCP server with embedded tools
    Standalone,
    /// REST API only (no MCP protocol)
    Server,
    /// MCP protocol proxying to REST backend
    Client { backend_url: String },
}

impl MCPServer {
    pub fn new(name: impl Into<String>, version: impl Into<String>) -> Self;
    pub fn with_port(self, port: u16) -> Self;
    pub fn with_mode(self, mode: ServerMode) -> Self;
    pub fn register_tool<T: Tool + 'static>(self, tool: T) -> Self;

    /// Run the server (blocking)
    pub async fn run(self) -> Result<()>;
}
```

### 2.4 Procedural Macros

```rust
// Usage example with macros
use mcp_core::prelude::*;
use mcp_macros::{mcp_tool, MCPServer};

#[derive(MCPServer)]
#[mcp(name = "reaction-search", version = "1.0.0", port = 8024)]
struct ReactionSearchServer {
    engine: ReactionSearchEngine,
}

#[mcp_tool(
    description = "Search for reaction images using natural language"
)]
async fn search_reactions(
    &self,
    #[mcp(description = "Natural language search query")]
    query: String,
    #[mcp(description = "Maximum results", default = 5)]
    limit: Option<i32>,
) -> Result<SearchResults> {
    self.engine.search(&query, limit.unwrap_or(5)).await
}
```

**Macro Expansion**:
- Generates `impl Tool for SearchReactionsTool`
- Generates JSON Schema from function signature
- Registers tool in server's tool map
- Handles async dispatch and error conversion

---

## 3. HTTP API Compatibility

### 3.1 Endpoint Parity

The Rust implementation must match Python's HTTP contract exactly:

| Endpoint | Method | Python | Rust |
|----------|--------|--------|------|
| `/health` | GET | Health check | Same |
| `/mcp/tools` | GET | List tools | Same |
| `/mcp/execute` | POST | Execute tool | Same |
| `/messages` | GET | Transport info | Same |
| `/messages` | POST | JSON-RPC (MCP) | Same |
| `/.well-known/mcp` | GET | Discovery | Same |

### 3.2 JSON-RPC Methods

```json
// Initialize
{"jsonrpc": "2.0", "method": "initialize", "params": {...}, "id": 1}

// List tools
{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}

// Call tool
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "...", "arguments": {...}}, "id": 3}
```

### 3.3 Headers

- `Mcp-Session-Id`: Session tracking
- `Mcp-Response-Mode`: `batch` (default) or `stream`
- `MCP-Protocol-Version`: Protocol version negotiation

---

## 4. Mode-Specific Behavior

### 4.1 Standalone Mode (Default)

```bash
./mcp-reaction-search --mode standalone --port 8024
```

- Full MCP server with embedded tools
- Supports both HTTP and STDIO transports
- Tools execute locally
- Identical behavior to Python servers

### 4.2 Server Mode (REST Only)

```bash
./mcp-reaction-search --mode server --port 8024
```

Exposes simplified REST API:

```
GET  /health              -> {"status": "healthy", ...}
GET  /tools               -> {"tools": [...]}
POST /tools/{name}/call   -> {"result": ...}
```

**No MCP protocol** - just clean REST for:
- Integration with non-MCP systems
- Microservice deployments
- Load balancer health checks
- Direct API testing

### 4.3 Client Mode (MCP Proxy)

```bash
./mcp-reaction-search --mode client --backend http://tools-server:8024
```

- Presents full MCP interface to Claude
- Proxies tool calls to REST backend
- Allows separating MCP protocol from tool execution
- Enables horizontal scaling of tool backends

```
┌──────────────┐     MCP      ┌──────────────┐     REST     ┌──────────────┐
│ Claude       │ ──────────── │ MCP Client   │ ──────────── │ Tool Server  │
│ Desktop      │              │ (Rust)       │              │ (Rust/Python)│
└──────────────┘              └──────────────┘              └──────────────┘
```

---

## 5. Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

**Deliverables**:
1. `mcp-core` crate with:
   - `Tool` trait
   - `MCPServer` struct
   - HTTP transport (Axum)
   - JSON-RPC handler
   - Session management

2. `mcp-macros` crate with:
   - `#[mcp_tool]` attribute macro
   - JSON Schema generation

3. Basic tests and documentation

**Success Criteria**:
- Can create a simple server with 1 tool
- HTTP endpoints match Python behavior
- Tool schema auto-generated from Rust types

### Phase 2: Pilot Server (Week 2-3)

**Deliverables**:
1. Port `mcp_reaction_search` to Rust
2. Verify feature parity:
   - `search_reactions`
   - `get_reaction`
   - `list_reaction_tags`
   - `refresh_reactions`
   - `reaction_search_status`

3. Performance benchmarks vs Python

**Success Criteria**:
- All 5 tools working identically
- Docker deployment working
- 2x+ performance improvement

### Phase 3: Multi-Mode Support (Week 3-4)

**Deliverables**:
1. `--mode server` REST-only mode
2. `mcp-client` crate for proxy mode
3. `--mode client --backend URL` support
4. Integration tests for all modes

**Success Criteria**:
- All 3 modes working
- Client can proxy to Python servers
- Server mode tested with curl/httpie

### Phase 4: Additional Servers (Week 4+)

**Migration Order** (by priority):

| Priority | Server | Reason |
|----------|--------|--------|
| P1 | reaction-search | Pilot, simple |
| P1 | codex, opencode, crush | API proxies, simple |
| P2 | github-board | Medium complexity |
| P2 | code-quality | Subprocess handling |
| P3 | Others | As needed |

---

## 6. Dependencies

### 6.1 Core Dependencies

```toml
[workspace.dependencies]
# Async runtime
tokio = { version = "1.40", features = ["full"] }
async-trait = "0.1"

# HTTP framework
axum = { version = "0.7", features = ["ws"] }
tower = "0.5"
tower-http = { version = "0.6", features = ["cors", "trace"] }

# Serialization
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

# Schema generation
schemars = "0.8"  # JSON Schema from Rust types

# CLI
clap = { version = "4.5", features = ["derive"] }

# Logging
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

# Error handling
thiserror = "2.0"
anyhow = "1.0"

# HTTP client (for client mode)
reqwest = { version = "0.12", features = ["json"] }

# UUID
uuid = { version = "1.10", features = ["v4", "serde"] }
```

### 6.2 No Official Rust MCP SDK

There is no official Anthropic Rust MCP SDK yet. This implementation will:
1. Implement MCP protocol directly (JSON-RPC 2.0 over HTTP)
2. Be compatible with future official SDK if released
3. Focus on HTTP transport (STDIO can be added later)

---

## 7. Testing Strategy

### 7.1 Unit Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use mcp_testing::MockServer;

    #[tokio::test]
    async fn test_tool_execution() {
        let server = MockServer::new()
            .with_tool(SearchReactionsTool::new());

        let result = server.call_tool("search_reactions", json!({
            "query": "happy"
        })).await;

        assert!(result.is_ok());
    }
}
```

### 7.2 Integration Tests

```rust
#[tokio::test]
async fn test_http_compatibility() {
    let server = spawn_server(8099).await;
    let client = reqwest::Client::new();

    // Test MCP initialize
    let resp = client.post("http://localhost:8099/messages")
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": 1
        }))
        .send()
        .await?;

    assert_eq!(resp.status(), 200);
}
```

### 7.3 Python Compatibility Tests

```python
# tests/test_rust_compatibility.py
"""Verify Rust server matches Python behavior"""

def test_tool_list_identical():
    """Tool list should match between Python and Rust"""
    py_tools = get_tools("http://localhost:8024")   # Python
    rs_tools = get_tools("http://localhost:8124")   # Rust

    assert py_tools == rs_tools
```

---

## 8. Docker Integration

### 8.1 Dockerfile Pattern

```dockerfile
# Rust MCP Server Dockerfile
FROM rust:1.93-slim as builder
WORKDIR /app

# Build dependencies first (caching)
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
RUN cargo build --release --package mcp-reaction-search

# Runtime image
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/mcp-reaction-search /usr/local/bin/

EXPOSE 8024
HEALTHCHECK --interval=30s --timeout=10s \
    CMD curl -f http://localhost:8024/health || exit 1

ENTRYPOINT ["mcp-reaction-search"]
CMD ["--mode", "standalone", "--port", "8024"]
```

### 8.2 Docker Compose Integration

```yaml
# docker-compose.yml
services:
  mcp-reaction-search-rust:
    build:
      context: ./tools/mcp/mcp_core_rust
      dockerfile: servers/reaction-search/Dockerfile
    ports:
      - "8124:8024"  # Different port during migration
    environment:
      - RUST_LOG=info
    networks:
      - mcp-network
```

---

## 9. Migration Path

### 9.1 Gradual Rollout

```
Week 1-2: Core + Pilot (reaction-search)
   └── Rust server on port 8124 (parallel to Python 8024)

Week 3-4: Validation
   └── A/B testing between Python and Rust
   └── Performance comparison
   └── Bug fixes

Week 5+: Production cutover
   └── Switch Claude config to Rust server
   └── Keep Python as fallback
   └── Migrate next server
```

### 9.2 Rollback Strategy

- Keep Python servers running during migration
- Use different ports for Rust servers
- Feature flag in Claude config to switch
- Monitor error rates and latency

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| API Compatibility | 100% | Integration tests pass |
| Performance | 2x faster | Benchmark p99 latency |
| Memory Usage | 50% less | Docker stats |
| Binary Size | < 20MB | Release build |
| Test Coverage | > 80% | cargo tarpaulin |

---

## 11. Open Questions

1. **STDIO Support**: Should Phase 1 include STDIO transport, or defer to Phase 3?
   - **Recommendation**: Defer to Phase 3, focus on HTTP first

2. **Schema Generation**: Use `schemars` crate or custom proc macro?
   - **Recommendation**: Start with `schemars`, customize if needed

3. **Session Persistence**: Store sessions in memory or Redis?
   - **Recommendation**: Memory for Phase 1, add Redis option later

4. **Error Mapping**: How to map Rust errors to JSON-RPC error codes?
   - **Recommendation**: Create error enum with `#[error_code]` attribute

---

## 12. Appendix: File Locations

### Python (Reference)
```
tools/mcp/mcp_core/mcp_core/base_server.py    # 550 lines
tools/mcp/mcp_reaction_search/                 # Pilot reference
```

### Rust (New)
```
tools/mcp/mcp_core_rust/                        # New workspace
tools/mcp/mcp_core_rust/crates/mcp-core/        # Core library
tools/mcp/mcp_core_rust/servers/reaction-search/ # Pilot server
```

---

## 13. Next Steps

1. [x] Review and approve this plan
2. [x] Create `tools/mcp/mcp_core_rust/` workspace structure
3. [x] Implement `mcp-core` crate with `Tool` trait
4. [x] Implement HTTP transport with Axum
5. [ ] Create `#[mcp_tool]` proc macro (deferred - manual impl works well)
6. [x] Port `reaction-search` as pilot
7. [x] Run compatibility tests
8. [x] Implement multi-mode support (server/client modes)
9. [x] Docker containerization and CI integration (Phase 4)

## 14. Implementation Progress

### Phase 1: Core Infrastructure - COMPLETE
- `mcp-core` crate with Tool trait, MCPServer, HTTP transport
- `mcp-macros` crate (placeholder for proc macros)
- `mcp-client` crate for REST client mode
- `mcp-testing` crate for test utilities
- 19 unit tests passing

### Phase 2: Pilot Server - COMPLETE
- Ported `mcp_reaction_search` to Rust
- 5 tools: search_reactions, get_reaction, list_reaction_tags, refresh_reactions, reaction_search_status
- Using fastembed for ONNX-based sentence embeddings
- 9 unit tests passing (+ 2 ignored requiring model download)

### Phase 3: Multi-Mode Support - COMPLETE
- Server mode (--mode server): REST-only API, no MCP protocol
- Client mode (--mode client --backend-url URL): MCP proxy to REST backend
- RestTransport for simplified REST API
- ProxyToolWrapper for forwarding tool calls
- All 33 tests passing

### Phase 4: Docker & CI Integration - COMPLETE
- Multi-stage Dockerfile for reaction-search server (builder + runtime)
- Docker Compose service `mcp-reaction-search-rust` on port 8124
- CI stages in run-ci.sh: mcp-fmt, mcp-clippy, mcp-test, mcp-build, mcp-deny, mcp-doc, mcp-full
- cargo-deny configuration for license/security checks
- All clippy warnings fixed (collapsible if statements, dead_code)
- 33 tests passing in Docker CI environment

---

*This plan is ready for review. Please provide feedback on the architecture, priorities, or any concerns before implementation begins.*

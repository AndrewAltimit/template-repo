# MCP Core Rust

A Rust library for building MCP (Model Context Protocol) servers with support for multiple operational modes.

## Overview

This workspace provides the core infrastructure for building MCP servers in Rust, designed to be a Rust equivalent of the Python `mcp_core` package. It supports three operational modes:

| Mode | Description |
|------|-------------|
| **standalone** | Full MCP server with embedded tools (default) |
| **server** | REST API only - no MCP protocol |
| **client** | MCP proxy that forwards to a REST backend |

## Crates

| Crate | Description |
|-------|-------------|
| `mcp-core` | Core server library with Tool trait, HTTP transport, and JSON-RPC handling |
| `mcp-macros` | Procedural macros for tool registration (WIP) |
| `mcp-client` | REST client for proxy mode |
| `mcp-testing` | Test utilities and mock tools |

## Quick Start

### Define a Tool

```rust
use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{json, Value};

struct EchoTool;

#[async_trait]
impl Tool for EchoTool {
    fn name(&self) -> &str { "echo" }

    fn description(&self) -> &str {
        "Echo the input message"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "message": {"type": "string"}
            },
            "required": ["message"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let msg = args["message"].as_str().unwrap_or("no message");
        Ok(ToolResult::text(format!("Echo: {msg}")))
    }
}
```

### Create a Server

```rust
use mcp_core::{init_logging, MCPServer};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_logging("info");

    let server = MCPServer::builder("my-server", "1.0.0")
        .port(8080)
        .tool(EchoTool)
        .build();

    server.run().await?;
    Ok(())
}
```

### Run the Example

```bash
# Build and run the example server
cargo run --example echo_server -- --port 8080

# Test the endpoints
curl http://localhost:8080/health
curl http://localhost:8080/mcp/tools
curl -X POST http://localhost:8080/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "echo", "arguments": {"message": "hello"}}'
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool (simple API) |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## CLI Arguments

All servers support these common arguments:

```
--mode <MODE>         Server mode: standalone, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8000]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

## Testing

```bash
# Run all tests
cargo test

# Run with output
cargo test -- --nocapture
```

## Project Structure

```
packages/mcp_core_rust/
├── Cargo.toml              # Workspace definition
├── README.md               # This file
├── crates/
│   ├── mcp-core/           # Core library
│   │   ├── src/
│   │   │   ├── lib.rs      # Public API
│   │   │   ├── server.rs   # MCPServer implementation
│   │   │   ├── tool.rs     # Tool trait and registry
│   │   │   ├── error.rs    # Error types
│   │   │   ├── session.rs  # Session management
│   │   │   ├── jsonrpc.rs  # JSON-RPC types
│   │   │   └── transport/  # HTTP transport
│   │   └── examples/
│   │       └── echo_server.rs
│   ├── mcp-macros/         # Proc macros (WIP)
│   ├── mcp-client/         # REST client
│   └── mcp-testing/        # Test utilities
└── servers/                # Converted MCP servers (future)
```

## Migration from Python

This library is designed to match the Python `mcp_core` API:

| Python | Rust |
|--------|------|
| `BaseMCPServer` | `MCPServer` |
| `get_tools()` | `impl Tool` |
| `run(mode="http")` | `server.run().await` |
| `@tool_decorator` | `#[mcp_tool]` (future) |

## Development Status

**Phase 1: Core Infrastructure** (Current)
- [x] Tool trait and registry
- [x] HTTP transport (Axum)
- [x] JSON-RPC handling
- [x] Session management
- [x] Server modes (standalone working)
- [x] Example server
- [x] Unit tests (15 passing)
- [ ] Proc macros for tool registration

**Phase 2: Pilot Server**
- [ ] Port `mcp_reaction_search` to Rust

**Phase 3: Multi-Mode Support**
- [ ] Server mode (REST only)
- [ ] Client mode (proxy)

## License

MIT

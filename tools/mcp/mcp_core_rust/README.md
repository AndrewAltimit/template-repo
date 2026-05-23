# MCP Core Rust

> A Rust library for building MCP (Model Context Protocol) servers with support for multiple operational modes.

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
| `mcp-macros` | `#[mcp_tool]` procedural macro for typed tool definitions |
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

### Define a Tool with `#[mcp_tool]` (recommended)

The hand-written `impl Tool` above extracts arguments out of a raw
`serde_json::Value`. That pattern is easy to get wrong: a `.unwrap()` /
`["field"]` on missing or wrong-typed input **panics**, and a panic in tool
execution used to be a latent crash vector. Prefer the `#[mcp_tool]` macro,
which generates the `Tool` impl from a typed `async fn`: parameters are
deserialized into their declared Rust types, the JSON schema is derived
automatically, and a missing/mismatched argument becomes a clean
`InvalidParameters` error instead of a panic.

```rust
use mcp_macros::mcp_tool;

#[mcp_tool(description = "Echo the input message a number of times")]
async fn echo(
    #[mcp(description = "Message to echo")]
    message: String,
    #[mcp(description = "Repeat count", default = 1)]
    count: i64,
    #[mcp(description = "Optional suffix")]
    suffix: Option<String>,
) -> Result<String, anyhow::Error> {
    let mut out = message.repeat(count as usize);
    if let Some(s) = suffix {
        out.push_str(&s);
    }
    Ok(out)
}
// Generates a unit struct `EchoTool` implementing `Tool`; register it with
// `.tool(EchoTool)` exactly like a hand-written tool.
```

Rules the macro applies:

- A plain parameter (e.g. `message: String`) is **required**.
- `Option<T>` is **optional** (an absent key deserializes as `None`).
- `#[mcp(default = ...)]` makes a parameter optional and supplies the default;
  the literal keeps its JSON type (`default = 1` is an integer, `default = "x"`
  a string).
- The function returns `Result<T, E>` where `T: Serialize` and `E: Display`.
  `Ok(value)` is serialized into the tool result; `Err(e)` becomes an
  `isError` tool result carrying `e.to_string()`.

See `crates/mcp-core/tests/mcp_tool_macro.rs` for the executable reference,
including the schema/required-field and error-path assertions.

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
tools/mcp/mcp_core_rust/
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
│   ├── mcp-macros/         # #[mcp_tool] proc macro
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
| `@tool_decorator` | `#[mcp_tool]` |

## Robustness: tool-execution panic boundary

`tools/call` runs each tool inside a `catch_unwind` boundary
(`transport/handler.rs`). If a tool panics — for example a stray `.unwrap()` on
a malformed argument — the panic is caught and returned to the client as an MCP
tool error (`isError: true`) instead of unwinding the connection task or
crashing the server. The server stays available for subsequent requests. This
is a safety net, not a license to panic: prefer `#[mcp_tool]` or explicit
`InvalidParameters` errors so failures are typed rather than caught.

## Development Status

**Phase 1: Core Infrastructure** (Current)
- [x] Tool trait and registry
- [x] HTTP transport (Axum)
- [x] JSON-RPC handling
- [x] Session management
- [x] Server modes (standalone working)
- [x] Example server
- [x] Unit tests
- [x] Tool-execution panic boundary (`catch_unwind` in `tools/call`)
- [x] Proc macros for tool registration (`#[mcp_tool]`)

**Phase 2: Pilot Server**
- [ ] Port `mcp_reaction_search` to Rust

**Phase 3: Multi-Mode Support**
- [ ] Server mode (REST only)
- [ ] Client mode (proxy)

## License

Part of the template-repo project. See repository LICENSE file.

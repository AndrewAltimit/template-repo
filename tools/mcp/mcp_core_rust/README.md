# MCP Core Rust

> A Rust library for building MCP (Model Context Protocol) servers with support for multiple operational modes.

## Overview

This workspace provides the shared infrastructure for every Rust MCP server in
`tools/mcp/mcp_*`. A server defines tools; the library handles the protocol
(JSON-RPC 2.0, MCP lifecycle and version negotiation), the transports, and the
failure modes (panics, timeouts, malformed input).

| Mode | Description |
|------|-------------|
| **stdio** | Newline-delimited JSON-RPC over stdin/stdout (how `.mcp.json` launches servers) |
| **standalone** | MCP over HTTP (Streamable HTTP, JSON responses) plus a simple REST API (default) |
| **server** | REST API only - no MCP protocol |
| **client** | MCP proxy that forwards tool calls to a REST backend |

Protocol support: MCP revisions `2025-11-25`, `2025-06-18`, `2025-03-26` and
`2024-11-05` (the client's requested revision is echoed if supported, otherwise
the latest is offered). Only the `tools` capability is advertised.

## Crates

| Crate | Description |
|-------|-------------|
| `mcp-core` | `Tool` trait, registry, protocol handler, STDIO/HTTP/REST transports, typed-args and schema helpers |
| `mcp-macros` | `#[mcp_tool]` procedural macro for typed tool definitions |
| `mcp-client` | REST client used by client (proxy) mode |
| `mcp-testing` | `TestServer`, `MockTool` and assertion helpers |
| `mcp-ai-consult` | Shared 4-tool framework for the AI consultation servers (implement `AiIntegration::start_consult`/`finish_consult` so a long consultation does not hold the integration lock) |

## Quick Start

### Define a Tool

```rust
use async_trait::async_trait;
use mcp_core::args::ArgsExt;
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
        // Missing or non-string `message` -> InvalidParameters, never a panic.
        let msg = args.required_str("message")?;
        Ok(ToolResult::text(format!("Echo: {msg}")))
    }
}
```

An `Err` returned from `execute` is sent to the client as a tool error result
(`isError: true` with the error text), so the model can read it and retry.

### Typed arguments and derived schemas

Indexing the raw `Value` (`args["limit"].as_u64().unwrap()`) panics or silently
defaults on bad input. Two helpers avoid that:

```rust
use mcp_core::args::{ArgsExt, parse_args};
use mcp_core::schema::schema_for;
use mcp_core::schemars::{self, JsonSchema};
use serde::Deserialize;

// Per-key accessors: required_* / optional_* for str, i64, u64, f64, bool,
// plus required::<T>() / optional::<T>() for anything Deserialize.
let limit = args.optional_u64("limit")?.unwrap_or(10);

// Whole-struct: one type drives both parsing and the advertised schema.
#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "mcp_core::schemars")] // only needed without a direct schemars dep
struct SearchArgs {
    /// Free-text query
    query: String,
    /// Maximum number of results
    limit: Option<u32>,
}

fn schema(&self) -> Value { schema_for::<SearchArgs>() }

async fn execute(&self, args: Value) -> Result<ToolResult> {
    let args: SearchArgs = parse_args(args)?;
    // ...
}
```

### Define a Tool with `#[mcp_tool]`

The macro generates the `Tool` impl from a typed function: parameters are
deserialized into their declared Rust types, the JSON schema is derived, and a
missing/mismatched argument becomes a clean `InvalidParameters` error.

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
- `Option<T>` is **optional** (an absent key or `null` deserializes as `None`).
- `#[mcp(default = ...)]` makes a parameter optional, supplies the default (also
  for `Option<T>`: `Some(default)`), and advertises it in the schema. The
  literal keeps its JSON type (`default = 1` is an integer, `default = "x"` a
  string, `default = -1` a negative integer).
- `#[mcp(state)]` injects a parameter from the tool's own fields instead of the
  JSON arguments (see below).
- `description` may be omitted when the function has a `///` doc comment.
  `name = "..."` overrides the tool name (`[A-Za-z0-9_.-]`, max 128 chars).
- Raw identifiers map to plain keys: `r#type: String` is the `"type"` argument.
- Unknown `#[mcp_tool]`/`#[mcp]` keys, `self` receivers, destructuring patterns,
  generics and a missing return type are compile errors.
- The function returns `Result<T, E>` with `E: Display`. `T = String` becomes
  plain text, `T = ToolResult` is returned as-is (images, several blocks),
  `T = ()` becomes `OK`, and any other `T: Serialize` becomes pretty JSON.
  `Err(e)` becomes an `isError` result carrying `e.to_string()`.
- Schema types: strings, integers (`minimum: 0` for unsigned), numbers,
  booleans, arrays with `items`, maps as objects. Other types (your own structs
  and enums, `serde_json::Value`) are left unconstrained in the schema and
  validated by serde at call time.

The generated code only references `mcp_core`, so the server crate needs no
direct `serde_json`/`async-trait` dependency for it.

#### Stateful tools with `#[mcp(state)]`

Most real tools need shared state (a store, an HTTP client, a job registry).
Mark those parameters `#[mcp(state)]`: they are excluded from the input schema
and instead become struct fields populated by a generated `new(...)`
constructor (state parameters, in declaration order). State types must be
`Clone` (typically an `Arc<...>`).

```rust
#[mcp_tool(description = "Add an amount to a shared counter")]
async fn add(
    #[mcp(state)]
    counter: std::sync::Arc<std::sync::atomic::AtomicI64>,
    #[mcp(description = "Amount to add")]
    amount: i64,
) -> Result<i64, anyhow::Error> {
    use std::sync::atomic::Ordering;
    Ok(counter.fetch_add(amount, Ordering::SeqCst) + amount)
}
// Generates `AddTool { counter: ... }` with `AddTool::new(counter)`.
// Register with: `.tool(AddTool::new(counter.clone()))`
```

See `crates/mcp-core/tests/mcp_tool_macro.rs` for the executable reference.

### Results: text, JSON, images, resources

```rust
ToolResult::text("done");
ToolResult::json(&my_serializable)?;           // pretty-printed JSON text
ToolResult::error("file not found");           // isError: true
ToolResult::json_error(&json!({"status": "error", "code": 7}))?;
ToolResult::with_content(vec![
    Content::text("rendered"),
    Content::image_bytes(&png_bytes, "image/png"), // base64-encodes for you
    Content::resource("file:///out/render.png", "image/png"), // sent as resource_link
]);
```

Tools can also advertise a display `title()` and `annotations()` (read-only,
destructive, idempotent, open-world hints) by overriding the default trait
methods, e.g. `fn annotations(&self) -> Option<ToolAnnotations> { Some(ToolAnnotations::read_only()) }`.

### Progress notifications

Inside `execute`, report progress for long operations. It is a no-op unless
the client sent a progress token and the transport can push notifications
(STDIO can; plain HTTP JSON responses cannot):

```rust
for (i, frame) in frames.iter().enumerate() {
    mcp_core::context::report_progress(i as f64, Some(frames.len() as f64), Some("rendering"));
    render(frame).await?;
}
```

The context is task-local: capture `mcp_core::context::current()` before moving
work onto a `tokio::spawn`ed task.

### Create a Server

```rust
use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use std::time::Duration;

#[derive(Parser)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs, // --mode, --port, --backend-url, --log-level
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level); // stderr only; RUST_LOG overrides

    let server = args
        .server
        .apply_to(MCPServer::builder("my-server", "1.0.0"))
        .tool(EchoTool)
        .instructions("Use `echo` to test connectivity.") // optional
        .tool_timeout(Duration::from_secs(300))           // optional
        .build();

    server.run().await?;
    Ok(())
}
```

Other builder options: `.host(IpAddr)` (HTTP bind address, default `0.0.0.0`),
`.tools_boxed(iter)` (register a `Vec<BoxedTool>`, e.g. from
`mcp_ai_consult::make_tools`), and `.into_handler()` on the built server to get
the protocol handler without a transport. HTTP modes shut down gracefully on
Ctrl-C/SIGTERM; `mcp_core::server::shutdown_signal()` is public for servers
that run their own axum routers.

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

# JSON-RPC over STDIO
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | cargo run -q --example echo_server -- --mode stdio
```

## Protocol behaviour

| Situation | Response |
|-----------|----------|
| Unparseable JSON | `-32700` Parse error (`id: null`); STDIO keeps reading |
| Not a request object, bad `jsonrpc`/`id`/`params`, empty batch | `-32600` Invalid Request |
| Unknown method | `-32601` Method not found |
| Bad `tools/call` params, unknown tool name | `-32602` Invalid params |
| Tool returns `Err`, panics, or exceeds `tool_timeout` | Result with `isError: true` |
| Notification / client response | No response (HTTP: `202 Accepted`) |
| Batch (array) | Array of responses; members processed concurrently |
| `ping` | `{}` |
| `resources/list`, `prompts/list` | Empty lists (capabilities not advertised) |

STDIO specifics: requests run concurrently (a slow tool does not block `ping`),
`notifications/cancelled` aborts the matching request and suppresses its
response, `\r\n` and blank lines are tolerated, invalid UTF-8 is a parse error,
and on EOF in-flight requests get up to 30 s to finish so their responses are
still written. Never write to stdout from a tool (`println!` corrupts the
protocol stream); logging goes to stderr.

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp`, `/messages`, `/mcp/rpc` | POST | MCP JSON-RPC (Streamable HTTP, JSON responses); `initialize` issues `Mcp-Session-Id` |
| `/mcp`, `/messages` | DELETE | Terminate the session in `Mcp-Session-Id` |
| `/mcp` | GET | `405` (no server-initiated SSE stream) |
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools (simple API) |
| `/mcp/execute` | POST | Execute a tool (simple API) |
| `/.well-known/mcp` | GET | MCP discovery |

Server (REST-only) mode instead serves `GET /health`, `GET /tools`,
`POST /tools/{name}/call` and `POST /execute`.

## CLI Arguments

All servers that flatten `MCPServerArgs` support:

```
--mode <MODE>         standalone, server, client, stdio [default: standalone]
--port <PORT>         Port to listen on [default: 8000]
--backend-url <URL>   Backend URL (required for client mode)
--log-level <LEVEL>   Log level [default: info]; RUST_LOG takes precedence
```

## Testing

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

The `mcp-testing` crate provides a `TestServer` that registers real tools and
calls them over the actual `Tool::execute` JSON boundary (with the production
panic boundary), or through the full protocol handler:

```rust
use mcp_testing::{TestServer, assertions};
use serde_json::json;

let server = TestServer::new().with_tool(MyTool { /* shared state */ });
let result = server.call_tool("my_tool", json!({ "field": "value" })).await.unwrap();
assertions::assert_success(&result);

// JSON-RPC level: error codes, isError mapping, tools/list output.
let resp = server.rpc("tools/call", json!({"name": "my_tool", "arguments": {}})).await;
assert_eq!(resp["result"]["isError"], true);
```

See `mcp_sprite_sheet`'s `execute_path_tests` for a worked example that drives
a multi-tool workflow over a shared store.

## Project Structure

```
tools/mcp/mcp_core_rust/
├── Cargo.toml              # Workspace definition
├── README.md               # This file
└── crates/
    ├── mcp-core/           # Core library
    │   ├── src/
    │   │   ├── lib.rs      # Public API
    │   │   ├── server.rs   # MCPServer builder, modes, logging, shutdown
    │   │   ├── tool.rs     # Tool trait, results, registry, panic boundary
    │   │   ├── args.rs     # Typed argument extraction
    │   │   ├── schema.rs   # schemars-based input schemas
    │   │   ├── context.rs  # Per-request context, progress notifications
    │   │   ├── error.rs    # Error types and JSON-RPC code mapping
    │   │   ├── session.rs  # Bounded session management
    │   │   ├── jsonrpc.rs  # JSON-RPC / MCP wire types, version negotiation
    │   │   ├── http.rs     # Shared reqwest client construction
    │   │   └── transport/  # handler (protocol), stdio, http, rest
    │   ├── tests/          # Macro and proxy-client integration tests
    │   └── examples/
    │       └── echo_server.rs
    ├── mcp-macros/         # #[mcp_tool] proc macro
    ├── mcp-client/         # REST client
    ├── mcp-testing/        # Test utilities
    └── mcp-ai-consult/     # Shared AI consultation tools
```

## Robustness: tool-execution panic boundary

Every transport runs tools through `ToolRegistry::call`, which wraps
`Tool::execute` in a `catch_unwind` boundary. If a tool panics (for example a
stray `.unwrap()` on a malformed argument) the panic is caught and returned as
an MCP tool error (`isError: true`) instead of unwinding the connection task or
crashing the server. This is a safety net, not a license to panic: prefer
`#[mcp_tool]`, `mcp_core::args`, or explicit `InvalidParameters` errors so
failures are typed rather than caught. Note that a panic while holding a
`std::sync::Mutex` poisons it; use `tokio::sync` locks or atomics for tool
state.

## Shared HTTP client

Servers that call an upstream HTTP service should build their `reqwest::Client`
via `mcp_core::http` instead of hand-rolling a builder. Both helpers apply a
shared connect timeout (`DEFAULT_CONNECT_TIMEOUT`, 10s) on top of the caller's
total request timeout, so a dead host fails fast:

```rust
use std::time::Duration;
use mcp_core::http;

// Infallible: never panics; falls back to a default client if the (rare)
// builder error occurs, so the server can still start. Use in `new() -> Self`.
let client = http::build_client_or_default(Duration::from_secs(30));

// Fallible: propagate the builder error where you have a `Result` to return.
let client = http::build_client(Duration::from_secs(30))?;
```

## Error conversions

`MCPError` converts from `serde_json::Error`, `std::io::Error` and
`anyhow::Error` (with its context chain), so `?` works on those directly inside
`execute`. Shorthands: `MCPError::invalid_params(msg)`, `MCPError::internal(msg)`
(usable as `.map_err(MCPError::internal)`), `MCPError::execution_failed(msg)`.

## Known limitations

- HTTP mode answers with JSON only (no SSE stream), so progress notifications
  are dropped over HTTP and `notifications/cancelled` cannot abort an HTTP
  request.
- `ToolResult` has no `structuredContent`/`outputSchema` support yet (adding a
  field would break servers that build `ToolResult { .. }` literally).
- HTTP mode does not validate the `Origin` header or require authentication;
  bind to `127.0.0.1` with `.host(...)` when the server is only used locally.

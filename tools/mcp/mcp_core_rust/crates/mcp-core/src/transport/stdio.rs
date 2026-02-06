//! STDIO transport for MCP servers.
//!
//! Implements the MCP STDIO transport protocol: newline-delimited JSON-RPC
//! over stdin (requests) and stdout (responses). All log output goes to stderr.
//!
//! This transport is used when MCP servers are spawned as child processes
//! (e.g., via `docker compose run --rm -T ... --mode stdio`).

use serde_json::json;
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tracing::{debug, error, info, warn};

use crate::error::JsonRpcErrorCode;
use crate::jsonrpc::{JsonRpcRequest, JsonRpcResponse};
use crate::transport::handler::MCPHandler;

/// STDIO transport for MCP server.
///
/// Reads newline-delimited JSON-RPC requests from stdin and writes
/// responses to stdout. Runs until stdin is closed (EOF).
pub struct StdioTransport;

impl StdioTransport {
    /// Run the STDIO transport loop with the given handler.
    ///
    /// This function blocks until stdin is closed. All tracing/log output
    /// goes to stderr (the default for `tracing_subscriber::fmt`), keeping
    /// stdout exclusively for JSON-RPC protocol messages.
    pub async fn run(handler: Arc<MCPHandler>) -> crate::error::Result<()> {
        let stdin = tokio::io::stdin();
        let mut stdout = tokio::io::stdout();
        let mut reader = BufReader::new(stdin);

        // Create an implicit session for this STDIO connection
        let session_id = Some(handler.sessions.create_session("stdio").await);

        info!(
            "{} v{} running in stdio mode",
            handler.name, handler.version
        );
        info!("Registered {} tools", handler.tools.len());
        for name in handler.tools.names() {
            info!("  - {}", name);
        }

        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line).await {
                Ok(0) => {
                    // EOF - stdin closed, clean shutdown
                    info!("Stdin closed, shutting down");
                    break;
                },
                Ok(_) => {
                    let trimmed = line.trim();
                    if trimmed.is_empty() {
                        continue;
                    }

                    debug!("Received: {}", trimmed);

                    // Parse JSON-RPC request
                    let response = match serde_json::from_str::<JsonRpcRequest>(trimmed) {
                        Ok(request) => handler.process_request(&request, &session_id).await,
                        Err(e) => {
                            warn!("Failed to parse JSON-RPC request: {}", e);
                            Some(JsonRpcResponse::error_with_code(
                                json!(null),
                                JsonRpcErrorCode::ParseError,
                                Some(e.to_string()),
                            ))
                        },
                    };

                    // Write response (if not a notification)
                    if let Some(resp) = response {
                        let json = match serde_json::to_string(&resp) {
                            Ok(j) => j,
                            Err(e) => {
                                error!("Failed to serialize response: {}", e);
                                continue;
                            },
                        };

                        debug!("Sending: {}", json);

                        if let Err(e) = stdout.write_all(json.as_bytes()).await {
                            error!("Failed to write to stdout: {}", e);
                            break;
                        }
                        if let Err(e) = stdout.write_all(b"\n").await {
                            error!("Failed to write newline to stdout: {}", e);
                            break;
                        }
                        if let Err(e) = stdout.flush().await {
                            error!("Failed to flush stdout: {}", e);
                            break;
                        }
                    }
                },
                Err(e) => {
                    error!("Error reading from stdin: {}", e);
                    break;
                },
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tool::{ToolRegistry, ToolResult};
    use async_trait::async_trait;
    use serde_json::Value;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};

    struct EchoTool;

    #[async_trait]
    impl crate::tool::Tool for EchoTool {
        fn name(&self) -> &str {
            "echo"
        }
        fn description(&self) -> &str {
            "Echo tool"
        }
        fn schema(&self) -> Value {
            json!({"type": "object", "properties": {"msg": {"type": "string"}}})
        }
        async fn execute(&self, args: Value) -> crate::error::Result<ToolResult> {
            let msg = args["msg"].as_str().unwrap_or("no msg");
            Ok(ToolResult::text(format!("echo: {msg}")))
        }
    }

    fn make_handler() -> Arc<MCPHandler> {
        let mut tools = ToolRegistry::new();
        tools.register(EchoTool);
        Arc::new(MCPHandler::new("test", "1.0.0", tools))
    }

    /// Helper: send a JSON-RPC request and read the response via in-memory pipes.
    async fn stdio_roundtrip(request: &str) -> String {
        let handler = make_handler();
        let session_id = Some(handler.sessions.create_session("test").await);

        // Parse and process directly (unit test for handler integration)
        let req: JsonRpcRequest = serde_json::from_str(request).unwrap();
        let resp = handler.process_request(&req, &session_id).await;
        serde_json::to_string(&resp.unwrap()).unwrap()
    }

    /// Integration test using tokio duplex channels to simulate stdin/stdout.
    async fn stdio_integration(requests: &[&str]) -> Vec<String> {
        let handler = make_handler();

        // Create duplex channels for stdin and stdout simulation
        let (stdin_write, stdin_read) = tokio::io::duplex(4096);
        let (stdout_write, mut stdout_read) = tokio::io::duplex(4096);

        let session_id = Some(handler.sessions.create_session("test").await);

        // Spawn the processing loop
        let handler_clone = Arc::clone(&handler);
        let session_clone = session_id.clone();
        let process_handle = tokio::spawn(async move {
            let mut reader = tokio::io::BufReader::new(stdin_read);
            let mut writer = stdout_write;
            let mut line = String::new();

            loop {
                line.clear();
                match reader.read_line(&mut line).await {
                    Ok(0) => break,
                    Ok(_) => {
                        let trimmed = line.trim();
                        if trimmed.is_empty() {
                            continue;
                        }
                        if let Ok(req) = serde_json::from_str::<JsonRpcRequest>(trimmed) {
                            if let Some(resp) =
                                handler_clone.process_request(&req, &session_clone).await
                            {
                                let json = serde_json::to_string(&resp).unwrap();
                                writer.write_all(json.as_bytes()).await.unwrap();
                                writer.write_all(b"\n").await.unwrap();
                                writer.flush().await.unwrap();
                            }
                        }
                    },
                    Err(_) => break,
                }
            }
        });

        // Write requests to stdin
        let mut stdin_writer = stdin_write;
        for req in requests {
            stdin_writer
                .write_all(format!("{}\n", req).as_bytes())
                .await
                .unwrap();
        }
        // Close stdin to signal EOF
        drop(stdin_writer);

        // Wait for processing to complete
        process_handle.await.unwrap();

        // Read all responses from stdout
        let mut output = String::new();
        stdout_read.read_to_string(&mut output).await.unwrap();

        output
            .lines()
            .filter(|l| !l.is_empty())
            .map(String::from)
            .collect()
    }

    #[tokio::test]
    async fn test_initialize_roundtrip() {
        let resp =
            stdio_roundtrip(r#"{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}"#).await;
        let parsed: JsonRpcResponse = serde_json::from_str(&resp).unwrap();
        assert!(parsed.result.is_some());
        assert_eq!(parsed.result.unwrap()["serverInfo"]["name"], "test");
    }

    #[tokio::test]
    async fn test_tools_list_roundtrip() {
        let resp =
            stdio_roundtrip(r#"{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}"#).await;
        let parsed: JsonRpcResponse = serde_json::from_str(&resp).unwrap();
        let tools = parsed.result.unwrap()["tools"].as_array().unwrap().clone();
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0]["name"], "echo");
    }

    #[tokio::test]
    async fn test_tool_call_roundtrip() {
        let resp = stdio_roundtrip(
            r#"{"jsonrpc":"2.0","method":"tools/call","params":{"name":"echo","arguments":{"msg":"hello"}},"id":3}"#,
        )
        .await;
        let parsed: JsonRpcResponse = serde_json::from_str(&resp).unwrap();
        let content = &parsed.result.unwrap()["content"];
        assert_eq!(content[0]["text"], "echo: hello");
    }

    #[tokio::test]
    async fn test_stdio_integration_flow() {
        let responses = stdio_integration(&[
            r#"{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}"#,
            r#"{"jsonrpc":"2.0","method":"initialized","params":{}}"#,
            r#"{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}"#,
            r#"{"jsonrpc":"2.0","method":"tools/call","params":{"name":"echo","arguments":{"msg":"test"}},"id":3}"#,
        ])
        .await;

        // initialized is a notification (no response), so we expect 3 responses
        assert_eq!(responses.len(), 3);

        // Verify initialize response
        let init: JsonRpcResponse = serde_json::from_str(&responses[0]).unwrap();
        assert!(init.result.is_some());

        // Verify tools/list response
        let list: JsonRpcResponse = serde_json::from_str(&responses[1]).unwrap();
        let tools = list.result.unwrap()["tools"].as_array().unwrap().clone();
        assert_eq!(tools.len(), 1);

        // Verify tools/call response
        let call: JsonRpcResponse = serde_json::from_str(&responses[2]).unwrap();
        assert_eq!(call.result.unwrap()["content"][0]["text"], "echo: test");
    }
}

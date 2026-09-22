//! STDIO transport for MCP servers.
//!
//! Implements the MCP STDIO transport: newline-delimited JSON-RPC over stdin
//! (client to server) and stdout (server to client). All log output goes to
//! stderr; **nothing else may write to stdout** (a stray `println!` in a tool
//! corrupts the protocol stream).
//!
//! This transport is used when MCP servers are spawned as child processes
//! (e.g., via `docker compose run --rm -T ... --mode stdio`).
//!
//! # Behaviour
//!
//! - Requests are handled **concurrently**: a slow `tools/call` does not block
//!   `ping` or other calls. Responses may therefore arrive out of order, which
//!   JSON-RPC permits (clients correlate by `id`).
//! - `notifications/cancelled` aborts the matching in-flight request; no
//!   response is sent for it, as the MCP spec requires.
//! - Tools can push `notifications/progress` via [`crate::context`].
//! - Malformed lines (invalid JSON or invalid UTF-8) get a `-32700` Parse
//!   error response and the loop keeps going; `\r\n` line endings and blank
//!   lines are tolerated.
//! - On EOF the transport stops reading, waits up to
//!   [`SHUTDOWN_GRACE_PERIOD`] for in-flight requests to finish (so their
//!   responses are still delivered), then returns.

use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, AsyncRead, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::sync::{mpsc, oneshot};
use tokio::task::{AbortHandle, JoinSet};
use tracing::{debug, error, info, warn};

use crate::context::Notifier;
use crate::jsonrpc::LATEST_PROTOCOL_VERSION;
use crate::transport::handler::MCPHandler;

/// How long to wait for in-flight requests after stdin closes before
/// aborting them.
pub const SHUTDOWN_GRACE_PERIOD: Duration = Duration::from_secs(30);

/// In-flight requests keyed by the JSON text of their id (so `1` and `"1"`
/// stay distinct). The sequence number guards against a finished task
/// removing the entry of a newer request that reused its id.
type InFlight = Arc<Mutex<HashMap<String, (u64, AbortHandle)>>>;

/// STDIO transport for MCP server.
///
/// Reads newline-delimited JSON-RPC messages from stdin and writes responses
/// to stdout. Runs until stdin is closed (EOF).
pub struct StdioTransport;

impl StdioTransport {
    /// Run the STDIO transport loop with the given handler.
    ///
    /// This function returns once stdin is closed and in-flight requests have
    /// drained. All tracing/log output goes to stderr (see
    /// [`init_logging`](crate::server::init_logging)), keeping stdout
    /// exclusively for JSON-RPC protocol messages.
    pub async fn run(handler: Arc<MCPHandler>) -> crate::error::Result<()> {
        info!(
            "{} v{} running in stdio mode",
            handler.name, handler.version
        );
        info!("Registered {} tools", handler.tools.len());
        for name in handler.tools.names() {
            debug!("  - {}", name);
        }
        Self::serve(handler, tokio::io::stdin(), tokio::io::stdout()).await
    }

    /// Run the transport over arbitrary byte streams.
    ///
    /// [`run`](Self::run) is `serve(handler, stdin, stdout)`. Use this to drive
    /// a server over pipes, sockets or in-memory duplex streams (tests).
    pub async fn serve<R, W>(
        handler: Arc<MCPHandler>,
        reader: R,
        writer: W,
    ) -> crate::error::Result<()>
    where
        R: AsyncRead + Unpin,
        W: AsyncWrite + Unpin + Send + 'static,
    {
        // One implicit session per STDIO connection; `initialize` fills in the
        // negotiated version and client info.
        let session_id: Arc<str> = handler
            .sessions
            .create_session(LATEST_PROTOCOL_VERSION)
            .await
            .into();

        let (tx, rx) = mpsc::unbounded_channel::<String>();
        let (stop_tx, stop_rx) = oneshot::channel::<()>();
        let writer_task = tokio::spawn(write_loop(writer, rx, stop_rx));

        let inflight: InFlight = Arc::default();
        let mut tasks: JoinSet<()> = JoinSet::new();
        let mut seq: u64 = 0;
        let mut reader = BufReader::new(reader);
        let mut buf = Vec::new();

        loop {
            buf.clear();
            match reader.read_until(b'\n', &mut buf).await {
                Ok(0) => {
                    info!("Stdin closed, shutting down");
                    break;
                },
                Ok(_) => {},
                Err(e) => {
                    error!("Error reading from stdin: {}", e);
                    break;
                },
            }
            // Reap finished tasks so the set does not grow without bound.
            while tasks.try_join_next().is_some() {}

            if tx.is_closed() {
                error!("Output stream closed, shutting down");
                break;
            }

            let line = buf.trim_ascii();
            if line.is_empty() {
                continue;
            }

            let message = match serde_json::from_slice::<Value>(line) {
                Ok(message) => message,
                Err(_) => {
                    // Let the handler produce the canonical parse-error reply.
                    if let Some(resp) = handler.handle_raw(line, Some(&session_id)).await {
                        let _ = tx.send(resp.to_string());
                    }
                    continue;
                },
            };

            if let Some(key) = cancelled_request_key(&message) {
                let entry = inflight
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .remove(&key);
                match entry {
                    Some((_, handle)) => {
                        handle.abort();
                        info!("Cancelled in-flight request {}", key);
                    },
                    None => debug!("Cancellation for unknown/finished request {}", key),
                }
                continue;
            }

            let request_key = request_key(&message);
            if request_key.is_none() && !message.is_array() {
                // Notifications, client responses and invalid messages are
                // cheap; handle them inline so ordering relative to later
                // requests is preserved (e.g. `notifications/initialized`).
                if let Some(resp) = handler
                    .handle_message_with(message, Some(&session_id), Some(&tx))
                    .await
                {
                    let _ = tx.send(resp.to_string());
                }
                continue;
            }

            seq += 1;
            let my_seq = seq;
            let task = {
                let handler = Arc::clone(&handler);
                let tx: Notifier = tx.clone();
                let session_id = Arc::clone(&session_id);
                let inflight = Arc::clone(&inflight);
                let key = request_key.clone();
                async move {
                    let resp = handler
                        .handle_message_with(message, Some(&session_id), Some(&tx))
                        .await;
                    if let Some(key) = key {
                        let mut map = inflight.lock().unwrap_or_else(PoisonError::into_inner);
                        if map.get(&key).is_some_and(|(s, _)| *s == my_seq) {
                            map.remove(&key);
                        }
                    }
                    if let Some(resp) = resp {
                        let _ = tx.send(resp.to_string());
                    }
                }
            };

            match request_key {
                Some(key) => {
                    // Hold the lock across spawn + insert so the task cannot
                    // finish (and try to deregister) before it is registered.
                    let mut map = inflight.lock().unwrap_or_else(PoisonError::into_inner);
                    let handle = tasks.spawn(task);
                    map.insert(key, (my_seq, handle));
                },
                None => {
                    tasks.spawn(task);
                },
            }
        }

        // Drain in-flight requests so their responses are still delivered.
        let drain = async { while tasks.join_next().await.is_some() {} };
        if tokio::time::timeout(SHUTDOWN_GRACE_PERIOD, drain)
            .await
            .is_err()
        {
            warn!(
                "{} request(s) still running after {:?}; aborting",
                tasks.len(),
                SHUTDOWN_GRACE_PERIOD
            );
            tasks.abort_all();
        }

        let _ = stop_tx.send(());
        match writer_task.await {
            Ok(Ok(())) => {},
            Ok(Err(e)) => error!("Failed to write to stdout: {}", e),
            Err(e) => error!("Stdout writer task failed: {}", e),
        }
        Ok(())
    }
}

/// Key for an in-flight request: `Some` for a single request object with a
/// string or numeric id.
fn request_key(message: &Value) -> Option<String> {
    let obj = message.as_object()?;
    if !obj.get("method")?.is_string() {
        return None;
    }
    match obj.get("id")? {
        id @ (Value::String(_) | Value::Number(_)) => Some(id.to_string()),
        _ => None,
    }
}

/// For a `notifications/cancelled` message, the key of the request to cancel.
fn cancelled_request_key(message: &Value) -> Option<String> {
    let obj = message.as_object()?;
    if obj.get("method")?.as_str()? != "notifications/cancelled" || obj.contains_key("id") {
        return None;
    }
    match obj.get("params")?.get("requestId")? {
        id @ (Value::String(_) | Value::Number(_)) => Some(id.to_string()),
        _ => None,
    }
}

/// Single writer for the output stream: one JSON message per line.
///
/// Runs until `stop` fires (then drains whatever is queued) or every sender is
/// dropped.
async fn write_loop<W>(
    mut writer: W,
    mut rx: mpsc::UnboundedReceiver<String>,
    mut stop: oneshot::Receiver<()>,
) -> std::io::Result<()>
where
    W: AsyncWrite + Unpin,
{
    loop {
        tokio::select! {
            biased;
            msg = rx.recv() => match msg {
                Some(msg) => write_line(&mut writer, msg).await?,
                None => break,
            },
            _ = &mut stop => {
                while let Ok(msg) = rx.try_recv() {
                    write_line(&mut writer, msg).await?;
                }
                break;
            },
        }
    }
    writer.flush().await
}

async fn write_line<W: AsyncWrite + Unpin>(writer: &mut W, mut msg: String) -> std::io::Result<()> {
    debug!("Sending: {}", msg);
    // Compact serde_json output never contains a raw newline, so one message
    // is exactly one line. Append the delimiter to write it in one call.
    msg.push('\n');
    writer.write_all(msg.as_bytes()).await?;
    writer.flush().await
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tool::{ToolRegistry, ToolResult};
    use async_trait::async_trait;
    use serde_json::json;
    use std::sync::atomic::{AtomicBool, Ordering};
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt};

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

    /// Sleeps for `ms` milliseconds; records whether it was dropped before
    /// finishing (i.e. cancelled).
    struct SleepTool {
        cancelled: Arc<AtomicBool>,
    }

    struct DropFlag(Arc<AtomicBool>, bool);
    impl Drop for DropFlag {
        fn drop(&mut self) {
            if !self.1 {
                self.0.store(true, Ordering::SeqCst);
            }
        }
    }

    #[async_trait]
    impl crate::tool::Tool for SleepTool {
        fn name(&self) -> &str {
            "sleep"
        }
        fn description(&self) -> &str {
            "Sleep"
        }
        fn schema(&self) -> Value {
            json!({"type": "object", "properties": {"ms": {"type": "integer"}}})
        }
        async fn execute(&self, args: Value) -> crate::error::Result<ToolResult> {
            let mut flag = DropFlag(Arc::clone(&self.cancelled), false);
            crate::context::report_progress(0.0, Some(1.0), Some("starting"));
            tokio::time::sleep(Duration::from_millis(args["ms"].as_u64().unwrap_or(0))).await;
            flag.1 = true;
            Ok(ToolResult::text("slept"))
        }
    }

    fn make_handler(cancelled: Arc<AtomicBool>) -> Arc<MCPHandler> {
        let mut tools = ToolRegistry::new();
        tools.register(EchoTool);
        tools.register(SleepTool { cancelled });
        Arc::new(MCPHandler::new("test", "1.0.0", tools))
    }

    /// Feed `input` to the transport, close stdin, and collect every output
    /// line as JSON.
    async fn run_to_completion(input: &[u8]) -> Vec<Value> {
        let handler = make_handler(Arc::default());
        let (mut client_in, server_in) = tokio::io::duplex(1 << 16);
        let (server_out, client_out) = tokio::io::duplex(1 << 16);
        let server = tokio::spawn(StdioTransport::serve(handler, server_in, server_out));
        client_in.write_all(input).await.unwrap();
        drop(client_in);
        server.await.unwrap().unwrap();
        let mut lines = tokio::io::BufReader::new(client_out).lines();
        let mut out = Vec::new();
        while let Some(line) = lines.next_line().await.unwrap() {
            out.push(serde_json::from_str(&line).unwrap());
        }
        out
    }

    fn by_id(responses: &[Value], id: i64) -> &Value {
        responses
            .iter()
            .find(|r| r["id"] == json!(id))
            .unwrap_or_else(|| panic!("no response with id {id} in {responses:?}"))
    }

    #[tokio::test]
    async fn test_stdio_integration_flow() {
        let responses = run_to_completion(
            concat!(
                r#"{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-06-18"},"id":1}"#,
                "\n",
                r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#,
                "\n",
                r#"{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}"#,
                "\n",
                r#"{"jsonrpc":"2.0","method":"tools/call","params":{"name":"echo","arguments":{"msg":"test"}},"id":3}"#,
                "\n",
            )
            .as_bytes(),
        )
        .await;

        // The notification gets no response.
        assert_eq!(responses.len(), 3, "{responses:?}");
        let init = by_id(&responses, 1);
        assert_eq!(init["result"]["serverInfo"]["name"], "test");
        assert_eq!(init["result"]["protocolVersion"], "2025-06-18");
        let tools = by_id(&responses, 2)["result"]["tools"].as_array().unwrap();
        assert_eq!(tools.len(), 2);
        assert_eq!(
            by_id(&responses, 3)["result"]["content"][0]["text"],
            "echo: test"
        );
    }

    #[tokio::test]
    async fn malformed_lines_do_not_stop_the_loop() {
        let mut input = Vec::new();
        input.extend_from_slice(b"{not json\n");
        input.extend_from_slice(b"\xff\xfe invalid utf8\n");
        input.extend_from_slice(b"\n   \r\n");
        input.extend_from_slice(b"{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"ping\"}\r\n");
        // Final line without a trailing newline is still processed.
        input.extend_from_slice(b"{\"jsonrpc\":\"2.0\",\"id\":8,\"method\":\"ping\"}");
        let responses = run_to_completion(&input).await;
        assert_eq!(responses.len(), 4, "{responses:?}");
        let parse_errors = responses
            .iter()
            .filter(|r| r["error"]["code"] == -32700 && r["id"].is_null())
            .count();
        assert_eq!(parse_errors, 2);
        assert_eq!(by_id(&responses, 7)["result"], json!({}));
        assert_eq!(by_id(&responses, 8)["result"], json!({}));
    }

    #[tokio::test]
    async fn batch_over_stdio() {
        let responses = run_to_completion(
            b"[{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\"},{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"ping\"}]\n",
        )
        .await;
        assert_eq!(responses.len(), 1);
        assert_eq!(responses[0].as_array().unwrap().len(), 2);
    }

    #[tokio::test]
    async fn eof_waits_for_in_flight_requests() {
        let responses = run_to_completion(
            b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"sleep\",\"arguments\":{\"ms\":50}}}\n",
        )
        .await;
        assert_eq!(
            by_id(&responses, 1)["result"]["content"][0]["text"],
            "slept"
        );
    }

    /// Drive the transport interactively: returns the stdin writer, a line
    /// reader over stdout and the server task.
    #[allow(clippy::type_complexity)]
    fn interactive(
        handler: Arc<MCPHandler>,
    ) -> (
        tokio::io::DuplexStream,
        tokio::io::Lines<tokio::io::BufReader<tokio::io::DuplexStream>>,
        tokio::task::JoinHandle<crate::error::Result<()>>,
    ) {
        let (client_in, server_in) = tokio::io::duplex(1 << 16);
        let (server_out, client_out) = tokio::io::duplex(1 << 16);
        let server = tokio::spawn(StdioTransport::serve(handler, server_in, server_out));
        (
            client_in,
            tokio::io::BufReader::new(client_out).lines(),
            server,
        )
    }

    async fn next_json(
        lines: &mut tokio::io::Lines<tokio::io::BufReader<tokio::io::DuplexStream>>,
    ) -> Value {
        let line = tokio::time::timeout(Duration::from_secs(5), lines.next_line())
            .await
            .expect("timed out waiting for output")
            .unwrap()
            .expect("stream ended");
        serde_json::from_str(&line).unwrap()
    }

    #[tokio::test]
    async fn slow_request_does_not_block_others() {
        let (mut stdin, mut stdout, server) = interactive(make_handler(Arc::default()));
        stdin
            .write_all(b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"sleep\",\"arguments\":{\"ms\":300}}}\n")
            .await
            .unwrap();
        stdin
            .write_all(b"{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"ping\"}\n")
            .await
            .unwrap();
        let first = next_json(&mut stdout).await;
        assert_eq!(first["id"], 2, "ping must not wait behind the slow call");
        let second = next_json(&mut stdout).await;
        assert_eq!(second["id"], 1);
        drop(stdin);
        server.await.unwrap().unwrap();
    }

    #[tokio::test]
    async fn cancellation_aborts_request_and_suppresses_response() {
        let cancelled = Arc::new(AtomicBool::new(false));
        let (mut stdin, mut stdout, server) = interactive(make_handler(Arc::clone(&cancelled)));
        stdin
            .write_all(b"{\"jsonrpc\":\"2.0\",\"id\":\"slow\",\"method\":\"tools/call\",\"params\":{\"name\":\"sleep\",\"arguments\":{\"ms\":10000}}}\n")
            .await
            .unwrap();
        // Give the task a moment to start before cancelling it.
        tokio::time::sleep(Duration::from_millis(50)).await;
        stdin
            .write_all(b"{\"jsonrpc\":\"2.0\",\"method\":\"notifications/cancelled\",\"params\":{\"requestId\":\"slow\",\"reason\":\"user\"}}\n")
            .await
            .unwrap();
        stdin
            .write_all(b"{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"ping\"}\n")
            .await
            .unwrap();
        let resp = next_json(&mut stdout).await;
        assert_eq!(resp["id"], 2);
        drop(stdin);
        // Must return promptly (not after the 10s sleep) and emit nothing else.
        tokio::time::timeout(Duration::from_secs(5), server)
            .await
            .expect("server should exit promptly")
            .unwrap()
            .unwrap();
        assert!(stdout.next_line().await.unwrap().is_none());
        assert!(cancelled.load(Ordering::SeqCst), "tool future was dropped");
    }

    #[tokio::test]
    async fn progress_notifications_reach_the_client() {
        let (mut stdin, mut stdout, server) = interactive(make_handler(Arc::default()));
        stdin
            .write_all(b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"sleep\",\"arguments\":{\"ms\":1},\"_meta\":{\"progressToken\":\"p1\"}}}\n")
            .await
            .unwrap();
        let progress = next_json(&mut stdout).await;
        assert_eq!(progress["method"], "notifications/progress");
        assert_eq!(progress["params"]["progressToken"], "p1");
        assert_eq!(progress["params"]["message"], "starting");
        let result = next_json(&mut stdout).await;
        assert_eq!(result["id"], 1);
        drop(stdin);
        server.await.unwrap().unwrap();
    }

    #[test]
    fn request_keys() {
        assert_eq!(
            request_key(&json!({"jsonrpc":"2.0","id":1,"method":"x"})),
            Some("1".into())
        );
        assert_eq!(
            request_key(&json!({"jsonrpc":"2.0","id":"1","method":"x"})),
            Some("\"1\"".into())
        );
        assert_eq!(request_key(&json!({"jsonrpc":"2.0","method":"x"})), None);
        assert_eq!(
            request_key(&json!({"jsonrpc":"2.0","id":1,"result":{}})),
            None
        );
        assert_eq!(
            cancelled_request_key(
                &json!({"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":3}})
            ),
            Some("3".into())
        );
        assert_eq!(
            cancelled_request_key(&json!({"jsonrpc":"2.0","method":"notifications/cancelled"})),
            None
        );
    }
}

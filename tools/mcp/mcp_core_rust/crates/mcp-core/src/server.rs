//! MCP Server implementation with multiple operational modes.

use clap::ValueEnum;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::sync::Arc;
use std::time::Duration;
use tokio::net::TcpListener;
use tracing::{debug, error, info, warn};

use crate::error::{MCPError, Result};
use crate::tool::{BoxedTool, Content, Tool, ToolRegistry, ToolResult};
use crate::transport::handler::MCPHandler;
use crate::transport::http::{HttpState, HttpTransport};
use crate::transport::rest::{RestState, RestTransport};
use crate::transport::stdio::StdioTransport;

/// Server operational mode
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, ValueEnum, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ServerMode {
    /// Full MCP server with embedded tools (default)
    #[default]
    Standalone,
    /// REST API only - no MCP protocol, just tool endpoints
    Server,
    /// MCP proxy - forwards tool calls to a REST backend
    Client,
    /// STDIO transport - JSON-RPC over stdin/stdout
    Stdio,
}

impl std::fmt::Display for ServerMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::Standalone => "standalone",
            Self::Server => "server",
            Self::Client => "client",
            Self::Stdio => "stdio",
        })
    }
}

/// Default bind address for the HTTP modes (all interfaces, for containers).
const DEFAULT_HOST: IpAddr = IpAddr::V4(Ipv4Addr::UNSPECIFIED);

/// Builder for constructing MCP servers
pub struct MCPServerBuilder {
    name: String,
    version: String,
    host: IpAddr,
    port: u16,
    mode: ServerMode,
    backend_url: Option<String>,
    tools: ToolRegistry,
    instructions: Option<String>,
    tool_timeout: Option<Duration>,
}

impl MCPServerBuilder {
    /// Create a new server builder
    pub fn new(name: impl Into<String>, version: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            version: version.into(),
            host: DEFAULT_HOST,
            port: 8000,
            mode: ServerMode::default(),
            backend_url: None,
            tools: ToolRegistry::new(),
            instructions: None,
            tool_timeout: None,
        }
    }

    /// Set the server port
    pub fn port(mut self, port: u16) -> Self {
        self.port = port;
        self
    }

    /// Set the address the HTTP modes bind to (default `0.0.0.0`). Use
    /// `127.0.0.1` for servers that should only be reachable locally.
    pub fn host(mut self, host: IpAddr) -> Self {
        self.host = host;
        self
    }

    /// Set the server mode
    pub fn mode(mut self, mode: ServerMode) -> Self {
        self.mode = mode;
        self
    }

    /// Set the backend URL for client mode
    pub fn backend_url(mut self, url: impl Into<String>) -> Self {
        self.backend_url = Some(url.into());
        self
    }

    /// Register a tool
    pub fn tool<T: Tool + 'static>(mut self, tool: T) -> Self {
        self.tools.register(tool);
        self
    }

    /// Register a boxed tool
    pub fn tool_boxed(mut self, tool: BoxedTool) -> Self {
        self.tools.register_boxed(tool);
        self
    }

    /// Register several boxed tools (e.g. the output of a `make_tools()`
    /// factory).
    pub fn tools_boxed(mut self, tools: impl IntoIterator<Item = BoxedTool>) -> Self {
        for tool in tools {
            self.tools.register_boxed(tool);
        }
        self
    }

    /// Usage hints returned to the client in the `initialize` result
    /// (`instructions`); clients may add them to the model's context.
    pub fn instructions(mut self, instructions: impl Into<String>) -> Self {
        self.instructions = Some(instructions.into());
        self
    }

    /// Bound every MCP `tools/call` by `timeout`; an overrunning tool is
    /// cancelled and reported as an `isError` result. Unbounded by default.
    pub fn tool_timeout(mut self, timeout: Duration) -> Self {
        self.tool_timeout = Some(timeout);
        self
    }

    /// Build the server
    pub fn build(self) -> MCPServer {
        MCPServer {
            name: self.name,
            version: self.version,
            host: self.host,
            port: self.port,
            mode: self.mode,
            backend_url: self.backend_url,
            tools: self.tools,
            instructions: self.instructions,
            tool_timeout: self.tool_timeout,
        }
    }
}

/// MCP Server with configurable operational modes
pub struct MCPServer {
    name: String,
    version: String,
    host: IpAddr,
    port: u16,
    mode: ServerMode,
    backend_url: Option<String>,
    tools: ToolRegistry,
    instructions: Option<String>,
    tool_timeout: Option<Duration>,
}

impl MCPServer {
    /// Create a new server builder
    pub fn builder(name: impl Into<String>, version: impl Into<String>) -> MCPServerBuilder {
        MCPServerBuilder::new(name, version)
    }

    /// Get the server name
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Get the server version
    pub fn version(&self) -> &str {
        &self.version
    }

    /// Get the bind address used by the HTTP modes
    pub fn host(&self) -> IpAddr {
        self.host
    }

    /// Get the server port
    pub fn port(&self) -> u16 {
        self.port
    }

    /// Get the server mode
    pub fn mode(&self) -> ServerMode {
        self.mode
    }

    /// Get the backend URL (for client mode)
    pub fn backend_url(&self) -> Option<&str> {
        self.backend_url.as_deref()
    }

    /// Get access to the tool registry
    pub fn tools(&self) -> &ToolRegistry {
        &self.tools
    }

    /// Convert into the protocol handler (tools, instructions and timeout
    /// applied) without starting a transport. Useful for driving the server
    /// in tests via [`MCPHandler::handle_message`].
    pub fn into_handler(self) -> MCPHandler {
        let mut handler = MCPHandler::new(self.name, self.version, self.tools);
        if let Some(instructions) = self.instructions {
            handler = handler.with_instructions(instructions);
        }
        if let Some(timeout) = self.tool_timeout {
            handler = handler.with_tool_timeout(timeout);
        }
        handler
    }

    /// Run the server
    pub async fn run(self) -> Result<()> {
        match self.mode {
            ServerMode::Standalone => self.run_standalone().await,
            ServerMode::Server => self.run_rest_only().await,
            ServerMode::Client => self.run_client().await,
            ServerMode::Stdio => self.run_stdio().await,
        }
    }

    fn addr(&self) -> SocketAddr {
        SocketAddr::new(self.host, self.port)
    }

    fn log_startup(&self) {
        info!(
            "{} v{} starting in {} mode on {}",
            self.name,
            self.version,
            self.mode,
            self.addr()
        );
    }

    fn log_tools(tools: &ToolRegistry, suffix: &str) {
        info!("Registered {} tools", tools.len());
        for name in tools.names() {
            info!("  - {}{}", name, suffix);
        }
    }

    /// Run in standalone mode (full MCP server with embedded tools)
    async fn run_standalone(self) -> Result<()> {
        self.log_startup();
        Self::log_tools(&self.tools, "");
        let addr = self.addr();
        let state = Arc::new(HttpState::from_handler(self.into_handler()));
        serve_http(addr, HttpTransport::router(state)).await
    }

    /// Run in server mode (REST API only, no MCP protocol)
    async fn run_rest_only(self) -> Result<()> {
        self.log_startup();
        info!("REST-only mode - MCP protocol disabled");
        Self::log_tools(&self.tools, "");
        info!("Endpoints: GET /health, GET /tools, POST /tools/{{name}}/call, POST /execute");
        let addr = self.addr();

        let state = Arc::new(RestState {
            name: self.name,
            version: self.version,
            tools: self.tools,
        });
        serve_http(addr, RestTransport::router(state)).await
    }

    /// Run in client mode (MCP proxy to backend)
    async fn run_client(mut self) -> Result<()> {
        let backend = self
            .backend_url
            .clone()
            .ok_or_else(|| MCPError::Internal("Client mode requires --backend-url".to_string()))?;

        self.log_startup();
        info!("Proxying to backend: {}", backend);

        let client = mcp_client::RestToolClient::new(backend.as_str());

        match client.health_check().await {
            Ok(true) => info!("Backend health check: OK"),
            Ok(false) => warn!("Backend health check failed, continuing anyway"),
            Err(e) => warn!("Backend health check error: {}, continuing anyway", e),
        }

        let backend_tools = client.list_tools().await.map_err(|e| {
            error!("Failed to fetch tools from backend: {}", e);
            MCPError::Internal(format!("Failed to fetch backend tools: {e}"))
        })?;
        info!("Fetched {} tools from backend", backend_tools.len());

        // Proxy tools replace any locally registered ones.
        let client = Arc::new(client);
        let mut tools = ToolRegistry::new();
        for tool_info in backend_tools {
            tools.register(ProxyToolWrapper {
                name: tool_info.name,
                description: tool_info.description,
                input_schema: tool_info.input_schema,
                client: Arc::clone(&client),
            });
        }
        Self::log_tools(&tools, " (proxied)");
        info!(
            "MCP protocol enabled, proxying {} tools to {}",
            tools.len(),
            backend
        );
        self.tools = tools;

        let addr = self.addr();
        let state = Arc::new(HttpState::from_handler(self.into_handler()));
        serve_http(addr, HttpTransport::router(state)).await
    }

    /// Run in STDIO mode (JSON-RPC over stdin/stdout)
    async fn run_stdio(self) -> Result<()> {
        StdioTransport::run(Arc::new(self.into_handler())).await
    }
}

/// Bind `addr` and serve `app` until [`shutdown_signal`] fires, letting
/// in-flight requests finish.
async fn serve_http(addr: SocketAddr, app: axum::Router) -> Result<()> {
    let listener = TcpListener::bind(addr).await.map_err(|e| {
        error!("Failed to bind to {}: {}", addr, e);
        MCPError::TransportError(format!("Failed to bind to {addr}: {e}"))
    })?;

    info!("Server ready, listening on http://{}", addr);

    axum::serve(listener, app.into_make_service())
        .with_graceful_shutdown(shutdown_signal())
        .await
        .map_err(|e| {
            error!("Server error: {}", e);
            MCPError::TransportError(e.to_string())
        })?;

    info!("Server stopped");
    Ok(())
}

/// Resolve when the process receives Ctrl-C (SIGINT) or, on Unix, SIGTERM
/// (what `docker stop` sends).
///
/// Used for graceful shutdown of the HTTP modes; also handy for servers that
/// run their own axum routers:
/// `axum::serve(listener, app).with_graceful_shutdown(mcp_core::server::shutdown_signal())`.
/// If a signal handler cannot be installed, that signal is simply never
/// observed (the future does not resolve early).
pub async fn shutdown_signal() {
    let ctrl_c = async {
        if tokio::signal::ctrl_c().await.is_err() {
            std::future::pending::<()>().await;
        }
    };

    #[cfg(unix)]
    let terminate = async {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut sig) => {
                sig.recv().await;
            },
            Err(_) => std::future::pending::<()>().await,
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        () = ctrl_c => info!("Received Ctrl-C, shutting down"),
        () = terminate => info!("Received SIGTERM, shutting down"),
    }
}

/// Wrapper that implements the Tool trait for proxied tools
struct ProxyToolWrapper {
    name: String,
    description: String,
    input_schema: Value,
    client: Arc<mcp_client::RestToolClient>,
}

/// Extract MCP content from a backend result of the shape
/// `{"content": [...], ...}` (what both the REST and simple HTTP APIs return).
fn backend_content(result: &Value) -> Option<Vec<Content>> {
    let items = result.get("content")?.as_array()?;
    Some(
        items
            .iter()
            .filter_map(|item| {
                serde_json::from_value::<Content>(item.clone())
                    .ok()
                    .or_else(|| item.get("text")?.as_str().map(Content::text))
            })
            .collect(),
    )
}

/// Convert a backend execution result into a local [`ToolResult`].
fn proxy_result(result: mcp_client::ToolExecutionResult) -> ToolResult {
    let content = result.result.as_ref().and_then(backend_content);
    if result.success {
        let content = match (content, result.result) {
            (Some(content), _) => content,
            (None, Some(res)) => vec![Content::text(
                serde_json::to_string_pretty(&res).unwrap_or_else(|_| res.to_string()),
            )],
            (None, None) => vec![Content::text("OK")],
        };
        ToolResult::with_content(content)
    } else {
        // Prefer the tool's own error content (an `isError` result) over the
        // generic envelope error.
        let content = match content {
            Some(content) if !content.is_empty() => content,
            _ => vec![Content::text(
                result.error.unwrap_or_else(|| "Unknown error".to_string()),
            )],
        };
        ToolResult {
            content,
            is_error: true,
        }
    }
}

#[async_trait::async_trait]
impl Tool for ProxyToolWrapper {
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn schema(&self) -> Value {
        self.input_schema.clone()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        debug!(
            "Proxying tool call: {} to {}",
            self.name,
            self.client.base_url()
        );

        self.client
            .execute_tool(&self.name, args)
            .await
            .map(proxy_result)
            .map_err(|e| MCPError::Internal(format!("Proxy error: {e}")))
    }
}

/// CLI arguments for MCP servers (can be embedded in server CLIs)
#[derive(Debug, Clone, clap::Parser)]
pub struct MCPServerArgs {
    /// Server operational mode
    #[arg(long, short, default_value = "standalone")]
    pub mode: ServerMode,

    /// Port to listen on (ignored in stdio mode)
    #[arg(long, short, default_value = "8000")]
    pub port: u16,

    /// Backend URL for client mode
    #[arg(long, required_if_eq("mode", "client"))]
    pub backend_url: Option<String>,

    /// Log level
    #[arg(long, default_value = "info")]
    pub log_level: String,
}

impl MCPServerArgs {
    /// Apply these arguments to a server builder
    pub fn apply_to(&self, mut builder: MCPServerBuilder) -> MCPServerBuilder {
        builder = builder.port(self.port).mode(self.mode);

        if let Some(url) = &self.backend_url {
            builder = builder.backend_url(url.clone());
        }

        builder
    }
}

/// Initialize logging for MCP servers.
///
/// All output goes to stderr (in STDIO mode stdout is the protocol channel).
/// `RUST_LOG`, when set, overrides `level`. ANSI colours are only used when
/// stderr is a terminal, so log files and client log panes stay clean.
///
/// Safe to call more than once: if a global subscriber is already installed
/// (e.g. by a test harness), the call is a no-op instead of panicking.
pub fn init_logging(level: &str) {
    use std::io::IsTerminal;
    use tracing_subscriber::{EnvFilter, fmt, prelude::*};

    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(level));

    let _ = tracing_subscriber::registry()
        .with(
            fmt::layer()
                .with_writer(std::io::stderr)
                .with_ansi(std::io::stderr().is_terminal()),
        )
        .with(filter)
        .try_init();
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;
    use serde_json::json;

    struct PingTool;

    #[async_trait::async_trait]
    impl Tool for PingTool {
        fn name(&self) -> &str {
            "ping"
        }
        fn description(&self) -> &str {
            "Return pong"
        }
        fn schema(&self) -> Value {
            json!({"type": "object", "properties": {}})
        }
        async fn execute(&self, _args: Value) -> crate::error::Result<ToolResult> {
            Ok(ToolResult::text("pong"))
        }
    }

    #[test]
    fn test_server_builder() {
        let server = MCPServer::builder("test", "1.0.0")
            .port(8080)
            .mode(ServerMode::Standalone)
            .tool(PingTool)
            .build();

        assert_eq!(server.name(), "test");
        assert_eq!(server.version(), "1.0.0");
        assert_eq!(server.port(), 8080);
        assert_eq!(server.mode(), ServerMode::Standalone);
        assert_eq!(server.tools().len(), 1);
        assert_eq!(server.host(), DEFAULT_HOST);
    }

    #[test]
    fn test_server_mode_display() {
        assert_eq!(ServerMode::Standalone.to_string(), "standalone");
        assert_eq!(ServerMode::Server.to_string(), "server");
        assert_eq!(ServerMode::Client.to_string(), "client");
        assert_eq!(ServerMode::Stdio.to_string(), "stdio");
    }

    #[test]
    fn test_stdio_mode() {
        let server = MCPServer::builder("test", "1.0.0")
            .mode(ServerMode::Stdio)
            .tool(PingTool)
            .build();

        assert_eq!(server.mode(), ServerMode::Stdio);
    }

    #[test]
    fn test_client_mode_requires_backend() {
        let server = MCPServer::builder("test", "1.0.0")
            .mode(ServerMode::Client)
            .build();

        assert!(server.backend_url().is_none());
    }

    #[tokio::test]
    async fn client_mode_without_backend_errors() {
        let err = MCPServer::builder("test", "1.0.0")
            .mode(ServerMode::Client)
            .build()
            .run()
            .await
            .unwrap_err();
        assert!(err.to_string().contains("backend-url"));
    }

    #[test]
    fn test_client_mode_with_backend() {
        let server = MCPServer::builder("test", "1.0.0")
            .mode(ServerMode::Client)
            .backend_url("http://localhost:8080")
            .build();

        assert_eq!(server.backend_url(), Some("http://localhost:8080"));
    }

    #[tokio::test]
    async fn into_handler_applies_builder_settings() {
        let handler = MCPServer::builder("test", "1.0.0")
            .tool(PingTool)
            .instructions("be nice")
            .tool_timeout(Duration::from_secs(5))
            .build()
            .into_handler();
        assert_eq!(handler.instructions(), Some("be nice"));
        assert_eq!(handler.tool_timeout(), Some(Duration::from_secs(5)));
        let resp = handler
            .handle_message(
                json!({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping"}}),
                None,
            )
            .await
            .unwrap();
        assert_eq!(resp["result"]["content"][0]["text"], "pong");
    }

    #[test]
    fn args_parse_and_apply() {
        let args =
            MCPServerArgs::try_parse_from(["srv", "--mode", "stdio", "--port", "9000"]).unwrap();
        let server = args.apply_to(MCPServer::builder("s", "1")).build();
        assert_eq!(server.mode(), ServerMode::Stdio);
        assert_eq!(server.port(), 9000);
        assert!(MCPServerArgs::try_parse_from(["srv", "--mode", "client"]).is_err());
    }

    #[test]
    fn init_logging_is_idempotent() {
        // "off" keeps the (process-global) subscriber from spamming other
        // tests' output; the second call must be a silent no-op.
        init_logging("off");
        init_logging("info");
    }

    fn exec(
        success: bool,
        result: Option<Value>,
        error: Option<&str>,
    ) -> mcp_client::ToolExecutionResult {
        mcp_client::ToolExecutionResult {
            success,
            result,
            error: error.map(String::from),
        }
    }

    #[test]
    fn proxy_result_conversion() {
        // Typed content from the backend is preserved (including images).
        let r = proxy_result(exec(
            true,
            Some(json!({"content": [
                {"type": "text", "text": "hi"},
                {"type": "image", "data": "AAA=", "mimeType": "image/png"}
            ]})),
            None,
        ));
        assert!(!r.is_error);
        assert_eq!(r.content[0], Content::text("hi"));
        assert_eq!(r.content[1], Content::image("AAA=", "image/png"));

        // A backend `isError` result keeps its own error text.
        let r = proxy_result(exec(
            false,
            Some(json!({"content": [{"type": "text", "text": "bad input"}], "is_error": true})),
            None,
        ));
        assert!(r.is_error);
        assert_eq!(r.first_text(), Some("bad input"));

        // Envelope error without content.
        let r = proxy_result(exec(false, None, Some("backend down")));
        assert!(r.is_error);
        assert_eq!(r.first_text(), Some("backend down"));

        // Non-MCP JSON is pretty-printed; no result at all is "OK".
        let r = proxy_result(exec(true, Some(json!({"x": 1})), None));
        assert!(r.first_text().unwrap().contains("\"x\": 1"));
        assert_eq!(
            proxy_result(exec(true, None, None)).first_text(),
            Some("OK")
        );
    }
}

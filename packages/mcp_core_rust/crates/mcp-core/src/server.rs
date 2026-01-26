//! MCP Server implementation with multiple operational modes.

use clap::ValueEnum;
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::TcpListener;
use tracing::{error, info};

use crate::error::Result;
use crate::session::SessionManager;
use crate::tool::{BoxedTool, Tool, ToolRegistry};
use crate::transport::http::{HttpState, HttpTransport};

/// Server operational mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ServerMode {
    /// Full MCP server with embedded tools (default)
    Standalone,
    /// REST API only - no MCP protocol, just tool endpoints
    Server,
    /// MCP proxy - forwards tool calls to a REST backend
    Client,
}

impl Default for ServerMode {
    fn default() -> Self {
        Self::Standalone
    }
}

impl std::fmt::Display for ServerMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Standalone => write!(f, "standalone"),
            Self::Server => write!(f, "server"),
            Self::Client => write!(f, "client"),
        }
    }
}

/// Builder for constructing MCP servers
pub struct MCPServerBuilder {
    name: String,
    version: String,
    port: u16,
    mode: ServerMode,
    backend_url: Option<String>,
    tools: ToolRegistry,
}

impl MCPServerBuilder {
    /// Create a new server builder
    pub fn new(name: impl Into<String>, version: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            version: version.into(),
            port: 8000,
            mode: ServerMode::default(),
            backend_url: None,
            tools: ToolRegistry::new(),
        }
    }

    /// Set the server port
    pub fn port(mut self, port: u16) -> Self {
        self.port = port;
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

    /// Build the server
    pub fn build(self) -> MCPServer {
        MCPServer {
            name: self.name,
            version: self.version,
            port: self.port,
            mode: self.mode,
            backend_url: self.backend_url,
            tools: self.tools,
        }
    }
}

/// MCP Server with configurable operational modes
pub struct MCPServer {
    name: String,
    version: String,
    port: u16,
    mode: ServerMode,
    backend_url: Option<String>,
    tools: ToolRegistry,
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

    /// Run the server
    pub async fn run(self) -> Result<()> {
        match self.mode {
            ServerMode::Standalone | ServerMode::Server => self.run_http().await,
            ServerMode::Client => self.run_client().await,
        }
    }

    /// Run in HTTP mode (standalone or server)
    async fn run_http(self) -> Result<()> {
        let addr = SocketAddr::from(([0, 0, 0, 0], self.port));

        info!(
            "{} v{} starting in {} mode on {}",
            self.name, self.version, self.mode, addr
        );
        info!("Registered {} tools", self.tools.len());

        for name in self.tools.names() {
            info!("  - {}", name);
        }

        let state = Arc::new(HttpState {
            name: self.name,
            version: self.version,
            tools: self.tools,
            sessions: SessionManager::new(),
        });

        let app = HttpTransport::router(state);

        let listener = TcpListener::bind(addr).await.map_err(|e| {
            error!("Failed to bind to {}: {}", addr, e);
            crate::error::MCPError::TransportError(e.to_string())
        })?;

        info!("Server ready, listening on http://{}", addr);

        axum::serve(listener, app.into_make_service())
            .await
            .map_err(|e: std::io::Error| {
                error!("Server error: {}", e);
                crate::error::MCPError::TransportError(e.to_string())
            })?;

        Ok(())
    }

    /// Run in client mode (proxy to backend)
    async fn run_client(self) -> Result<()> {
        let backend = self.backend_url.as_deref().ok_or_else(|| {
            crate::error::MCPError::Internal("Client mode requires --backend-url".to_string())
        })?;

        info!(
            "{} v{} starting in client mode, proxying to {}",
            self.name, self.version, backend
        );

        // TODO: Implement client mode with mcp-client crate
        // For now, this is a placeholder
        error!("Client mode not yet implemented");
        Err(crate::error::MCPError::Internal(
            "Client mode not yet implemented".to_string(),
        ))
    }
}

/// CLI arguments for MCP servers (can be embedded in server CLIs)
#[derive(Debug, Clone, clap::Parser)]
pub struct MCPServerArgs {
    /// Server operational mode
    #[arg(long, short, default_value = "standalone")]
    pub mode: ServerMode,

    /// Port to listen on
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
    pub fn apply_to<'a>(&self, mut builder: MCPServerBuilder) -> MCPServerBuilder {
        builder = builder.port(self.port).mode(self.mode);

        if let Some(url) = &self.backend_url {
            builder = builder.backend_url(url.clone());
        }

        builder
    }
}

/// Initialize logging for MCP servers
pub fn init_logging(level: &str) {
    use tracing_subscriber::{fmt, prelude::*, EnvFilter};

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(level));

    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(filter)
        .init();
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tool::ToolResult;
    use async_trait::async_trait;
    use serde_json::{json, Value};

    struct PingTool;

    #[async_trait]
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
    }

    #[test]
    fn test_server_mode_display() {
        assert_eq!(ServerMode::Standalone.to_string(), "standalone");
        assert_eq!(ServerMode::Server.to_string(), "server");
        assert_eq!(ServerMode::Client.to_string(), "client");
    }
}

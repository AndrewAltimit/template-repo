//! MCP tool registry for browsing and invoking tools from configured servers.
//!
//! Configuration is loaded from `mcp.toml` in the VFS.

use std::fmt;

use serde::Deserialize;

use crate::error::{OasisError, Result};

/// Transport used to communicate with an MCP server.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum McpTransport {
    /// Standard I/O (local process).
    Stdio,
    /// HTTP/SSE (remote or local).
    Http,
}

impl fmt::Display for McpTransport {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Stdio => write!(f, "stdio"),
            Self::Http => write!(f, "http"),
        }
    }
}

/// A configured MCP server.
#[derive(Debug, Clone, Deserialize)]
pub struct McpServerEntry {
    /// Server name (e.g., "code-quality", "gemini").
    pub name: String,
    /// Transport type.
    pub transport: McpTransport,
    /// Address (path for stdio, URL for HTTP).
    #[serde(default)]
    pub address: String,
    /// Available tools on this server.
    #[serde(default)]
    pub tools: Vec<McpToolEntry>,
}

/// A single MCP tool exposed by a server.
#[derive(Debug, Clone, Deserialize)]
pub struct McpToolEntry {
    /// Tool name (e.g., "lint", "run_tests", "security_scan").
    pub name: String,
    /// One-line description of what the tool does.
    #[serde(default)]
    pub description: String,
}

/// TOML wrapper for `[[server]]` array.
#[derive(Debug, Deserialize)]
struct McpConfig {
    #[serde(default)]
    server: Vec<McpServerEntry>,
}

/// Registry of MCP servers and their tools.
#[derive(Debug, Clone)]
pub struct McpRegistry {
    servers: Vec<McpServerEntry>,
}

impl McpRegistry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self {
            servers: Vec::new(),
        }
    }

    /// Load from a TOML string (contents of `mcp.toml`).
    pub fn from_toml(toml_str: &str) -> Result<Self> {
        let config: McpConfig =
            toml::from_str(toml_str).map_err(|e| OasisError::Config(format!("mcp.toml: {e}")))?;
        Ok(Self {
            servers: config.server,
        })
    }

    /// Return all configured servers.
    pub fn servers(&self) -> &[McpServerEntry] {
        &self.servers
    }

    /// Find a server by name.
    pub fn find_server(&self, name: &str) -> Option<&McpServerEntry> {
        self.servers.iter().find(|s| s.name == name)
    }

    /// Find a tool by server name and tool name.
    pub fn find_tool(&self, server_name: &str, tool_name: &str) -> Option<&McpToolEntry> {
        self.find_server(server_name)
            .and_then(|s| s.tools.iter().find(|t| t.name == tool_name))
    }

    /// List all tools across all servers as `(server_name, tool)` pairs.
    pub fn all_tools(&self) -> Vec<(&str, &McpToolEntry)> {
        let mut out = Vec::new();
        for server in &self.servers {
            for tool in &server.tools {
                out.push((server.name.as_str(), tool));
            }
        }
        out
    }

    /// Return the total number of servers.
    pub fn server_count(&self) -> usize {
        self.servers.len()
    }

    /// Return the total number of tools across all servers.
    pub fn tool_count(&self) -> usize {
        self.servers.iter().map(|s| s.tools.len()).sum()
    }
}

impl Default for McpRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MCP_TOML: &str = r#"
[[server]]
name = "code-quality"
transport = "stdio"
address = "/usr/local/bin/mcp-code-quality"
tools = [
    { name = "lint", description = "Run code linting" },
    { name = "run_tests", description = "Run pytest tests" },
    { name = "security_scan", description = "Run bandit security scan" },
]

[[server]]
name = "gemini"
transport = "stdio"
address = "/usr/local/bin/mcp-gemini"
tools = [
    { name = "consult_gemini", description = "Consult Gemini AI" },
]

[[server]]
name = "ai-toolkit"
transport = "http"
address = "http://192.168.0.222:8007"
tools = [
    { name = "train_lora", description = "Train LoRA model" },
    { name = "generate_image", description = "Generate image" },
]
"#;

    #[test]
    fn parse_mcp_toml() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        assert_eq!(reg.server_count(), 3);
        assert_eq!(reg.tool_count(), 6);
    }

    #[test]
    fn find_server() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        let server = reg.find_server("code-quality").unwrap();
        assert_eq!(server.transport, McpTransport::Stdio);
        assert_eq!(server.tools.len(), 3);
    }

    #[test]
    fn find_server_missing() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        assert!(reg.find_server("nonexistent").is_none());
    }

    #[test]
    fn find_tool() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        let tool = reg.find_tool("code-quality", "lint").unwrap();
        assert_eq!(tool.description, "Run code linting");
    }

    #[test]
    fn find_tool_missing_server() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        assert!(reg.find_tool("nonexistent", "lint").is_none());
    }

    #[test]
    fn find_tool_missing_tool() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        assert!(reg.find_tool("code-quality", "nonexistent").is_none());
    }

    #[test]
    fn all_tools() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        let tools = reg.all_tools();
        assert_eq!(tools.len(), 6);
        assert_eq!(tools[0].0, "code-quality");
        assert_eq!(tools[0].1.name, "lint");
    }

    #[test]
    fn http_transport() {
        let reg = McpRegistry::from_toml(MCP_TOML).unwrap();
        let server = reg.find_server("ai-toolkit").unwrap();
        assert_eq!(server.transport, McpTransport::Http);
        assert!(server.address.contains("192.168.0.222"));
    }

    #[test]
    fn empty_registry() {
        let reg = McpRegistry::new();
        assert_eq!(reg.server_count(), 0);
        assert_eq!(reg.tool_count(), 0);
    }

    #[test]
    fn empty_toml() {
        let reg = McpRegistry::from_toml("").unwrap();
        assert_eq!(reg.server_count(), 0);
    }

    #[test]
    fn display_transport() {
        assert_eq!(McpTransport::Stdio.to_string(), "stdio");
        assert_eq!(McpTransport::Http.to_string(), "http");
    }
}

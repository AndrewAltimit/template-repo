//! MCP server implementation for Codex integration.

use mcp_ai_consult::make_tools;
use mcp_core::prelude::*;
use serde_json::json;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::codex::CodexIntegration;
use crate::types::CodexConfig;

/// Codex MCP server
pub struct CodexServer {
    integration: Arc<RwLock<CodexIntegration>>,
}

impl CodexServer {
    /// Create a new Codex server
    pub fn new(config: CodexConfig) -> Self {
        Self {
            integration: Arc::new(RwLock::new(CodexIntegration::new(config))),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        make_tools(
            self.integration.clone(),
            "codex",
            "Consult Codex AI for code generation, completion, or refactoring",
            Some(json!({
                "mode": {
                    "type": "string",
                    "description": "Consultation mode",
                    "enum": ["generate", "complete", "refactor", "explain", "quick"],
                    "default": "quick"
                }
            })),
        )
    }
}

impl Default for CodexServer {
    fn default() -> Self {
        Self::new(CodexConfig::from_env())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = CodexServer::default();
        let tools = server.tools();
        assert_eq!(tools.len(), 4);
    }

    #[test]
    fn test_tool_names() {
        let server = CodexServer::default();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"consult_codex"));
        assert!(names.contains(&"clear_codex_history"));
        assert!(names.contains(&"codex_status"));
        assert!(names.contains(&"toggle_codex_auto_consult"));
    }
}

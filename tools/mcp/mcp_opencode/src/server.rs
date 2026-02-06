//! MCP server implementation for OpenCode integration.

use mcp_ai_consult::make_tools;
use mcp_core::prelude::*;
use serde_json::json;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::opencode::OpenCodeIntegration;
use crate::types::OpenCodeConfig;

/// OpenCode MCP server
pub struct OpenCodeServer {
    integration: Arc<RwLock<OpenCodeIntegration>>,
}

impl OpenCodeServer {
    /// Create a new OpenCode server
    pub fn new(config: OpenCodeConfig) -> Self {
        Self {
            integration: Arc::new(RwLock::new(OpenCodeIntegration::new(config))),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        make_tools(
            self.integration.clone(),
            "opencode",
            "Consult OpenCode AI for code generation, refactoring, or review",
            Some(json!({
                "mode": {
                    "type": "string",
                    "description": "Consultation mode",
                    "enum": ["generate", "refactor", "review", "explain", "quick"],
                    "default": "quick"
                }
            })),
        )
    }
}

impl Default for OpenCodeServer {
    fn default() -> Self {
        Self::new(OpenCodeConfig::from_env())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = OpenCodeServer::default();
        let tools = server.tools();
        assert_eq!(tools.len(), 4);
    }

    #[test]
    fn test_tool_names() {
        let server = OpenCodeServer::default();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"consult_opencode"));
        assert!(names.contains(&"clear_opencode_history"));
        assert!(names.contains(&"opencode_status"));
        assert!(names.contains(&"toggle_opencode_auto_consult"));
    }
}

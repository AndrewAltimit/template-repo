//! MCP server implementation for Gemini integration.

use mcp_ai_consult::make_tools;
use mcp_core::prelude::*;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::gemini::GeminiIntegration;
use crate::types::GeminiConfig;

/// Gemini MCP server
pub struct GeminiServer {
    integration: Arc<RwLock<GeminiIntegration>>,
}

impl GeminiServer {
    /// Create a new Gemini server
    pub fn new(config: GeminiConfig) -> Self {
        Self {
            integration: Arc::new(RwLock::new(GeminiIntegration::new(config))),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        make_tools(
            self.integration.clone(),
            "gemini",
            "Consult Gemini AI for a second opinion or validation",
            None,
        )
    }
}

impl Default for GeminiServer {
    fn default() -> Self {
        Self::new(GeminiConfig::from_env())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = GeminiServer::default();
        let tools = server.tools();
        assert_eq!(tools.len(), 4);
    }

    #[test]
    fn test_tool_names() {
        let server = GeminiServer::default();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"consult_gemini"));
        assert!(names.contains(&"clear_gemini_history"));
        assert!(names.contains(&"gemini_status"));
        assert!(names.contains(&"toggle_gemini_auto_consult"));
    }
}

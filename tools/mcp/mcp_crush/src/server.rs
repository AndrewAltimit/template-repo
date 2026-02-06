//! MCP server implementation for Crush integration.

use mcp_ai_consult::make_tools;
use mcp_core::prelude::*;
use serde_json::json;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::crush::CrushIntegration;
use crate::types::CrushConfig;

/// Crush MCP server
pub struct CrushServer {
    integration: Arc<RwLock<CrushIntegration>>,
}

impl CrushServer {
    /// Create a new Crush server
    pub fn new(config: CrushConfig) -> Self {
        Self {
            integration: Arc::new(RwLock::new(CrushIntegration::new(config))),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        make_tools(
            self.integration.clone(),
            "crush",
            "Consult Crush AI for quick code generation, explanation, or conversion",
            Some(json!({
                "mode": {
                    "type": "string",
                    "description": "Consultation mode",
                    "enum": ["generate", "explain", "convert", "quick"],
                    "default": "quick"
                }
            })),
        )
    }
}

impl Default for CrushServer {
    fn default() -> Self {
        Self::new(CrushConfig::from_env())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = CrushServer::default();
        let tools = server.tools();
        assert_eq!(tools.len(), 4);
    }

    #[test]
    fn test_tool_names() {
        let server = CrushServer::default();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"consult_crush"));
        assert!(names.contains(&"clear_crush_history"));
        assert!(names.contains(&"crush_status"));
        assert!(names.contains(&"toggle_crush_auto_consult"));
    }
}

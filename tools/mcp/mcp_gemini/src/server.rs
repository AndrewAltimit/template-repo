//! MCP server implementation for Gemini integration.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::gemini::GeminiIntegration;
use crate::types::{ConsultStatus, GeminiConfig};

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
        vec![
            Arc::new(ConsultGeminiTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ClearGeminiHistoryTool {
                integration: self.integration.clone(),
            }),
            Arc::new(GeminiStatusTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ToggleGeminiAutoConsultTool {
                integration: self.integration.clone(),
            }),
        ]
    }
}

impl Default for GeminiServer {
    fn default() -> Self {
        Self::new(GeminiConfig::from_env())
    }
}

// ============================================================================
// Tool: consult_gemini
// ============================================================================

struct ConsultGeminiTool {
    integration: Arc<RwLock<GeminiIntegration>>,
}

#[async_trait]
impl Tool for ConsultGeminiTool {
    fn name(&self) -> &str {
        "consult_gemini"
    }

    fn description(&self) -> &str {
        "Consult Gemini AI for a second opinion or validation"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The question or code to consult Gemini about"
                },
                "context": {
                    "type": "string",
                    "description": "Additional context for the consultation",
                    "default": ""
                },
                "comparison_mode": {
                    "type": "boolean",
                    "default": true,
                    "description": "Compare with previous Claude response"
                },
                "force": {
                    "type": "boolean",
                    "default": false,
                    "description": "Force consultation even if disabled"
                }
            },
            "required": ["query"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let query = args
            .get("query")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'query' parameter".to_string()))?;

        let context = args.get("context").and_then(|v| v.as_str()).unwrap_or("");

        let comparison_mode = args
            .get("comparison_mode")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let force = args.get("force").and_then(|v| v.as_bool()).unwrap_or(false);

        let mut integration = self.integration.write().await;

        // Check if enabled
        if !integration.config().enabled && !force {
            let response = json!({
                "status": "disabled",
                "message": "Gemini consultation is disabled. Use 'force=true' to override."
            });
            return ToolResult::json(&response);
        }

        info!(
            "Gemini consultation: query_length={}, comparison_mode={}",
            query.len(),
            comparison_mode
        );

        let result = integration.consult(query, context, comparison_mode, force).await;

        let response = match result.status {
            ConsultStatus::Success => {
                json!({
                    "status": "success",
                    "response": result.response,
                    "execution_time": result.execution_time,
                    "consultation_id": result.consultation_id,
                    "timestamp": result.timestamp.to_rfc3339()
                })
            }
            ConsultStatus::Error => {
                json!({
                    "status": "error",
                    "error": result.error,
                    "consultation_id": result.consultation_id
                })
            }
            ConsultStatus::Disabled => {
                json!({
                    "status": "disabled",
                    "message": "Gemini integration is disabled"
                })
            }
            ConsultStatus::Timeout => {
                json!({
                    "status": "timeout",
                    "error": result.error,
                    "consultation_id": result.consultation_id
                })
            }
        };

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: clear_gemini_history
// ============================================================================

struct ClearGeminiHistoryTool {
    integration: Arc<RwLock<GeminiIntegration>>,
}

#[async_trait]
impl Tool for ClearGeminiHistoryTool {
    fn name(&self) -> &str {
        "clear_gemini_history"
    }

    fn description(&self) -> &str {
        "Clear Gemini conversation history"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut integration = self.integration.write().await;
        let cleared_count = integration.clear_history();

        info!("Gemini history cleared: {} entries", cleared_count);

        let response = json!({
            "status": "success",
            "cleared_entries": cleared_count,
            "message": format!("Cleared {} conversation entries", cleared_count)
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: gemini_status
// ============================================================================

struct GeminiStatusTool {
    integration: Arc<RwLock<GeminiIntegration>>,
}

#[async_trait]
impl Tool for GeminiStatusTool {
    fn name(&self) -> &str {
        "gemini_status"
    }

    fn description(&self) -> &str {
        "Get Gemini integration status and statistics"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let integration = self.integration.read().await;

        let gemini_available = integration.check_gemini_available().await;
        let stats = integration.stats();
        let config = integration.config();

        let response = json!({
            "enabled": config.enabled,
            "auto_consult": config.auto_consult,
            "gemini_available": gemini_available,
            "model": config.model,
            "timeout": config.timeout_secs,
            "use_container": config.use_container,
            "statistics": {
                "consultations": stats.consultations,
                "completed": stats.completed,
                "errors": stats.errors,
                "average_execution_time": stats.average_execution_time(),
                "last_consultation": stats.last_consultation.map(|t| t.to_rfc3339())
            },
            "history_size": integration.history_size()
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: toggle_gemini_auto_consult
// ============================================================================

struct ToggleGeminiAutoConsultTool {
    integration: Arc<RwLock<GeminiIntegration>>,
}

#[async_trait]
impl Tool for ToggleGeminiAutoConsultTool {
    fn name(&self) -> &str {
        "toggle_gemini_auto_consult"
    }

    fn description(&self) -> &str {
        "Toggle automatic Gemini consultation on uncertainty detection"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "enable": {
                    "type": "boolean",
                    "description": "Enable or disable auto-consultation"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let enable = args.get("enable").and_then(|v| v.as_bool());

        let mut integration = self.integration.write().await;
        let new_state = integration.toggle_auto_consult(enable);

        info!("Gemini auto-consult toggled: {}", new_state);

        let response = json!({
            "enabled": new_state,
            "message": format!(
                "Gemini auto-consultation {}",
                if new_state { "enabled" } else { "disabled" }
            )
        });

        ToolResult::json(&response)
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

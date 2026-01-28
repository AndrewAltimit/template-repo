//! MCP server implementation for Crush integration.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::crush::CrushIntegration;
use crate::types::{ConsultMode, ConsultStatus, CrushConfig};

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
        vec![
            Arc::new(ConsultCrushTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ClearCrushHistoryTool {
                integration: self.integration.clone(),
            }),
            Arc::new(CrushStatusTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ToggleCrushAutoConsultTool {
                integration: self.integration.clone(),
            }),
        ]
    }
}

impl Default for CrushServer {
    fn default() -> Self {
        Self::new(CrushConfig::from_env())
    }
}

// ============================================================================
// Tool: consult_crush
// ============================================================================

struct ConsultCrushTool {
    integration: Arc<RwLock<CrushIntegration>>,
}

#[async_trait]
impl Tool for ConsultCrushTool {
    fn name(&self) -> &str {
        "consult_crush"
    }

    fn description(&self) -> &str {
        "Consult Crush AI for quick code generation, explanation, or conversion"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The coding question, task, or code to consult about"
                },
                "context": {
                    "type": "string",
                    "description": "Additional context or target language for conversion",
                    "default": ""
                },
                "mode": {
                    "type": "string",
                    "enum": ["generate", "explain", "convert", "quick"],
                    "default": "quick",
                    "description": "Consultation mode"
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

        if query.is_empty() {
            let response = json!({
                "success": false,
                "error": "'query' parameter is required for Crush consultation"
            });
            return ToolResult::json(&response);
        }

        let context = args.get("context").and_then(|v| v.as_str()).unwrap_or("");

        let mode_str = args.get("mode").and_then(|v| v.as_str()).unwrap_or("quick");
        let mode = ConsultMode::from_str(mode_str);

        let force = args.get("force").and_then(|v| v.as_bool()).unwrap_or(false);

        // Build the prompt based on mode
        let prompt = match mode {
            ConsultMode::Explain => {
                if context.is_empty() {
                    format!("Explain the following code:\n\n```\n{}\n```", query)
                } else {
                    format!(
                        "Explain the following code, focusing on {}:\n\n```\n{}\n```",
                        context, query
                    )
                }
            }
            ConsultMode::Convert => {
                if context.is_empty() {
                    let response = json!({
                        "success": false,
                        "error": "'context' parameter is required for conversion (target language)"
                    });
                    return ToolResult::json(&response);
                }
                format!(
                    "Convert the following code to {}:\n\n```\n{}\n```",
                    context, query
                )
            }
            ConsultMode::Generate => {
                format!("{} (provide detailed implementation)", query)
            }
            ConsultMode::Quick => {
                format!("{} (be concise)", query)
            }
        };

        let mut integration = self.integration.write().await;

        // Check if enabled
        if !integration.config().enabled && !force {
            let response = json!({
                "success": false,
                "error": "Crush consultation is disabled. Use 'force=true' to override."
            });
            return ToolResult::json(&response);
        }

        info!(
            "Crush consultation: query_length={}, mode={:?}",
            query.len(),
            mode
        );

        let result = integration.consult(&prompt, force).await;

        let response = match result.status {
            ConsultStatus::Success => {
                json!({
                    "success": true,
                    "result": result.response,
                    "execution_time": result.execution_time,
                    "consultation_id": result.consultation_id,
                    "timestamp": result.timestamp.to_rfc3339()
                })
            }
            ConsultStatus::Error => {
                json!({
                    "success": false,
                    "error": result.error,
                    "consultation_id": result.consultation_id
                })
            }
            ConsultStatus::Disabled => {
                json!({
                    "success": false,
                    "error": "Crush integration is disabled"
                })
            }
            ConsultStatus::Timeout => {
                json!({
                    "success": false,
                    "error": result.error,
                    "consultation_id": result.consultation_id
                })
            }
        };

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: clear_crush_history
// ============================================================================

struct ClearCrushHistoryTool {
    integration: Arc<RwLock<CrushIntegration>>,
}

#[async_trait]
impl Tool for ClearCrushHistoryTool {
    fn name(&self) -> &str {
        "clear_crush_history"
    }

    fn description(&self) -> &str {
        "Clear Crush conversation history"
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

        info!("Crush history cleared: {} entries", cleared_count);

        let response = json!({
            "success": true,
            "cleared_entries": cleared_count,
            "message": format!("Cleared {} conversation entries", cleared_count)
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: crush_status
// ============================================================================

struct CrushStatusTool {
    integration: Arc<RwLock<CrushIntegration>>,
}

#[async_trait]
impl Tool for CrushStatusTool {
    fn name(&self) -> &str {
        "crush_status"
    }

    fn description(&self) -> &str {
        "Get Crush integration status and statistics"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let integration = self.integration.read().await;

        let stats = integration.stats();
        let config = integration.config();

        let response = json!({
            "enabled": config.enabled,
            "auto_consult": config.auto_consult,
            "api_key_configured": !config.api_key.is_empty(),
            "timeout": config.timeout_secs,
            "docker_service": config.docker_service,
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
// Tool: toggle_crush_auto_consult
// ============================================================================

struct ToggleCrushAutoConsultTool {
    integration: Arc<RwLock<CrushIntegration>>,
}

#[async_trait]
impl Tool for ToggleCrushAutoConsultTool {
    fn name(&self) -> &str {
        "toggle_crush_auto_consult"
    }

    fn description(&self) -> &str {
        "Toggle automatic Crush consultation on uncertainty detection"
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

        info!("Crush auto-consult toggled: {}", new_state);

        let response = json!({
            "enabled": new_state,
            "message": format!(
                "Crush auto-consultation {}",
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

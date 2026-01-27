//! MCP server implementation for OpenCode integration.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::opencode::OpenCodeIntegration;
use crate::types::{ConsultMode, ConsultStatus, OpenCodeConfig};

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
        vec![
            Arc::new(ConsultOpenCodeTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ClearOpenCodeHistoryTool {
                integration: self.integration.clone(),
            }),
            Arc::new(OpenCodeStatusTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ToggleOpenCodeAutoConsultTool {
                integration: self.integration.clone(),
            }),
        ]
    }
}

impl Default for OpenCodeServer {
    fn default() -> Self {
        Self::new(OpenCodeConfig::from_env())
    }
}

// ============================================================================
// Tool: consult_opencode
// ============================================================================

struct ConsultOpenCodeTool {
    integration: Arc<RwLock<OpenCodeIntegration>>,
}

#[async_trait]
impl Tool for ConsultOpenCodeTool {
    fn name(&self) -> &str {
        "consult_opencode"
    }

    fn description(&self) -> &str {
        "Consult OpenCode AI for code generation, refactoring, or review"
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
                    "description": "Additional context or existing code",
                    "default": ""
                },
                "mode": {
                    "type": "string",
                    "enum": ["generate", "refactor", "review", "explain", "quick"],
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
                "error": "'query' parameter is required for OpenCode consultation"
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
            ConsultMode::Refactor => {
                if context.is_empty() {
                    format!(
                        "Refactor the following code for better readability and performance:\n\n```\n{}\n```",
                        query
                    )
                } else {
                    format!(
                        "Refactor the following code with these requirements: {}\n\n```\n{}\n```",
                        context, query
                    )
                }
            }
            ConsultMode::Review => {
                if context.is_empty() {
                    format!(
                        "Review the following code for bugs, security issues, and improvements:\n\n```\n{}\n```",
                        query
                    )
                } else {
                    format!(
                        "Review the following code, focusing on {}: \n\n```\n{}\n```",
                        context, query
                    )
                }
            }
            ConsultMode::Generate => {
                if context.is_empty() {
                    query.to_string()
                } else {
                    format!("{}\n\nContext:\n{}", query, context)
                }
            }
            ConsultMode::Quick => {
                if context.is_empty() {
                    query.to_string()
                } else {
                    format!("{}\n\nContext:\n{}", query, context)
                }
            }
        };

        let mut integration = self.integration.write().await;

        // Check if enabled
        if !integration.config().enabled && !force {
            let response = json!({
                "success": false,
                "error": "OpenCode consultation is disabled. Use 'force=true' to override."
            });
            return ToolResult::json(&response);
        }

        info!(
            "OpenCode consultation: query_length={}, mode={:?}",
            query.len(),
            mode
        );

        let result = integration.consult(&prompt, mode, force).await;

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
                    "error": "OpenCode integration is disabled"
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
// Tool: clear_opencode_history
// ============================================================================

struct ClearOpenCodeHistoryTool {
    integration: Arc<RwLock<OpenCodeIntegration>>,
}

#[async_trait]
impl Tool for ClearOpenCodeHistoryTool {
    fn name(&self) -> &str {
        "clear_opencode_history"
    }

    fn description(&self) -> &str {
        "Clear OpenCode conversation history"
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

        info!("OpenCode history cleared: {} entries", cleared_count);

        let response = json!({
            "success": true,
            "cleared_entries": cleared_count,
            "message": format!("Cleared {} conversation entries", cleared_count)
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: opencode_status
// ============================================================================

struct OpenCodeStatusTool {
    integration: Arc<RwLock<OpenCodeIntegration>>,
}

#[async_trait]
impl Tool for OpenCodeStatusTool {
    fn name(&self) -> &str {
        "opencode_status"
    }

    fn description(&self) -> &str {
        "Get OpenCode integration status and statistics"
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
            "success": true,
            "status": {
                "enabled": config.enabled,
                "auto_consult": config.auto_consult,
                "api_key_configured": !config.api_key.is_empty(),
                "model": config.model,
                "timeout": config.timeout_secs,
                "statistics": {
                    "consultations": stats.consultations,
                    "completed": stats.completed,
                    "errors": stats.errors,
                    "average_execution_time": stats.average_execution_time(),
                    "last_consultation": stats.last_consultation.map(|t| t.to_rfc3339())
                },
                "history_size": integration.history_size()
            }
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: toggle_opencode_auto_consult
// ============================================================================

struct ToggleOpenCodeAutoConsultTool {
    integration: Arc<RwLock<OpenCodeIntegration>>,
}

#[async_trait]
impl Tool for ToggleOpenCodeAutoConsultTool {
    fn name(&self) -> &str {
        "toggle_opencode_auto_consult"
    }

    fn description(&self) -> &str {
        "Toggle automatic OpenCode consultation on uncertainty detection"
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

        info!("OpenCode auto-consult toggled: {}", new_state);

        let response = json!({
            "success": true,
            "enabled": new_state,
            "message": format!(
                "OpenCode auto-consultation {}",
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

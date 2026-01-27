//! MCP server implementation for Codex integration.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::codex::CodexIntegration;
use crate::types::{CodexConfig, ConsultMode, ConsultStatus};

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
        vec![
            Arc::new(ConsultCodexTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ClearCodexHistoryTool {
                integration: self.integration.clone(),
            }),
            Arc::new(CodexStatusTool {
                integration: self.integration.clone(),
            }),
            Arc::new(ToggleCodexAutoConsultTool {
                integration: self.integration.clone(),
            }),
        ]
    }
}

impl Default for CodexServer {
    fn default() -> Self {
        Self::new(CodexConfig::from_env())
    }
}

// ============================================================================
// Tool: consult_codex
// ============================================================================

struct ConsultCodexTool {
    integration: Arc<RwLock<CodexIntegration>>,
}

#[async_trait]
impl Tool for ConsultCodexTool {
    fn name(&self) -> &str {
        "consult_codex"
    }

    fn description(&self) -> &str {
        "Consult Codex AI for code generation, completion, or refactoring"
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
                    "enum": ["generate", "complete", "refactor", "explain", "quick"],
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

        let context = args.get("context").and_then(|v| v.as_str()).unwrap_or("");

        let mode = args
            .get("mode")
            .and_then(|v| v.as_str())
            .map(ConsultMode::from_str)
            .unwrap_or(ConsultMode::Quick);

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
                "message": "Codex consultation is disabled. Use 'force=true' to override."
            });
            return ToolResult::json(&response);
        }

        // Check for auth
        if !integration.auth_exists() {
            let response = json!({
                "status": "error",
                "error": format!(
                    "Codex authentication not found at {}. Please run 'codex auth' first.",
                    integration.config().auth_path
                )
            });
            return ToolResult::json(&response);
        }

        info!(
            "Codex consultation: mode={:?}, query_length={}",
            mode,
            query.len()
        );

        let result = integration
            .consult(query, context, mode, comparison_mode)
            .await;

        let response = match result.status {
            ConsultStatus::Success => {
                json!({
                    "status": "success",
                    "output": result.output,
                    "mode": format!("{:?}", result.mode).to_lowercase(),
                    "message": result.message
                })
            }
            ConsultStatus::Error => {
                json!({
                    "status": "error",
                    "error": result.error,
                    "mode": format!("{:?}", result.mode).to_lowercase()
                })
            }
            ConsultStatus::Disabled => {
                json!({
                    "status": "disabled",
                    "message": result.message
                })
            }
        };

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: clear_codex_history
// ============================================================================

struct ClearCodexHistoryTool {
    integration: Arc<RwLock<CodexIntegration>>,
}

#[async_trait]
impl Tool for ClearCodexHistoryTool {
    fn name(&self) -> &str {
        "clear_codex_history"
    }

    fn description(&self) -> &str {
        "Clear Codex conversation history"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut integration = self.integration.write().await;
        integration.clear_history();

        info!("Codex history cleared");

        let response = json!({
            "status": "success",
            "message": "Codex conversation history cleared"
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: codex_status
// ============================================================================

struct CodexStatusTool {
    integration: Arc<RwLock<CodexIntegration>>,
}

#[async_trait]
impl Tool for CodexStatusTool {
    fn name(&self) -> &str {
        "codex_status"
    }

    fn description(&self) -> &str {
        "Get Codex integration status and statistics"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let integration = self.integration.read().await;

        let codex_available = integration.check_codex_available().await;
        let stats = integration.stats();
        let config = integration.config();

        let response = json!({
            "enabled": config.enabled,
            "auto_consult": config.auto_consult,
            "auth_exists": integration.auth_exists(),
            "codex_available": codex_available,
            "is_container": integration.is_container(),
            "stats": {
                "consultations": stats.consultations,
                "errors": stats.errors,
                "last_consultation": stats.last_consultation
            },
            "history_size": integration.history_size(),
            "config": {
                "enabled": config.enabled,
                "auto_consult": config.auto_consult,
                "auth_exists": integration.auth_exists(),
                "timeout": config.timeout_secs,
                "max_context": config.max_context_length
            }
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: toggle_codex_auto_consult
// ============================================================================

struct ToggleCodexAutoConsultTool {
    integration: Arc<RwLock<CodexIntegration>>,
}

#[async_trait]
impl Tool for ToggleCodexAutoConsultTool {
    fn name(&self) -> &str {
        "toggle_codex_auto_consult"
    }

    fn description(&self) -> &str {
        "Toggle automatic Codex consultation on uncertainty detection"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "enable": {
                    "type": "boolean",
                    "description": "Enable or disable auto-consultation"
                }
            },
            "required": []
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let enable = args.get("enable").and_then(|v| v.as_bool());

        let mut integration = self.integration.write().await;
        let new_state = integration.toggle_auto_consult(enable);

        info!("Codex auto-consult toggled: {}", new_state);

        let response = json!({
            "enabled": new_state,
            "message": format!(
                "Codex auto-consultation {}",
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

    #[test]
    fn test_consult_mode_from_str() {
        assert_eq!(ConsultMode::from_str("generate"), ConsultMode::Generate);
        assert_eq!(ConsultMode::from_str("complete"), ConsultMode::Complete);
        assert_eq!(ConsultMode::from_str("refactor"), ConsultMode::Refactor);
        assert_eq!(ConsultMode::from_str("explain"), ConsultMode::Explain);
        assert_eq!(ConsultMode::from_str("quick"), ConsultMode::Quick);
        assert_eq!(ConsultMode::from_str("unknown"), ConsultMode::Quick);
    }
}

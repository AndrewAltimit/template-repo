//! Generic tool implementations for AI consultation servers.
//!
//! These tools can be instantiated for any type that implements `AiIntegration`,
//! eliminating the need for each server to define its own tool structs.

use std::sync::Arc;

use async_trait::async_trait;
use serde_json::{Value, json};
use tokio::sync::RwLock;
use tracing::info;

use mcp_core::error::Result;
use mcp_core::tool::{Tool, ToolResult};

use crate::types::{AiIntegration, ConsultParams, ConsultStatus};

/// Type alias for the shared integration handle.
pub type SharedIntegration<I> = Arc<RwLock<I>>;

/// Boxed tool type for convenience.
type BoxedTool = Arc<dyn Tool>;

/// Create all 4 standard tools for an AI consultation integration.
///
/// Returns tools named: `consult_{name}`, `clear_{name}_history`,
/// `{name}_status`, `toggle_{name}_auto_consult`.
pub fn make_tools<I: AiIntegration>(
    integration: SharedIntegration<I>,
    name: &str,
    consult_description: &str,
    extra_schema_properties: Option<Value>,
) -> Vec<BoxedTool> {
    vec![
        Arc::new(ConsultTool {
            integration: Arc::clone(&integration),
            tool_name: format!("consult_{name}"),
            description: consult_description.to_string(),
            extra_schema_properties: extra_schema_properties.unwrap_or(json!({})),
        }),
        Arc::new(ClearHistoryTool {
            integration: Arc::clone(&integration),
            tool_name: format!("clear_{name}_history"),
            display_name: name.to_string(),
        }),
        Arc::new(StatusTool {
            integration: Arc::clone(&integration),
            tool_name: format!("{name}_status"),
            display_name: name.to_string(),
        }),
        Arc::new(ToggleAutoConsultTool {
            integration,
            tool_name: format!("toggle_{name}_auto_consult"),
            display_name: name.to_string(),
        }),
    ]
}

// -- Consult Tool --

pub struct ConsultTool<I: AiIntegration> {
    integration: SharedIntegration<I>,
    tool_name: String,
    description: String,
    extra_schema_properties: Value,
}

#[async_trait]
impl<I: AiIntegration> Tool for ConsultTool<I> {
    fn name(&self) -> &str {
        &self.tool_name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn schema(&self) -> Value {
        let mut properties = json!({
            "query": {
                "type": "string",
                "description": "The question or code to consult about"
            },
            "context": {
                "type": "string",
                "description": "Additional context for the consultation",
                "default": ""
            },
            "comparison_mode": {
                "type": "boolean",
                "description": "Compare with previous Claude response",
                "default": true
            },
            "force": {
                "type": "boolean",
                "description": "Force consultation even if disabled",
                "default": false
            }
        });

        // Merge in any extra properties (e.g., "mode" for codex/crush/opencode)
        if let (Some(base), Some(extra)) = (
            properties.as_object_mut(),
            self.extra_schema_properties.as_object(),
        ) {
            for (k, v) in extra {
                base.insert(k.clone(), v.clone());
            }
        }

        json!({
            "type": "object",
            "properties": properties,
            "required": ["query"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();

        if query.is_empty() {
            return ToolResult::json(&json!({
                "status": "error",
                "error": "Query parameter is required and cannot be empty"
            }));
        }

        let context = args
            .get("context")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();

        let comparison_mode = args
            .get("comparison_mode")
            .and_then(Value::as_bool)
            .unwrap_or(true);

        let force = args.get("force").and_then(Value::as_bool).unwrap_or(false);

        let mode = args.get("mode").and_then(Value::as_str).map(String::from);

        let params = ConsultParams {
            query,
            context,
            mode,
            comparison_mode,
            force,
        };

        let mut integration = self.integration.write().await;
        let result = integration.consult(params).await;

        let response = match &result.status {
            ConsultStatus::Success => {
                json!({
                    "status": "success",
                    "response": result.response,
                    "execution_time": result.execution_time,
                    "consultation_id": result.consultation_id,
                })
            },
            ConsultStatus::Error => {
                json!({
                    "status": "error",
                    "error": result.error,
                    "execution_time": result.execution_time,
                })
            },
            ConsultStatus::Disabled => {
                json!({
                    "status": "disabled",
                    "message": "Integration is disabled. Use force=true to override.",
                })
            },
            ConsultStatus::Timeout => {
                json!({
                    "status": "timeout",
                    "error": result.error,
                    "execution_time": result.execution_time,
                })
            },
        };

        ToolResult::json(&response)
    }
}

// -- Clear History Tool --

pub struct ClearHistoryTool<I: AiIntegration> {
    integration: SharedIntegration<I>,
    tool_name: String,
    display_name: String,
}

#[async_trait]
impl<I: AiIntegration> Tool for ClearHistoryTool<I> {
    fn name(&self) -> &str {
        &self.tool_name
    }

    fn description(&self) -> &str {
        "Clear conversation history"
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

        info!(
            integration = self.display_name.as_str(),
            cleared = cleared_count,
            "Cleared consultation history"
        );

        ToolResult::json(&json!({
            "status": "success",
            "message": format!("Cleared {} history entries", cleared_count),
            "cleared_count": cleared_count,
        }))
    }
}

// -- Status Tool --

pub struct StatusTool<I: AiIntegration> {
    integration: SharedIntegration<I>,
    tool_name: String,
    display_name: String,
}

#[async_trait]
impl<I: AiIntegration> Tool for StatusTool<I> {
    fn name(&self) -> &str {
        &self.tool_name
    }

    fn description(&self) -> &str {
        "Get integration status and statistics"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let integration = self.integration.read().await;
        let stats = integration.snapshot_stats();

        ToolResult::json(&json!({
            "integration": self.display_name,
            "enabled": integration.enabled(),
            "auto_consult": integration.auto_consult(),
            "history_entries": integration.history_len(),
            "stats": {
                "total_consultations": stats.consultations,
                "completed": stats.completed,
                "errors": stats.errors,
                "average_execution_time": stats.average_execution_time(),
                "last_consultation": stats.last_consultation,
            }
        }))
    }
}

// -- Toggle Auto Consult Tool --

pub struct ToggleAutoConsultTool<I: AiIntegration> {
    integration: SharedIntegration<I>,
    tool_name: String,
    display_name: String,
}

#[async_trait]
impl<I: AiIntegration> Tool for ToggleAutoConsultTool<I> {
    fn name(&self) -> &str {
        &self.tool_name
    }

    fn description(&self) -> &str {
        "Toggle automatic consultation on uncertainty detection"
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
        let enable = args.get("enable").and_then(Value::as_bool);

        let mut integration = self.integration.write().await;
        let new_state = integration.toggle_auto_consult(enable);

        info!(
            integration = self.display_name.as_str(),
            enabled = new_state,
            "Toggled auto-consultation"
        );

        ToolResult::json(&json!({
            "status": "success",
            "auto_consult_enabled": new_state,
            "message": format!(
                "Auto-consultation {}",
                if new_state { "enabled" } else { "disabled" }
            ),
        }))
    }
}

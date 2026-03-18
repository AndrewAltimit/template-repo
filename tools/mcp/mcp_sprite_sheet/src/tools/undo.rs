//! Undo/redo tool.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::engine::{self, ProjectStore};

pub struct UndoTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for UndoTool {
    fn name(&self) -> &str {
        "sprite_undo"
    }

    fn description(&self) -> &str {
        "Undo the last drawing operation, or redo if redo=true."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "redo": { "type": "boolean", "default": false, "description": "Redo instead of undo" }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = args["name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name'".to_string()))?;
        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let is_redo = args["redo"].as_bool().unwrap_or(false);

        if is_redo {
            engine::redo(project).map_err(MCPError::Internal)?;
        } else {
            engine::undo(project).map_err(MCPError::Internal)?;
        }

        ToolResult::json(&json!({
            "success": true,
            "action": if is_redo { "redo" } else { "undo" },
            "undo_depth": project.undo_stack.len(),
            "redo_depth": project.redo_stack.len()
        }))
    }
}

//! Transform tool: flip, rotate, shift.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::engine::{self, ProjectStore};
use crate::types::TransformOp;

pub struct TransformTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for TransformTool {
    fn name(&self) -> &str {
        "sprite_transform"
    }

    fn description(&self) -> &str {
        "Apply a transform to a layer: flip_h, flip_v, rotate_90_cw, rotate_90_ccw, rotate_180, shift. Optionally constrained to a region."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string" },
                "operation": {
                    "type": "string",
                    "enum": ["flip_h", "flip_v", "rotate_90_cw", "rotate_90_ccw", "rotate_180", "shift"]
                },
                "shift_dx": { "type": "integer", "description": "Shift X offset (for shift op)" },
                "shift_dy": { "type": "integer", "description": "Shift Y offset (for shift op)" },
                "region": {
                    "type": "object",
                    "properties": {
                        "x": { "type": "integer" },
                        "y": { "type": "integer" },
                        "width": { "type": "integer" },
                        "height": { "type": "integer" }
                    },
                    "description": "Optional region to constrain transform"
                }
            },
            "required": ["name", "layer_id", "operation"]
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

        let layer_id = args["layer_id"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'layer_id'".to_string()))?;

        let op_str = args["operation"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'operation'".to_string()))?;

        let op = match op_str {
            "flip_h" => TransformOp::FlipH,
            "flip_v" => TransformOp::FlipV,
            "rotate_90_cw" => TransformOp::Rotate90Cw,
            "rotate_90_ccw" => TransformOp::Rotate90Ccw,
            "rotate_180" => TransformOp::Rotate180,
            "shift" => TransformOp::Shift,
            other => {
                return Err(MCPError::InvalidParameters(format!(
                    "Unknown operation: {other}"
                )));
            },
        };

        let shift_dx = args["shift_dx"].as_i64().map(|v| v as i32);
        let shift_dy = args["shift_dy"].as_i64().map(|v| v as i32);

        let region = args.get("region").and_then(|r| {
            Some((
                r["x"].as_u64()? as u32,
                r["y"].as_u64()? as u32,
                r["width"].as_u64()? as u32,
                r["height"].as_u64()? as u32,
            ))
        });

        engine::transform_layer(project, layer_id, op, shift_dx, shift_dy, region)
            .map_err(MCPError::Internal)?;

        ToolResult::json(&json!({ "success": true, "operation": op_str }))
    }
}

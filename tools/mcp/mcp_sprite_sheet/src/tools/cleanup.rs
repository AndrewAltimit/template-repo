//! Edge cleanup tool: trim fringe pixels from an existing project.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::engine::{self, ProjectStore};

pub struct TrimEdgesTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for TrimEdgesTool {
    fn name(&self) -> &str {
        "sprite_trim_edges"
    }

    fn description(&self) -> &str {
        "Remove anti-aliasing fringe from sprite edges. Strips bright/light edge pixels that \
         result from white-background removal. Uses two tests: absolute luminance (catches \
         near-white fringe) and relative brightness vs neighbors (catches colored fringe). \
         Run multiple times with different thresholds for progressive cleanup."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name"
                },
                "layer_id": {
                    "type": "string",
                    "description": "Layer ID to trim (omit for all layers)"
                },
                "luma_threshold": {
                    "type": "integer",
                    "default": 190,
                    "description": "Absolute luminance cutoff (0-255). Edge pixels brighter than this are removed."
                },
                "passes": {
                    "type": "integer",
                    "default": 3,
                    "description": "Erosion passes (1-10). Each pass exposes new edges."
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = args["name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name'".to_string()))?;
        let target_layer = args["layer_id"].as_str();
        let luma_threshold = args["luma_threshold"]
            .as_u64()
            .or_else(|| args["luma_threshold"].as_f64().map(|f| f as u64))
            .unwrap_or(190) as u8;
        let passes = args["passes"]
            .as_u64()
            .or_else(|| args["passes"].as_f64().map(|f| f as u64))
            .unwrap_or(3)
            .min(10) as u32;

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let canvas_w = project.canvas.width;
        let canvas_h = project.canvas.height;
        let palette = project.palette.clone();

        let mut total_trimmed = 0;

        for layer in &mut project.layers {
            if let Some(tid) = target_layer
                && layer.id != tid
            {
                continue;
            }
            if layer.locked {
                continue;
            }

            let before = layer.pixels.len();
            engine::trim_border_fringe(
                &mut layer.pixels,
                &palette,
                luma_threshold,
                passes,
                canvas_w,
                canvas_h,
            );
            total_trimmed += before - layer.pixels.len();
        }

        let total_pixels: usize = project.layers.iter().map(|l| l.pixels.len()).sum();

        ToolResult::json(&json!({
            "success": true,
            "pixels_trimmed": total_trimmed,
            "pixels_remaining": total_pixels,
            "luma_threshold": luma_threshold,
            "passes": passes
        }))
    }
}

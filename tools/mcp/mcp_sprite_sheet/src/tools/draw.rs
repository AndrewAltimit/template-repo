//! Drawing tools: set_pixels, draw_line, draw_rect, draw_ellipse, flood_fill.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use super::parse::{json_as_i32, json_as_u8, json_as_u32};
use crate::engine::{self, ProjectStore};

fn require_name(args: &Value) -> Result<&str> {
    args["name"]
        .as_str()
        .ok_or_else(|| MCPError::InvalidParameters("Missing 'name'".to_string()))
}

fn require_layer_id(args: &Value) -> Result<&str> {
    args["layer_id"]
        .as_str()
        .ok_or_else(|| MCPError::InvalidParameters("Missing 'layer_id'".to_string()))
}

// ---------------------------------------------------------------------------
// set_pixels
// ---------------------------------------------------------------------------

pub struct SetPixelsTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for SetPixelsTool {
    fn name(&self) -> &str {
        "sprite_set_pixels"
    }

    fn description(&self) -> &str {
        "Batch set pixels on a layer. Each pixel is {x, y, color_index}."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string" },
                "pixels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": { "type": "integer" },
                            "y": { "type": "integer" },
                            "color_index": { "type": "integer" }
                        },
                        "required": ["x", "y", "color_index"]
                    },
                    "description": "Array of pixel positions with palette color indices"
                }
            },
            "required": ["name", "layer_id", "pixels"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;

        let pixels_arr = args["pixels"]
            .as_array()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'pixels' array".to_string()))?;

        let pixels: Vec<(u32, u32, u8)> = pixels_arr
            .iter()
            .filter_map(|p| {
                Some((
                    json_as_u32(&p["x"])?,
                    json_as_u32(&p["y"])?,
                    json_as_u8(&p["color_index"])?,
                ))
            })
            .collect();

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let count = engine::set_pixels(project, layer_id, &pixels).map_err(MCPError::Internal)?;

        ToolResult::json(&json!({ "success": true, "pixels_set": count }))
    }
}

// ---------------------------------------------------------------------------
// draw_line
// ---------------------------------------------------------------------------

pub struct DrawLineTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for DrawLineTool {
    fn name(&self) -> &str {
        "sprite_draw_line"
    }

    fn description(&self) -> &str {
        "Draw a line between two points using Bresenham's algorithm."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string" },
                "x0": { "type": "integer" },
                "y0": { "type": "integer" },
                "x1": { "type": "integer" },
                "y1": { "type": "integer" },
                "color_index": { "type": "integer" }
            },
            "required": ["name", "layer_id", "x0", "y0", "x1", "y1", "color_index"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;
        let x0 = json_as_i32(&args["x0"]).unwrap_or(0);
        let y0 = json_as_i32(&args["y0"]).unwrap_or(0);
        let x1 = json_as_i32(&args["x1"]).unwrap_or(0);
        let y1 = json_as_i32(&args["y1"]).unwrap_or(0);
        let ci = json_as_u8(&args["color_index"]).unwrap_or(0);

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let count =
            engine::draw_line(project, layer_id, x0, y0, x1, y1, ci).map_err(MCPError::Internal)?;

        ToolResult::json(&json!({ "success": true, "pixels_set": count }))
    }
}

// ---------------------------------------------------------------------------
// draw_rect
// ---------------------------------------------------------------------------

pub struct DrawRectTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for DrawRectTool {
    fn name(&self) -> &str {
        "sprite_draw_rect"
    }

    fn description(&self) -> &str {
        "Draw a rectangle (outline or filled)."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string" },
                "x": { "type": "integer" },
                "y": { "type": "integer" },
                "width": { "type": "integer" },
                "height": { "type": "integer" },
                "color_index": { "type": "integer" },
                "filled": { "type": "boolean", "default": false }
            },
            "required": ["name", "layer_id", "x", "y", "width", "height", "color_index"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;
        let x = json_as_u32(&args["x"]).unwrap_or(0);
        let y = json_as_u32(&args["y"]).unwrap_or(0);
        let w = json_as_u32(&args["width"]).unwrap_or(0);
        let h = json_as_u32(&args["height"]).unwrap_or(0);
        let ci = json_as_u8(&args["color_index"]).unwrap_or(0);
        let filled = args["filled"].as_bool().unwrap_or(false);

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let count = engine::draw_rect(project, layer_id, x, y, w, h, ci, filled)
            .map_err(MCPError::Internal)?;

        ToolResult::json(&json!({ "success": true, "pixels_set": count }))
    }
}

// ---------------------------------------------------------------------------
// draw_ellipse
// ---------------------------------------------------------------------------

pub struct DrawEllipseTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for DrawEllipseTool {
    fn name(&self) -> &str {
        "sprite_draw_ellipse"
    }

    fn description(&self) -> &str {
        "Draw an ellipse (outline or filled)."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string" },
                "cx": { "type": "integer", "description": "Center X" },
                "cy": { "type": "integer", "description": "Center Y" },
                "rx": { "type": "integer", "description": "Radius X" },
                "ry": { "type": "integer", "description": "Radius Y" },
                "color_index": { "type": "integer" },
                "filled": { "type": "boolean", "default": false }
            },
            "required": ["name", "layer_id", "cx", "cy", "rx", "ry", "color_index"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;
        let cx = json_as_i32(&args["cx"]).unwrap_or(0);
        let cy = json_as_i32(&args["cy"]).unwrap_or(0);
        let rx = json_as_i32(&args["rx"]).unwrap_or(0);
        let ry = json_as_i32(&args["ry"]).unwrap_or(0);
        let ci = json_as_u8(&args["color_index"]).unwrap_or(0);
        let filled = args["filled"].as_bool().unwrap_or(false);

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let count = engine::draw_ellipse(project, layer_id, cx, cy, rx, ry, ci, filled)
            .map_err(MCPError::Internal)?;

        ToolResult::json(&json!({ "success": true, "pixels_set": count }))
    }
}

// ---------------------------------------------------------------------------
// flood_fill
// ---------------------------------------------------------------------------

pub struct FloodFillTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for FloodFillTool {
    fn name(&self) -> &str {
        "sprite_flood_fill"
    }

    fn description(&self) -> &str {
        "Flood fill from a starting point with a palette color."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string" },
                "x": { "type": "integer", "description": "Start X" },
                "y": { "type": "integer", "description": "Start Y" },
                "color_index": { "type": "integer" }
            },
            "required": ["name", "layer_id", "x", "y", "color_index"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;
        let x = json_as_u32(&args["x"]).unwrap_or(0);
        let y = json_as_u32(&args["y"]).unwrap_or(0);
        let ci = json_as_u8(&args["color_index"]).unwrap_or(0);

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let count = engine::flood_fill(project, layer_id, x, y, ci).map_err(MCPError::Internal)?;

        ToolResult::json(&json!({ "success": true, "pixels_filled": count }))
    }
}

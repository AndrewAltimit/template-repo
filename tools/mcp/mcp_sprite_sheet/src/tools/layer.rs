//! Layer management tools.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::engine::{self, ProjectStore};
use crate::types::BlendMode;
use super::parse::json_as_u32;

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
// add_layer
// ---------------------------------------------------------------------------

pub struct AddLayerTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for AddLayerTool {
    fn name(&self) -> &str {
        "sprite_add_layer"
    }

    fn description(&self) -> &str {
        "Add a new layer to the project at an optional z_order."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_name": { "type": "string", "description": "Layer name" },
                "z_order": { "type": "integer", "description": "Z-order (default: top)" }
            },
            "required": ["name", "layer_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_name = args["layer_name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'layer_name'".to_string()))?;
        let z_order = args["z_order"].as_i64().map(|v| v as i32);

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let id = engine::add_layer(project, layer_name, z_order);
        ToolResult::json(&json!({ "success": true, "layer_id": id }))
    }
}

// ---------------------------------------------------------------------------
// remove_layer
// ---------------------------------------------------------------------------

pub struct RemoveLayerTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for RemoveLayerTool {
    fn name(&self) -> &str {
        "sprite_remove_layer"
    }

    fn description(&self) -> &str {
        "Remove a layer by ID."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID to remove" }
            },
            "required": ["name", "layer_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        engine::remove_layer(project, layer_id).map_err(MCPError::InvalidParameters)?;
        ToolResult::json(&json!({ "success": true }))
    }
}

// ---------------------------------------------------------------------------
// update_layer
// ---------------------------------------------------------------------------

pub struct UpdateLayerTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for UpdateLayerTool {
    fn name(&self) -> &str {
        "sprite_update_layer"
    }

    fn description(&self) -> &str {
        "Update layer properties: name, visible, opacity, blend_mode, locked, z_order."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID" },
                "layer_name": { "type": "string", "description": "New layer name" },
                "visible": { "type": "boolean" },
                "opacity": { "type": "integer", "minimum": 0, "maximum": 255 },
                "blend_mode": { "type": "string", "enum": ["normal", "multiply", "screen", "overlay"] },
                "locked": { "type": "boolean" },
                "z_order": { "type": "integer" }
            },
            "required": ["name", "layer_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let layer =
            engine::find_layer_mut(project, layer_id).map_err(MCPError::InvalidParameters)?;

        if let Some(n) = args["layer_name"].as_str() {
            layer.name = n.to_string();
        }
        if let Some(v) = args["visible"].as_bool() {
            layer.visible = v;
        }
        if let Some(o) = args["opacity"].as_u64() {
            layer.opacity = o.min(255) as u8;
        }
        if let Some(bm) = args["blend_mode"].as_str() {
            layer.blend_mode = match bm {
                "multiply" => BlendMode::Multiply,
                "screen" => BlendMode::Screen,
                "overlay" => BlendMode::Overlay,
                _ => BlendMode::Normal,
            };
        }
        if let Some(l) = args["locked"].as_bool() {
            layer.locked = l;
        }
        if let Some(z) = args["z_order"].as_i64() {
            layer.z_order = z as i32;
        }

        ToolResult::json(&json!({ "success": true }))
    }
}

// ---------------------------------------------------------------------------
// duplicate_layer
// ---------------------------------------------------------------------------

pub struct DuplicateLayerTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for DuplicateLayerTool {
    fn name(&self) -> &str {
        "sprite_duplicate_layer"
    }

    fn description(&self) -> &str {
        "Duplicate a layer including all pixel data."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID to duplicate" }
            },
            "required": ["name", "layer_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let new_id =
            engine::duplicate_layer(project, layer_id).map_err(MCPError::InvalidParameters)?;
        ToolResult::json(&json!({ "success": true, "new_layer_id": new_id }))
    }
}

// ---------------------------------------------------------------------------
// merge_layers
// ---------------------------------------------------------------------------

pub struct MergeLayersTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for MergeLayersTool {
    fn name(&self) -> &str {
        "sprite_merge_layers"
    }

    fn description(&self) -> &str {
        "Merge top layer onto bottom layer, removing top layer."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "top_layer_id": { "type": "string" },
                "bottom_layer_id": { "type": "string" }
            },
            "required": ["name", "top_layer_id", "bottom_layer_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let top = args["top_layer_id"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'top_layer_id'".to_string()))?;
        let bottom = args["bottom_layer_id"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'bottom_layer_id'".to_string()))?;

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        engine::merge_layers(project, top, bottom).map_err(MCPError::InvalidParameters)?;
        ToolResult::json(&json!({ "success": true }))
    }
}

// ---------------------------------------------------------------------------
// clear_layer
// ---------------------------------------------------------------------------

pub struct ClearLayerTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for ClearLayerTool {
    fn name(&self) -> &str {
        "sprite_clear_layer"
    }

    fn description(&self) -> &str {
        "Clear all pixels on a layer, or just a rectangular region."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string" },
                "region": {
                    "type": "object",
                    "properties": {
                        "x": { "type": "integer" },
                        "y": { "type": "integer" },
                        "width": { "type": "integer" },
                        "height": { "type": "integer" }
                    },
                    "required": ["x", "y", "width", "height"],
                    "description": "Optional region to clear"
                }
            },
            "required": ["name", "layer_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pname = require_name(&args)?;
        let layer_id = require_layer_id(&args)?;

        let region = if let Some(r) = args.get("region") {
            // Try parsing as an object first; if it's a string, parse it as JSON
            let region_obj = if r.is_object() {
                r.clone()
            } else if let Some(s) = r.as_str() {
                serde_json::from_str(s).unwrap_or(Value::Null)
            } else {
                return Err(MCPError::InvalidParameters(format!(
                    "region: expected object, got {}",
                    r
                )));
            };
            let x = json_as_u32(&region_obj["x"]).ok_or_else(|| {
                MCPError::InvalidParameters(format!(
                    "region.x: cannot parse (region={})",
                    region_obj
                ))
            })?;
            let y = json_as_u32(&region_obj["y"])
                .ok_or_else(|| MCPError::InvalidParameters("region.y: cannot parse".to_string()))?;
            let w = json_as_u32(&region_obj["width"]).ok_or_else(|| {
                MCPError::InvalidParameters("region.width: cannot parse".to_string())
            })?;
            let h = json_as_u32(&region_obj["height"]).ok_or_else(|| {
                MCPError::InvalidParameters("region.height: cannot parse".to_string())
            })?;
            Some((x, y, w, h))
        } else {
            None
        };

        let mut store = self.store.write().await;
        let project = store
            .get_mut(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        engine::clear_layer(project, layer_id, region).map_err(MCPError::InvalidParameters)?;
        ToolResult::json(&json!({ "success": true }))
    }
}

// ---------------------------------------------------------------------------
// list_layers
// ---------------------------------------------------------------------------

pub struct ListLayersTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for ListLayersTool {
    fn name(&self) -> &str {
        "sprite_list_layers"
    }

    fn description(&self) -> &str {
        "List all layers with their properties."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = require_name(&args)?;

        let store = self.store.read().await;
        let project = store
            .get(name)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {name}")))?;

        let layers: Vec<Value> = project
            .layers
            .iter()
            .map(|l| {
                json!({
                    "id": l.id,
                    "name": l.name,
                    "visible": l.visible,
                    "opacity": l.opacity,
                    "blend_mode": l.blend_mode,
                    "locked": l.locked,
                    "z_order": l.z_order,
                    "pixel_count": l.pixels.len()
                })
            })
            .collect();

        ToolResult::json(&json!({ "layers": layers }))
    }
}

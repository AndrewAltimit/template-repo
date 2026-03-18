//! Project management tools: create, save, load, status.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::engine::{self, ProjectStore};
use crate::palette;

// ---------------------------------------------------------------------------
// create_project
// ---------------------------------------------------------------------------

pub struct CreateProjectTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for CreateProjectTool {
    fn name(&self) -> &str {
        "sprite_create_project"
    }

    fn description(&self) -> &str {
        "Create a new sprite sheet project with canvas size, grid configuration, and optional palette preset."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name (used as key)" },
                "width": { "type": "integer", "description": "Canvas width in pixels" },
                "height": { "type": "integer", "description": "Canvas height in pixels" },
                "cell_width": { "type": "integer", "description": "Grid cell width", "default": 16 },
                "cell_height": { "type": "integer", "description": "Grid cell height", "default": 16 },
                "padding": { "type": "integer", "description": "Grid padding between cells", "default": 0 },
                "margin": { "type": "integer", "description": "Grid margin around edges", "default": 0 },
                "background_color": {
                    "type": "array", "items": { "type": "integer" }, "minItems": 4, "maxItems": 4,
                    "description": "Background RGBA [r,g,b,a], default [0,0,0,0]"
                },
                "palette_preset": {
                    "type": "string",
                    "description": "Palette preset name (pico8, gameboy, nes, snes, endesga32)"
                }
            },
            "required": ["name", "width", "height"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args["name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name'".to_string()))?;
        let width = args["width"]
            .as_u64()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'width'".to_string()))?
            as u32;
        let height = args["height"]
            .as_u64()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'height'".to_string()))?
            as u32;
        let cell_w = args["cell_width"].as_u64().unwrap_or(16) as u32;
        let cell_h = args["cell_height"].as_u64().unwrap_or(16) as u32;
        let padding = args["padding"].as_u64().unwrap_or(0) as u32;
        let margin = args["margin"].as_u64().unwrap_or(0) as u32;
        let bg = parse_rgba(&args["background_color"]).unwrap_or([0, 0, 0, 0]);
        let preset = args["palette_preset"].as_str();

        let project = engine::create_project(
            name, width, height, cell_w, cell_h, padding, margin, bg, preset,
        )
        .map_err(MCPError::InvalidParameters)?;

        let mut store = self.store.write().await;
        store.insert(name.to_string(), project);

        ToolResult::json(&json!({
            "success": true,
            "project": name,
            "canvas": { "width": width, "height": height },
            "grid": { "cell_width": cell_w, "cell_height": cell_h },
            "available_presets": palette::preset_names()
        }))
    }
}

// ---------------------------------------------------------------------------
// save_project
// ---------------------------------------------------------------------------

pub struct SaveProjectTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for SaveProjectTool {
    fn name(&self) -> &str {
        "sprite_save_project"
    }

    fn description(&self) -> &str {
        "Serialize a project to JSON for persistence."
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
        let name = require_str(&args, "name")?;
        let store = self.store.read().await;
        let project = store
            .get(name)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {name}")))?;

        let json_data = serde_json::to_value(project)
            .map_err(|e| MCPError::Internal(format!("Serialize error: {e}")))?;

        ToolResult::json(&json!({
            "success": true,
            "project_data": json_data
        }))
    }
}

// ---------------------------------------------------------------------------
// load_project
// ---------------------------------------------------------------------------

pub struct LoadProjectTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for LoadProjectTool {
    fn name(&self) -> &str {
        "sprite_load_project"
    }

    fn description(&self) -> &str {
        "Load a project from JSON data into memory."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project_data": {
                    "type": "object",
                    "description": "Full project JSON (as returned by sprite_save_project)"
                }
            },
            "required": ["project_data"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let data = args
            .get("project_data")
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project_data'".to_string()))?;

        let project: crate::types::SpriteProject = serde_json::from_value(data.clone())
            .map_err(|e| MCPError::InvalidParameters(format!("Invalid project data: {e}")))?;

        let name = project.name.clone();
        let mut store = self.store.write().await;
        store.insert(name.clone(), project);

        ToolResult::json(&json!({ "success": true, "project": name }))
    }
}

// ---------------------------------------------------------------------------
// project_status
// ---------------------------------------------------------------------------

pub struct ProjectStatusTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for ProjectStatusTool {
    fn name(&self) -> &str {
        "sprite_project_status"
    }

    fn description(&self) -> &str {
        "Get a summary of a project: dimensions, layers, sprites, animations, palette info."
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
        let name = require_str(&args, "name")?;
        let store = self.store.read().await;
        let p = store
            .get(name)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {name}")))?;

        let total_pixels: usize = p.layers.iter().map(|l| l.pixels.len()).sum();

        ToolResult::json(&json!({
            "project": name,
            "canvas": { "width": p.canvas.width, "height": p.canvas.height },
            "grid": {
                "cell_width": p.grid.cell_width,
                "cell_height": p.grid.cell_height,
                "padding": p.grid.padding,
                "margin": p.grid.margin
            },
            "palette": {
                "name": p.palette.name,
                "colors": p.palette.colors.len(),
                "enforce": p.palette.enforce
            },
            "layers": p.layers.len(),
            "sprites": p.sprites.len(),
            "animations": p.animations.len(),
            "total_pixels": total_pixels,
            "undo_depth": p.undo_stack.len(),
            "redo_depth": p.redo_stack.len()
        }))
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn require_str<'a>(args: &'a Value, key: &str) -> Result<&'a str> {
    args[key]
        .as_str()
        .ok_or_else(|| MCPError::InvalidParameters(format!("Missing '{key}'")))
}

fn parse_rgba(val: &Value) -> Option<[u8; 4]> {
    let arr = val.as_array()?;
    if arr.len() != 4 {
        return None;
    }
    Some([
        arr[0].as_u64()? as u8,
        arr[1].as_u64()? as u8,
        arr[2].as_u64()? as u8,
        arr[3].as_u64()? as u8,
    ])
}

//! Sprite and animation definition tools.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use crate::engine::ProjectStore;
use crate::types::*;

// ---------------------------------------------------------------------------
// define_sprite
// ---------------------------------------------------------------------------

pub struct DefineSpriteToolImpl {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for DefineSpriteToolImpl {
    fn name(&self) -> &str {
        "sprite_define_sprite"
    }

    fn description(&self) -> &str {
        "Define a named sprite region on the grid with optional anchor, hitbox, and tags."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "sprite_name": { "type": "string", "description": "Sprite display name" },
                "grid_x": { "type": "integer", "description": "Grid column" },
                "grid_y": { "type": "integer", "description": "Grid row" },
                "width_cells": { "type": "integer", "default": 1 },
                "height_cells": { "type": "integer", "default": 1 },
                "anchor_x": { "type": "integer", "default": 0 },
                "anchor_y": { "type": "integer", "default": 0 },
                "hitbox": {
                    "type": "object",
                    "properties": {
                        "x": { "type": "integer" },
                        "y": { "type": "integer" },
                        "width": { "type": "integer" },
                        "height": { "type": "integer" }
                    }
                },
                "tags": { "type": "array", "items": { "type": "string" } }
            },
            "required": ["name", "sprite_name", "grid_x", "grid_y"]
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

        let sprite_name = args["sprite_name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'sprite_name'".to_string()))?;

        let id = uuid::Uuid::new_v4().to_string();

        let hitbox = args.get("hitbox").and_then(|h| {
            Some(HitboxRect {
                x: h["x"].as_u64()? as u32,
                y: h["y"].as_u64()? as u32,
                width: h["width"].as_u64()? as u32,
                height: h["height"].as_u64()? as u32,
            })
        });

        let tags: Vec<String> = args["tags"]
            .as_array()
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        project.sprites.push(SpriteDef {
            id: id.clone(),
            name: sprite_name.to_string(),
            grid_x: args["grid_x"].as_u64().unwrap_or(0) as u32,
            grid_y: args["grid_y"].as_u64().unwrap_or(0) as u32,
            width_cells: args["width_cells"].as_u64().unwrap_or(1) as u32,
            height_cells: args["height_cells"].as_u64().unwrap_or(1) as u32,
            anchor_x: args["anchor_x"].as_u64().unwrap_or(0) as u32,
            anchor_y: args["anchor_y"].as_u64().unwrap_or(0) as u32,
            hitbox,
            tags,
        });

        ToolResult::json(&json!({ "success": true, "sprite_id": id }))
    }
}

// ---------------------------------------------------------------------------
// remove_sprite
// ---------------------------------------------------------------------------

pub struct RemoveSpriteTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for RemoveSpriteTool {
    fn name(&self) -> &str {
        "sprite_remove_sprite"
    }

    fn description(&self) -> &str {
        "Remove a sprite definition by ID."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "sprite_id": { "type": "string" }
            },
            "required": ["name", "sprite_id"]
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

        let sprite_id = args["sprite_id"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'sprite_id'".to_string()))?;

        let idx = project
            .sprites
            .iter()
            .position(|s| s.id == sprite_id)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Sprite not found: {sprite_id}")))?;

        project.sprites.remove(idx);
        ToolResult::json(&json!({ "success": true }))
    }
}

// ---------------------------------------------------------------------------
// list_sprites
// ---------------------------------------------------------------------------

pub struct ListSpritesTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for ListSpritesTool {
    fn name(&self) -> &str {
        "sprite_list_sprites"
    }

    fn description(&self) -> &str {
        "List all sprite definitions."
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
        let pname = args["name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name'".to_string()))?;
        let store = self.store.read().await;
        let project = store
            .get(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let sprites: Vec<Value> = project
            .sprites
            .iter()
            .map(|s| {
                json!({
                    "id": s.id,
                    "name": s.name,
                    "grid_x": s.grid_x,
                    "grid_y": s.grid_y,
                    "width_cells": s.width_cells,
                    "height_cells": s.height_cells,
                    "anchor": [s.anchor_x, s.anchor_y],
                    "has_hitbox": s.hitbox.is_some(),
                    "tags": s.tags
                })
            })
            .collect();

        ToolResult::json(&json!({ "sprites": sprites }))
    }
}

// ---------------------------------------------------------------------------
// define_animation
// ---------------------------------------------------------------------------

pub struct DefineAnimationTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for DefineAnimationTool {
    fn name(&self) -> &str {
        "sprite_define_animation"
    }

    fn description(&self) -> &str {
        "Define an animation as a sequence of sprite frames with timing."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "anim_name": { "type": "string", "description": "Animation name" },
                "frames": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sprite_id": { "type": "string" },
                            "duration_ms": { "type": "integer", "default": 100 }
                        },
                        "required": ["sprite_id"]
                    }
                },
                "loop_mode": { "type": "string", "enum": ["loop", "once", "ping_pong"], "default": "loop" },
                "tags": { "type": "array", "items": { "type": "string" } }
            },
            "required": ["name", "anim_name", "frames"]
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

        let anim_name = args["anim_name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'anim_name'".to_string()))?;

        let frames_arr = args["frames"]
            .as_array()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'frames'".to_string()))?;

        let frames: Vec<AnimFrame> = frames_arr
            .iter()
            .filter_map(|f| {
                Some(AnimFrame {
                    sprite_id: f["sprite_id"].as_str()?.to_string(),
                    duration_ms: f["duration_ms"].as_u64().unwrap_or(100) as u32,
                })
            })
            .collect();

        let loop_mode = match args["loop_mode"].as_str().unwrap_or("loop") {
            "once" => LoopMode::Once,
            "ping_pong" => LoopMode::PingPong,
            _ => LoopMode::Loop,
        };

        let tags: Vec<String> = args["tags"]
            .as_array()
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        let id = uuid::Uuid::new_v4().to_string();

        project.animations.push(AnimationDef {
            id: id.clone(),
            name: anim_name.to_string(),
            frames,
            loop_mode,
            tags,
        });

        ToolResult::json(&json!({ "success": true, "animation_id": id }))
    }
}

// ---------------------------------------------------------------------------
// list_animations
// ---------------------------------------------------------------------------

pub struct ListAnimationsTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for ListAnimationsTool {
    fn name(&self) -> &str {
        "sprite_list_animations"
    }

    fn description(&self) -> &str {
        "List all animation definitions."
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
        let pname = args["name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name'".to_string()))?;
        let store = self.store.read().await;
        let project = store
            .get(pname)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Project not found: {pname}")))?;

        let anims: Vec<Value> = project
            .animations
            .iter()
            .map(|a| {
                json!({
                    "id": a.id,
                    "name": a.name,
                    "frame_count": a.frames.len(),
                    "loop_mode": a.loop_mode,
                    "tags": a.tags,
                    "total_duration_ms": a.frames.iter().map(|f| f.duration_ms).sum::<u32>()
                })
            })
            .collect();

        ToolResult::json(&json!({ "animations": anims }))
    }
}

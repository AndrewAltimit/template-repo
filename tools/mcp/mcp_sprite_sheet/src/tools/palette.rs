//! Palette management tools.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::collections::HashMap;

use crate::engine::{self, ProjectStore};
use crate::palette as palette_mod;
use crate::types::{Palette, PaletteColor};

// ---------------------------------------------------------------------------
// set_palette
// ---------------------------------------------------------------------------

pub struct SetPaletteTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for SetPaletteTool {
    fn name(&self) -> &str {
        "sprite_set_palette"
    }

    fn description(&self) -> &str {
        "Set the palette from a preset name or an explicit list of colors."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "preset": {
                    "type": "string",
                    "description": "Preset name (pico8, gameboy, nes, snes, endesga32)"
                },
                "colors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": { "type": "integer" },
                            "name": { "type": "string" },
                            "rgba": {
                                "type": "array", "items": { "type": "integer" },
                                "minItems": 4, "maxItems": 4
                            }
                        },
                        "required": ["index", "name", "rgba"]
                    },
                    "description": "Explicit color list (used if preset not given)"
                },
                "enforce": { "type": "boolean", "default": true }
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

        let palette = if let Some(preset) = args["preset"].as_str() {
            palette_mod::from_preset(preset)
                .ok_or_else(|| MCPError::InvalidParameters(format!("Unknown preset: {preset}")))?
        } else if let Some(colors_arr) = args["colors"].as_array() {
            let colors: Vec<PaletteColor> = colors_arr
                .iter()
                .filter_map(|c| {
                    let rgba_arr = c["rgba"].as_array()?;
                    if rgba_arr.len() != 4 {
                        return None;
                    }
                    Some(PaletteColor {
                        index: c["index"].as_u64()? as u8,
                        name: c["name"].as_str()?.to_string(),
                        rgba: [
                            rgba_arr[0].as_u64()? as u8,
                            rgba_arr[1].as_u64()? as u8,
                            rgba_arr[2].as_u64()? as u8,
                            rgba_arr[3].as_u64()? as u8,
                        ],
                    })
                })
                .collect();
            Palette {
                name: "custom".to_string(),
                colors,
                enforce: args["enforce"].as_bool().unwrap_or(true),
            }
        } else {
            return Err(MCPError::InvalidParameters(
                "Provide either 'preset' or 'colors'".to_string(),
            ));
        };

        let count = palette.colors.len();
        project.palette = palette;

        ToolResult::json(&json!({ "success": true, "colors": count }))
    }
}

// ---------------------------------------------------------------------------
// swap_palette
// ---------------------------------------------------------------------------

pub struct SwapPaletteTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for SwapPaletteTool {
    fn name(&self) -> &str {
        "sprite_swap_palette"
    }

    fn description(&self) -> &str {
        "Remap palette indices across all layers. Provide an index_map of old_index -> new_index."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "index_map": {
                    "type": "object",
                    "description": "Mapping of old index (string) to new index (integer)",
                    "additionalProperties": { "type": "integer" }
                }
            },
            "required": ["name", "index_map"]
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

        let map_val = args
            .get("index_map")
            .and_then(|v| v.as_object())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'index_map'".to_string()))?;

        let mut index_map: HashMap<u8, u8> = HashMap::new();
        for (k, v) in map_val {
            let old: u8 = k
                .parse()
                .map_err(|_| MCPError::InvalidParameters(format!("Invalid index key: {k}")))?;
            let new = v.as_u64().ok_or_else(|| {
                MCPError::InvalidParameters(format!("Invalid index value for key {k}"))
            })? as u8;
            index_map.insert(old, new);
        }

        engine::swap_palette(project, &index_map);

        ToolResult::json(&json!({ "success": true, "remapped": index_map.len() }))
    }
}

// ---------------------------------------------------------------------------
// get_palette
// ---------------------------------------------------------------------------

pub struct GetPaletteTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for GetPaletteTool {
    fn name(&self) -> &str {
        "sprite_get_palette"
    }

    fn description(&self) -> &str {
        "Return the current palette with all colors."
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

        let colors: Vec<Value> = project
            .palette
            .colors
            .iter()
            .map(|c| {
                json!({
                    "index": c.index,
                    "name": c.name,
                    "rgba": c.rgba
                })
            })
            .collect();

        ToolResult::json(&json!({
            "palette_name": project.palette.name,
            "enforce": project.palette.enforce,
            "colors": colors,
            "available_presets": palette_mod::preset_names()
        }))
    }
}

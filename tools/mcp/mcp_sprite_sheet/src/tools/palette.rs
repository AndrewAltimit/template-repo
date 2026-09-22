//! Palette management tools.

use serde::Deserialize;
use serde_json::json;
use std::collections::HashMap;

use super::{edit_project, get, invalid, ok_json, sprite_tool};
use crate::args::{self, Rgba};
use crate::engine;
use crate::palette as presets;
use crate::types::{Palette, PaletteColor};

#[derive(Deserialize)]
pub struct ColorArg {
    #[serde(deserialize_with = "args::int")]
    index: u8,
    #[serde(default)]
    name: Option<String>,
    rgba: Rgba,
}

#[derive(Deserialize)]
pub struct SetArgs {
    name: String,
    #[serde(default)]
    preset: Option<String>,
    #[serde(default, deserialize_with = "args::opt_json")]
    colors: Option<Vec<ColorArg>>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    enforce: Option<bool>,
    #[serde(default)]
    palette_name: Option<String>,
}

sprite_tool! {
    SetPaletteTool {
        name: "sprite_set_palette",
        description: "Replace the palette with a preset or an explicit color list. Pixels keep \
            their indices (use sprite_swap_palette to remap); the response reports how many \
            pixels now reference undefined indices (they render transparent). With enforce=true \
            drawing undefined indices is rejected. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "preset": {
                    "type": "string",
                    "enum": presets::preset_names(),
                    "description": "Preset name (takes precedence over 'colors')"
                },
                "colors": {
                    "type": "array",
                    "maxItems": 256,
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": { "type": "integer", "minimum": 0, "maximum": 255 },
                            "name": { "type": "string" },
                            "rgba": {
                                "type": "array", "items": { "type": "integer", "minimum": 0, "maximum": 255 },
                                "minItems": 3, "maxItems": 4
                            }
                        },
                        "required": ["index", "rgba"]
                    },
                    "description": "Explicit color list with unique indices (used if preset not given)"
                },
                "enforce": { "type": "boolean", "description": "Reject drawing with undefined indices (default: true for presets and explicit lists)" },
                "palette_name": { "type": "string", "description": "Name for an explicit palette (default 'custom')" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: SetArgs| {
            let mut palette = if let Some(preset) = &a.preset {
                presets::from_preset(preset).ok_or_else(|| {
                    invalid(format!(
                        "Unknown preset: {preset}. Available: {}",
                        presets::preset_names().join(", ")
                    ))
                })?
            } else if let Some(colors) = a.colors {
                Palette {
                    name: a.palette_name.unwrap_or_else(|| "custom".to_string()),
                    colors: colors
                        .into_iter()
                        .map(|c| PaletteColor {
                            index: c.index,
                            name: c.name.unwrap_or_else(|| format!("color_{}", c.index)),
                            rgba: c.rgba.0,
                        })
                        .collect(),
                    enforce: true,
                }
            } else {
                return Err(invalid("Provide either 'preset' or 'colors'".into()));
            };
            if let Some(e) = a.enforce {
                palette.enforce = e;
            }
            let count = palette.colors.len();
            let (pname, enforce) = (palette.name.clone(), palette.enforce);
            let orphaned = edit_project(ctx, &a.name, "set_palette", |p| {
                engine::set_palette(p, palette)
            })
            .await?;
            ok_json(json!({
                "success": true,
                "palette": pname,
                "colors": count,
                "enforce": enforce,
                "pixels_with_undefined_color": orphaned
            }))
        }
    }
}

#[derive(Deserialize)]
pub struct SwapArgs {
    name: String,
    #[serde(deserialize_with = "args::json")]
    index_map: HashMap<String, serde_json::Value>,
}

sprite_tool! {
    SwapPaletteTool {
        name: "sprite_swap_palette",
        description: "Remap pixel color indices across all layers using index_map \
            {\"old_index\": new_index}. Mappings are applied simultaneously (swaps like \
            {\"1\": 2, \"2\": 1} work). Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "index_map": {
                    "type": "object",
                    "description": "Mapping of old index (string key) to new index (0-255)",
                    "additionalProperties": { "type": "integer", "minimum": 0, "maximum": 255 }
                }
            },
            "required": ["name", "index_map"]
        }),
        execute: |ctx, a: SwapArgs| {
            let mut map: HashMap<u8, u8> = HashMap::new();
            for (k, v) in &a.index_map {
                let old: u8 = k
                    .trim()
                    .parse()
                    .map_err(|_| invalid(format!("index_map key '{k}' is not an index 0-255")))?;
                let new = args::value_as_i64(v)
                    .and_then(|n| u8::try_from(n).ok())
                    .ok_or_else(|| {
                        invalid(format!("index_map['{k}'] = {v} is not an index 0-255"))
                    })?;
                map.insert(old, new);
            }
            let changed = edit_project(ctx, &a.name, "swap_palette", |p| {
                let enforce = p.palette.enforce;
                if enforce
                    && let Some(bad) = map.values().find(|&&n| !p.palette.is_valid_index(n))
                {
                    return Err(format!(
                        "Target index {bad} is not in the enforced palette"
                    ));
                }
                Ok(engine::swap_palette(p, &map))
            })
            .await?;
            ok_json(json!({ "success": true, "remapped": map.len(), "pixels_changed": changed }))
        }
    }
}

#[derive(Deserialize)]
pub struct GetArgs {
    name: String,
}

sprite_tool! {
    GetPaletteTool {
        name: "sprite_get_palette",
        description: "Return the current palette (index, name, rgba for each color), whether \
            it is enforced, and the available presets.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: GetArgs| {
            let store = ctx.store.read().await;
            let p = get(&store, &a.name)?;
            ok_json(json!({
                "palette_name": p.palette.name,
                "enforce": p.palette.enforce,
                "colors": p.palette.colors,
                "available_presets": presets::preset_names()
            }))
        }
    }
}

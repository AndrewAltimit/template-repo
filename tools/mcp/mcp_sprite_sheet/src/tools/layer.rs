//! Layer management tools.
//!
//! Every `layer_id` argument accepts either a layer ID or a unique layer name.

use serde::Deserialize;
use serde_json::{Value, json};

use super::{edit_project, get, ok_json, region_schema, sprite_tool};
use crate::args::{self, RegionArg};
use crate::engine;
use crate::types::BlendMode;

// ---------------------------------------------------------------------------
// add_layer
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct AddArgs {
    name: String,
    layer_name: String,
    #[serde(default, deserialize_with = "args::opt_int")]
    z_order: Option<i32>,
}

sprite_tool! {
    AddLayerTool {
        name: "sprite_add_layer",
        description: "Add a new empty layer. Defaults to the top of the stack (highest \
            z_order). Returns the new layer_id. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_name": { "type": "string", "description": "Layer name (can be used in place of the ID when unique)" },
                "z_order": { "type": "integer", "description": "Z-order; higher draws on top (default: above all layers)" }
            },
            "required": ["name", "layer_name"]
        }),
        execute: |ctx, a: AddArgs| {
            if a.layer_name.trim().is_empty() {
                return Err(super::invalid("layer_name must not be empty".into()));
            }
            let id = edit_project(ctx, &a.name, "add_layer", |p| {
                Ok(engine::add_layer(p, &a.layer_name, a.z_order))
            })
            .await?;
            ok_json(json!({ "success": true, "layer_id": id }))
        }
    }
}

// ---------------------------------------------------------------------------
// remove_layer
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct LayerArgs {
    name: String,
    layer_id: String,
}

sprite_tool! {
    RemoveLayerTool {
        name: "sprite_remove_layer",
        description: "Remove a layer (by ID or unique name). Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" }
            },
            "required": ["name", "layer_id"]
        }),
        execute: |ctx, a: LayerArgs| {
            let removed = edit_project(ctx, &a.name, "remove_layer", |p| {
                engine::remove_layer(p, &a.layer_id)
            })
            .await?;
            ok_json(json!({
                "success": true,
                "removed_layer": { "id": removed.id, "name": removed.name, "pixels": removed.pixels.len() }
            }))
        }
    }
}

// ---------------------------------------------------------------------------
// update_layer
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct UpdateArgs {
    name: String,
    layer_id: String,
    #[serde(default)]
    layer_name: Option<String>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    visible: Option<bool>,
    #[serde(default, deserialize_with = "args::opt_int")]
    opacity: Option<u8>,
    #[serde(default)]
    blend_mode: Option<BlendMode>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    locked: Option<bool>,
    #[serde(default, deserialize_with = "args::opt_int")]
    z_order: Option<i32>,
}

sprite_tool! {
    UpdateLayerTool {
        name: "sprite_update_layer",
        description: "Update layer properties: layer_name, visible, opacity (0-255), \
            blend_mode, locked, z_order. Only provided fields change. Locked layers reject \
            pixel edits. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "layer_name": { "type": "string", "description": "New layer name" },
                "visible": { "type": "boolean" },
                "opacity": { "type": "integer", "minimum": 0, "maximum": 255 },
                "blend_mode": { "type": "string", "enum": ["normal", "multiply", "screen", "overlay"] },
                "locked": { "type": "boolean" },
                "z_order": { "type": "integer" }
            },
            "required": ["name", "layer_id"]
        }),
        execute: |ctx, a: UpdateArgs| {
            let layer = edit_project(ctx, &a.name, "update_layer", |p| {
                let i = engine::resolve_layer(p, &a.layer_id)?;
                let l = &mut p.layers[i];
                if let Some(n) = &a.layer_name {
                    if n.trim().is_empty() {
                        return Err("layer_name must not be empty".into());
                    }
                    l.name = n.clone();
                }
                if let Some(v) = a.visible {
                    l.visible = v;
                }
                if let Some(o) = a.opacity {
                    l.opacity = o;
                }
                if let Some(b) = a.blend_mode {
                    l.blend_mode = b;
                }
                if let Some(v) = a.locked {
                    l.locked = v;
                }
                if let Some(z) = a.z_order {
                    l.z_order = z;
                }
                Ok(layer_json(l))
            })
            .await?;
            ok_json(json!({ "success": true, "layer": layer }))
        }
    }
}

fn layer_json(l: &crate::types::Layer) -> Value {
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
}

// ---------------------------------------------------------------------------
// duplicate_layer
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct DuplicateArgs {
    name: String,
    layer_id: String,
    #[serde(default)]
    new_name: Option<String>,
}

sprite_tool! {
    DuplicateLayerTool {
        name: "sprite_duplicate_layer",
        description: "Duplicate a layer including all pixel data and properties; the copy is \
            placed directly above the source and is unlocked. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name to duplicate" },
                "new_name": { "type": "string", "description": "Name for the copy (default '<name> copy')" }
            },
            "required": ["name", "layer_id"]
        }),
        execute: |ctx, a: DuplicateArgs| {
            let id = edit_project(ctx, &a.name, "duplicate_layer", |p| {
                engine::duplicate_layer(p, &a.layer_id, a.new_name.as_deref())
            })
            .await?;
            ok_json(json!({ "success": true, "new_layer_id": id }))
        }
    }
}

// ---------------------------------------------------------------------------
// merge_layers
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct MergeArgs {
    name: String,
    top_layer_id: String,
    bottom_layer_id: String,
}

sprite_tool! {
    MergeLayersTool {
        name: "sprite_merge_layers",
        description: "Merge the top layer's pixels onto the bottom layer (top pixels \
            overwrite), then remove the top layer. Opacity/blend mode of the top layer cannot \
            be baked into indexed pixels (a warning is returned). Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "top_layer_id": { "type": "string", "description": "Layer ID or unique name (removed after merge)" },
                "bottom_layer_id": { "type": "string", "description": "Layer ID or unique name (receives pixels)" }
            },
            "required": ["name", "top_layer_id", "bottom_layer_id"]
        }),
        execute: |ctx, a: MergeArgs| {
            let rep = edit_project(ctx, &a.name, "merge_layers", |p| {
                engine::merge_layers(p, &a.top_layer_id, &a.bottom_layer_id)
            })
            .await?;
            ok_json(json!({
                "success": true,
                "pixels_merged": rep.pixels_merged,
                "warnings": rep.warnings
            }))
        }
    }
}

// ---------------------------------------------------------------------------
// clear_layer
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct ClearArgs {
    name: String,
    layer_id: String,
    #[serde(default, deserialize_with = "args::opt_json")]
    region: Option<RegionArg>,
}

sprite_tool! {
    ClearLayerTool {
        name: "sprite_clear_layer",
        description: "Clear all pixels on a layer, or only those inside a rectangular region. \
            Returns the number of pixels cleared. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "region": region_schema("Optional region to clear (clipped to the canvas)")
            },
            "required": ["name", "layer_id"]
        }),
        execute: |ctx, a: ClearArgs| {
            let n = edit_project(ctx, &a.name, "clear_layer", |p| {
                engine::clear_layer(p, &a.layer_id, a.region.map(Into::into))
            })
            .await?;
            ok_json(json!({ "success": true, "pixels_cleared": n }))
        }
    }
}

// ---------------------------------------------------------------------------
// list_layers
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct ListArgs {
    name: String,
}

sprite_tool! {
    ListLayersTool {
        name: "sprite_list_layers",
        description: "List all layers (sorted bottom to top by z_order) with their properties \
            and pixel counts.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: ListArgs| {
            let store = ctx.store.read().await;
            let p = get(&store, &a.name)?;
            let mut layers: Vec<&crate::types::Layer> = p.layers.iter().collect();
            layers.sort_by_key(|l| l.z_order);
            let layers: Vec<Value> = layers.into_iter().map(layer_json).collect();
            ok_json(json!({ "layers": layers }))
        }
    }
}

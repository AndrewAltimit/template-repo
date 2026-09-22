//! Sprite and animation definition tools.
//!
//! `sprite_id` / `animation_id` arguments accept an ID or a unique name.

use serde::Deserialize;
use serde_json::{Value, json};

use super::{edit_project, get, ok_json, sprite_tool};
use crate::args;
use crate::engine;
use crate::types::{AnimFrame, HitboxRect, LoopMode, SpriteDef};

#[derive(Deserialize)]
pub struct HitboxArg {
    #[serde(deserialize_with = "args::int")]
    x: u32,
    #[serde(deserialize_with = "args::int")]
    y: u32,
    #[serde(deserialize_with = "args::int")]
    width: u32,
    #[serde(deserialize_with = "args::int")]
    height: u32,
}

#[derive(Deserialize)]
pub struct DefineSpriteArgs {
    name: String,
    sprite_name: String,
    #[serde(deserialize_with = "args::int")]
    grid_x: u32,
    #[serde(deserialize_with = "args::int")]
    grid_y: u32,
    #[serde(default, deserialize_with = "args::opt_int")]
    width_cells: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    height_cells: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    anchor_x: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    anchor_y: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_json")]
    hitbox: Option<HitboxArg>,
    #[serde(default, deserialize_with = "args::opt_json")]
    tags: Option<Vec<String>>,
}

fn sprite_json(p: &crate::types::SpriteProject, s: &SpriteDef) -> Value {
    let (x, y, w, h) = engine::sprite_pixel_bounds(p, s);
    json!({
        "id": s.id,
        "name": s.name,
        "grid_x": s.grid_x,
        "grid_y": s.grid_y,
        "width_cells": s.width_cells,
        "height_cells": s.height_cells,
        "pixel_bounds": { "x": x, "y": y, "width": w, "height": h },
        "anchor": [s.anchor_x, s.anchor_y],
        "hitbox": s.hitbox,
        "tags": s.tags
    })
}

sprite_tool! {
    DefineSpriteTool {
        name: "sprite_define_sprite",
        description: "Define a named sprite region on the grid (grid_x/grid_y are cell \
            coordinates) with optional anchor (pixels from the sprite's top-left), hitbox, and \
            tags. The region must fit on the canvas. Defining an existing sprite_name updates it \
            in place (same ID). Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "sprite_name": { "type": "string", "description": "Sprite name (unique per project)" },
                "grid_x": { "type": "integer", "minimum": 0, "description": "Grid column" },
                "grid_y": { "type": "integer", "minimum": 0, "description": "Grid row" },
                "width_cells": { "type": "integer", "minimum": 1, "default": 1 },
                "height_cells": { "type": "integer", "minimum": 1, "default": 1 },
                "anchor_x": { "type": "integer", "minimum": 0, "default": 0 },
                "anchor_y": { "type": "integer", "minimum": 0, "default": 0 },
                "hitbox": {
                    "type": "object",
                    "properties": {
                        "x": { "type": "integer" },
                        "y": { "type": "integer" },
                        "width": { "type": "integer" },
                        "height": { "type": "integer" }
                    },
                    "required": ["x", "y", "width", "height"],
                    "description": "Hitbox relative to the sprite's top-left pixel"
                },
                "tags": { "type": "array", "items": { "type": "string" } }
            },
            "required": ["name", "sprite_name", "grid_x", "grid_y"]
        }),
        execute: |ctx, a: DefineSpriteArgs| {
            let def = SpriteDef {
                id: String::new(),
                name: a.sprite_name,
                grid_x: a.grid_x,
                grid_y: a.grid_y,
                width_cells: a.width_cells.unwrap_or(1),
                height_cells: a.height_cells.unwrap_or(1),
                anchor_x: a.anchor_x.unwrap_or(0),
                anchor_y: a.anchor_y.unwrap_or(0),
                hitbox: a.hitbox.map(|h| HitboxRect {
                    x: h.x,
                    y: h.y,
                    width: h.width,
                    height: h.height,
                }),
                tags: a.tags.unwrap_or_default(),
            };
            let out = edit_project(ctx, &a.name, "define_sprite", |p| {
                let (id, updated) = engine::define_sprite(p, def)?;
                let i = engine::resolve_sprite(p, &id)?;
                Ok((id, updated, sprite_json(p, &p.sprites[i])))
            })
            .await?;
            ok_json(json!({
                "success": true,
                "sprite_id": out.0,
                "updated_existing": out.1,
                "sprite": out.2
            }))
        }
    }
}

#[derive(Deserialize)]
pub struct RemoveSpriteArgs {
    name: String,
    sprite_id: String,
}

sprite_tool! {
    RemoveSpriteTool {
        name: "sprite_remove_sprite",
        description: "Remove a sprite definition (by ID or name). Pixels are untouched. Frames \
            that referenced it are removed from animations; affected animations are reported. \
            Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "sprite_id": { "type": "string", "description": "Sprite ID or unique name" }
            },
            "required": ["name", "sprite_id"]
        }),
        execute: |ctx, a: RemoveSpriteArgs| {
            let (removed, affected) = edit_project(ctx, &a.name, "remove_sprite", |p| {
                engine::remove_sprite(p, &a.sprite_id)
            })
            .await?;
            ok_json(json!({
                "success": true,
                "removed": { "id": removed.id, "name": removed.name },
                "animations_affected": affected
            }))
        }
    }
}

#[derive(Deserialize)]
pub struct NameArgs {
    name: String,
}

sprite_tool! {
    ListSpritesTool {
        name: "sprite_list_sprites",
        description: "List all sprite definitions with grid position, pixel bounds, anchor, \
            hitbox, and tags.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: NameArgs| {
            let store = ctx.store.read().await;
            let p = get(&store, &a.name)?;
            let sprites: Vec<Value> = p.sprites.iter().map(|s| sprite_json(p, s)).collect();
            ok_json(json!({ "sprites": sprites }))
        }
    }
}

#[derive(Deserialize)]
pub struct FrameArg {
    sprite_id: String,
    #[serde(default, deserialize_with = "args::opt_int")]
    duration_ms: Option<u32>,
}

#[derive(Deserialize)]
pub struct DefineAnimationArgs {
    name: String,
    anim_name: String,
    #[serde(deserialize_with = "args::json")]
    frames: Vec<FrameArg>,
    #[serde(default)]
    loop_mode: Option<LoopMode>,
    #[serde(default, deserialize_with = "args::opt_json")]
    tags: Option<Vec<String>>,
}

sprite_tool! {
    DefineAnimationTool {
        name: "sprite_define_animation",
        description: "Define an animation as a sequence of sprite frames with per-frame timing \
            (default 100 ms). Frame sprite_id may be a sprite ID or unique name; every frame \
            must reference an existing sprite. Defining an existing anim_name replaces it (same \
            ID). Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "anim_name": { "type": "string", "description": "Animation name" },
                "frames": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "sprite_id": { "type": "string", "description": "Sprite ID or unique name" },
                            "duration_ms": { "type": "integer", "minimum": 1, "default": 100 }
                        },
                        "required": ["sprite_id"]
                    }
                },
                "loop_mode": { "type": "string", "enum": ["loop", "once", "ping_pong"], "default": "loop" },
                "tags": { "type": "array", "items": { "type": "string" } }
            },
            "required": ["name", "anim_name", "frames"]
        }),
        execute: |ctx, a: DefineAnimationArgs| {
            let frames: Vec<AnimFrame> = a
                .frames
                .into_iter()
                .map(|f| AnimFrame {
                    sprite_id: f.sprite_id,
                    duration_ms: f.duration_ms.unwrap_or(100),
                })
                .collect();
            let n = frames.len();
            let (id, updated) = edit_project(ctx, &a.name, "define_animation", |p| {
                engine::define_animation(
                    p,
                    &a.anim_name,
                    frames,
                    a.loop_mode.unwrap_or_default(),
                    a.tags.unwrap_or_default(),
                )
            })
            .await?;
            ok_json(json!({
                "success": true,
                "animation_id": id,
                "updated_existing": updated,
                "frame_count": n
            }))
        }
    }
}

sprite_tool! {
    ListAnimationsTool {
        name: "sprite_list_animations",
        description: "List all animation definitions with frames (sprite name + duration), loop \
            mode, tags, and total duration.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: NameArgs| {
            let store = ctx.store.read().await;
            let p = get(&store, &a.name)?;
            let anims: Vec<Value> = p
                .animations
                .iter()
                .map(|an| {
                    let frames: Vec<Value> = an
                        .frames
                        .iter()
                        .map(|f| {
                            let sprite = p
                                .sprites
                                .iter()
                                .find(|s| s.id == f.sprite_id)
                                .map(|s| s.name.as_str());
                            json!({ "sprite_id": f.sprite_id, "sprite": sprite, "duration_ms": f.duration_ms })
                        })
                        .collect();
                    json!({
                        "id": an.id,
                        "name": an.name,
                        "frame_count": an.frames.len(),
                        "frames": frames,
                        "loop_mode": an.loop_mode,
                        "tags": an.tags,
                        "total_duration_ms": an.total_duration_ms()
                    })
                })
                .collect();
            ok_json(json!({ "animations": anims }))
        }
    }
}

#[derive(Deserialize)]
pub struct RemoveAnimationArgs {
    name: String,
    animation_id: String,
}

sprite_tool! {
    RemoveAnimationTool {
        name: "sprite_remove_animation",
        description: "Remove an animation definition (by ID or name). Sprites are untouched. \
            Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "animation_id": { "type": "string", "description": "Animation ID or unique name" }
            },
            "required": ["name", "animation_id"]
        }),
        execute: |ctx, a: RemoveAnimationArgs| {
            let removed = edit_project(ctx, &a.name, "remove_animation", |p| {
                engine::remove_animation(p, &a.animation_id)
            })
            .await?;
            ok_json(json!({ "success": true, "removed": { "id": removed.id, "name": removed.name } }))
        }
    }
}

//! Drawing tools: set_pixels, draw_line, draw_rect, draw_ellipse, flood_fill,
//! and get_pixels (read-back).
//!
//! All primitives clip to the canvas, accept a layer ID or unique layer name,
//! and are undoable. With an enforced palette, drawing an undefined color
//! index is an error (set_pixels skips and counts such pixels instead).

use serde::Deserialize;
use serde_json::{Value, json};

use super::{edit_project, get, invalid, ok_json, region_schema, sprite_tool};
use crate::args::{self, PixelArg, PointArg, RegionArg};
use crate::engine::{self, Region};

fn pixel_item_schema() -> Value {
    json!({
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "x": { "type": "integer" },
                    "y": { "type": "integer" },
                    "color_index": { "type": "integer", "minimum": 0, "maximum": 255 }
                },
                "required": ["x", "y", "color_index"]
            },
            {
                "type": "array", "items": { "type": "integer" }, "minItems": 3, "maxItems": 3,
                "description": "Compact form [x, y, color_index]"
            }
        ]
    })
}

// ---------------------------------------------------------------------------
// set_pixels
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct SetPixelsArgs {
    name: String,
    layer_id: String,
    #[serde(deserialize_with = "args::json")]
    pixels: Vec<PixelArg>,
    #[serde(default, deserialize_with = "args::opt_json")]
    erase: Option<Vec<PointArg>>,
}

sprite_tool! {
    SetPixelsTool {
        name: "sprite_set_pixels",
        description: "Batch set pixels on a layer. Each pixel is {x, y, color_index} or the \
            compact [x, y, color_index]. Optional 'erase' removes pixels ([x, y] list) before \
            painting. Out-of-canvas pixels and (with an enforced palette) undefined colors are \
            skipped and reported. Undoable as one step.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "pixels": {
                    "type": "array",
                    "items": pixel_item_schema(),
                    "description": "Pixels to paint (may be empty when only erasing)"
                },
                "erase": {
                    "type": "array",
                    "items": { "type": "array", "items": { "type": "integer" }, "minItems": 2, "maxItems": 2 },
                    "description": "Pixels to make empty/transparent, as [x, y] pairs or {x, y}"
                }
            },
            "required": ["name", "layer_id", "pixels"]
        }),
        execute: |ctx, a: SetPixelsArgs| {
            let pixels: Vec<(i64, i64, u8)> =
                a.pixels.iter().map(|p| (p.x, p.y, p.color_index)).collect();
            let erase: Vec<(i64, i64)> = a
                .erase
                .unwrap_or_default()
                .iter()
                .map(|p| (p.x, p.y))
                .collect();
            let (erased, rep) = edit_project(ctx, &a.name, "set_pixels", |p| {
                let erased = if erase.is_empty() {
                    0
                } else {
                    engine::erase_pixels(p, &a.layer_id, &erase)?
                };
                Ok((erased, engine::set_pixels(p, &a.layer_id, &pixels)?))
            })
            .await?;
            ok_json(json!({
                "success": true,
                "pixels_set": rep.painted,
                "pixels_erased": erased,
                "skipped_out_of_bounds": rep.out_of_bounds,
                "skipped_invalid_color": rep.invalid_color
            }))
        }
    }
}

// ---------------------------------------------------------------------------
// draw_line
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct LineArgs {
    name: String,
    layer_id: String,
    #[serde(deserialize_with = "args::int")]
    x0: i64,
    #[serde(deserialize_with = "args::int")]
    y0: i64,
    #[serde(deserialize_with = "args::int")]
    x1: i64,
    #[serde(deserialize_with = "args::int")]
    y1: i64,
    #[serde(deserialize_with = "args::int")]
    color_index: u8,
}

sprite_tool! {
    DrawLineTool {
        name: "sprite_draw_line",
        description: "Draw a 1px line between two points (inclusive) using Bresenham's \
            algorithm. Endpoints may lie outside the canvas; the line is clipped. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "x0": { "type": "integer" },
                "y0": { "type": "integer" },
                "x1": { "type": "integer" },
                "y1": { "type": "integer" },
                "color_index": { "type": "integer", "minimum": 0, "maximum": 255 }
            },
            "required": ["name", "layer_id", "x0", "y0", "x1", "y1", "color_index"]
        }),
        execute: |ctx, a: LineArgs| {
            let rep = edit_project(ctx, &a.name, "draw_line", |p| {
                engine::draw_line(p, &a.layer_id, (a.x0, a.y0), (a.x1, a.y1), a.color_index)
            })
            .await?;
            ok_json(json!({
                "success": true,
                "pixels_set": rep.painted,
                "clipped": rep.out_of_bounds
            }))
        }
    }
}

// ---------------------------------------------------------------------------
// draw_rect
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct RectArgs {
    name: String,
    layer_id: String,
    #[serde(deserialize_with = "args::int")]
    x: i64,
    #[serde(deserialize_with = "args::int")]
    y: i64,
    #[serde(deserialize_with = "args::int")]
    width: i64,
    #[serde(deserialize_with = "args::int")]
    height: i64,
    #[serde(deserialize_with = "args::int")]
    color_index: u8,
    #[serde(default, deserialize_with = "args::opt_bool")]
    filled: Option<bool>,
}

sprite_tool! {
    DrawRectTool {
        name: "sprite_draw_rect",
        description: "Draw a rectangle (1px outline or filled) with top-left (x, y) and size \
            width x height (both >= 1). Clipped to the canvas. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "x": { "type": "integer" },
                "y": { "type": "integer" },
                "width": { "type": "integer", "minimum": 1 },
                "height": { "type": "integer", "minimum": 1 },
                "color_index": { "type": "integer", "minimum": 0, "maximum": 255 },
                "filled": { "type": "boolean", "default": false }
            },
            "required": ["name", "layer_id", "x", "y", "width", "height", "color_index"]
        }),
        execute: |ctx, a: RectArgs| {
            let r = Region {
                x: a.x,
                y: a.y,
                width: a.width,
                height: a.height,
            };
            let filled = a.filled.unwrap_or(false);
            let n = edit_project(ctx, &a.name, "draw_rect", |p| {
                engine::draw_rect(p, &a.layer_id, r, a.color_index, filled)
            })
            .await?;
            ok_json(json!({ "success": true, "pixels_set": n }))
        }
    }
}

// ---------------------------------------------------------------------------
// draw_ellipse
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct EllipseArgs {
    name: String,
    layer_id: String,
    #[serde(deserialize_with = "args::int")]
    cx: i64,
    #[serde(deserialize_with = "args::int")]
    cy: i64,
    #[serde(deserialize_with = "args::int")]
    rx: i64,
    #[serde(deserialize_with = "args::int")]
    ry: i64,
    #[serde(deserialize_with = "args::int")]
    color_index: u8,
    #[serde(default, deserialize_with = "args::opt_bool")]
    filled: Option<bool>,
}

sprite_tool! {
    DrawEllipseTool {
        name: "sprite_draw_ellipse",
        description: "Draw an ellipse centered at (cx, cy) with radii (rx, ry); the shape \
            spans exactly 2*rx+1 by 2*ry+1 pixels. Outlines are closed, 1px, gap-free. \
            A zero radius draws a line (both zero: one pixel). Clipped to the canvas. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "cx": { "type": "integer", "description": "Center X" },
                "cy": { "type": "integer", "description": "Center Y" },
                "rx": { "type": "integer", "minimum": 0, "description": "Radius X" },
                "ry": { "type": "integer", "minimum": 0, "description": "Radius Y" },
                "color_index": { "type": "integer", "minimum": 0, "maximum": 255 },
                "filled": { "type": "boolean", "default": false }
            },
            "required": ["name", "layer_id", "cx", "cy", "rx", "ry", "color_index"]
        }),
        execute: |ctx, a: EllipseArgs| {
            let filled = a.filled.unwrap_or(false);
            let n = edit_project(ctx, &a.name, "draw_ellipse", |p| {
                engine::draw_ellipse(p, &a.layer_id, (a.cx, a.cy), (a.rx, a.ry), a.color_index, filled)
            })
            .await?;
            ok_json(json!({ "success": true, "pixels_set": n }))
        }
    }
}

// ---------------------------------------------------------------------------
// flood_fill
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct FillArgs {
    name: String,
    layer_id: String,
    #[serde(deserialize_with = "args::int")]
    x: i64,
    #[serde(deserialize_with = "args::int")]
    y: i64,
    #[serde(deserialize_with = "args::int")]
    color_index: u8,
    #[serde(default, deserialize_with = "args::opt_bool")]
    contiguous: Option<bool>,
}

sprite_tool! {
    FloodFillTool {
        name: "sprite_flood_fill",
        description: "Fill from (x, y) with a palette color. Considers only this layer's \
            pixels; empty (transparent) counts as a color. contiguous=true (default) fills the \
            4-connected region via a scanline fill; contiguous=false replaces every pixel of \
            the start color on the layer. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "x": { "type": "integer", "description": "Start X (must be inside the canvas)" },
                "y": { "type": "integer", "description": "Start Y (must be inside the canvas)" },
                "color_index": { "type": "integer", "minimum": 0, "maximum": 255 },
                "contiguous": { "type": "boolean", "default": true }
            },
            "required": ["name", "layer_id", "x", "y", "color_index"]
        }),
        execute: |ctx, a: FillArgs| {
            let contiguous = a.contiguous.unwrap_or(true);
            let n = edit_project(ctx, &a.name, "flood_fill", |p| {
                engine::flood_fill(p, &a.layer_id, a.x, a.y, a.color_index, contiguous)
            })
            .await?;
            ok_json(json!({ "success": true, "pixels_filled": n }))
        }
    }
}

// ---------------------------------------------------------------------------
// get_pixels
// ---------------------------------------------------------------------------

/// Maximum pixels returned by one `sprite_get_pixels` call.
const MAX_READBACK: usize = 20_000;

#[derive(Deserialize)]
pub struct GetPixelsArgs {
    name: String,
    layer_id: String,
    #[serde(default, deserialize_with = "args::opt_json")]
    region: Option<RegionArg>,
    #[serde(default)]
    format: Option<String>,
}

sprite_tool! {
    GetPixelsTool {
        name: "sprite_get_pixels",
        description: "Read back a layer's pixels (optionally within a region) so edits can be \
            verified without rendering. format='list' (default) returns [x, y, color_index] \
            triples sorted by row; format='grid' returns one string per row where each cell \
            is the color index in hex (2 chars) or '..' for empty. Grid output requires a \
            region of at most 64x64.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "region": region_schema("Optional region to read (clipped to the canvas)"),
                "format": { "type": "string", "enum": ["list", "grid"], "default": "list" }
            },
            "required": ["name", "layer_id"]
        }),
        execute: |ctx, a: GetPixelsArgs| {
            let store = ctx.store.read().await;
            let p = get(&store, &a.name)?;
            let layer = engine::find_layer(p, &a.layer_id).map_err(invalid)?;
            let (x0, y0, x1, y1) = match a.region {
                Some(r) => {
                    let r: Region = r.into();
                    r.check().map_err(invalid)?;
                    crate::geometry::clip_rect(r.x, r.y, r.width, r.height, p.canvas.width, p.canvas.height)
                        .unwrap_or((0, 0, 0, 0))
                },
                None => (0, 0, p.canvas.width, p.canvas.height),
            };
            match a.format.as_deref().unwrap_or("list") {
                "list" => {
                    let mut px: Vec<[u32; 3]> = layer
                        .pixels
                        .iter()
                        .filter(|&(&(x, y), _)| x >= x0 && x < x1 && y >= y0 && y < y1)
                        .map(|(&(x, y), &c)| [x, y, u32::from(c)])
                        .collect();
                    px.sort_unstable_by_key(|p| (p[1], p[0]));
                    let total = px.len();
                    px.truncate(MAX_READBACK);
                    ok_json(json!({
                        "layer": layer.name,
                        "bounds": { "x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0 },
                        "count": total,
                        "truncated": total > MAX_READBACK,
                        "pixels": px
                    }))
                },
                "grid" => {
                    if a.region.is_none() || x1 - x0 > 64 || y1 - y0 > 64 {
                        return Err(invalid(
                            "format='grid' requires a region of at most 64x64".into(),
                        ));
                    }
                    let rows: Vec<String> = (y0..y1)
                        .map(|y| {
                            (x0..x1)
                                .map(|x| match layer.pixels.get(&(x, y)) {
                                    Some(c) => format!("{c:02x}"),
                                    None => "..".to_string(),
                                })
                                .collect()
                        })
                        .collect();
                    ok_json(json!({
                        "layer": layer.name,
                        "bounds": { "x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0 },
                        "rows": rows
                    }))
                },
                other => Err(invalid(format!(
                    "format must be 'list' or 'grid', got '{other}'"
                ))),
            }
        }
    }
}

//! Transform tool: flip, rotate, shift.

use serde::Deserialize;
use serde_json::json;

use super::{edit_project, ok_json, region_schema, sprite_tool};
use crate::args::{self, RegionArg};
use crate::engine;
use crate::types::TransformOp;

#[derive(Deserialize)]
pub struct TransformArgs {
    name: String,
    layer_id: String,
    operation: TransformOp,
    #[serde(default, deserialize_with = "args::opt_int")]
    shift_dx: Option<i64>,
    #[serde(default, deserialize_with = "args::opt_int")]
    shift_dy: Option<i64>,
    #[serde(default, deserialize_with = "args::opt_json")]
    region: Option<RegionArg>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    wrap: Option<bool>,
}

sprite_tool! {
    TransformTool {
        name: "sprite_transform",
        description: "Transform a layer's pixels: flip_h, flip_v, rotate_90_cw, rotate_90_ccw, \
            rotate_180, or shift (by shift_dx/shift_dy). Optionally constrained to a region \
            (e.g. one sprite cell). 90-degree rotations of a non-square region keep its \
            top-left corner fixed. Pixels pushed off the canvas are dropped and reported, \
            unless wrap=true for shift (wraps within the region or canvas). Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name" },
                "operation": {
                    "type": "string",
                    "enum": ["flip_h", "flip_v", "rotate_90_cw", "rotate_90_ccw", "rotate_180", "shift"]
                },
                "shift_dx": { "type": "integer", "default": 0, "description": "Shift X offset (for shift op)" },
                "shift_dy": { "type": "integer", "default": 0, "description": "Shift Y offset (for shift op)" },
                "region": region_schema("Optional region to constrain the transform (clipped to the canvas)"),
                "wrap": { "type": "boolean", "default": false, "description": "For shift: wrap pixels around instead of dropping them" }
            },
            "required": ["name", "layer_id", "operation"]
        }),
        execute: |ctx, a: TransformArgs| {
            let shift = (a.shift_dx.unwrap_or(0), a.shift_dy.unwrap_or(0));
            let wrap = a.wrap.unwrap_or(false);
            let rep = edit_project(ctx, &a.name, "transform", |p| {
                engine::transform_layer(p, &a.layer_id, a.operation, shift, a.region.map(Into::into), wrap)
            })
            .await?;
            ok_json(json!({
                "success": true,
                "operation": a.operation,
                "pixels_moved": rep.moved,
                "pixels_dropped": rep.dropped
            }))
        }
    }
}

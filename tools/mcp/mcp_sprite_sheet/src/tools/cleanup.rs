//! Edge cleanup tool: trim anti-aliasing fringe from an existing project.

use serde::Deserialize;
use serde_json::json;
use std::sync::Arc;

use super::{edit_project, ok_json, sprite_tool};
use crate::args;
use crate::engine;
use crate::import;

#[derive(Deserialize)]
pub struct TrimArgs {
    name: String,
    #[serde(default)]
    layer_id: Option<String>,
    #[serde(default, deserialize_with = "args::opt_int")]
    luma_threshold: Option<u8>,
    #[serde(default, deserialize_with = "args::opt_int")]
    passes: Option<u32>,
}

sprite_tool! {
    TrimEdgesTool {
        name: "sprite_trim_edges",
        description: "Remove anti-aliasing fringe from sprite edges (typically left over after \
            importing art drawn on a white background). An edge pixel is removed if its \
            luminance >= luma_threshold, if it is noticeably brighter than its filled \
            neighbors, or if it is isolated. Intended for imported art: it also removes \
            deliberate single-pixel details. Applies to one layer or all unlocked layers. \
            Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "layer_id": { "type": "string", "description": "Layer ID or unique name (omit for all unlocked layers)" },
                "luma_threshold": {
                    "type": "integer", "minimum": 0, "maximum": 255, "default": 190,
                    "description": "Absolute luminance cutoff. Values below 128 are also used as the relative-brightness delta (otherwise 25)."
                },
                "passes": { "type": "integer", "minimum": 1, "maximum": 10, "default": 3, "description": "Erosion passes; each pass exposes new edges" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: TrimArgs| {
            let luma = a.luma_threshold.unwrap_or(190);
            let passes = a.passes.unwrap_or(3).clamp(1, 10);
            let (trimmed, skipped, remaining) = edit_project(ctx, &a.name, "trim_edges", |p| {
                let targets: Vec<usize> = match &a.layer_id {
                    Some(key) => {
                        let i = engine::resolve_layer(p, key)?;
                        if p.layers[i].locked {
                            return Err(format!("Layer '{}' is locked", p.layers[i].name));
                        }
                        vec![i]
                    },
                    None => (0..p.layers.len()).collect(),
                };
                let (cw, ch) = (p.canvas.width, p.canvas.height);
                let palette = p.palette.clone();
                let mut trimmed = 0;
                let mut skipped = Vec::new();
                for i in targets {
                    let layer = &mut p.layers[i];
                    if layer.locked {
                        skipped.push(layer.name.clone());
                        continue;
                    }
                    let mut px = (*layer.pixels).clone();
                    let n = import::trim_border_fringe(&mut px, &palette, luma, passes, cw, ch);
                    if n > 0 {
                        layer.pixels = Arc::new(px);
                        trimmed += n;
                    }
                }
                Ok((trimmed, skipped, engine::total_pixels(p)))
            })
            .await?;
            ok_json(json!({
                "success": true,
                "pixels_trimmed": trimmed,
                "pixels_remaining": remaining,
                "locked_layers_skipped": skipped,
                "luma_threshold": luma,
                "passes": passes
            }))
        }
    }
}

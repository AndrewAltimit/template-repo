//! Image import tool: convert a reference image to an editable sprite project.

use mcp_core::prelude::*;
use serde::Deserialize;
use serde_json::json;
use std::path::PathBuf;
use std::sync::Arc;

use super::{invalid, ok_json, sprite_tool};
use crate::args::{self, Rgba};
use crate::engine;
use crate::import;
use crate::palette as presets;
use crate::types::{Grid, MAX_CANVAS_DIM};

#[derive(Deserialize)]
pub struct ImportArgs {
    name: String,
    image_path: String,
    #[serde(default)]
    layer_name: Option<String>,
    #[serde(default, deserialize_with = "args::opt_int")]
    max_width: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    max_height: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    alpha_threshold: Option<u8>,
    #[serde(default)]
    palette_preset: Option<String>,
    #[serde(default, deserialize_with = "args::opt_int")]
    max_colors: Option<u32>,
    #[serde(default)]
    background_color: Option<Rgba>,
    #[serde(default, deserialize_with = "args::opt_int")]
    bg_tolerance: Option<u8>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    trim_fringe: Option<bool>,
    #[serde(default, deserialize_with = "args::opt_int")]
    trim_luma_threshold: Option<u8>,
    #[serde(default, deserialize_with = "args::opt_int")]
    trim_passes: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    cell_width: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    cell_height: Option<u32>,
}

/// Everything the blocking import pipeline produces.
struct Imported {
    orig: (u32, u32),
    size: (u32, u32),
    palette: crate::types::Palette,
    pixels: crate::types::PixelMap,
    imported: usize,
    trimmed: usize,
    bg_removed: usize,
}

sprite_tool! {
    ImportImageTool {
        name: "sprite_import_image",
        description: "Import a reference image (PNG/JPEG/WebP/GIF, first frame) as a new \
            editable sprite project (replacing any project with the same name). Optionally \
            removes a background color, downsizes with nearest-neighbor to fit max_width/\
            max_height, maps each pixel to the nearest palette color (a preset, or up to \
            max_colors most frequent colors extracted from the image), and trims \
            anti-aliasing fringe. The file must be readable by the server process (in Docker \
            only /home is mounted, read-only). The result must fit the canvas limits \
            (4096 px per side, 4194304 px total); use max_width/max_height for large images.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name to create (overwrites if exists)" },
                "image_path": { "type": "string", "description": "Absolute path to the image file" },
                "layer_name": { "type": "string", "default": "imported", "description": "Name for the imported layer" },
                "max_width": { "type": "integer", "minimum": 1, "description": "Downscale to fit this width (nearest-neighbor, keeps aspect ratio)" },
                "max_height": { "type": "integer", "minimum": 1, "description": "Downscale to fit this height (nearest-neighbor, keeps aspect ratio)" },
                "alpha_threshold": { "type": "integer", "minimum": 0, "maximum": 255, "default": 128, "description": "Pixels with alpha below this are treated as transparent" },
                "palette_preset": { "type": "string", "enum": presets::preset_names(), "description": "Map to a preset palette. Omit to auto-extract from the image." },
                "max_colors": { "type": "integer", "minimum": 1, "maximum": 256, "default": 64, "description": "Max palette colors when auto-extracting" },
                "background_color": {
                    "type": "array", "items": { "type": "integer", "minimum": 0, "maximum": 255 },
                    "minItems": 3, "maxItems": 4,
                    "description": "Background RGB to make transparent, e.g. [255,255,255]"
                },
                "bg_tolerance": { "type": "integer", "minimum": 0, "maximum": 255, "default": 30, "description": "Per-channel tolerance for background removal" },
                "trim_fringe": { "type": "boolean", "default": true, "description": "Strip anti-aliasing fringe at sprite edges" },
                "trim_luma_threshold": { "type": "integer", "minimum": 0, "maximum": 255, "default": 200, "description": "Luminance cutoff for fringe trimming" },
                "trim_passes": { "type": "integer", "minimum": 1, "maximum": 5, "default": 3, "description": "Fringe erosion passes" },
                "cell_width": { "type": "integer", "minimum": 1, "description": "Grid cell width (default: whole image)" },
                "cell_height": { "type": "integer", "minimum": 1, "description": "Grid cell height (default: whole image)" }
            },
            "required": ["name", "image_path"]
        }),
        execute: |ctx, a: ImportArgs| {
            engine::validate_project_name(&a.name).map_err(invalid)?;
            let preset = match &a.palette_preset {
                Some(p) => Some(presets::from_preset(p).ok_or_else(|| {
                    invalid(format!(
                        "Unknown preset: {p}. Available: {}",
                        presets::preset_names().join(", ")
                    ))
                })?),
                None => None,
            };
            let path = PathBuf::from(&a.image_path);
            let alpha = a.alpha_threshold.unwrap_or(128);
            let max_colors = a.max_colors.unwrap_or(64).clamp(1, 256) as usize;
            let bg = a.background_color.map(|c| [c.0[0], c.0[1], c.0[2]]);
            let bg_tol = a.bg_tolerance.unwrap_or(30);
            let trim = a.trim_fringe.unwrap_or(true);
            let trim_luma = a.trim_luma_threshold.unwrap_or(200);
            let trim_passes = a.trim_passes.unwrap_or(3).clamp(1, 5);
            let (max_w, max_h) = (a.max_width, a.max_height);
            if max_w == Some(0) || max_h == Some(0) {
                return Err(invalid("max_width/max_height must be >= 1".into()));
            }

            // Decoding and pixel mapping are CPU/IO heavy: keep them off the runtime.
            let job = tokio::task::spawn_blocking(move || -> std::result::Result<Imported, String> {
                let mut img = import::load_image(&path)?;
                let orig = (img.width(), img.height());
                let bg_removed = bg.map_or(0, |c| import::remove_background(&mut img, c, bg_tol));
                let img = import::resize_to_fit(img, max_w, max_h);
                let size = (img.width(), img.height());
                engine::validate_canvas(size.0, size.1).map_err(|e| {
                    format!("{e}. Pass max_width/max_height (<= {MAX_CANVAS_DIM}) to downscale")
                })?;
                let palette = preset.unwrap_or_else(|| import::extract_palette(&img, max_colors, alpha));
                let mut pixels = import::map_to_palette(&img, &palette, alpha);
                let imported = pixels.len();
                let trimmed = if trim {
                    import::trim_border_fringe(&mut pixels, &palette, trim_luma, trim_passes, size.0, size.1)
                } else {
                    0
                };
                Ok(Imported { orig, size, palette, pixels, imported, trimmed, bg_removed })
            });
            let im = job
                .await
                .map_err(|e| MCPError::Internal(format!("import task failed: {e}")))?
                .map_err(invalid)?;

            let grid = Grid {
                cell_width: a.cell_width.unwrap_or(im.size.0).max(1),
                cell_height: a.cell_height.unwrap_or(im.size.1).max(1),
                padding: 0,
                margin: 0,
            };
            let mut project =
                engine::create_project(&a.name, im.size.0, im.size.1, grid, [0, 0, 0, 0], None)
                    .map_err(invalid)?;
            let palette_count = im.palette.colors.len();
            project.palette = im.palette;
            let layer_name = a.layer_name.unwrap_or_else(|| "imported".to_string());
            let layer_id = engine::add_layer(&mut project, &layer_name, None);
            let final_count = im.pixels.len();
            project.layers[0].pixels = Arc::new(im.pixels);

            let replaced = ctx.store.write().await.insert(a.name.clone(), project).is_some();
            ok_json(json!({
                "success": true,
                "project": a.name,
                "replaced_existing": replaced,
                "layer_id": layer_id,
                "original_size": { "width": im.orig.0, "height": im.orig.1 },
                "canvas": { "width": im.size.0, "height": im.size.1 },
                "palette_colors": palette_count,
                "background_pixels_removed": im.bg_removed,
                "pixels_imported": im.imported,
                "pixels_trimmed": im.trimmed,
                "pixels_final": final_count,
                "source": a.image_path
            }))
        }
    }
}

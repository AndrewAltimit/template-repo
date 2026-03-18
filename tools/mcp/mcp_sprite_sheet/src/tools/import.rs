//! Image import tool: convert a reference image to an editable sprite project.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

use super::parse::{json_as_u8, json_as_u32};
use crate::engine::{self, ProjectStore};
use crate::palette as palette_mod;

pub struct ImportImageTool {
    pub store: ProjectStore,
}

#[async_trait]
impl Tool for ImportImageTool {
    fn name(&self) -> &str {
        "sprite_import_image"
    }

    fn description(&self) -> &str {
        "Import a reference image (PNG/JPEG/WebP/GIF) as an editable sprite project. Reads the \
         image, optionally resizes it, maps each pixel to the nearest palette color, and creates \
         a fully editable sprite layer. If no palette preset is given, extracts colors from the \
         image automatically. The image file must be accessible inside the Docker container \
         (mounted via /home or /input)."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name to create (overwrites if exists)"
                },
                "image_path": {
                    "type": "string",
                    "description": "Absolute path to the image file"
                },
                "layer_name": {
                    "type": "string",
                    "default": "imported",
                    "description": "Name for the imported layer"
                },
                "max_width": {
                    "type": "integer",
                    "description": "Resize to fit this width (nearest-neighbor, preserves aspect ratio)"
                },
                "max_height": {
                    "type": "integer",
                    "description": "Resize to fit this height (nearest-neighbor, preserves aspect ratio)"
                },
                "alpha_threshold": {
                    "type": "integer",
                    "default": 128,
                    "description": "Pixels with alpha below this are treated as transparent (0-255)"
                },
                "palette_preset": {
                    "type": "string",
                    "description": "Palette preset (pico8, gameboy, nes, snes, endesga32). Omit to auto-extract from image."
                },
                "max_colors": {
                    "type": "integer",
                    "default": 64,
                    "description": "Max palette colors when auto-extracting (1-256)"
                },
                "background_color": {
                    "type": "array",
                    "items": { "type": "integer" },
                    "minItems": 3, "maxItems": 3,
                    "description": "Background RGB to treat as transparent, e.g. [255,255,255] for white bg. Pixels within bg_tolerance of this color are excluded."
                },
                "bg_tolerance": {
                    "type": "integer",
                    "default": 30,
                    "description": "Color distance tolerance for background removal (0-255 per channel). Higher = more aggressive."
                },
                "trim_fringe": {
                    "type": "boolean",
                    "default": true,
                    "description": "Strip anti-aliasing fringe (bright edge pixels near transparency). Enabled by default."
                },
                "trim_luma_threshold": {
                    "type": "integer",
                    "default": 200,
                    "description": "Luminance cutoff for fringe trimming (0-255). Pixels brighter than this on edges get removed."
                },
                "trim_passes": {
                    "type": "integer",
                    "default": 3,
                    "description": "Number of fringe erosion passes (1-5)"
                }
            },
            "required": ["name", "image_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args["name"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name'".to_string()))?;
        let image_path = args["image_path"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'image_path'".to_string()))?;
        let layer_name = args["layer_name"].as_str().unwrap_or("imported");
        let max_width = json_as_u32(&args["max_width"]);
        let max_height = json_as_u32(&args["max_height"]);
        let alpha_threshold = json_as_u8(&args["alpha_threshold"]).unwrap_or(128);
        let palette_preset = args["palette_preset"].as_str();
        let max_colors = json_as_u32(&args["max_colors"]).unwrap_or(64) as usize;

        // Parse background color removal
        let bg_color: Option<[u8; 3]> = args.get("background_color").and_then(|v| {
            let arr = v.as_array()?;
            if arr.len() >= 3 {
                Some([
                    json_as_u8(&arr[0])?,
                    json_as_u8(&arr[1])?,
                    json_as_u8(&arr[2])?,
                ])
            } else {
                None
            }
        });
        let bg_tolerance = json_as_u8(&args["bg_tolerance"]).unwrap_or(30);

        // Load image
        let mut img = image::open(image_path)
            .map_err(|e| MCPError::Internal(format!("Failed to load image '{image_path}': {e}")))?
            .to_rgba8();

        let orig_w = img.width();
        let orig_h = img.height();

        // Strip background color by setting matching pixels to fully transparent
        if let Some(bg) = bg_color {
            for pixel in img.pixels_mut() {
                let dr = (pixel.0[0] as i32 - bg[0] as i32).unsigned_abs();
                let dg = (pixel.0[1] as i32 - bg[1] as i32).unsigned_abs();
                let db = (pixel.0[2] as i32 - bg[2] as i32).unsigned_abs();
                if dr <= bg_tolerance as u32
                    && dg <= bg_tolerance as u32
                    && db <= bg_tolerance as u32
                {
                    pixel.0[3] = 0; // make transparent
                }
            }
        }

        // Resize if needed (nearest-neighbor to preserve pixel art)
        let img = resize_if_needed(img, max_width, max_height);
        let width = img.width();
        let height = img.height();

        // Determine palette
        let palette = if let Some(preset) = palette_preset {
            palette_mod::from_preset(preset).ok_or_else(|| {
                MCPError::InvalidParameters(format!(
                    "Unknown preset: {preset}. Available: {}",
                    palette_mod::preset_names().join(", ")
                ))
            })?
        } else {
            engine::extract_palette_from_image(&img, max_colors.clamp(1, 256), alpha_threshold)
        };

        // Map pixels to palette
        let (mut pixels, pixel_count) =
            engine::import_image_to_pixels(&img, &palette, alpha_threshold);
        let palette_count = palette.colors.len();

        // Trim anti-aliasing fringe if requested
        let trim_fringe = args["trim_fringe"].as_bool().unwrap_or(true);
        let trim_luma = json_as_u8(&args["trim_luma_threshold"]).unwrap_or(200);
        let trim_passes = json_as_u32(&args["trim_passes"]).unwrap_or(3).min(5);

        let trimmed = if trim_fringe {
            engine::trim_border_fringe(&mut pixels, &palette, trim_luma, trim_passes, width, height)
        } else {
            0
        };

        let final_pixel_count = pixels.len();

        // Create project (overwrite if exists)
        let mut store = self.store.write().await;

        let mut project =
            engine::create_project(name, width, height, width, height, 0, 0, [0, 0, 0, 0], None)
                .map_err(MCPError::InvalidParameters)?;

        project.palette = palette;

        let layer_id = engine::add_layer(&mut project, layer_name, None);
        let layer = engine::find_layer_mut(&mut project, &layer_id).map_err(MCPError::Internal)?;
        layer.pixels = pixels;

        store.insert(name.to_string(), project);

        ToolResult::json(&json!({
            "success": true,
            "project": name,
            "layer_id": layer_id,
            "original_size": { "width": orig_w, "height": orig_h },
            "canvas": { "width": width, "height": height },
            "palette_colors": palette_count,
            "pixels_imported": pixel_count,
            "pixels_trimmed": trimmed,
            "pixels_final": final_pixel_count,
            "source": image_path
        }))
    }
}

/// Resize image if it exceeds max dimensions, preserving aspect ratio with nearest-neighbor.
fn resize_if_needed(
    img: image::RgbaImage,
    max_width: Option<u32>,
    max_height: Option<u32>,
) -> image::RgbaImage {
    let w = img.width();
    let h = img.height();

    let scale_w = max_width
        .filter(|&mw| w > mw)
        .map(|mw| mw as f64 / w as f64);
    let scale_h = max_height
        .filter(|&mh| h > mh)
        .map(|mh| mh as f64 / h as f64);

    let scale = match (scale_w, scale_h) {
        (Some(sw), Some(sh)) => Some(sw.min(sh)),
        (Some(s), None) | (None, Some(s)) => Some(s),
        (None, None) => None,
    };

    match scale {
        Some(s) => {
            let nw = (w as f64 * s).round().max(1.0) as u32;
            let nh = (h as f64 * s).round().max(1.0) as u32;
            image::imageops::resize(&img, nw, nh, image::imageops::FilterType::Nearest)
        },
        None => img,
    }
}

//! Render and export tools: full sheet / region, single sprite, animation
//! frames, animated GIF, and texture atlas (PNG + JSON metadata).
//!
//! Every tool writes its files into the server's output directory (plain
//! file names only) and, unless `inline=false` or the image is larger than
//! [`MAX_INLINE_BYTES`], also returns the image inline as base64.
//! Compositing happens under a read lock; encoding and file I/O run after the
//! lock is released, with encoding on the blocking thread pool.

use image::RgbaImage;
use mcp_core::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};

use super::{Ctx, get, invalid, region_schema, sprite_tool};
use crate::args::{self, RegionArg};
use crate::engine;
use crate::files;
use crate::geometry;
use crate::persist;
use crate::render;
use crate::types::{LoopMode, OverlayOptions};

/// Images larger than this (encoded) are written to disk but not inlined.
pub const MAX_INLINE_BYTES: usize = 4 * 1024 * 1024;

/// Encode on the blocking pool.
async fn encode_png(img: RgbaImage) -> Result<Vec<u8>> {
    tokio::task::spawn_blocking(move || render::encode_png(&img))
        .await
        .map_err(|e| MCPError::Internal(format!("encode task failed: {e}")))?
        .map_err(MCPError::Internal)
}

/// Write bytes to the output dir and return the path as a string.
async fn write(ctx: &Ctx, filename: &str, bytes: Vec<u8>) -> Result<String> {
    files::write_output(&ctx.output_dir, filename, bytes)
        .await
        .map(|p| p.display().to_string())
        .map_err(MCPError::Internal)
}

/// Build a result: JSON metadata text plus optional inline images.
fn result(meta: Value, images: Vec<(Vec<u8>, &str)>, inline: bool) -> Result<ToolResult> {
    let mut content = vec![Content::json(&meta)?];
    if inline {
        for (bytes, mime) in images {
            if bytes.len() <= MAX_INLINE_BYTES {
                content.push(Content::Image {
                    data: render::to_base64(&bytes),
                    mime_type: mime.to_string(),
                });
            }
        }
    }
    Ok(ToolResult::with_content(content))
}

fn scale_of(s: Option<u32>) -> u32 {
    s.unwrap_or(1)
}

// ---------------------------------------------------------------------------
// render (full sheet or region)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct RenderArgs {
    name: String,
    #[serde(default, deserialize_with = "args::opt_json")]
    region: Option<RegionArg>,
    #[serde(default, deserialize_with = "args::opt_int")]
    scale: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_json")]
    overlays: Option<OverlayOptions>,
    #[serde(default)]
    filename: Option<String>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    inline: Option<bool>,
}

sprite_tool! {
    RenderTool {
        name: "sprite_render",
        description: "Render the full sheet (or a region) as PNG with nearest-neighbor scaling \
            (1-64). Optional debug overlays: grid_lines, bounding_boxes, anchors, hitboxes, \
            sprite_names; overlays are drawn after scaling so they stay 1px wide and align with \
            regions. Saves to the output directory and returns the file path plus the image \
            inline (unless inline=false or it exceeds 4 MB).",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "region": region_schema("Optional region to render (clipped to the canvas)"),
                "scale": { "type": "integer", "minimum": 1, "maximum": 64, "default": 1, "description": "Nearest-neighbor scale factor" },
                "overlays": {
                    "type": "object",
                    "properties": {
                        "grid_lines": { "type": "boolean" },
                        "bounding_boxes": { "type": "boolean" },
                        "anchors": { "type": "boolean" },
                        "hitboxes": { "type": "boolean" },
                        "sprite_names": { "type": "boolean" }
                    }
                },
                "filename": { "type": "string", "description": "Output file name (default: <project>_render.png); plain name only" },
                "inline": { "type": "boolean", "default": true, "description": "Return the image inline as base64" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: RenderArgs| {
            let scale = scale_of(a.scale);
            let overlays = a.overlays.unwrap_or_default();
            let fname = files::output_name(a.filename.as_deref(), &format!("{}_render", a.name), "png")
                .map_err(invalid)?;
            let img = {
                let store = ctx.store.read().await;
                let p = get(&store, &a.name)?;
                let (x0, y0, x1, y1) = match a.region {
                    Some(r) => {
                        let r: engine::Region = r.into();
                        r.check().map_err(invalid)?;
                        geometry::clip_rect(r.x, r.y, r.width, r.height, p.canvas.width, p.canvas.height)
                            .ok_or_else(|| invalid("Region lies entirely outside the canvas".into()))?
                    },
                    None => (0, 0, p.canvas.width, p.canvas.height),
                };
                let (w, h) = (x1 - x0, y1 - y0);
                render::check_output_size(w, h, scale).map_err(invalid)?;
                let mut img = render::scale_nearest(&render::composite_region(p, x0, y0, w, h), scale);
                if overlays.any() {
                    render::draw_overlays(&mut img, p, &overlays, (i64::from(x0), i64::from(y0)), scale);
                }
                img
            };
            let (w, h) = (img.width(), img.height());
            let png = encode_png(img).await?;
            let file = write(ctx, &fname, png.clone()).await?;
            result(
                json!({ "file": file, "width": w, "height": h, "scale": scale, "bytes": png.len() }),
                vec![(png, "image/png")],
                a.inline.unwrap_or(true),
            )
        }
    }
}

// ---------------------------------------------------------------------------
// render_sprite
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct RenderSpriteArgs {
    name: String,
    sprite_id: String,
    #[serde(default, deserialize_with = "args::opt_int")]
    scale: Option<u32>,
    #[serde(default)]
    filename: Option<String>,
    #[serde(default, deserialize_with = "args::opt_json")]
    overlays: Option<OverlayOptions>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    inline: Option<bool>,
}

sprite_tool! {
    RenderSpriteTool {
        name: "sprite_render_sprite",
        description: "Render a single sprite (by ID or name) as a standalone PNG, optionally \
            scaled and with overlays (anchors, hitboxes, ...). Saves to the output directory.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "sprite_id": { "type": "string", "description": "Sprite ID or unique name" },
                "scale": { "type": "integer", "minimum": 1, "maximum": 64, "default": 1 },
                "overlays": {
                    "type": "object",
                    "properties": {
                        "bounding_boxes": { "type": "boolean" },
                        "anchors": { "type": "boolean" },
                        "hitboxes": { "type": "boolean" },
                        "sprite_names": { "type": "boolean" },
                        "grid_lines": { "type": "boolean" }
                    }
                },
                "filename": { "type": "string", "description": "Output file name (default: <project>_<sprite_name>.png); plain name only" },
                "inline": { "type": "boolean", "default": true }
            },
            "required": ["name", "sprite_id"]
        }),
        execute: |ctx, a: RenderSpriteArgs| {
            let scale = scale_of(a.scale);
            let overlays = a.overlays.unwrap_or_default();
            let (img, fname, sprite_name) = {
                let store = ctx.store.read().await;
                let p = get(&store, &a.name)?;
                let i = engine::resolve_sprite(p, &a.sprite_id).map_err(invalid)?;
                let s = &p.sprites[i];
                let fname = files::output_name(a.filename.as_deref(), &format!("{}_{}", a.name, s.name), "png")
                    .map_err(invalid)?;
                let (x, y, w, h) = engine::sprite_pixel_bounds(p, s);
                render::check_output_size(w, h, scale).map_err(invalid)?;
                let mut img = render::scale_nearest(&render::composite_region(p, x, y, w, h), scale);
                if overlays.any() {
                    render::draw_overlays(&mut img, p, &overlays, (i64::from(x), i64::from(y)), scale);
                }
                (img, fname, s.name.clone())
            };
            let (w, h) = (img.width(), img.height());
            let png = encode_png(img).await?;
            let file = write(ctx, &fname, png.clone()).await?;
            result(
                json!({ "file": file, "sprite": sprite_name, "width": w, "height": h, "scale": scale }),
                vec![(png, "image/png")],
                a.inline.unwrap_or(true),
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Animation helpers
// ---------------------------------------------------------------------------

struct FrameImage {
    img: RgbaImage,
    sprite_id: String,
    sprite_name: String,
    duration_ms: u32,
}

/// Composite the sheet once and crop every frame of an animation.
fn animation_frames(
    p: &crate::types::SpriteProject,
    anim_key: &str,
    scale: u32,
) -> std::result::Result<(crate::types::AnimationDef, Vec<FrameImage>), String> {
    let ai = engine::resolve_animation(p, anim_key)?;
    let anim = p.animations[ai].clone();
    if anim.frames.is_empty() {
        return Err(format!("Animation '{}' has no frames", anim.name));
    }
    let sheet = render::composite(p);
    let mut out = Vec::with_capacity(anim.frames.len());
    for (i, f) in anim.frames.iter().enumerate() {
        let s = p
            .sprites
            .iter()
            .find(|s| s.id == f.sprite_id)
            .ok_or_else(|| format!("Frame {i} references missing sprite {}", f.sprite_id))?;
        let (x, y, w, h) = engine::sprite_pixel_bounds(p, s);
        render::check_output_size(w, h, scale)?;
        let img = render::scale_nearest(&render::crop_padded(&sheet, x, y, w, h), scale);
        out.push(FrameImage {
            img,
            sprite_id: s.id.clone(),
            sprite_name: s.name.clone(),
            duration_ms: f.duration_ms,
        });
    }
    Ok((anim, out))
}

// ---------------------------------------------------------------------------
// render_animation_frames
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct RenderFramesArgs {
    name: String,
    animation_id: String,
    #[serde(default, deserialize_with = "args::opt_int")]
    scale: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    inline: Option<bool>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    strip: Option<bool>,
}

sprite_tool! {
    RenderAnimationFramesTool {
        name: "sprite_render_animation_frames",
        description: "Render every frame of an animation (by ID or name) as individual PNGs \
            (<project>_<anim>_<NNN>.png) and return per-frame timing. With strip=true also \
            writes one horizontal strip PNG of all frames (frames of different sizes are \
            top-aligned).",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "animation_id": { "type": "string", "description": "Animation ID or unique name" },
                "scale": { "type": "integer", "minimum": 1, "maximum": 64, "default": 1 },
                "inline": { "type": "boolean", "default": true, "description": "Return frame images inline" },
                "strip": { "type": "boolean", "default": false, "description": "Also write a horizontal strip image" }
            },
            "required": ["name", "animation_id"]
        }),
        execute: |ctx, a: RenderFramesArgs| {
            let scale = scale_of(a.scale);
            let (anim, frames) = {
                let store = ctx.store.read().await;
                let p = get(&store, &a.name)?;
                animation_frames(p, &a.animation_id, scale).map_err(invalid)?
            };
            let stem = files::safe_stem(&format!("{}_{}", a.name, anim.name));
            let mut images = Vec::new();
            let mut paths = Vec::new();
            let mut timing = Vec::new();
            for (i, f) in frames.iter().enumerate() {
                let png = encode_png(f.img.clone()).await?;
                paths.push(write(ctx, &format!("{stem}_{i:03}.png"), png.clone()).await?);
                images.push((png, "image/png"));
                timing.push(json!({
                    "frame": i,
                    "sprite_id": f.sprite_id,
                    "sprite_name": f.sprite_name,
                    "duration_ms": f.duration_ms
                }));
            }
            let strip_file = if a.strip.unwrap_or(false) {
                let w: u64 = frames.iter().map(|f| u64::from(f.img.width())).sum();
                let h = frames.iter().map(|f| f.img.height()).max().unwrap_or(0);
                let w = u32::try_from(w).unwrap_or(u32::MAX);
                render::check_output_size(w, h, 1).map_err(invalid)?;
                let mut strip = RgbaImage::new(w, h);
                let mut x = 0i64;
                for f in &frames {
                    image::imageops::replace(&mut strip, &f.img, x, 0);
                    x += i64::from(f.img.width());
                }
                let png = encode_png(strip).await?;
                Some(write(ctx, &format!("{stem}_strip.png"), png).await?)
            } else {
                None
            };
            result(
                json!({
                    "animation": anim.name,
                    "loop_mode": anim.loop_mode,
                    "frame_count": frames.len(),
                    "total_duration_ms": anim.total_duration_ms(),
                    "files": paths,
                    "strip_file": strip_file,
                    "frames": timing
                }),
                images,
                a.inline.unwrap_or(true),
            )
        }
    }
}

// ---------------------------------------------------------------------------
// export_gif
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct ExportGifArgs {
    name: String,
    animation_id: String,
    #[serde(default, deserialize_with = "args::opt_int")]
    scale: Option<u32>,
    #[serde(default)]
    filename: Option<String>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    inline: Option<bool>,
}

sprite_tool! {
    ExportGifTool {
        name: "sprite_export_gif",
        description: "Export an animation (by ID or name) as an animated GIF honoring per-frame \
            durations and loop_mode (loop: repeat forever; once: play once; ping_pong: \
            forward then backward, repeating). GIF limitations: 10 ms timing resolution, \
            1-bit transparency (alpha < 128 becomes transparent), max 256 colors per frame.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "animation_id": { "type": "string", "description": "Animation ID or unique name" },
                "scale": { "type": "integer", "minimum": 1, "maximum": 64, "default": 1 },
                "filename": { "type": "string", "description": "Output file name (default: <project>_<anim>.gif); plain name only" },
                "inline": { "type": "boolean", "default": true, "description": "Return the GIF inline (image/gif)" }
            },
            "required": ["name", "animation_id"]
        }),
        execute: |ctx, a: ExportGifArgs| {
            let scale = scale_of(a.scale);
            let (anim, frames) = {
                let store = ctx.store.read().await;
                let p = get(&store, &a.name)?;
                animation_frames(p, &a.animation_id, scale).map_err(invalid)?
            };
            let fname = files::output_name(a.filename.as_deref(), &format!("{}_{}", a.name, anim.name), "gif")
                .map_err(invalid)?;
            let mut seq: Vec<(RgbaImage, u32)> =
                frames.iter().map(|f| (f.img.clone(), f.duration_ms)).collect();
            if anim.loop_mode == LoopMode::PingPong && seq.len() > 2 {
                let back: Vec<(RgbaImage, u32)> = seq[1..seq.len() - 1].iter().rev().cloned().collect();
                seq.extend(back);
            }
            let frame_count = seq.len();
            // GIF frames must share one size; pad smaller frames (top-left aligned).
            let w = seq.iter().map(|f| f.0.width()).max().unwrap_or(1);
            let h = seq.iter().map(|f| f.0.height()).max().unwrap_or(1);
            let seq: Vec<(RgbaImage, u32)> = seq
                .into_iter()
                .map(|(img, ms)| {
                    if img.width() == w && img.height() == h {
                        (img, ms)
                    } else {
                        (render::crop_padded(&img, 0, 0, w, h), ms)
                    }
                })
                .collect();
            let repeat = anim.loop_mode != LoopMode::Once;
            let gif = tokio::task::spawn_blocking(move || render::encode_gif(seq, repeat))
                .await
                .map_err(|e| MCPError::Internal(format!("encode task failed: {e}")))?
                .map_err(MCPError::Internal)?;
            let file = write(ctx, &fname, gif.clone()).await?;
            result(
                json!({
                    "file": file,
                    "animation": anim.name,
                    "loop_mode": anim.loop_mode,
                    "gif_frames": frame_count,
                    "width": w,
                    "height": h,
                    "bytes": gif.len()
                }),
                vec![(gif, "image/gif")],
                a.inline.unwrap_or(true),
            )
        }
    }
}

// ---------------------------------------------------------------------------
// export_atlas
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct ExportAtlasArgs {
    name: String,
    #[serde(default, deserialize_with = "args::opt_int")]
    scale: Option<u32>,
    #[serde(default)]
    filename: Option<String>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    inline: Option<bool>,
}

sprite_tool! {
    ExportAtlasTool {
        name: "sprite_export_atlas",
        description: "Export the sheet for game engines: writes <filename>.png (composited, no \
            overlays) and <filename>.json with every sprite's frame rectangle, anchor, \
            normalized pivot, hitbox, and tags, plus all animations with frame timing and loop \
            mode. Coordinates are in output pixels (multiplied by scale).",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "scale": { "type": "integer", "minimum": 1, "maximum": 64, "default": 1 },
                "filename": { "type": "string", "description": "Base file name without extension (default: <project>_atlas); plain name only" },
                "inline": { "type": "boolean", "default": false, "description": "Also return the PNG inline" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: ExportAtlasArgs| {
            let scale = scale_of(a.scale);
            let stem = match &a.filename {
                Some(f) => {
                    let f = f.trim();
                    let lower = f.to_ascii_lowercase();
                    let stem = [".png", ".json"]
                        .iter()
                        .find(|ext| lower.ends_with(*ext))
                        .map_or(f, |ext| &f[..f.len() - ext.len()]);
                    let checked = files::user_filename(stem, "png").map_err(invalid)?;
                    checked[..checked.len() - ".png".len()].to_string()
                },
                None => files::safe_stem(&format!("{}_atlas", a.name)),
            };
            let png_name = format!("{stem}.png");
            let (img, meta) = {
                let store = ctx.store.read().await;
                let p = get(&store, &a.name)?;
                render::check_output_size(p.canvas.width, p.canvas.height, scale).map_err(invalid)?;
                let img = render::scale_nearest(&render::composite(p), scale);
                (img, persist::atlas_json(p, &png_name, scale))
            };
            let png = encode_png(img).await?;
            let png_file = write(ctx, &png_name, png.clone()).await?;
            let json_bytes = serde_json::to_vec_pretty(&meta)
                .map_err(|e| MCPError::Internal(e.to_string()))?;
            let json_file = write(ctx, &format!("{stem}.json"), json_bytes).await?;
            result(
                json!({
                    "image_file": png_file,
                    "metadata_file": json_file,
                    "sprites": meta["frames"].as_array().map_or(0, Vec::len),
                    "animations": meta["animations"].as_array().map_or(0, Vec::len),
                    "metadata": meta
                }),
                vec![(png, "image/png")],
                a.inline.unwrap_or(false),
            )
        }
    }
}

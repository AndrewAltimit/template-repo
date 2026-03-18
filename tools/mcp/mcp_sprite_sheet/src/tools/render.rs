//! Render tools: full sheet, single sprite, animation frames.
//! All renders save PNG files to the output directory and return both
//! the base64-encoded image and the file path.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::path::PathBuf;

use crate::engine::{self, ProjectStore};
use crate::render;
use crate::types::OverlayOptions;

/// Save PNG bytes to output_dir/<filename>, return the full path.
fn save_png(
    output_dir: &std::path::Path,
    filename: &str,
    png_bytes: &[u8],
) -> std::result::Result<String, String> {
    let path = output_dir.join(filename);
    std::fs::write(&path, png_bytes)
        .map_err(|e| format!("Failed to write {}: {e}", path.display()))?;
    Ok(path.display().to_string())
}

// ---------------------------------------------------------------------------
// render (full sheet or region)
// ---------------------------------------------------------------------------

pub struct RenderTool {
    pub store: ProjectStore,
    pub output_dir: PathBuf,
}

#[async_trait]
impl Tool for RenderTool {
    fn name(&self) -> &str {
        "sprite_render"
    }

    fn description(&self) -> &str {
        "Render the full sprite sheet (or a region) as a PNG image. Saves to output directory and returns base64. Supports overlays (grid_lines, bounding_boxes, anchors, hitboxes) and nearest-neighbor scaling."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "region": {
                    "type": "object",
                    "properties": {
                        "x": { "type": "integer" },
                        "y": { "type": "integer" },
                        "width": { "type": "integer" },
                        "height": { "type": "integer" }
                    },
                    "description": "Optional region to render"
                },
                "scale": { "type": "integer", "default": 1, "description": "Nearest-neighbor scale factor" },
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
                "filename": { "type": "string", "description": "Output filename (default: <project>_render.png)" }
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

        let scale = args["scale"].as_u64().unwrap_or(1).max(1) as u32;

        let overlays: OverlayOptions = args
            .get("overlays")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .unwrap_or_default();

        let mut img = match args.get("region") {
            Some(r) if r.is_object() => {
                let rx = r["x"].as_u64().unwrap_or(0) as u32;
                let ry = r["y"].as_u64().unwrap_or(0) as u32;
                let rw = r["width"].as_u64().unwrap_or(project.canvas.width as u64) as u32;
                let rh = r["height"].as_u64().unwrap_or(project.canvas.height as u64) as u32;
                let mut img = render::composite_region(project, rx, ry, rw, rh);
                render::draw_overlays(&mut img, project, &overlays, 0, 0);
                img
            },
            _ => {
                let mut img = render::composite(project);
                render::draw_overlays(&mut img, project, &overlays, 0, 0);
                img
            },
        };

        img = render::scale_nearest(&img, scale);

        let png = render::encode_png(&img).map_err(MCPError::Internal)?;
        let b64 = render::png_to_base64(&png);

        let filename = args["filename"]
            .as_str()
            .map(String::from)
            .unwrap_or_else(|| format!("{pname}_render.png"));
        let file_path = save_png(&self.output_dir, &filename, &png).map_err(MCPError::Internal)?;

        Ok(ToolResult::with_content(vec![
            Content::text(json!({ "file": file_path }).to_string()),
            Content::Image {
                data: b64,
                mime_type: "image/png".to_string(),
            },
        ]))
    }
}

// ---------------------------------------------------------------------------
// render_sprite
// ---------------------------------------------------------------------------

pub struct RenderSpriteTool {
    pub store: ProjectStore,
    pub output_dir: PathBuf,
}

#[async_trait]
impl Tool for RenderSpriteTool {
    fn name(&self) -> &str {
        "sprite_render_sprite"
    }

    fn description(&self) -> &str {
        "Render a single sprite as a standalone PNG image. Saves to output directory."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "sprite_id": { "type": "string" },
                "scale": { "type": "integer", "default": 1 },
                "filename": { "type": "string", "description": "Output filename (default: <project>_<sprite_name>.png)" }
            },
            "required": ["name", "sprite_id"]
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

        let sprite_id = args["sprite_id"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'sprite_id'".to_string()))?;

        let sprite = project
            .sprites
            .iter()
            .find(|s| s.id == sprite_id)
            .ok_or_else(|| MCPError::InvalidParameters(format!("Sprite not found: {sprite_id}")))?;

        let (sx, sy, sw, sh) = engine::sprite_pixel_bounds(project, sprite);
        let scale = args["scale"].as_u64().unwrap_or(1).max(1) as u32;

        let mut img = render::composite_region(project, sx, sy, sw, sh);
        img = render::scale_nearest(&img, scale);

        let png = render::encode_png(&img).map_err(MCPError::Internal)?;
        let b64 = render::png_to_base64(&png);

        let filename = args["filename"]
            .as_str()
            .map(String::from)
            .unwrap_or_else(|| format!("{}_{}.png", pname, sprite.name));
        let file_path = save_png(&self.output_dir, &filename, &png).map_err(MCPError::Internal)?;

        Ok(ToolResult::with_content(vec![
            Content::text(json!({ "file": file_path }).to_string()),
            Content::Image {
                data: b64,
                mime_type: "image/png".to_string(),
            },
        ]))
    }
}

// ---------------------------------------------------------------------------
// render_animation_frames
// ---------------------------------------------------------------------------

pub struct RenderAnimationFramesTool {
    pub store: ProjectStore,
    pub output_dir: PathBuf,
}

#[async_trait]
impl Tool for RenderAnimationFramesTool {
    fn name(&self) -> &str {
        "sprite_render_animation_frames"
    }

    fn description(&self) -> &str {
        "Render all frames of an animation as individual PNG images. Saves to output directory."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "animation_id": { "type": "string" },
                "scale": { "type": "integer", "default": 1 }
            },
            "required": ["name", "animation_id"]
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

        let anim_id = args["animation_id"]
            .as_str()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'animation_id'".to_string()))?;

        let anim = project
            .animations
            .iter()
            .find(|a| a.id == anim_id)
            .ok_or_else(|| {
                MCPError::InvalidParameters(format!("Animation not found: {anim_id}"))
            })?;

        let scale = args["scale"].as_u64().unwrap_or(1).max(1) as u32;

        let mut content = Vec::new();
        let mut timing = Vec::new();
        let mut file_paths = Vec::new();

        for (i, frame) in anim.frames.iter().enumerate() {
            let sprite = project
                .sprites
                .iter()
                .find(|s| s.id == frame.sprite_id)
                .ok_or_else(|| {
                    MCPError::Internal(format!(
                        "Sprite {} referenced by frame {} not found",
                        frame.sprite_id, i
                    ))
                })?;

            let (sx, sy, sw, sh) = engine::sprite_pixel_bounds(project, sprite);
            let mut img = render::composite_region(project, sx, sy, sw, sh);
            img = render::scale_nearest(&img, scale);

            let png = render::encode_png(&img).map_err(MCPError::Internal)?;
            let b64 = render::png_to_base64(&png);

            let filename = format!("{}_{}_{:03}.png", pname, anim.name, i);
            let file_path =
                save_png(&self.output_dir, &filename, &png).map_err(MCPError::Internal)?;
            file_paths.push(file_path);

            content.push(Content::Image {
                data: b64,
                mime_type: "image/png".to_string(),
            });

            timing.push(json!({
                "frame": i,
                "sprite_id": frame.sprite_id,
                "sprite_name": sprite.name,
                "duration_ms": frame.duration_ms
            }));
        }

        // Add timing metadata as text content at the end
        content.push(Content::text(
            serde_json::to_string_pretty(&json!({
                "animation": anim.name,
                "loop_mode": anim.loop_mode,
                "frame_count": anim.frames.len(),
                "total_duration_ms": anim.frames.iter().map(|f| f.duration_ms).sum::<u32>(),
                "files": file_paths,
                "frames": timing
            }))
            .unwrap_or_default(),
        ));

        Ok(ToolResult::with_content(content))
    }
}

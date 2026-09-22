//! Project tools: create, save, load, status, list, delete, resize canvas.

use mcp_core::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};
use std::path::PathBuf;

use super::{edit_project, get, invalid, ok_json, sprite_tool};
use crate::args::{self, Rgba};
use crate::engine;
use crate::files;
use crate::palette;
use crate::persist;
use crate::types::Grid;

// ---------------------------------------------------------------------------
// create_project
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct CreateArgs {
    name: String,
    #[serde(deserialize_with = "args::int")]
    width: u32,
    #[serde(deserialize_with = "args::int")]
    height: u32,
    #[serde(default, deserialize_with = "args::opt_int")]
    cell_width: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    cell_height: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    padding: Option<u32>,
    #[serde(default, deserialize_with = "args::opt_int")]
    margin: Option<u32>,
    #[serde(default)]
    background_color: Option<Rgba>,
    #[serde(default)]
    palette_preset: Option<String>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    overwrite: Option<bool>,
}

sprite_tool! {
    CreateProjectTool {
        name: "sprite_create_project",
        description: "Create a new in-memory sprite sheet project with canvas size, grid \
            configuration, and optional palette preset. Without a preset the palette is \
            [0 transparent, 1 black, 2 white] and not enforced. Replaces an existing project \
            of the same name unless overwrite=false.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name (used as key)" },
                "width": { "type": "integer", "minimum": 1, "maximum": 4096, "description": "Canvas width in pixels" },
                "height": { "type": "integer", "minimum": 1, "maximum": 4096, "description": "Canvas height in pixels (width*height <= 4194304)" },
                "cell_width": { "type": "integer", "description": "Grid cell width", "default": 16 },
                "cell_height": { "type": "integer", "description": "Grid cell height", "default": 16 },
                "padding": { "type": "integer", "description": "Grid padding between cells", "default": 0 },
                "margin": { "type": "integer", "description": "Grid margin around edges", "default": 0 },
                "background_color": {
                    "type": "array", "items": { "type": "integer", "minimum": 0, "maximum": 255 },
                    "minItems": 3, "maxItems": 4,
                    "description": "Background RGBA [r,g,b,a] (default [0,0,0,0] = transparent)"
                },
                "palette_preset": {
                    "type": "string",
                    "enum": palette::preset_names(),
                    "description": "Palette preset name"
                },
                "overwrite": { "type": "boolean", "default": true, "description": "Replace an existing project with the same name" }
            },
            "required": ["name", "width", "height"]
        }),
        execute: |ctx, a: CreateArgs| {
            let grid = Grid {
                cell_width: a.cell_width.unwrap_or(16),
                cell_height: a.cell_height.unwrap_or(16),
                padding: a.padding.unwrap_or(0),
                margin: a.margin.unwrap_or(0),
            };
            let bg = a.background_color.map_or([0, 0, 0, 0], |c| c.0);
            let project = engine::create_project(
                &a.name,
                a.width,
                a.height,
                grid.clone(),
                bg,
                a.palette_preset.as_deref(),
            )
            .map_err(invalid)?;
            let palette_name = project.palette.name.clone();
            let mut store = ctx.store.write().await;
            let replaced = store.contains_key(&a.name);
            if replaced && a.overwrite == Some(false) {
                return Err(invalid(format!(
                    "Project '{}' already exists (overwrite=false)",
                    a.name
                )));
            }
            store.insert(a.name.clone(), project);
            ok_json(json!({
                "success": true,
                "project": a.name,
                "replaced_existing": replaced,
                "canvas": { "width": a.width, "height": a.height },
                "grid": grid,
                "palette": palette_name,
                "available_presets": palette::preset_names()
            }))
        }
    }
}

// ---------------------------------------------------------------------------
// save_project
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct SaveArgs {
    name: String,
    #[serde(default)]
    filename: Option<String>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    include_data: Option<bool>,
}

sprite_tool! {
    SaveProjectTool {
        name: "sprite_save_project",
        description: "Serialize a project to versioned JSON. Returns the JSON inline \
            (project_data) and, if 'filename' is given, also writes <filename>.json to the \
            output directory. Pixels are stored as [x, y, color_index] triples. Undo history \
            is not saved.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "filename": { "type": "string", "description": "Optional plain file name to write in the output directory ('.json' appended if missing)" },
                "include_data": { "type": "boolean", "default": true, "description": "Include project_data inline in the response (set false for large projects saved to a file)" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: SaveArgs| {
            let data = {
                let store = ctx.store.read().await;
                persist::to_json(get(&store, &a.name)?).map_err(MCPError::Internal)?
            };
            let file = match &a.filename {
                Some(f) => {
                    let fname = files::user_filename(f, "json").map_err(invalid)?;
                    let bytes = serde_json::to_vec_pretty(&data)
                        .map_err(|e| MCPError::Internal(e.to_string()))?;
                    let path = files::write_output(&ctx.output_dir, &fname, bytes)
                        .await
                        .map_err(MCPError::Internal)?;
                    Some(path.display().to_string())
                },
                None => None,
            };
            let include = a.include_data.unwrap_or(true) || file.is_none();
            let mut out = json!({
                "success": true,
                "format_version": crate::types::FORMAT_VERSION,
                "file": file,
            });
            if include {
                out["project_data"] = data;
            }
            ok_json(out)
        }
    }
}

// ---------------------------------------------------------------------------
// load_project
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct LoadArgs {
    #[serde(default, deserialize_with = "args::opt_json")]
    project_data: Option<Value>,
    #[serde(default)]
    file: Option<String>,
    #[serde(default)]
    name: Option<String>,
    #[serde(default, deserialize_with = "args::opt_bool")]
    overwrite: Option<bool>,
}

sprite_tool! {
    LoadProjectTool {
        name: "sprite_load_project",
        description: "Load a project into memory from JSON (as produced by \
            sprite_save_project), passed inline via 'project_data' or read from 'file'. \
            Validates the data, accepts older format versions, and repairs recoverable issues \
            (pixels outside the canvas, dangling animation frames) with warnings.",
        schema: json!({
            "type": "object",
            "properties": {
                "project_data": {
                    "type": "object",
                    "description": "Full project JSON (as returned by sprite_save_project)"
                },
                "file": {
                    "type": "string",
                    "description": "Path to a project .json file. Relative paths resolve against the output directory. Used when project_data is absent."
                },
                "name": { "type": "string", "description": "Load under this project name instead of the stored one" },
                "overwrite": { "type": "boolean", "default": true, "description": "Replace an already-loaded project with the same name" }
            }
        }),
        execute: |ctx, a: LoadArgs| {
            let data = match (a.project_data, &a.file) {
                (Some(d), _) => d,
                (None, Some(f)) => read_project_file(&ctx.output_dir, f).await?,
                (None, None) => {
                    return Err(invalid("Provide 'project_data' or 'file'".into()));
                },
            };
            let (project, report) =
                persist::from_json(data, a.name.as_deref()).map_err(invalid)?;
            let name = project.name.clone();
            let layers = project.layers.len();
            let pixels = engine::total_pixels(&project);
            let mut store = ctx.store.write().await;
            let replaced = store.contains_key(&name);
            if replaced && a.overwrite == Some(false) {
                return Err(invalid(format!(
                    "Project '{name}' is already loaded (overwrite=false)"
                )));
            }
            store.insert(name.clone(), project);
            ok_json(json!({
                "success": true,
                "project": name,
                "replaced_existing": replaced,
                "source_format_version": report.source_version,
                "layers": layers,
                "total_pixels": pixels,
                "warnings": report.warnings
            }))
        }
    }
}

async fn read_project_file(output_dir: &std::path::Path, file: &str) -> Result<Value> {
    let p = PathBuf::from(file);
    let path = if p.is_absolute() {
        p
    } else {
        output_dir.join(p)
    };
    let meta = tokio::fs::metadata(&path)
        .await
        .map_err(|e| invalid(format!("Cannot read '{}': {e}", path.display())))?;
    if !meta.is_file() {
        return Err(invalid(format!("'{}' is not a file", path.display())));
    }
    if meta.len() > persist::MAX_PROJECT_FILE_BYTES {
        return Err(invalid(format!(
            "'{}' is {} bytes; the limit is {}",
            path.display(),
            meta.len(),
            persist::MAX_PROJECT_FILE_BYTES
        )));
    }
    let bytes = tokio::fs::read(&path)
        .await
        .map_err(|e| invalid(format!("Cannot read '{}': {e}", path.display())))?;
    serde_json::from_slice(&bytes)
        .map_err(|e| invalid(format!("'{}' is not valid JSON: {e}", path.display())))
}

// ---------------------------------------------------------------------------
// project_status
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct NameArgs {
    name: String,
}

sprite_tool! {
    ProjectStatusTool {
        name: "sprite_project_status",
        description: "Summarize a project: canvas, grid (including how many cells fit), \
            palette, layers, sprites, animations, pixel counts, and undo/redo state.",
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
            let g = &p.grid;
            let cols = (p.canvas.width.saturating_sub(g.margin) + g.padding)
                / (g.cell_width + g.padding).max(1);
            let rows = (p.canvas.height.saturating_sub(g.margin) + g.padding)
                / (g.cell_height + g.padding).max(1);
            ok_json(json!({
                "project": a.name,
                "format_version": p.format_version,
                "canvas": {
                    "width": p.canvas.width,
                    "height": p.canvas.height,
                    "background_color": p.canvas.background_color
                },
                "grid": {
                    "cell_width": g.cell_width,
                    "cell_height": g.cell_height,
                    "padding": g.padding,
                    "margin": g.margin,
                    "columns": cols,
                    "rows": rows
                },
                "palette": {
                    "name": p.palette.name,
                    "colors": p.palette.colors.len(),
                    "enforce": p.palette.enforce
                },
                "layers": p.layers.len(),
                "sprites": p.sprites.len(),
                "animations": p.animations.len(),
                "total_pixels": engine::total_pixels(p),
                "pixels_with_undefined_color": engine::orphaned_pixels(p),
                "undo_depth": p.history.undo.len(),
                "redo_depth": p.history.redo.len(),
                "next_undo": p.history.undo.back().map(|s| s.label.clone()),
                "next_redo": p.history.redo.last().map(|s| s.label.clone())
            }))
        }
    }
}

// ---------------------------------------------------------------------------
// list_projects / delete_project
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct NoArgs {}

sprite_tool! {
    ListProjectsTool {
        name: "sprite_list_projects",
        description: "List all projects currently loaded in memory with basic stats.",
        schema: json!({ "type": "object", "properties": {} }),
        execute: |ctx, _a: NoArgs| {
            let store = ctx.store.read().await;
            let mut list: Vec<Value> = store
                .values()
                .map(|p| {
                    json!({
                        "name": p.name,
                        "canvas": [p.canvas.width, p.canvas.height],
                        "layers": p.layers.len(),
                        "sprites": p.sprites.len(),
                        "animations": p.animations.len(),
                        "total_pixels": engine::total_pixels(p)
                    })
                })
                .collect();
            list.sort_by(|a, b| a["name"].as_str().cmp(&b["name"].as_str()));
            ok_json(json!({ "projects": list, "output_dir": ctx.output_dir.display().to_string() }))
        }
    }
}

sprite_tool! {
    DeleteProjectTool {
        name: "sprite_delete_project",
        description: "Remove a project from memory (files already written are not touched). \
            Not undoable: save first if you may need it again.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: NameArgs| {
            let mut store = ctx.store.write().await;
            get(&store, &a.name)?;
            store.remove(&a.name);
            ok_json(json!({ "success": true, "deleted": a.name }))
        }
    }
}

// ---------------------------------------------------------------------------
// resize_canvas
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct ResizeArgs {
    name: String,
    #[serde(deserialize_with = "args::int")]
    width: u32,
    #[serde(deserialize_with = "args::int")]
    height: u32,
    #[serde(default, deserialize_with = "args::opt_int")]
    offset_x: Option<i64>,
    #[serde(default, deserialize_with = "args::opt_int")]
    offset_y: Option<i64>,
}

sprite_tool! {
    ResizeCanvasTool {
        name: "sprite_resize_canvas",
        description: "Resize the canvas (e.g. to add rows of sprite cells). Existing pixels \
            on every layer are shifted by (offset_x, offset_y); pixels that fall outside the \
            new canvas are discarded and counted. Undoable.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "width": { "type": "integer", "minimum": 1, "maximum": 4096 },
                "height": { "type": "integer", "minimum": 1, "maximum": 4096 },
                "offset_x": { "type": "integer", "default": 0, "description": "Shift content right by this many pixels (negative = left)" },
                "offset_y": { "type": "integer", "default": 0, "description": "Shift content down by this many pixels (negative = up)" }
            },
            "required": ["name", "width", "height"]
        }),
        execute: |ctx, a: ResizeArgs| {
            let (ox, oy) = (a.offset_x.unwrap_or(0), a.offset_y.unwrap_or(0));
            let dropped = edit_project(ctx, &a.name, "resize_canvas", |p| {
                engine::resize_canvas(p, a.width, a.height, ox, oy)
            })
            .await?;
            let store = ctx.store.read().await;
            let p = get(&store, &a.name)?;
            let invalid_sprites: Vec<&str> = p
                .sprites
                .iter()
                .filter(|s| engine::validate_sprite(p, s).is_err())
                .map(|s| s.name.as_str())
                .collect();
            ok_json(json!({
                "success": true,
                "canvas": { "width": a.width, "height": a.height },
                "pixels_dropped": dropped,
                "sprites_outside_canvas": invalid_sprites
            }))
        }
    }
}

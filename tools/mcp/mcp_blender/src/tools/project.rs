//! Project lifecycle and server status tools.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::paths;
use crate::server::{
    BlenderTool, Ctx, ToolError, ToolOutput, check_range, check_resolution, enum_prop,
};
use crate::types::{ProjectTemplate, RenderEngine};

/// Optional render settings applied when a project is created.
#[derive(Debug, Default, Deserialize, Serialize)]
pub struct ProjectSettings {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    resolution: Option<[u32; 2]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    fps: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    engine: Option<RenderEngine>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    frame_start: Option<i32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    frame_end: Option<i32>,
}

/// `create_blender_project` arguments.
#[derive(Debug, Deserialize)]
pub struct CreateProjectArgs {
    name: String,
    #[serde(default = "default_template")]
    template: ProjectTemplate,
    #[serde(default)]
    settings: ProjectSettings,
    #[serde(default)]
    overwrite: bool,
}

fn default_template() -> ProjectTemplate {
    ProjectTemplate::BasicScene
}

/// Create a `.blend` file from a template.
pub struct CreateProject;

#[async_trait]
impl BlenderTool for CreateProject {
    type Args = CreateProjectArgs;
    const NAME: &'static str = "create_blender_project";
    const DESCRIPTION: &'static str = "Create a new Blender project (.blend) from a template.\n\n\
Templates: empty (camera only), basic_scene (ground, sun, camera), studio_lighting (three area lights, dark world), \
lit_empty (bright lights, no ground), procedural (ground + subdivided 'ProceduralBase' grid for geometry nodes), \
animation (EEVEE, frame range), physics (rigid-body world with passive ground), architectural (sky, 24mm camera), \
product (backdrop + three-point lights, 85mm camera), vfx (transparent film + glare compositor), \
game_asset (metric units, EEVEE), sculpting (high-res sphere with Multires, Workbench/matcap).\n\
Fails if the project exists unless overwrite=true. Returns the project name to pass to other tools.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name (letters, digits, space, '.', '_', '-'; '.blend' is added automatically)"
                },
                "template": enum_prop(ProjectTemplate::ALL, Some("basic_scene"), "Template to start from"),
                "settings": {
                    "type": "object",
                    "description": "Render settings",
                    "properties": {
                        "resolution": { "type": "array", "items": { "type": "integer", "minimum": 1 }, "minItems": 2, "maxItems": 2, "default": [1920, 1080] },
                        "fps": { "type": "integer", "minimum": 1, "maximum": 240, "default": 24 },
                        "engine": enum_prop(RenderEngine::ALL, None, "Render engine (template default when omitted; EEVEE/Workbench need an OpenGL-capable host)"),
                        "frame_start": { "type": "integer", "description": "First frame (animation/physics templates)" },
                        "frame_end": { "type": "integer", "description": "Last frame (animation/physics templates)" }
                    }
                },
                "overwrite": { "type": "boolean", "default": false, "description": "Replace an existing project with the same name" }
            },
            "required": ["name"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let raw = args.name.trim();
        let stem = raw
            .strip_suffix(".blend")
            .or_else(|| raw.strip_suffix(".BLEND"))
            .unwrap_or(raw);
        let stem = paths::validate_file_name(stem)?;
        if let Some(res) = &args.settings.resolution {
            check_resolution(res)?;
        }
        if let Some(fps) = args.settings.fps {
            check_range("settings.fps", fps, 1, 240)?;
        }

        let file_name = format!("{stem}.blend");
        let project_path = paths::resolve_under(&ctx.config.projects_dir, &file_name)?;
        if project_path.exists() && !args.overwrite {
            return Err(ToolError::invalid(format!(
                "Project '{file_name}' already exists; pass overwrite=true to replace it"
            )));
        }

        let script_args = json!({
            "operation": "create_project",
            "project_path": project_path.to_string_lossy(),
            "template": args.template,
            "settings": args.settings,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project_path))
            .await?;

        Ok(json!({
            "success": true,
            "project_path": file_name,
            "full_path": project_path.to_string_lossy(),
            "template": args.template,
            "message": format!("Project '{file_name}' created from template '{}'", args.template),
            "result": result,
        }))
    }
}

/// `list_projects` takes no arguments.
#[derive(Debug, Deserialize)]
pub struct NoArgs {}

/// List `.blend` files in the projects directory.
pub struct ListProjects;

#[async_trait]
impl BlenderTool for ListProjects {
    type Args = NoArgs;
    const NAME: &'static str = "list_projects";
    const DESCRIPTION: &'static str = "List Blender projects (.blend files) in the projects directory, \
including one level of sub-directories, with size and modification time.";

    fn schema() -> Value {
        json!({ "type": "object", "properties": {} })
    }

    async fn run(ctx: &Ctx, _args: Self::Args) -> ToolOutput {
        let root = ctx.config.projects_dir.clone();
        let entries = tokio::task::spawn_blocking(move || scan_projects(&root, 1))
            .await
            .map_err(|e| ToolError::failed(format!("project scan failed: {e}")))?;
        let names: Vec<&str> = entries.iter().map(|e| e.name.as_str()).collect();
        Ok(json!({
            "success": true,
            "projects": names,
            "details": entries,
            "count": entries.len(),
            "projects_dir": ctx.config.projects_dir.to_string_lossy(),
        }))
    }
}

/// One entry of `list_projects`.
#[derive(Debug, Serialize, PartialEq)]
pub struct ProjectEntry {
    name: String,
    size_bytes: u64,
    modified: Option<String>,
}

/// Collect `.blend` files under `root` (recursing `depth` levels, skipping
/// hidden entries and Blender's `.blend1` backups).
pub fn scan_projects(root: &std::path::Path, depth: usize) -> Vec<ProjectEntry> {
    fn walk(
        root: &std::path::Path,
        dir: &std::path::Path,
        depth: usize,
        out: &mut Vec<ProjectEntry>,
    ) {
        let Ok(entries) = std::fs::read_dir(dir) else {
            return;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let file_name = entry.file_name().to_string_lossy().to_string();
            if file_name.starts_with('.') {
                continue;
            }
            let Ok(meta) = entry.metadata() else { continue };
            if meta.is_dir() {
                if depth > 0 {
                    walk(root, &path, depth - 1, out);
                }
            } else if path
                .extension()
                .is_some_and(|e| e.eq_ignore_ascii_case("blend"))
            {
                let name = path
                    .strip_prefix(root)
                    .unwrap_or(&path)
                    .to_string_lossy()
                    .replace('\\', "/");
                let modified = meta
                    .modified()
                    .ok()
                    .map(|t| chrono::DateTime::<chrono::Utc>::from(t).to_rfc3339());
                out.push(ProjectEntry {
                    name,
                    size_bytes: meta.len(),
                    modified,
                });
            }
        }
    }
    let mut out = Vec::new();
    walk(root, root, depth, &mut out);
    out.sort_by(|a, b| a.name.cmp(&b.name));
    out
}

/// Report configuration, Blender availability and job counts.
pub struct BlenderStatus;

#[async_trait]
impl BlenderTool for BlenderStatus {
    type Args = NoArgs;
    const NAME: &'static str = "blender_status";
    const DESCRIPTION: &'static str = "Get server status: Blender executable and version, working directories, \
concurrency limits, timeouts and job counts.";

    fn schema() -> Value {
        json!({ "type": "object", "properties": {} })
    }

    async fn run(ctx: &Ctx, _args: Self::Args) -> ToolOutput {
        let blender = ctx.exec.blender().await;
        let (queued, running, total) = ctx.jobs.counts();
        let (free_job_slots, free_operation_slots) = ctx.exec.available_slots();
        let config = &ctx.config;
        Ok(json!({
            "server": "blender",
            "version": env!("CARGO_PKG_VERSION"),
            "blender_available": blender.is_ok(),
            "blender_path": blender.as_ref().ok().map(|b| b.path.to_string_lossy().to_string()),
            "blender_version": blender.as_ref().ok().map(|b| b.version.clone()),
            "blender_error": blender.as_ref().err().map(|e| e.to_string()),
            "base_dir": config.base_dir.to_string_lossy(),
            "projects_dir": config.projects_dir.to_string_lossy(),
            "assets_dir": config.assets_dir.to_string_lossy(),
            "output_dir": config.output_dir.to_string_lossy(),
            "scripts_dir": config.scripts_dir.to_string_lossy(),
            "limits": {
                "max_concurrent_jobs": config.max_concurrent_jobs,
                "max_concurrent_operations": config.max_concurrent_operations,
                "free_job_slots": free_job_slots,
                "free_operation_slots": free_operation_slots,
                "operation_timeout_secs": config.operation_timeout.as_secs(),
                "job_timeout_secs": config.job_timeout.as_secs(),
            },
            "jobs": { "running": running, "queued": queued, "total": total },
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scan_finds_blend_files_one_level_deep() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();
        std::fs::write(root.join("b.blend"), b"x").unwrap();
        std::fs::write(root.join("a.BLEND"), b"xy").unwrap();
        std::fs::write(root.join("a.blend1"), b"backup").unwrap();
        std::fs::write(root.join(".hidden.blend"), b"x").unwrap();
        std::fs::write(root.join("notes.txt"), b"x").unwrap();
        std::fs::create_dir_all(root.join("sub/deeper")).unwrap();
        std::fs::write(root.join("sub/c.blend"), b"x").unwrap();
        std::fs::write(root.join("sub/deeper/d.blend"), b"x").unwrap();

        let names: Vec<String> = scan_projects(root, 1).into_iter().map(|e| e.name).collect();
        assert_eq!(names, vec!["a.BLEND", "b.blend", "sub/c.blend"]);
        let sizes: Vec<u64> = scan_projects(root, 0)
            .iter()
            .map(|e| e.size_bytes)
            .collect();
        assert_eq!(sizes, vec![2, 1]);
    }

    #[test]
    fn scan_of_missing_dir_is_empty() {
        assert!(scan_projects(std::path::Path::new("/definitely/missing/dir"), 1).is_empty());
    }
}

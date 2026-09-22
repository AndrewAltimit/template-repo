//! MCP tool implementations: thin, typed wrappers around the engine.
//!
//! Each tool is declared with [`sprite_tool!`], which generates the struct,
//! the `Tool` impl, and typed argument parsing via [`crate::args::parse`].

use mcp_core::prelude::*;
use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;

use crate::engine::{self, EResult, ProjectStore};
use crate::types::SpriteProject;

pub mod cleanup;
pub mod draw;
pub mod import;
pub mod layer;
pub mod palette;
pub mod project;
pub mod render;
pub mod sprite;
pub mod transform;
pub mod undo;

/// Shared state handed to every tool.
#[derive(Clone)]
pub struct Ctx {
    /// In-memory projects keyed by name.
    pub store: ProjectStore,
    /// Directory that receives every generated file.
    pub output_dir: Arc<PathBuf>,
}

impl Ctx {
    pub fn new(store: ProjectStore, output_dir: PathBuf) -> Self {
        Self {
            store,
            output_dir: Arc::new(output_dir),
        }
    }
}

/// Declare a tool: struct + `Tool` impl with typed argument parsing.
macro_rules! sprite_tool {
    (
        $(#[$meta:meta])*
        $ty:ident {
            name: $name:literal,
            description: $desc:expr,
            schema: $schema:expr,
            execute: |$ctx:ident, $args:ident : $argty:ty| $body:block $(,)?
        }
    ) => {
        $(#[$meta])*
        pub struct $ty {
            pub ctx: $crate::tools::Ctx,
        }

        impl $ty {
            pub fn new(ctx: $crate::tools::Ctx) -> Self {
                Self { ctx }
            }
        }

        #[async_trait::async_trait]
        impl mcp_core::tool::Tool for $ty {
            fn name(&self) -> &str {
                $name
            }
            fn description(&self) -> &str {
                $desc
            }
            fn schema(&self) -> serde_json::Value {
                $schema
            }
            async fn execute(
                &self,
                raw: serde_json::Value,
            ) -> mcp_core::error::Result<mcp_core::tool::ToolResult> {
                let $args: $argty = $crate::args::parse(raw)?;
                let $ctx: &$crate::tools::Ctx = &self.ctx;
                $body
            }
        }
    };
}
pub(crate) use sprite_tool;

/// Map an engine error to `InvalidParameters`.
pub fn invalid(e: String) -> MCPError {
    MCPError::InvalidParameters(e)
}

/// Look up a project, listing known projects in the error.
pub fn get<'a>(store: &'a HashMap<String, SpriteProject>, name: &str) -> Result<&'a SpriteProject> {
    store.get(name).ok_or_else(|| not_found(store, name))
}

/// Mutable project lookup, listing known projects in the error.
pub fn get_mut<'a>(
    store: &'a mut HashMap<String, SpriteProject>,
    name: &str,
) -> Result<&'a mut SpriteProject> {
    if !store.contains_key(name) {
        return Err(not_found(store, name));
    }
    store
        .get_mut(name)
        .ok_or_else(|| MCPError::Internal("project vanished".into()))
}

fn not_found(store: &HashMap<String, SpriteProject>, name: &str) -> MCPError {
    let mut names: Vec<&str> = store.keys().map(String::as_str).collect();
    names.sort_unstable();
    MCPError::InvalidParameters(format!(
        "Project not found: {name}. Loaded projects: [{}]",
        names.join(", ")
    ))
}

/// Run an undoable edit on a named project and return its result.
pub async fn edit_project<T>(
    ctx: &Ctx,
    name: &str,
    label: &str,
    f: impl FnOnce(&mut SpriteProject) -> EResult<T>,
) -> Result<T> {
    let mut store = ctx.store.write().await;
    let p = get_mut(&mut store, name)?;
    engine::edit(p, label, f).map_err(invalid)
}

/// JSON tool result helper.
pub fn ok_json(v: Value) -> Result<ToolResult> {
    ToolResult::json(&v)
}

/// Shared JSON schema fragment for a region object.
pub fn region_schema(description: &str) -> Value {
    serde_json::json!({
        "type": "object",
        "properties": {
            "x": { "type": "integer" },
            "y": { "type": "integer" },
            "width": { "type": "integer", "minimum": 1 },
            "height": { "type": "integer", "minimum": 1 }
        },
        "required": ["x", "y", "width", "height"],
        "description": description
    })
}

/// Build every tool this server exposes.
pub fn all(ctx: &Ctx) -> Vec<BoxedTool> {
    let c = || ctx.clone();
    vec![
        // Project (7)
        Arc::new(project::CreateProjectTool::new(c())),
        Arc::new(project::SaveProjectTool::new(c())),
        Arc::new(project::LoadProjectTool::new(c())),
        Arc::new(project::ProjectStatusTool::new(c())),
        Arc::new(project::ListProjectsTool::new(c())),
        Arc::new(project::DeleteProjectTool::new(c())),
        Arc::new(project::ResizeCanvasTool::new(c())),
        // Layers (7)
        Arc::new(layer::AddLayerTool::new(c())),
        Arc::new(layer::RemoveLayerTool::new(c())),
        Arc::new(layer::UpdateLayerTool::new(c())),
        Arc::new(layer::DuplicateLayerTool::new(c())),
        Arc::new(layer::MergeLayersTool::new(c())),
        Arc::new(layer::ClearLayerTool::new(c())),
        Arc::new(layer::ListLayersTool::new(c())),
        // Drawing (6)
        Arc::new(draw::SetPixelsTool::new(c())),
        Arc::new(draw::DrawLineTool::new(c())),
        Arc::new(draw::DrawRectTool::new(c())),
        Arc::new(draw::DrawEllipseTool::new(c())),
        Arc::new(draw::FloodFillTool::new(c())),
        Arc::new(draw::GetPixelsTool::new(c())),
        // Palette (3)
        Arc::new(palette::SetPaletteTool::new(c())),
        Arc::new(palette::SwapPaletteTool::new(c())),
        Arc::new(palette::GetPaletteTool::new(c())),
        // Sprites & animations (6)
        Arc::new(sprite::DefineSpriteTool::new(c())),
        Arc::new(sprite::RemoveSpriteTool::new(c())),
        Arc::new(sprite::ListSpritesTool::new(c())),
        Arc::new(sprite::DefineAnimationTool::new(c())),
        Arc::new(sprite::ListAnimationsTool::new(c())),
        Arc::new(sprite::RemoveAnimationTool::new(c())),
        // Transform (1)
        Arc::new(transform::TransformTool::new(c())),
        // Render & export (5)
        Arc::new(render::RenderTool::new(c())),
        Arc::new(render::RenderSpriteTool::new(c())),
        Arc::new(render::RenderAnimationFramesTool::new(c())),
        Arc::new(render::ExportGifTool::new(c())),
        Arc::new(render::ExportAtlasTool::new(c())),
        // Undo (1)
        Arc::new(undo::UndoTool::new(c())),
        // Import & cleanup (2)
        Arc::new(import::ImportImageTool::new(c())),
        Arc::new(cleanup::TrimEdgesTool::new(c())),
    ]
}

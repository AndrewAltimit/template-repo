//! MCP server: SpriteSheetServer with tool registration.

use mcp_core::prelude::*;
use std::path::PathBuf;
use std::sync::Arc;

use crate::engine::{self, ProjectStore};
use crate::tools;

/// Sprite sheet MCP server
pub struct SpriteSheetServer {
    store: ProjectStore,
    output_dir: PathBuf,
}

impl SpriteSheetServer {
    pub fn new(output_dir: PathBuf) -> Self {
        Self {
            store: engine::new_store(),
            output_dir,
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        let s = &self.store;
        let o = &self.output_dir;
        vec![
            // Project (4)
            Arc::new(tools::project::CreateProjectTool { store: s.clone() }),
            Arc::new(tools::project::SaveProjectTool { store: s.clone() }),
            Arc::new(tools::project::LoadProjectTool { store: s.clone() }),
            Arc::new(tools::project::ProjectStatusTool { store: s.clone() }),
            // Layers (7)
            Arc::new(tools::layer::AddLayerTool { store: s.clone() }),
            Arc::new(tools::layer::RemoveLayerTool { store: s.clone() }),
            Arc::new(tools::layer::UpdateLayerTool { store: s.clone() }),
            Arc::new(tools::layer::DuplicateLayerTool { store: s.clone() }),
            Arc::new(tools::layer::MergeLayersTool { store: s.clone() }),
            Arc::new(tools::layer::ClearLayerTool { store: s.clone() }),
            Arc::new(tools::layer::ListLayersTool { store: s.clone() }),
            // Drawing (5)
            Arc::new(tools::draw::SetPixelsTool { store: s.clone() }),
            Arc::new(tools::draw::DrawLineTool { store: s.clone() }),
            Arc::new(tools::draw::DrawRectTool { store: s.clone() }),
            Arc::new(tools::draw::DrawEllipseTool { store: s.clone() }),
            Arc::new(tools::draw::FloodFillTool { store: s.clone() }),
            // Palette (3)
            Arc::new(tools::palette::SetPaletteTool { store: s.clone() }),
            Arc::new(tools::palette::SwapPaletteTool { store: s.clone() }),
            Arc::new(tools::palette::GetPaletteTool { store: s.clone() }),
            // Sprites & Animations (5)
            Arc::new(tools::sprite::DefineSpriteToolImpl { store: s.clone() }),
            Arc::new(tools::sprite::RemoveSpriteTool { store: s.clone() }),
            Arc::new(tools::sprite::ListSpritesTool { store: s.clone() }),
            Arc::new(tools::sprite::DefineAnimationTool { store: s.clone() }),
            Arc::new(tools::sprite::ListAnimationsTool { store: s.clone() }),
            // Transform (1)
            Arc::new(tools::transform::TransformTool { store: s.clone() }),
            // Render (3)
            Arc::new(tools::render::RenderTool {
                store: s.clone(),
                output_dir: o.clone(),
            }),
            Arc::new(tools::render::RenderSpriteTool {
                store: s.clone(),
                output_dir: o.clone(),
            }),
            Arc::new(tools::render::RenderAnimationFramesTool {
                store: s.clone(),
                output_dir: o.clone(),
            }),
            // Undo (1)
            Arc::new(tools::undo::UndoTool { store: s.clone() }),
            // Import (1)
            Arc::new(tools::import::ImportImageTool { store: s.clone() }),
            // Cleanup (1)
            Arc::new(tools::cleanup::TrimEdgesTool { store: s.clone() }),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_has_31_tools() {
        let server = SpriteSheetServer::new(PathBuf::from("/tmp/sprites"));
        let tools = server.tools();
        assert_eq!(tools.len(), 31);
    }

    #[test]
    fn test_all_tool_names_unique() {
        let server = SpriteSheetServer::new(PathBuf::from("/tmp/sprites"));
        let tools = server.tools();
        let mut names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        let count = names.len();
        names.sort();
        names.dedup();
        assert_eq!(names.len(), count, "Duplicate tool names found");
    }

    #[test]
    fn test_all_tools_prefixed() {
        let server = SpriteSheetServer::new(PathBuf::from("/tmp/sprites"));
        for tool in server.tools() {
            assert!(
                tool.name().starts_with("sprite_"),
                "Tool {} not prefixed with sprite_",
                tool.name()
            );
        }
    }
}

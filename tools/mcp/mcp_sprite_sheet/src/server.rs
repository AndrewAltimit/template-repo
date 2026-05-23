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

/// Execute-path tests driven through the shared `mcp-testing` harness.
///
/// Unlike the `engine` unit tests, these exercise the real `Tool::execute`
/// JSON boundary (argument parsing -> engine call -> `ToolResult`) for several
/// tools that share one project store, plus the error paths for malformed or
/// inconsistent arguments.
#[cfg(test)]
mod execute_path_tests {
    use crate::engine;
    use crate::tools;
    use mcp_core::tool::{Content, ToolResult};
    use mcp_testing::{TestServer, assertions};
    use serde_json::json;

    /// Build a TestServer wired with several real tools sharing one store.
    fn server() -> TestServer {
        let store = engine::new_store();
        TestServer::new()
            .with_tool(tools::project::CreateProjectTool {
                store: store.clone(),
            })
            .with_tool(tools::project::ProjectStatusTool {
                store: store.clone(),
            })
            .with_tool(tools::layer::AddLayerTool {
                store: store.clone(),
            })
            .with_tool(tools::draw::SetPixelsTool { store })
    }

    /// Collect the text content of a tool result as a single string.
    fn result_text(result: &ToolResult) -> String {
        result
            .content
            .iter()
            .filter_map(|c| match c {
                Content::Text { text } => Some(text.as_str()),
                _ => None,
            })
            .collect()
    }

    #[tokio::test]
    async fn full_create_layer_draw_status_workflow() {
        let server = server();

        // Create a project.
        let res = server
            .call_tool(
                "sprite_create_project",
                json!({ "name": "hero", "width": 32, "height": 32 }),
            )
            .await
            .expect("create_project should succeed");
        assertions::assert_success(&res);
        assertions::assert_text_contains(&res, "hero");

        // Add a layer and pull the generated layer_id out of the result JSON.
        let res = server
            .call_tool(
                "sprite_add_layer",
                json!({ "name": "hero", "layer_name": "base" }),
            )
            .await
            .expect("add_layer should succeed");
        assertions::assert_success(&res);
        let parsed: serde_json::Value =
            serde_json::from_str(&result_text(&res)).expect("layer result is JSON");
        let layer_id = parsed["layer_id"]
            .as_str()
            .expect("layer_id present")
            .to_string();

        // Draw pixels onto the layer.
        let res = server
            .call_tool(
                "sprite_set_pixels",
                json!({
                    "name": "hero",
                    "layer_id": layer_id,
                    "pixels": [
                        { "x": 0, "y": 0, "color_index": 1 },
                        { "x": 1, "y": 1, "color_index": 2 }
                    ]
                }),
            )
            .await
            .expect("set_pixels should succeed");
        assertions::assert_success(&res);
        assertions::assert_text_contains(&res, "\"pixels_set\": 2");

        // Status reflects the layer and the drawn pixels.
        let res = server
            .call_tool("sprite_project_status", json!({ "name": "hero" }))
            .await
            .expect("status should succeed");
        assertions::assert_success(&res);
        assertions::assert_text_contains(&res, "\"layers\": 1");
        assertions::assert_text_contains(&res, "\"total_pixels\": 2");
    }

    #[tokio::test]
    async fn missing_required_arg_is_error_not_panic() {
        let server = server();
        // 'name' is required; omit it.
        let err = server
            .call_tool(
                "sprite_create_project",
                json!({ "width": 16, "height": 16 }),
            )
            .await
            .expect_err("missing 'name' should be an error");
        assert!(
            err.contains("name"),
            "error should mention the field: {err}"
        );
    }

    #[tokio::test]
    async fn operating_on_unknown_project_is_error() {
        let server = server();
        let err = server
            .call_tool(
                "sprite_add_layer",
                json!({ "name": "does_not_exist", "layer_name": "base" }),
            )
            .await
            .expect_err("adding a layer to an unknown project should error");
        assert!(
            err.contains("not found"),
            "error should explain the project is missing: {err}"
        );
    }

    #[tokio::test]
    async fn unknown_tool_name_is_error() {
        let server = server();
        let err = server
            .call_tool("sprite_does_not_exist", json!({}))
            .await
            .expect_err("calling an unregistered tool should error");
        assert!(err.contains("Tool not found"), "unexpected error: {err}");
    }
}

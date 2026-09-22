//! MCP server: SpriteSheetServer with tool registration.

use mcp_core::prelude::*;
use std::path::PathBuf;

use crate::engine;
use crate::tools::{self, Ctx};

/// Sprite sheet MCP server: one shared in-memory project store plus the
/// directory that receives every generated file.
pub struct SpriteSheetServer {
    ctx: Ctx,
}

impl SpriteSheetServer {
    pub fn new(output_dir: PathBuf) -> Self {
        Self {
            ctx: Ctx::new(engine::new_store(), output_dir),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        tools::all(&self.ctx)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn server() -> SpriteSheetServer {
        SpriteSheetServer::new(std::env::temp_dir().join("sprites-test"))
    }

    #[test]
    fn test_server_tool_count() {
        assert_eq!(server().tools().len(), 38);
    }

    #[test]
    fn test_all_tool_names_unique() {
        let tools = server().tools();
        let mut names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        let count = names.len();
        names.sort();
        names.dedup();
        assert_eq!(names.len(), count, "Duplicate tool names found");
    }

    #[test]
    fn test_all_tools_prefixed_and_have_object_schemas() {
        for tool in server().tools() {
            assert!(
                tool.name().starts_with("sprite_"),
                "Tool {} not prefixed with sprite_",
                tool.name()
            );
            let schema = tool.schema();
            assert_eq!(schema["type"], "object", "{} schema", tool.name());
            // Every required field must be declared in properties.
            if let Some(req) = schema["required"].as_array() {
                for r in req {
                    let r = r.as_str().unwrap();
                    assert!(
                        schema["properties"].get(r).is_some(),
                        "{}: required '{r}' missing from properties",
                        tool.name()
                    );
                }
            }
        }
    }

    #[test]
    fn test_original_tools_still_present() {
        // Backward compatibility: every tool from the 0.1 API must remain.
        let original = [
            "sprite_create_project",
            "sprite_save_project",
            "sprite_load_project",
            "sprite_project_status",
            "sprite_add_layer",
            "sprite_remove_layer",
            "sprite_update_layer",
            "sprite_duplicate_layer",
            "sprite_merge_layers",
            "sprite_clear_layer",
            "sprite_list_layers",
            "sprite_set_pixels",
            "sprite_draw_line",
            "sprite_draw_rect",
            "sprite_draw_ellipse",
            "sprite_flood_fill",
            "sprite_set_palette",
            "sprite_swap_palette",
            "sprite_get_palette",
            "sprite_define_sprite",
            "sprite_remove_sprite",
            "sprite_list_sprites",
            "sprite_define_animation",
            "sprite_list_animations",
            "sprite_transform",
            "sprite_render",
            "sprite_render_sprite",
            "sprite_render_animation_frames",
            "sprite_undo",
            "sprite_import_image",
            "sprite_trim_edges",
        ];
        let tools = server().tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        for n in original {
            assert!(names.contains(&n), "missing {n}");
        }
    }
}

/// Execute-path tests driven through the shared `mcp-testing` harness.
///
/// These exercise the real `Tool::execute` JSON boundary (argument parsing ->
/// engine call -> `ToolResult`) for tools sharing one project store and one
/// temporary output directory.
#[cfg(test)]
mod execute_path_tests {
    use super::*;
    use mcp_core::tool::{Content, ToolResult};
    use mcp_testing::{TestServer, assertions};
    use serde_json::{Value, json};

    struct Harness {
        server: TestServer,
        dir: PathBuf,
    }

    impl Drop for Harness {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.dir);
        }
    }

    fn harness() -> Harness {
        let dir = std::env::temp_dir().join(format!("sprites-exec-{}", uuid::Uuid::new_v4()));
        let ctx = Ctx::new(engine::new_store(), dir.clone());
        let mut server = TestServer::new();
        for t in tools::all(&ctx) {
            server = server.with_tool(Boxed(t));
        }
        Harness { server, dir }
    }

    /// Adapter so boxed tools can be registered with `TestServer::with_tool`.
    struct Boxed(BoxedTool);

    #[async_trait::async_trait]
    impl Tool for Boxed {
        fn name(&self) -> &str {
            self.0.name()
        }
        fn description(&self) -> &str {
            self.0.description()
        }
        fn schema(&self) -> Value {
            self.0.schema()
        }
        async fn execute(&self, args: Value) -> mcp_core::error::Result<ToolResult> {
            self.0.execute(args).await
        }
    }

    fn text(result: &ToolResult) -> String {
        result
            .content
            .iter()
            .filter_map(|c| match c {
                Content::Text { text } => Some(text.as_str()),
                _ => None,
            })
            .collect()
    }

    fn body(result: &ToolResult) -> Value {
        serde_json::from_str(&text(result)).expect("tool result text is JSON")
    }

    fn images(result: &ToolResult) -> usize {
        result
            .content
            .iter()
            .filter(|c| matches!(c, Content::Image { .. }))
            .count()
    }

    async fn call(h: &Harness, tool: &str, args: Value) -> Value {
        let r = h
            .server
            .call_tool(tool, args.clone())
            .await
            .unwrap_or_else(|e| panic!("{tool}({args}) failed: {e}"));
        assertions::assert_success(&r);
        body(&r)
    }

    async fn call_err(h: &Harness, tool: &str, args: Value) -> String {
        h.server
            .call_tool(tool, args)
            .await
            .expect_err("expected an error")
    }

    /// Create project "hero" (32x16, 16px cells, pico8) with one layer "base".
    async fn setup(h: &Harness) -> String {
        call(
            h,
            "sprite_create_project",
            json!({ "name": "hero", "width": 32, "height": 16, "palette_preset": "pico8" }),
        )
        .await;
        let r = call(
            h,
            "sprite_add_layer",
            json!({ "name": "hero", "layer_name": "base" }),
        )
        .await;
        r["layer_id"].as_str().unwrap().to_string()
    }

    #[tokio::test]
    async fn full_create_layer_draw_status_workflow() {
        let h = harness();
        let layer = setup(&h).await;
        let r = call(
            &h,
            "sprite_set_pixels",
            json!({
                "name": "hero",
                "layer_id": layer,
                "pixels": [
                    { "x": 0, "y": 0, "color_index": 1 },
                    [1, 1, 2],
                    { "x": 99, "y": 0, "color_index": 1 },
                    { "x": 2, "y": 2, "color_index": 200 }
                ]
            }),
        )
        .await;
        assert_eq!(r["pixels_set"], 2);
        assert_eq!(r["skipped_out_of_bounds"], 1);
        assert_eq!(r["skipped_invalid_color"], 1);

        let r = call(&h, "sprite_project_status", json!({ "name": "hero" })).await;
        assert_eq!(r["layers"], 1);
        assert_eq!(r["total_pixels"], 2);
        assert_eq!(r["grid"]["columns"], 2);
        assert_eq!(r["next_undo"], "set_pixels");
    }

    #[tokio::test]
    async fn missing_required_arg_is_error_not_panic() {
        let h = harness();
        let err = call_err(
            &h,
            "sprite_create_project",
            json!({ "width": 16, "height": 16 }),
        )
        .await;
        assert!(
            err.contains("name"),
            "error should mention the field: {err}"
        );
    }

    #[tokio::test]
    async fn wrong_types_and_ranges_are_errors() {
        let h = harness();
        let layer = setup(&h).await;
        let err = call_err(
            &h,
            "sprite_draw_line",
            json!({ "name": "hero", "layer_id": layer, "x0": 0, "y0": 0, "x1": 3, "y1": 0, "color_index": 999 }),
        )
        .await;
        assert!(err.contains("color_index"), "{err}");
        let err = call_err(
            &h,
            "sprite_update_layer",
            json!({ "name": "hero", "layer_id": "base", "blend_mode": "dodge" }),
        )
        .await;
        assert!(err.contains("blend_mode"), "{err}");
        // Numeric strings are accepted.
        call(
            &h,
            "sprite_draw_rect",
            json!({ "name": "hero", "layer_id": "base", "x": "0", "y": "0", "width": "4", "height": 4, "color_index": 8 }),
        )
        .await;
    }

    #[tokio::test]
    async fn operating_on_unknown_project_is_error() {
        let h = harness();
        let err = call_err(
            &h,
            "sprite_add_layer",
            json!({ "name": "does_not_exist", "layer_name": "base" }),
        )
        .await;
        assert!(err.contains("not found"), "{err}");
    }

    #[tokio::test]
    async fn unknown_tool_name_is_error() {
        let h = harness();
        let err = call_err(&h, "sprite_does_not_exist", json!({})).await;
        assert!(err.contains("Tool not found"), "{err}");
    }

    #[tokio::test]
    async fn undo_covers_clear_and_failed_ops_leave_no_history() {
        let h = harness();
        let layer = setup(&h).await;
        call(
            &h,
            "sprite_flood_fill",
            json!({ "name": "hero", "layer_id": layer, "x": 0, "y": 0, "color_index": 3 }),
        )
        .await;
        call(
            &h,
            "sprite_clear_layer",
            json!({ "name": "hero", "layer_id": "base" }),
        )
        .await;
        // A failing edit (out-of-canvas fill start) must not add history.
        call_err(
            &h,
            "sprite_flood_fill",
            json!({ "name": "hero", "layer_id": layer, "x": 500, "y": 0, "color_index": 3 }),
        )
        .await;
        let r = call(&h, "sprite_undo", json!({ "name": "hero" })).await;
        assert_eq!(r["operations"], json!(["clear_layer"]));
        let r = call(&h, "sprite_project_status", json!({ "name": "hero" })).await;
        assert_eq!(r["total_pixels"], 32 * 16);
    }

    #[tokio::test]
    async fn save_to_file_and_load_back() {
        let h = harness();
        let layer = setup(&h).await;
        call(
            &h,
            "sprite_draw_ellipse",
            json!({ "name": "hero", "layer_id": layer, "cx": 8, "cy": 8, "rx": 5, "ry": 4, "color_index": 8, "filled": true }),
        )
        .await;
        let saved = call(
            &h,
            "sprite_save_project",
            json!({ "name": "hero", "filename": "hero_save" }),
        )
        .await;
        let file = saved["file"].as_str().unwrap().to_string();
        assert!(file.ends_with("hero_save.json"));
        assert!(saved["project_data"]["layers"][0]["pixels"].is_array());

        let r = call(
            &h,
            "sprite_load_project",
            json!({ "file": "hero_save.json", "name": "copy" }),
        )
        .await;
        assert_eq!(r["project"], "copy");
        let a = call(&h, "sprite_project_status", json!({ "name": "hero" })).await;
        let b = call(&h, "sprite_project_status", json!({ "name": "copy" })).await;
        assert_eq!(a["total_pixels"], b["total_pixels"]);

        // Inline load also still works (original API).
        let r = call(
            &h,
            "sprite_load_project",
            json!({ "project_data": saved["project_data"].clone() }),
        )
        .await;
        assert_eq!(r["project"], "hero");
    }

    #[tokio::test]
    async fn output_filenames_cannot_escape_output_dir() {
        let h = harness();
        setup(&h).await;
        for bad in [
            "../evil.png",
            "/etc/evil.png",
            "sub/dir.png",
            "..\\evil.png",
        ] {
            let err = call_err(
                &h,
                "sprite_render",
                json!({ "name": "hero", "filename": bad }),
            )
            .await;
            assert!(err.contains("plain file name"), "{bad}: {err}");
        }
        // Hostile project names are sanitized in default filenames.
        call(
            &h,
            "sprite_create_project",
            json!({ "name": "../../x", "width": 4, "height": 4 }),
        )
        .await;
        let r = h
            .server
            .call_tool("sprite_render", json!({ "name": "../../x" }))
            .await
            .unwrap();
        let file = PathBuf::from(body(&r)["file"].as_str().unwrap());
        assert_eq!(file.parent().unwrap(), h.dir.as_path());
    }

    #[tokio::test]
    async fn render_sprite_animation_gif_and_atlas() {
        let h = harness();
        let layer = setup(&h).await;
        call(
            &h,
            "sprite_draw_rect",
            json!({ "name": "hero", "layer_id": layer, "x": 2, "y": 2, "width": 10, "height": 10, "color_index": 8, "filled": true }),
        )
        .await;
        call(
            &h,
            "sprite_define_sprite",
            json!({ "name": "hero", "sprite_name": "f0", "grid_x": 0, "grid_y": 0, "anchor_x": 8, "anchor_y": 16 }),
        )
        .await;
        call(
            &h,
            "sprite_define_sprite",
            json!({ "name": "hero", "sprite_name": "f1", "grid_x": 1, "grid_y": 0 }),
        )
        .await;
        call(
            &h,
            "sprite_define_animation",
            json!({ "name": "hero", "anim_name": "walk", "loop_mode": "ping_pong",
                    "frames": [{ "sprite_id": "f0", "duration_ms": 80 }, { "sprite_id": "f1" }] }),
        )
        .await;

        let r = h
            .server
            .call_tool(
                "sprite_render",
                json!({ "name": "hero", "scale": 4, "overlays": { "grid_lines": true, "sprite_names": true } }),
            )
            .await
            .unwrap();
        assert_eq!(images(&r), 1);
        assert_eq!(body(&r)["width"], 128);

        let r = h
            .server
            .call_tool(
                "sprite_render_sprite",
                json!({ "name": "hero", "sprite_id": "f0", "scale": 2, "inline": false }),
            )
            .await
            .unwrap();
        assert_eq!(images(&r), 0);
        assert!(std::path::Path::new(body(&r)["file"].as_str().unwrap()).exists());

        let r = h
            .server
            .call_tool(
                "sprite_render_animation_frames",
                json!({ "name": "hero", "animation_id": "walk", "strip": true }),
            )
            .await
            .unwrap();
        assert_eq!(images(&r), 2);
        let b = body(&r);
        assert_eq!(b["total_duration_ms"], 180);
        assert!(
            b["strip_file"]
                .as_str()
                .unwrap()
                .ends_with("hero_walk_strip.png")
        );

        let r = h
            .server
            .call_tool(
                "sprite_export_gif",
                json!({ "name": "hero", "animation_id": "walk", "scale": 2 }),
            )
            .await
            .unwrap();
        let b = body(&r);
        let gif = std::fs::read(b["file"].as_str().unwrap()).unwrap();
        assert_eq!(&gif[0..6], b"GIF89a");

        let b = call(
            &h,
            "sprite_export_atlas",
            json!({ "name": "hero", "filename": "sheet" }),
        )
        .await;
        assert!(b["image_file"].as_str().unwrap().ends_with("sheet.png"));
        let meta: Value =
            serde_json::from_slice(&std::fs::read(b["metadata_file"].as_str().unwrap()).unwrap())
                .unwrap();
        assert_eq!(meta["frames"][0]["name"], "f0");
        assert_eq!(meta["animations"][0]["frames"][1]["sprite"], "f1");

        // Oversized render is rejected, not attempted.
        let err = call_err(
            &h,
            "sprite_render",
            json!({ "name": "hero", "scale": 1000 }),
        )
        .await;
        assert!(err.contains("scale"), "{err}");
    }

    #[tokio::test]
    async fn get_pixels_grid_readback() {
        let h = harness();
        let layer = setup(&h).await;
        call(
            &h,
            "sprite_draw_ellipse",
            json!({ "name": "hero", "layer_id": layer, "cx": 1, "cy": 1, "rx": 1, "ry": 1, "color_index": 10 }),
        )
        .await;
        let r = call(
            &h,
            "sprite_get_pixels",
            json!({ "name": "hero", "layer_id": "base", "format": "grid",
                    "region": { "x": 0, "y": 0, "width": 3, "height": 3 } }),
        )
        .await;
        assert_eq!(r["rows"], json!(["..0a..", "0a..0a", "..0a.."]));
    }

    #[tokio::test]
    async fn import_image_from_disk() {
        let h = harness();
        std::fs::create_dir_all(&h.dir).unwrap();
        let src = h.dir.join("src.png");
        let mut img = image::RgbaImage::from_pixel(8, 8, image::Rgba([255, 255, 255, 255]));
        for y in 2..6 {
            for x in 2..6 {
                img.put_pixel(x, y, image::Rgba([200, 30, 30, 255]));
            }
        }
        img.save(&src).unwrap();
        let r = call(
            &h,
            "sprite_import_image",
            json!({ "name": "imp", "image_path": src.to_string_lossy(), "background_color": [255, 255, 255] }),
        )
        .await;
        assert_eq!(r["canvas"]["width"], 8);
        assert_eq!(r["pixels_final"], 16);
        assert_eq!(r["palette_colors"], 1);

        let err = call_err(
            &h,
            "sprite_import_image",
            json!({ "name": "imp2", "image_path": h.dir.join("missing.png").to_string_lossy() }),
        )
        .await;
        assert!(err.contains("Cannot read image"), "{err}");
    }
}

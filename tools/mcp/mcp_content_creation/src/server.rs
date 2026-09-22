//! MCP tool definitions for the content creation server.
//!
//! Each tool deserializes its arguments into a typed struct from
//! [`crate::types`] (bad input becomes `InvalidParameters`, never a panic),
//! delegates to [`ContentEngine`], and returns the engine's JSON result. When
//! the result has `success: false` the MCP response is flagged `isError`.

use std::sync::Arc;

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::Serialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};

use crate::engine::{
    ContentEngine, DPI_RANGE, EngineConfig, MAX_PREVIEW_PAGES, PREVIEW_DPI_HIGH,
    PREVIEW_DPI_STANDARD,
};
use crate::types::{
    CompileLatexArgs, LatexFormat, LatexTemplate, ManimArgs, ManimFormat, ManimQuality,
    PreviewPdfArgs, RenderTikzArgs, ResponseMode, TikzFormat,
};

/// Server name reported over MCP.
pub const SERVER_NAME: &str = "content-creation";
/// Server version reported over MCP (from Cargo.toml).
pub const SERVER_VERSION: &str = env!("CARGO_PKG_VERSION");

/// Content creation MCP server: owns the engine and hands out tools.
pub struct ContentCreationServer {
    engine: Arc<ContentEngine>,
}

impl ContentCreationServer {
    /// Create the server (and its output directories).
    pub fn new(config: EngineConfig) -> Self {
        Self {
            engine: Arc::new(ContentEngine::new(config)),
        }
    }

    /// All tools as boxed trait objects.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let e = &self.engine;
        vec![
            Arc::new(CompileLatexTool(e.clone())),
            Arc::new(RenderTikzTool(e.clone())),
            Arc::new(PreviewPdfTool(e.clone())),
            Arc::new(CreateManimAnimationTool(e.clone())),
            Arc::new(ContentCreationStatusTool(e.clone())),
        ]
    }
}

/// Deserialize tool arguments, mapping failures to `InvalidParameters`.
fn parse_args<T: DeserializeOwned>(tool: &str, args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args)
        .map_err(|e| MCPError::InvalidParameters(format!("{}: {}", tool, e)))
}

/// Serialize a result, flagging it as an MCP error when `success` is false.
fn respond<T: Serialize>(value: &T, success: bool) -> Result<ToolResult> {
    let mut result = ToolResult::json(value)?;
    result.is_error = !success;
    Ok(result)
}

fn enum_values(values: &[&str]) -> Value {
    Value::from(values.to_vec())
}

fn response_mode_schema(standard: &str) -> Value {
    json!({
        "type": "string",
        "enum": enum_values(ResponseMode::VALUES),
        "default": "standard",
        "description": format!("minimal: paths only. standard: {}", standard)
    })
}

// ============================================================================
// Tool: compile_latex
// ============================================================================

struct CompileLatexTool(Arc<ContentEngine>);

#[async_trait]
impl Tool for CompileLatexTool {
    fn name(&self) -> &str {
        "compile_latex"
    }

    fn description(&self) -> &str {
        "Compile a LaTeX document to PDF, DVI, or PostScript.\n\n\
         Provide exactly one of 'content' (inline LaTeX) or 'input_path' (a .tex file inside the \
         project root; sibling files such as \\input chapters, images, and .bib files are found \
         automatically). Runs pdflatex (PDF) or latex (+dvips for PS), re-running as needed for \
         cross-references and tables of contents, and runs BibTeX when the document uses \
         \\bibliography. Compilation is sandboxed: no shell escape, no reads/writes outside the \
         working directory. Optionally renders PNG previews of selected pages. \
         Returns output_path (host-relative), container_path, page_count, warnings, and on \
         failure the LaTeX error lines."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "LaTeX source (alternative to input_path). A fragment without \\documentclass needs a template other than 'custom'."
                },
                "input_path": {
                    "type": "string",
                    "description": "Path to a .tex file, relative to the project root (or absolute inside it). Alternative to content."
                },
                "output_format": {
                    "type": "string",
                    "enum": enum_values(LatexFormat::VALUES),
                    "default": "pdf",
                    "description": "Output format ('format' is accepted as an alias)"
                },
                "template": {
                    "type": "string",
                    "enum": enum_values(LatexTemplate::VALUES),
                    "default": "custom",
                    "description": "Wrap a fragment in this document class (with amsmath/amssymb/graphicx). Ignored when the content has \\documentclass. 'custom' uses content verbatim."
                },
                "response_mode": response_mode_schema("+format, timing, LaTeX passes, previews"),
                "preview_pages": {
                    "type": "string",
                    "default": "none",
                    "description": format!("PDF pages to render as PNG: 'none', '1', '1,3,5', '2-4', '5-', 'all' (max {} pages)", MAX_PREVIEW_PAGES)
                },
                "preview_dpi": {
                    "type": "integer",
                    "default": PREVIEW_DPI_STANDARD,
                    "minimum": DPI_RANGE.0,
                    "maximum": DPI_RANGE.1,
                    "description": "DPI for preview images (72=low, 150=standard, 300=high)"
                },
                "visual_feedback": {
                    "type": "boolean",
                    "default": false,
                    "description": "Shortcut for preview_pages='1' when preview_pages is not given"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: CompileLatexArgs = parse_args(self.name(), args)?;
        let result = self.0.compile_latex(args).await;
        respond(&result, result.success)
    }
}

// ============================================================================
// Tool: render_tikz
// ============================================================================

struct RenderTikzTool(Arc<ContentEngine>);

#[async_trait]
impl Tool for RenderTikzTool {
    fn name(&self) -> &str {
        "render_tikz"
    }

    fn description(&self) -> &str {
        "Render a TikZ diagram as a standalone PDF, PNG, or SVG.\n\n\
         tikz_code may be a full tikzpicture environment, bare TikZ commands (wrapped \
         automatically), or a complete standalone document. The libraries arrows.meta, \
         positioning, shapes, and calc are always loaded; add more with tikz_libraries and \
         extra packages (e.g. pgfplots) with packages."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "tikz_code": {
                    "type": "string",
                    "description": "TikZ code: a tikzpicture environment, bare TikZ commands, or a full document"
                },
                "output_format": {
                    "type": "string",
                    "enum": enum_values(TikzFormat::VALUES),
                    "default": "pdf",
                    "description": "Output format for the diagram"
                },
                "tikz_libraries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra TikZ libraries to load (e.g. ['decorations.pathmorphing', 'matrix'])"
                },
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra LaTeX packages to load (e.g. ['pgfplots', 'xcolor'])"
                },
                "dpi": {
                    "type": "integer",
                    "default": PREVIEW_DPI_HIGH,
                    "minimum": DPI_RANGE.0,
                    "maximum": DPI_RANGE.1,
                    "description": "Resolution for PNG output"
                },
                "response_mode": response_mode_schema("+format, LaTeX passes, intermediate pdf_path")
            },
            "required": ["tikz_code"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: RenderTikzArgs = parse_args(self.name(), args)?;
        let result = self.0.render_tikz(args).await;
        respond(&result, result.success)
    }
}

// ============================================================================
// Tool: preview_pdf
// ============================================================================

struct PreviewPdfTool(Arc<ContentEngine>);

#[async_trait]
impl Tool for PreviewPdfTool {
    fn name(&self) -> &str {
        "preview_pdf"
    }

    fn description(&self) -> &str {
        "Render pages of an existing PDF as PNG images.\n\n\
         pdf_path must be inside the project root or the server's output directory (e.g. the \
         container_path returned by compile_latex)."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "Path to the PDF (relative to the project root, or absolute inside the project root / output directory)"
                },
                "pages": {
                    "type": "string",
                    "default": "1",
                    "description": format!("Pages to render: '1', '1,3,5', '2-4', '5-', 'all' (max {} pages)", MAX_PREVIEW_PAGES)
                },
                "dpi": {
                    "type": "integer",
                    "default": PREVIEW_DPI_STANDARD,
                    "minimum": DPI_RANGE.0,
                    "maximum": DPI_RANGE.1,
                    "description": "Resolution for preview images"
                },
                "response_mode": response_mode_schema("+pdf_path, page_count, pages_exported")
            },
            "required": ["pdf_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: PreviewPdfArgs = parse_args(self.name(), args)?;
        let result = self.0.preview_pdf(args).await;
        respond(&result, result.success)
    }
}

// ============================================================================
// Tool: create_manim_animation
// ============================================================================

struct CreateManimAnimationTool(Arc<ContentEngine>);

#[async_trait]
impl Tool for CreateManimAnimationTool {
    fn name(&self) -> &str {
        "create_manim_animation"
    }

    fn description(&self) -> &str {
        "Render a Manim Community Edition scene to MP4, GIF, WebM, or a PNG of the last frame.\n\n\
         The script must define a top-level Scene subclass (e.g. `class Intro(Scene):`) and \
         normally starts with `from manim import *`. If several scenes are defined, the first \
         is rendered unless scene_name is given. The script is executed as Python inside the \
         server's container with a timeout."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "Manim Python script defining at least one Scene subclass"
                },
                "output_format": {
                    "type": "string",
                    "enum": enum_values(ManimFormat::VALUES),
                    "default": "mp4",
                    "description": "Output format. 'png' saves the last frame as a still image."
                },
                "scene_name": {
                    "type": "string",
                    "description": "Scene class to render (default: first Scene subclass in the script)"
                },
                "quality": {
                    "type": "string",
                    "enum": enum_values(ManimQuality::VALUES),
                    "default": "low",
                    "description": "Render quality: low=480p15, medium=720p30, high=1080p60, production=1440p60, fourk=2160p60"
                },
                "preview": {
                    "type": "boolean",
                    "default": false,
                    "description": "Render only the last frame as PNG (fast check before a full render)"
                }
            },
            "required": ["script"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: ManimArgs = parse_args(self.name(), args)?;
        let result = self.0.create_manim_animation(args).await;
        respond(&result, result.success)
    }
}

// ============================================================================
// Tool: content_creation_status
// ============================================================================

struct ContentCreationStatusTool(Arc<ContentEngine>);

#[async_trait]
impl Tool for ContentCreationStatusTool {
    fn name(&self) -> &str {
        "content_creation_status"
    }

    fn description(&self) -> &str {
        "Report server configuration and which external tools (pdflatex, latex, bibtex, dvips, \
         pdfinfo, pdftoppm, pdf2svg, manim) are installed, with versions."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let cfg = self.0.config();
        let deps = self.0.dependency_status().await;
        let missing: Vec<&str> = deps
            .iter()
            .filter(|d| !d.available)
            .map(|d| d.name)
            .collect();

        let response = json!({
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "initialized": true,
            "output_dir": cfg.output_dir.display().to_string(),
            "project_root": cfg.project_root.display().to_string(),
            "host_output_dir": cfg.host_output_dir,
            "latex_timeout_seconds": cfg.latex_timeout.as_secs(),
            "manim_timeout_seconds": cfg.manim_timeout.as_secs(),
            "max_concurrent_jobs": cfg.max_concurrent_jobs,
            "dependencies": deps,
            "missing_dependencies": missing,
        });
        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::Binaries;
    use mcp_core::Content;

    fn server() -> (ContentCreationServer, tempfile::TempDir) {
        let dir = tempfile::tempdir().unwrap();
        let mut cfg = EngineConfig::new(dir.path().join("out"), dir.path().to_path_buf());
        let missing = |n: &str| format!("/nonexistent-mcp-test-dir/{}", n);
        cfg.binaries = Binaries {
            pdflatex: missing("pdflatex"),
            latex: missing("latex"),
            dvips: missing("dvips"),
            bibtex: missing("bibtex"),
            pdfinfo: missing("pdfinfo"),
            pdftoppm: missing("pdftoppm"),
            pdf2svg: missing("pdf2svg"),
            manim: missing("manim"),
        };
        (ContentCreationServer::new(cfg), dir)
    }

    fn tool(server: &ContentCreationServer, name: &str) -> BoxedTool {
        server
            .tools()
            .into_iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("tool {name} missing"))
    }

    fn text(result: &ToolResult) -> Value {
        match &result.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap(),
            other => panic!("unexpected content {other:?}"),
        }
    }

    #[test]
    fn exposes_backward_compatible_tool_names() {
        let (s, _d) = server();
        let names: Vec<String> = s.tools().iter().map(|t| t.name().to_string()).collect();
        assert_eq!(
            names,
            [
                "compile_latex",
                "render_tikz",
                "preview_pdf",
                "create_manim_animation",
                "content_creation_status"
            ]
        );
    }

    #[test]
    fn schemas_keep_required_params() {
        let (s, _d) = server();
        let required = |name: &str| tool(&s, name).schema()["required"].clone();
        assert_eq!(required("render_tikz"), json!(["tikz_code"]));
        assert_eq!(required("preview_pdf"), json!(["pdf_path"]));
        assert_eq!(required("create_manim_animation"), json!(["script"]));
        assert!(required("compile_latex").is_null());
        let fmt = &tool(&s, "compile_latex").schema()["properties"]["output_format"]["enum"];
        assert_eq!(fmt, &json!(["pdf", "dvi", "ps"]));
    }

    #[tokio::test]
    async fn missing_required_argument_is_invalid_parameters() {
        let (s, _d) = server();
        let err = tool(&s, "render_tikz")
            .execute(json!({}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));
        assert!(err.to_string().contains("tikz_code"));
    }

    #[tokio::test]
    async fn wrong_type_is_invalid_parameters() {
        let (s, _d) = server();
        let err = tool(&s, "preview_pdf")
            .execute(json!({"pdf_path": "a.pdf", "dpi": "high"}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));

        let err = tool(&s, "compile_latex")
            .execute(json!({"content": "x", "output_format": "png"}))
            .await
            .unwrap_err();
        assert!(err.to_string().contains("expected one of"));
    }

    #[tokio::test]
    async fn engine_failures_are_flagged_as_errors() {
        let (s, _d) = server();
        let result = tool(&s, "compile_latex").execute(json!({})).await.unwrap();
        assert!(result.is_error);
        let body = text(&result);
        assert_eq!(body["success"], json!(false));
        assert!(body["error"].as_str().unwrap().contains("content"));
    }

    #[tokio::test]
    async fn null_arguments_are_accepted() {
        let (s, _d) = server();
        let result = tool(&s, "compile_latex")
            .execute(Value::Null)
            .await
            .unwrap();
        assert!(result.is_error);
    }

    #[tokio::test]
    async fn status_reports_config_and_missing_dependencies() {
        let (s, _d) = server();
        let result = tool(&s, "content_creation_status")
            .execute(json!({}))
            .await
            .unwrap();
        assert!(!result.is_error);
        let body = text(&result);
        assert_eq!(body["server"], json!(SERVER_NAME));
        assert_eq!(body["version"], json!(SERVER_VERSION));
        assert_eq!(body["missing_dependencies"].as_array().unwrap().len(), 8);
        assert_eq!(body["latex_timeout_seconds"], json!(120));
    }
}

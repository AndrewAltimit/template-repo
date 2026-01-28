//! MCP server implementation for content creation.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::engine::{ContentEngine, PREVIEW_DPI_STANDARD};
use crate::types::{LatexTemplate, ManimFormat, OutputFormat, ResponseMode};

/// Content creation MCP server
pub struct ContentCreationServer {
    engine: Arc<RwLock<Option<ContentEngine>>>,
    output_dir: PathBuf,
    project_root: PathBuf,
}

impl ContentCreationServer {
    /// Create a new content creation server
    pub fn new(output_dir: PathBuf, project_root: PathBuf) -> Self {
        Self {
            engine: Arc::new(RwLock::new(None)),
            output_dir,
            project_root,
        }
    }

    /// Ensure engine is initialized
    #[allow(dead_code)]
    async fn ensure_initialized(&self) -> Result<()> {
        let mut guard = self.engine.write().await;
        if guard.is_none() {
            info!("Initializing content creation engine...");
            let engine = ContentEngine::new(self.output_dir.clone(), self.project_root.clone());
            *guard = Some(engine);
        }
        Ok(())
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(CompileLatexTool {
                server: self.clone_refs(),
            }),
            Arc::new(RenderTikzTool {
                server: self.clone_refs(),
            }),
            Arc::new(PreviewPdfTool {
                server: self.clone_refs(),
            }),
            Arc::new(CreateManimAnimationTool {
                server: self.clone_refs(),
            }),
            Arc::new(ContentCreationStatusTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            engine: self.engine.clone(),
            output_dir: self.output_dir.clone(),
            project_root: self.project_root.clone(),
        }
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    engine: Arc<RwLock<Option<ContentEngine>>>,
    output_dir: PathBuf,
    project_root: PathBuf,
}

impl ServerRefs {
    async fn ensure_initialized(&self) -> Result<()> {
        let mut guard = self.engine.write().await;
        if guard.is_none() {
            info!("Initializing content creation engine...");
            let engine = ContentEngine::new(self.output_dir.clone(), self.project_root.clone());
            *guard = Some(engine);
        }
        Ok(())
    }
}

// ============================================================================
// Tool: compile_latex
// ============================================================================

struct CompileLatexTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CompileLatexTool {
    fn name(&self) -> &str {
        "compile_latex"
    }

    fn description(&self) -> &str {
        r#"Compile LaTeX documents to various formats.

Supports PDF, DVI, and PS output formats. Can compile from inline content or from a .tex file path."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "LaTeX document content (alternative to input_path)"
                },
                "input_path": {
                    "type": "string",
                    "description": "Path to .tex file to compile (alternative to content)"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["pdf", "dvi", "ps"],
                    "default": "pdf",
                    "description": "Output format"
                },
                "template": {
                    "type": "string",
                    "enum": ["article", "report", "book", "beamer", "custom"],
                    "default": "custom",
                    "description": "Document template (ignored if content has documentclass)"
                },
                "response_mode": {
                    "type": "string",
                    "enum": ["minimal", "standard"],
                    "default": "standard",
                    "description": "minimal: path only. standard: +previews and metadata"
                },
                "preview_pages": {
                    "type": "string",
                    "default": "none",
                    "description": "Pages to preview: 'none', '1', '1,3,5', '1-5', 'all'"
                },
                "preview_dpi": {
                    "type": "integer",
                    "default": 150,
                    "description": "DPI for preview images (72=low, 150=standard, 300=high)"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let content = args.get("content").and_then(|v| v.as_str());
        let input_path = args.get("input_path").and_then(|v| v.as_str());

        let output_format = args
            .get("output_format")
            .and_then(|v| v.as_str())
            .and_then(OutputFormat::from_str)
            .unwrap_or(OutputFormat::Pdf);

        let template = args
            .get("template")
            .and_then(|v| v.as_str())
            .map(LatexTemplate::from_str)
            .unwrap_or(LatexTemplate::Custom);

        let response_mode = args
            .get("response_mode")
            .and_then(|v| v.as_str())
            .map(ResponseMode::from_str)
            .unwrap_or(ResponseMode::Standard);

        let preview_pages = args
            .get("preview_pages")
            .and_then(|v| v.as_str())
            .unwrap_or("none");

        let preview_dpi = args
            .get("preview_dpi")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32)
            .unwrap_or(PREVIEW_DPI_STANDARD);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine
            .compile_latex(
                content,
                input_path,
                output_format,
                template,
                response_mode,
                preview_pages,
                preview_dpi,
            )
            .await;

        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: render_tikz
// ============================================================================

struct RenderTikzTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RenderTikzTool {
    fn name(&self) -> &str {
        "render_tikz"
    }

    fn description(&self) -> &str {
        r#"Render TikZ diagrams as standalone images.

Compiles TikZ code to PDF, PNG, or SVG format."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "tikz_code": {
                    "type": "string",
                    "description": "TikZ code for the diagram"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["pdf", "png", "svg"],
                    "default": "pdf",
                    "description": "Output format for the diagram"
                },
                "response_mode": {
                    "type": "string",
                    "enum": ["minimal", "standard"],
                    "default": "standard",
                    "description": "minimal: path only. standard: +metadata"
                }
            },
            "required": ["tikz_code"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let tikz_code = args
            .get("tikz_code")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'tikz_code' parameter".to_string())
            })?;

        let output_format = args
            .get("output_format")
            .and_then(|v| v.as_str())
            .and_then(OutputFormat::from_str)
            .unwrap_or(OutputFormat::Pdf);

        let response_mode = args
            .get("response_mode")
            .and_then(|v| v.as_str())
            .map(ResponseMode::from_str)
            .unwrap_or(ResponseMode::Standard);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine
            .render_tikz(tikz_code, output_format, response_mode)
            .await;

        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: preview_pdf
// ============================================================================

struct PreviewPdfTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for PreviewPdfTool {
    fn name(&self) -> &str {
        "preview_pdf"
    }

    fn description(&self) -> &str {
        r#"Generate PNG previews from an existing PDF file.

Converts specific pages of a PDF to PNG images for preview."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "Path to PDF file to preview"
                },
                "pages": {
                    "type": "string",
                    "default": "1",
                    "description": "Pages to preview: '1', '1,3,5', '1-5', 'all'"
                },
                "dpi": {
                    "type": "integer",
                    "default": 150,
                    "description": "Resolution for preview images"
                },
                "response_mode": {
                    "type": "string",
                    "enum": ["minimal", "standard"],
                    "default": "standard",
                    "description": "minimal: paths only. standard: +metadata"
                }
            },
            "required": ["pdf_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let pdf_path = args
            .get("pdf_path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'pdf_path' parameter".to_string())
            })?;

        let pages = args.get("pages").and_then(|v| v.as_str()).unwrap_or("1");

        let dpi = args
            .get("dpi")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32)
            .unwrap_or(PREVIEW_DPI_STANDARD);

        let response_mode = args
            .get("response_mode")
            .and_then(|v| v.as_str())
            .map(ResponseMode::from_str)
            .unwrap_or(ResponseMode::Standard);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine
            .preview_pdf(pdf_path, pages, dpi, response_mode)
            .await;

        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: create_manim_animation
// ============================================================================

struct CreateManimAnimationTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateManimAnimationTool {
    fn name(&self) -> &str {
        "create_manim_animation"
    }

    fn description(&self) -> &str {
        r#"Create mathematical animations using Manim.

Runs a Manim Python script to generate animations in various formats."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "Python script for Manim animation"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["mp4", "gif", "png", "webm"],
                    "default": "mp4",
                    "description": "Output format for the animation"
                }
            },
            "required": ["script"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let script = args
            .get("script")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'script' parameter".to_string()))?;

        let output_format = args
            .get("output_format")
            .and_then(|v| v.as_str())
            .and_then(ManimFormat::from_str)
            .unwrap_or(ManimFormat::Mp4);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.create_manim_animation(script, output_format).await;

        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: content_creation_status
// ============================================================================

struct ContentCreationStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ContentCreationStatusTool {
    fn name(&self) -> &str {
        "content_creation_status"
    }

    fn description(&self) -> &str {
        r#"Get content creation server status.

Returns information about initialization state and output directories."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let guard = self.server.engine.read().await;
        let initialized = guard.is_some();

        let response = json!({
            "server": "content-creation",
            "version": "2.0.0",
            "initialized": initialized,
            "output_dir": self.server.output_dir.display().to_string(),
            "project_root": self.server.project_root.display().to_string(),
            "note": if !initialized { Some("Engine will initialize on first use") } else { None }
        });

        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = ContentCreationServer::new(PathBuf::from("/tmp"), PathBuf::from("/app"));
        let tools = server.tools();
        assert_eq!(tools.len(), 5);
    }

    #[test]
    fn test_tool_names() {
        let server = ContentCreationServer::new(PathBuf::from("/tmp"), PathBuf::from("/app"));
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"compile_latex"));
        assert!(names.contains(&"render_tikz"));
        assert!(names.contains(&"preview_pdf"));
        assert!(names.contains(&"create_manim_animation"));
        assert!(names.contains(&"content_creation_status"));
    }
}

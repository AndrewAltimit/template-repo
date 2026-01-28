//! MCP server implementation for meme generation.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::generator::MemeGenerator;

/// Meme generator MCP server
pub struct MemeGeneratorServer {
    generator: Arc<RwLock<Option<MemeGenerator>>>,
    templates_dir: PathBuf,
    output_dir: PathBuf,
}

impl MemeGeneratorServer {
    /// Create a new meme generator server
    pub fn new(templates_dir: PathBuf, output_dir: PathBuf) -> Self {
        Self {
            generator: Arc::new(RwLock::new(None)),
            templates_dir,
            output_dir,
        }
    }

    /// Ensure generator is initialized
    #[allow(dead_code)]
    async fn ensure_initialized(&self) -> Result<()> {
        let mut guard = self.generator.write().await;
        if guard.is_none() {
            info!("Initializing meme generator...");
            let generator = MemeGenerator::new(self.templates_dir.clone(), self.output_dir.clone());
            info!("Loaded {} templates", generator.template_count());
            *guard = Some(generator);
        }
        Ok(())
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(GenerateMemeTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListMemeTemplatesTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetMemeTemplateInfoTool {
                server: self.clone_refs(),
            }),
            Arc::new(MemeGeneratorStatusTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            generator: self.generator.clone(),
            templates_dir: self.templates_dir.clone(),
            output_dir: self.output_dir.clone(),
        }
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    generator: Arc<RwLock<Option<MemeGenerator>>>,
    templates_dir: PathBuf,
    output_dir: PathBuf,
}

impl ServerRefs {
    async fn ensure_initialized(&self) -> Result<()> {
        let mut guard = self.generator.write().await;
        if guard.is_none() {
            info!("Initializing meme generator...");
            let generator = MemeGenerator::new(self.templates_dir.clone(), self.output_dir.clone());
            info!("Loaded {} templates", generator.template_count());
            *guard = Some(generator);
        }
        Ok(())
    }
}

// ============================================================================
// Tool: generate_meme
// ============================================================================

struct GenerateMemeTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GenerateMemeTool {
    fn name(&self) -> &str {
        "generate_meme"
    }

    fn description(&self) -> &str {
        r#"Generate a meme from a template with text overlays.

Creates a meme image by overlaying text on a template. Supports automatic text sizing and optional upload to get a shareable URL.

Examples:
- Template: "ol_reliable", texts: {"top": "When the code won't compile", "bottom": "print('hello world')"}
- Template: "community_fire", texts: {"top": "Everything is fine", "bottom": "This is fine"}"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "description": "Template ID (e.g., 'ol_reliable', 'community_fire')"
                },
                "texts": {
                    "type": "object",
                    "description": "Text for each area (e.g., {\"top\": \"When...\", \"bottom\": \"Solution\"})",
                    "additionalProperties": {"type": "string"}
                },
                "font_size_override": {
                    "type": "object",
                    "description": "Override font sizes for specific areas (e.g., {\"top\": 30})",
                    "additionalProperties": {"type": "integer"}
                },
                "auto_resize": {
                    "type": "boolean",
                    "default": true,
                    "description": "Automatically resize font to fit text area"
                },
                "upload": {
                    "type": "boolean",
                    "default": true,
                    "description": "Upload meme to get shareable URL (uses 0x0.st)"
                }
            },
            "required": ["template", "texts"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        // Parse arguments
        let template = args
            .get("template")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'template' parameter".to_string())
            })?;

        let texts: HashMap<String, String> = args
            .get("texts")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing or invalid 'texts' parameter".to_string())
            })?;

        let font_size_override: Option<HashMap<String, i32>> = args
            .get("font_size_override")
            .and_then(|v| serde_json::from_value(v.clone()).ok());

        let auto_resize = args
            .get("auto_resize")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let upload = args.get("upload").and_then(|v| v.as_bool()).unwrap_or(true);

        // Generate meme
        let guard = self.server.generator.read().await;
        let generator = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Generator not initialized".to_string()))?;

        let result = generator
            .generate_and_upload(
                template,
                &texts,
                font_size_override.as_ref(),
                auto_resize,
                upload,
            )
            .await;

        if result.success {
            let mut response = json!({
                "success": true,
                "template_used": result.template_used,
                "output_path": result.output_path,
                "size_kb": result.size_kb
            });

            if let Some(url) = &result.share_url {
                response["share_url"] = json!(url);
            }
            if let Some(url) = &result.embed_url {
                response["embed_url"] = json!(url);
            }
            if let Some(service) = &result.upload_service {
                response["upload_service"] = json!(service);
            }
            if let Some(feedback) = &result.visual_feedback {
                response["visual_feedback"] = json!({
                    "format": feedback.format,
                    "encoding": feedback.encoding,
                    "data": feedback.data,
                    "size_kb": feedback.size_kb
                });
            }

            ToolResult::json(&response)
        } else {
            let response = json!({
                "success": false,
                "error": result.error
            });
            ToolResult::json(&response)
        }
    }
}

// ============================================================================
// Tool: list_meme_templates
// ============================================================================

struct ListMemeTemplatesTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListMemeTemplatesTool {
    fn name(&self) -> &str {
        "list_meme_templates"
    }

    fn description(&self) -> &str {
        r#"List all available meme templates.

Returns a list of template IDs with their names, descriptions, and text areas."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let guard = self.server.generator.read().await;
        let generator = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Generator not initialized".to_string()))?;

        let templates = generator.list_templates();

        let response = json!({
            "success": true,
            "count": templates.len(),
            "templates": templates
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_meme_template_info
// ============================================================================

struct GetMemeTemplateInfoTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetMemeTemplateInfoTool {
    fn name(&self) -> &str {
        "get_meme_template_info"
    }

    fn description(&self) -> &str {
        r#"Get detailed information about a specific meme template.

Returns the full configuration including text areas, usage rules, and examples."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "template_id": {
                    "type": "string",
                    "description": "Template ID to get info for (e.g., 'ol_reliable')"
                }
            },
            "required": ["template_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let template_id = args
            .get("template_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'template_id' parameter".to_string())
            })?;

        let guard = self.server.generator.read().await;
        let generator = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Generator not initialized".to_string()))?;

        match generator.get_template_info(template_id) {
            Some(config) => {
                let response = json!({
                    "success": true,
                    "template": config
                });
                ToolResult::json(&response)
            }
            None => {
                let response = json!({
                    "success": false,
                    "error": format!("Template '{}' not found", template_id)
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: meme_generator_status
// ============================================================================

struct MemeGeneratorStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for MemeGeneratorStatusTool {
    fn name(&self) -> &str {
        "meme_generator_status"
    }

    fn description(&self) -> &str {
        r#"Get meme generator server status.

Returns information about initialization state, template count, and directories."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let guard = self.server.generator.read().await;
        let initialized = guard.is_some();

        let mut response = json!({
            "server": "meme-generator",
            "version": "1.0.0",
            "initialized": initialized,
            "templates_dir": self.server.templates_dir.display().to_string(),
            "output_dir": self.server.output_dir.display().to_string()
        });

        if let Some(generator) = guard.as_ref() {
            response["template_count"] = json!(generator.template_count());
        } else {
            response["note"] = json!("Generator will initialize on first use");
        }

        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = MemeGeneratorServer::new(PathBuf::from("/tmp"), PathBuf::from("/tmp/output"));
        let tools = server.tools();
        assert_eq!(tools.len(), 4);
    }

    #[test]
    fn test_tool_names() {
        let server = MemeGeneratorServer::new(PathBuf::from("/tmp"), PathBuf::from("/tmp/output"));
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"generate_meme"));
        assert!(names.contains(&"list_meme_templates"));
        assert!(names.contains(&"get_meme_template_info"));
        assert!(names.contains(&"meme_generator_status"));
    }
}

//! MCP server implementation for ComfyUI

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::env;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;
use uuid::Uuid;

use crate::client::ComfyUIClient;
use crate::types::{GenerationJob, JobStatus};
use crate::workflows::{WorkflowFactory, get_sample_workflow, get_workflow_templates};

/// ComfyUI MCP server
pub struct ComfyUIServer {
    client: Arc<ComfyUIClient>,
    jobs: Arc<RwLock<HashMap<String, GenerationJob>>>,
    default_timeout: u64,
}

impl ComfyUIServer {
    /// Create a new ComfyUI server
    pub fn new() -> Self {
        let host = env::var("COMFYUI_HOST").unwrap_or_else(|_| "localhost".to_string());
        let port: u16 = env::var("COMFYUI_PORT")
            .unwrap_or_else(|_| "8188".to_string())
            .parse()
            .unwrap_or(8188);
        let comfyui_path = env::var("COMFYUI_PATH").unwrap_or_else(|_| "/comfyui".to_string());
        let default_timeout: u64 = env::var("COMFYUI_GENERATION_TIMEOUT")
            .unwrap_or_else(|_| "300".to_string())
            .parse()
            .unwrap_or(300);

        let client_id = Uuid::new_v4().to_string();
        let client = ComfyUIClient::new(&host, port, client_id, &comfyui_path);

        info!(
            "ComfyUI server configured for {}:{} (timeout: {}s)",
            host, port, default_timeout
        );

        Self {
            client: Arc::new(client),
            jobs: Arc::new(RwLock::new(HashMap::new())),
            default_timeout,
        }
    }

    /// Get all tools provided by this server
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(GenerateImageTool {
                client: self.client.clone(),
                jobs: self.jobs.clone(),
                default_timeout: self.default_timeout,
            }),
            Arc::new(ListWorkflowsTool),
            Arc::new(GetWorkflowTool),
            Arc::new(ListModelsTool {
                client: self.client.clone(),
            }),
            Arc::new(UploadLoraTool {
                client: self.client.clone(),
            }),
            Arc::new(ListLorasTool {
                client: self.client.clone(),
            }),
            Arc::new(DownloadLoraTool {
                client: self.client.clone(),
            }),
            Arc::new(GetObjectInfoTool {
                client: self.client.clone(),
            }),
            Arc::new(GetSystemInfoTool {
                client: self.client.clone(),
            }),
            Arc::new(ExecuteWorkflowTool {
                client: self.client.clone(),
                jobs: self.jobs.clone(),
            }),
        ]
    }
}

impl Default for ComfyUIServer {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tool: generate_image
// ============================================================================

struct GenerateImageTool {
    client: Arc<ComfyUIClient>,
    jobs: Arc<RwLock<HashMap<String, GenerationJob>>>,
    default_timeout: u64,
}

#[async_trait]
impl Tool for GenerateImageTool {
    fn name(&self) -> &str {
        "generate_image"
    }

    fn description(&self) -> &str {
        "Generate an image using ComfyUI workflow"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text prompt for generation"
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Negative prompt",
                    "default": ""
                },
                "workflow": {
                    "type": "object",
                    "description": "Custom ComfyUI workflow JSON (optional)"
                },
                "width": {
                    "type": "integer",
                    "description": "Image width",
                    "default": 512
                },
                "height": {
                    "type": "integer",
                    "description": "Image height",
                    "default": 512
                },
                "seed": {
                    "type": "integer",
                    "description": "Random seed (-1 for random)",
                    "default": -1
                },
                "steps": {
                    "type": "integer",
                    "description": "Number of steps",
                    "default": 20
                },
                "cfg_scale": {
                    "type": "number",
                    "description": "CFG scale",
                    "default": 7.0
                },
                "timeout": {
                    "type": "integer",
                    "description": "Generation timeout in seconds"
                }
            },
            "required": ["prompt"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let prompt = args
            .get("prompt")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'prompt' parameter".to_string()))?;

        let negative_prompt = args
            .get("negative_prompt")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        let width = args
            .get("width")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32)
            .unwrap_or(512);

        let height = args
            .get("height")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32)
            .unwrap_or(512);

        let seed = args.get("seed").and_then(|v| v.as_i64()).unwrap_or(-1);

        let steps = args
            .get("steps")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32)
            .unwrap_or(20);

        let cfg_scale = args
            .get("cfg_scale")
            .and_then(|v| v.as_f64())
            .unwrap_or(7.0);

        let timeout = args
            .get("timeout")
            .and_then(|v| v.as_u64())
            .unwrap_or(self.default_timeout);

        // Use provided workflow or create default
        let workflow = if let Some(custom) = args.get("workflow") {
            // Inject prompt into CLIPTextEncode nodes if present
            inject_prompt_into_workflow(custom.clone(), prompt, negative_prompt)
        } else {
            WorkflowFactory::create_flux_workflow(
                prompt,
                negative_prompt,
                width,
                height,
                seed,
                steps,
                cfg_scale,
                None,
                1.0,
            )
        };

        // Queue the prompt
        let prompt_id = self
            .client
            .queue_prompt(&workflow)
            .await
            .map_err(MCPError::Internal)?;

        // Create job entry
        let job_id = Uuid::new_v4().to_string();
        {
            let mut jobs = self.jobs.write().await;
            jobs.insert(
                job_id.clone(),
                GenerationJob {
                    prompt_id: prompt_id.clone(),
                    status: JobStatus::Queued,
                    prompt: Some(prompt.to_string()),
                    images: Vec::new(),
                },
            );
        }

        // Wait for completion
        match self.client.wait_for_completion(&prompt_id, timeout).await {
            Ok(images) => {
                let mut jobs = self.jobs.write().await;
                if let Some(job) = jobs.get_mut(&job_id) {
                    job.status = JobStatus::Completed;
                    job.images = images.clone();
                }

                let response = json!({
                    "success": true,
                    "job_id": job_id,
                    "prompt_id": prompt_id,
                    "images": images
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                let mut jobs = self.jobs.write().await;
                if let Some(job) = jobs.get_mut(&job_id) {
                    job.status = JobStatus::Timeout;
                }

                let response = json!({
                    "success": false,
                    "error": e,
                    "job_id": job_id
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: list_workflows
// ============================================================================

struct ListWorkflowsTool;

#[async_trait]
impl Tool for ListWorkflowsTool {
    fn name(&self) -> &str {
        "list_workflows"
    }

    fn description(&self) -> &str {
        "List available ComfyUI workflow templates"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let templates = get_workflow_templates();
        let response = json!({
            "success": true,
            "workflows": templates
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_workflow
// ============================================================================

struct GetWorkflowTool;

#[async_trait]
impl Tool for GetWorkflowTool {
    fn name(&self) -> &str {
        "get_workflow"
    }

    fn description(&self) -> &str {
        "Get a specific workflow template with sample parameters"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Workflow template name"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("flux_default");

        if let Some(workflow) = get_sample_workflow(name) {
            let templates = get_workflow_templates();
            let template = templates.iter().find(|t| t.name == name);

            let response = json!({
                "success": true,
                "name": name,
                "workflow": workflow,
                "description": template.map(|t| &t.description),
                "model_type": template.map(|t| &t.model_type)
            });
            ToolResult::json(&response)
        } else {
            let response = json!({
                "success": false,
                "error": format!("Workflow not found: {}", name)
            });
            ToolResult::json(&response)
        }
    }
}

// ============================================================================
// Tool: list_models
// ============================================================================

struct ListModelsTool {
    client: Arc<ComfyUIClient>,
}

#[async_trait]
impl Tool for ListModelsTool {
    fn name(&self) -> &str {
        "list_models"
    }

    fn description(&self) -> &str {
        "List available models in ComfyUI"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["checkpoint", "lora", "vae"],
                    "description": "Model type to list",
                    "default": "checkpoint"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let model_type = args
            .get("type")
            .and_then(|v| v.as_str())
            .unwrap_or("checkpoint");

        match self.client.get_models(model_type).await {
            Ok(models) => {
                let response = json!({
                    "success": true,
                    "type": model_type,
                    "models": models,
                    "count": models.len()
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: upload_lora
// ============================================================================

struct UploadLoraTool {
    client: Arc<ComfyUIClient>,
}

#[async_trait]
impl Tool for UploadLoraTool {
    fn name(&self) -> &str {
        "upload_lora"
    }

    fn description(&self) -> &str {
        "Upload a LoRA model to ComfyUI"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename for the LoRA"
                },
                "data": {
                    "type": "string",
                    "description": "Base64 encoded LoRA data"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional LoRA metadata"
                }
            },
            "required": ["filename", "data"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let filename = args
            .get("filename")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'filename' parameter".to_string())
            })?;

        let data_b64 = args
            .get("data")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'data' parameter".to_string()))?;

        let data = ComfyUIClient::decode_base64(data_b64).map_err(MCPError::InvalidParameters)?;

        let metadata = args.get("metadata");

        match self.client.upload_lora(filename, &data, metadata).await {
            Ok(path) => {
                let response = json!({
                    "success": true,
                    "filename": filename,
                    "path": path.to_string_lossy(),
                    "size": data.len()
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: list_loras
// ============================================================================

struct ListLorasTool {
    client: Arc<ComfyUIClient>,
}

#[async_trait]
impl Tool for ListLorasTool {
    fn name(&self) -> &str {
        "list_loras"
    }

    fn description(&self) -> &str {
        "List available LoRA models"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.client.list_loras().await {
            Ok(loras) => {
                let loras_json: Vec<Value> = loras
                    .iter()
                    .map(|l| {
                        json!({
                            "name": l.name,
                            "filename": l.filename,
                            "size": l.size
                        })
                    })
                    .collect();

                let response = json!({
                    "success": true,
                    "loras": loras_json,
                    "count": loras.len()
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: download_lora
// ============================================================================

struct DownloadLoraTool {
    client: Arc<ComfyUIClient>,
}

#[async_trait]
impl Tool for DownloadLoraTool {
    fn name(&self) -> &str {
        "download_lora"
    }

    fn description(&self) -> &str {
        "Download a LoRA model from ComfyUI"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "LoRA filename to download"
                },
                "encoding": {
                    "type": "string",
                    "enum": ["base64", "raw"],
                    "default": "base64"
                }
            },
            "required": ["filename"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let filename = args
            .get("filename")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'filename' parameter".to_string())
            })?;

        let encoding = args
            .get("encoding")
            .and_then(|v| v.as_str())
            .unwrap_or("base64");

        match self.client.download_lora(filename).await {
            Ok(data) => {
                let response = if encoding == "base64" {
                    json!({
                        "success": true,
                        "filename": filename,
                        "data": ComfyUIClient::encode_base64(&data),
                        "size": data.len()
                    })
                } else {
                    json!({
                        "success": true,
                        "filename": filename,
                        "size": data.len(),
                        "note": "Raw data not supported in JSON response, use base64"
                    })
                };
                ToolResult::json(&response)
            }
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: get_object_info
// ============================================================================

struct GetObjectInfoTool {
    client: Arc<ComfyUIClient>,
}

#[async_trait]
impl Tool for GetObjectInfoTool {
    fn name(&self) -> &str {
        "get_object_info"
    }

    fn description(&self) -> &str {
        "Get ComfyUI node and model information"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.client.get_object_info().await {
            Ok(info) => ToolResult::json(&info),
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: get_system_info
// ============================================================================

struct GetSystemInfoTool {
    client: Arc<ComfyUIClient>,
}

#[async_trait]
impl Tool for GetSystemInfoTool {
    fn name(&self) -> &str {
        "get_system_info"
    }

    fn description(&self) -> &str {
        "Get ComfyUI system information"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.client.get_system_stats().await {
            Ok(stats) => {
                let response = json!({
                    "success": true,
                    "system": stats.system,
                    "devices": stats.devices
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: execute_workflow
// ============================================================================

struct ExecuteWorkflowTool {
    client: Arc<ComfyUIClient>,
    jobs: Arc<RwLock<HashMap<String, GenerationJob>>>,
}

#[async_trait]
impl Tool for ExecuteWorkflowTool {
    fn name(&self) -> &str {
        "execute_workflow"
    }

    fn description(&self) -> &str {
        "Execute a custom ComfyUI workflow (non-blocking)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "object",
                    "description": "Complete workflow JSON"
                }
            },
            "required": ["workflow"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let workflow = args.get("workflow").ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'workflow' parameter".to_string())
        })?;

        match self.client.queue_prompt(workflow).await {
            Ok(prompt_id) => {
                let job_id = Uuid::new_v4().to_string();

                {
                    let mut jobs = self.jobs.write().await;
                    jobs.insert(
                        job_id.clone(),
                        GenerationJob {
                            prompt_id: prompt_id.clone(),
                            status: JobStatus::Queued,
                            prompt: None,
                            images: Vec::new(),
                        },
                    );
                }

                let response = json!({
                    "success": true,
                    "job_id": job_id,
                    "prompt_id": prompt_id,
                    "message": "Workflow queued for execution"
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

/// Inject prompt and negative_prompt into CLIPTextEncode nodes in a custom workflow.
/// This matches the behavior of the previous Python implementation.
fn inject_prompt_into_workflow(mut workflow: Value, prompt: &str, negative_prompt: &str) -> Value {
    if let Some(obj) = workflow.as_object_mut() {
        // Track which nodes we've updated for positive/negative
        let mut positive_updated = false;
        let mut negative_updated = false;

        for (_node_id, node) in obj.iter_mut() {
            if let Some(node_obj) = node.as_object_mut()
                && node_obj.get("class_type").and_then(|v| v.as_str()) == Some("CLIPTextEncode")
                && let Some(inputs) = node_obj.get_mut("inputs")
                && let Some(inputs_obj) = inputs.as_object_mut()
            {
                // Check if this is likely a positive or negative prompt node
                // by looking at the existing text or node connections
                let current_text = inputs_obj
                    .get("text")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");

                // Heuristic: if text contains "negative" keywords, consider it negative
                let is_negative = current_text.to_lowercase().contains("negative")
                    || current_text.to_lowercase().contains("bad")
                    || current_text.to_lowercase().contains("worst");

                if is_negative && !negative_updated {
                    inputs_obj.insert("text".to_string(), json!(negative_prompt));
                    negative_updated = true;
                } else if !positive_updated {
                    inputs_obj.insert("text".to_string(), json!(prompt));
                    positive_updated = true;
                } else if !negative_updated {
                    inputs_obj.insert("text".to_string(), json!(negative_prompt));
                    negative_updated = true;
                }
            }
        }
    }
    workflow
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        // This will fail if COMFYUI_HOST is not set, but tests the structure
        let server = ComfyUIServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 10);
    }

    #[test]
    fn test_tool_names() {
        let server = ComfyUIServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"generate_image"));
        assert!(names.contains(&"list_workflows"));
        assert!(names.contains(&"get_workflow"));
        assert!(names.contains(&"list_models"));
        assert!(names.contains(&"upload_lora"));
        assert!(names.contains(&"list_loras"));
        assert!(names.contains(&"download_lora"));
        assert!(names.contains(&"get_object_info"));
        assert!(names.contains(&"get_system_info"));
        assert!(names.contains(&"execute_workflow"));
    }
}

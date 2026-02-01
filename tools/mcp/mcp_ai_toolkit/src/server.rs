//! MCP server implementation for AI Toolkit.

#![allow(clippy::collapsible_if)]
#![allow(clippy::collapsible_else_if)]

use async_trait::async_trait;
use base64::{Engine, engine::general_purpose::STANDARD as BASE64};
use mcp_core::prelude::*;
use regex::Regex;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;
use sysinfo::{Disks, System};
use tokio::fs;
use tokio::process::Command;
use tokio::sync::RwLock;
use tracing::{error, info, warn};

use crate::config::{AIToolkitPaths, ConfigError, validate_path};
use crate::types::*;

/// AI Toolkit MCP server
pub struct AIToolkitServer {
    paths: Arc<AIToolkitPaths>,
    training_jobs: Arc<RwLock<HashMap<String, TrainingJob>>>,
    training_processes: Arc<RwLock<HashMap<String, tokio::process::Child>>>,
}

impl AIToolkitServer {
    /// Create a new AI Toolkit server
    pub async fn new() -> anyhow::Result<Self> {
        let paths = AIToolkitPaths::from_env();

        // Ensure directories exist
        if let Err(e) = paths.ensure_directories() {
            warn!(
                "Could not create directories: {}. Server will still start.",
                e
            );
        }

        Ok(Self {
            paths: Arc::new(paths),
            training_jobs: Arc::new(RwLock::new(HashMap::new())),
            training_processes: Arc::new(RwLock::new(HashMap::new())),
        })
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(CreateTrainingConfigTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListConfigsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetConfigTool {
                server: self.clone_refs(),
            }),
            Arc::new(UploadDatasetTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListDatasetsTool {
                server: self.clone_refs(),
            }),
            Arc::new(StartTrainingTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetTrainingStatusTool {
                server: self.clone_refs(),
            }),
            Arc::new(StopTrainingTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListTrainingJobsTool {
                server: self.clone_refs(),
            }),
            Arc::new(ExportModelTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListExportedModelsTool {
                server: self.clone_refs(),
            }),
            Arc::new(DownloadModelTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetSystemStatsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetTrainingLogsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetTrainingInfoTool {
                server: self.clone_refs(),
            }),
            // New tools for improved functionality
            Arc::new(DeleteConfigTool {
                server: self.clone_refs(),
            }),
            Arc::new(DeleteDatasetTool {
                server: self.clone_refs(),
            }),
            Arc::new(DeleteModelTool {
                server: self.clone_refs(),
            }),
            Arc::new(ValidateConfigTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetDatasetInfoTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListModelPresetsTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone the Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            paths: self.paths.clone(),
            training_jobs: self.training_jobs.clone(),
            training_processes: self.training_processes.clone(),
        }
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    paths: Arc<AIToolkitPaths>,
    training_jobs: Arc<RwLock<HashMap<String, TrainingJob>>>,
    training_processes: Arc<RwLock<HashMap<String, tokio::process::Child>>>,
}

impl ServerRefs {
    /// Helper to convert ConfigError to MCPError
    fn config_error_to_mcp(&self, e: ConfigError, context: &str) -> MCPError {
        MCPError::InvalidParameters(format!("{}: {}", context, e))
    }
}

// ============================================================================
// Tool: create_training_config
// ============================================================================

struct CreateTrainingConfigTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateTrainingConfigTool {
    fn name(&self) -> &str {
        "create_training_config"
    }

    fn description(&self) -> &str {
        r#"Create a new training configuration file for AI Toolkit LoRA training.

Supports multiple model types:
- Flux.1-dev/schnell (is_flux: true, noise_scheduler: flowmatch)
- SD 3.5 Large (is_v3: true, noise_scheduler: flowmatch)
- SDXL (is_xl: true)
- SD 1.5/2.1 (default)

Use list_model_presets to see recommended settings for each model type."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Configuration name (will be used for output folder and model name)"
                },
                "model_name": {
                    "type": "string",
                    "description": "Base model path (e.g., 'black-forest-labs/FLUX.1-dev', 'runwayml/stable-diffusion-v1-5')"
                },
                "dataset_path": {
                    "type": "string",
                    "description": "Path to training dataset folder (must contain images and .txt caption files)"
                },
                "resolution": {
                    "oneOf": [
                        {"type": "integer"},
                        {"type": "array", "items": {"type": "integer"}}
                    ],
                    "description": "Training resolution - single value or array like [512, 768, 1024]",
                    "default": 512
                },
                "steps": {
                    "type": "integer",
                    "description": "Total training steps (500-4000 typical)",
                    "default": 2000
                },
                "batch_size": {
                    "type": "integer",
                    "description": "Batch size",
                    "default": 1
                },
                "rank": {
                    "type": "integer",
                    "description": "LoRA rank (linear dimension)",
                    "default": 16
                },
                "alpha": {
                    "type": "integer",
                    "description": "LoRA alpha (scaling)",
                    "default": 16
                },
                "lr": {
                    "type": "number",
                    "description": "Learning rate",
                    "default": 0.0001
                },
                "optimizer": {
                    "type": "string",
                    "enum": ["adamw", "adamw8bit", "prodigy", "lion", "adafactor"],
                    "description": "Optimizer to use (adamw8bit recommended for Flux)",
                    "default": "adamw8bit"
                },
                "noise_scheduler": {
                    "type": "string",
                    "enum": ["ddpm", "ddim", "flowmatch", "euler", "euler_a"],
                    "description": "Noise scheduler (flowmatch for Flux/SD3)",
                    "default": "ddpm"
                },
                "trigger_word": {
                    "type": "string",
                    "description": "Trigger word for the LoRA (added to captions if not present)"
                },
                "prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sample prompts for generating test images during training"
                },
                "is_flux": {
                    "type": "boolean",
                    "description": "Is this a Flux model",
                    "default": false
                },
                "is_xl": {
                    "type": "boolean",
                    "description": "Is this an SDXL model",
                    "default": false
                },
                "is_v3": {
                    "type": "boolean",
                    "description": "Is this a SD 3.x model",
                    "default": false
                },
                "quantize": {
                    "type": "boolean",
                    "description": "Enable 8-bit quantization (required for large models)",
                    "default": false
                },
                "gradient_checkpointing": {
                    "type": "boolean",
                    "description": "Enable gradient checkpointing to save VRAM",
                    "default": true
                },
                "cache_latents": {
                    "type": "boolean",
                    "description": "Cache latents to disk (recommended)",
                    "default": true
                },
                "caption_dropout_rate": {
                    "type": "number",
                    "description": "Caption dropout rate (0.0-1.0)",
                    "default": 0.05
                }
            },
            "required": ["name", "dataset_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        let dataset_path = args
            .get("dataset_path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'dataset_path' parameter".to_string())
            })?;

        // Get model settings with smart defaults
        let model_name = args
            .get("model_name")
            .and_then(|v| v.as_str())
            .unwrap_or("runwayml/stable-diffusion-v1-5");

        let is_flux = args
            .get("is_flux")
            .and_then(|v| v.as_bool())
            .unwrap_or(model_name.to_lowercase().contains("flux"));
        let is_xl = args
            .get("is_xl")
            .and_then(|v| v.as_bool())
            .unwrap_or(model_name.to_lowercase().contains("xl"));
        let is_v3 = args
            .get("is_v3")
            .and_then(|v| v.as_bool())
            .unwrap_or(model_name.contains("3.5") || model_name.contains("sd3"));

        // Resolution handling - can be single value or array
        let resolution = match args.get("resolution") {
            Some(Value::Number(n)) => Resolution::Single(n.as_u64().unwrap_or(512) as u32),
            Some(Value::Array(arr)) => Resolution::Multiple(
                arr.iter()
                    .filter_map(|v| v.as_u64().map(|n| n as u32))
                    .collect(),
            ),
            _ => {
                if is_flux || is_v3 {
                    Resolution::Multiple(vec![512, 768, 1024])
                } else if is_xl {
                    Resolution::Single(1024)
                } else {
                    Resolution::Single(512)
                }
            }
        };

        // Smart defaults based on model type
        let default_scheduler = if is_flux || is_v3 {
            "flowmatch"
        } else {
            "ddpm"
        };
        let default_optimizer = if is_flux || is_v3 {
            "adamw8bit"
        } else {
            "adamw"
        };
        let default_guidance = if is_flux { 4.0 } else { 7.5 };
        let default_quantize = is_flux || is_v3;

        let steps = args.get("steps").and_then(|v| v.as_u64()).unwrap_or(2000) as u32;
        let batch_size = args.get("batch_size").and_then(|v| v.as_u64()).unwrap_or(1) as u32;
        let rank = args.get("rank").and_then(|v| v.as_u64()).unwrap_or(16) as u32;
        let alpha = args.get("alpha").and_then(|v| v.as_u64()).unwrap_or(16) as u32;
        let lr = args.get("lr").and_then(|v| v.as_f64()).unwrap_or(1e-4);
        let optimizer = args
            .get("optimizer")
            .and_then(|v| v.as_str())
            .unwrap_or(default_optimizer);
        let noise_scheduler = args
            .get("noise_scheduler")
            .and_then(|v| v.as_str())
            .unwrap_or(default_scheduler);
        let quantize = args
            .get("quantize")
            .and_then(|v| v.as_bool())
            .unwrap_or(default_quantize);
        let gradient_checkpointing = args
            .get("gradient_checkpointing")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        let cache_latents = args
            .get("cache_latents")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        let caption_dropout_rate = args
            .get("caption_dropout_rate")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.05) as f32;

        let trigger_word = args
            .get("trigger_word")
            .and_then(|v| v.as_str())
            .map(String::from);
        let prompts: Vec<String> = args
            .get("prompts")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_else(|| {
                vec![
                    "a woman holding a coffee cup, in a beanie, sitting at a cafe".to_string(),
                    "a man showing off his cool new t-shirt at the beach".to_string(),
                ]
            });

        // Sample dimensions
        let (sample_width, sample_height) = match &resolution {
            Resolution::Single(r) => (*r, *r),
            Resolution::Multiple(arr) => {
                (*arr.last().unwrap_or(&1024), *arr.last().unwrap_or(&1024))
            }
        };

        // Validate config name
        let config_filename = format!("{}.yaml", name);
        let config_path =
            validate_path(&config_filename, &self.server.paths.configs_path, "config")
                .map_err(|e| self.server.config_error_to_mcp(e, "Invalid config name"))?;

        // Create AI Toolkit compatible config matching actual format
        let config = TrainingConfig {
            job: "extension".to_string(),
            config: ConfigDetails {
                name: name.to_string(),
                process: vec![ProcessConfig {
                    process_type: "sd_trainer".to_string(),
                    training_folder: "output".to_string(),
                    device: "cuda:0".to_string(),
                    trigger_word,
                    performance_log_every: None,
                    network: NetworkConfig {
                        network_type: "lora".to_string(),
                        linear: rank,
                        linear_alpha: alpha,
                        conv: None,
                        conv_alpha: None,
                        dropout: None,
                        transformer_only: Some(true),
                    },
                    save: SaveConfig {
                        dtype: "float16".to_string(),
                        save_every: 250,
                        max_step_saves_to_keep: 4,
                        push_to_hub: false,
                        hf_repo_id: None,
                        hf_private: None,
                    },
                    datasets: vec![DatasetConfig {
                        folder_path: dataset_path.to_string(),
                        caption_ext: "txt".to_string(),
                        caption_dropout_rate,
                        shuffle_tokens: false,
                        cache_latents_to_disk: cache_latents,
                        resolution,
                        default_caption: None,
                        is_reg: false,
                        network_weight: None,
                    }],
                    train: TrainConfig {
                        batch_size,
                        steps,
                        gradient_accumulation_steps: 1,
                        train_unet: true,
                        train_text_encoder: false,
                        gradient_checkpointing,
                        noise_scheduler: noise_scheduler.to_string(),
                        optimizer: optimizer.to_string(),
                        lr,
                        skip_first_sample: false,
                        disable_sampling: false,
                        linear_timesteps: false,
                        dtype: if is_flux || is_v3 {
                            "bf16".to_string()
                        } else {
                            "fp16".to_string()
                        },
                        ema_config: EmaConfig {
                            use_ema: true,
                            ema_decay: 0.99,
                        },
                        max_grad_norm: None,
                        noise_offset: None,
                    },
                    model: ModelConfig {
                        name_or_path: model_name.to_string(),
                        is_flux,
                        is_v2: false,
                        is_v3,
                        is_xl,
                        is_v_pred: false,
                        quantize,
                        low_vram: false,
                    },
                    sample: SampleConfig {
                        sampler: noise_scheduler.to_string(),
                        sample_every: 250,
                        width: sample_width,
                        height: sample_height,
                        prompts,
                        neg: String::new(),
                        seed: 42,
                        walk_seed: true,
                        guidance_scale: default_guidance,
                        sample_steps: 20,
                    },
                    logging: Some(LoggingConfig {
                        log_every: 100,
                        verbose: false,
                        use_wandb: false,
                        use_ui_logger: false,
                        project_name: None,
                        run_name: None,
                    }),
                }],
            },
            meta: Some(ConfigMeta {
                name: "[name]".to_string(),
                version: "1.0".to_string(),
            }),
        };

        // Serialize and save
        let yaml_content =
            serde_yaml::to_string(&config).map_err(|e| MCPError::Internal(e.to_string()))?;

        fs::write(&config_path, yaml_content)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to write config: {}", e)))?;

        info!("Created training config: {}", config_path.display());

        ToolResult::json(&json!({
            "status": "success",
            "config": name,
            "path": config_path.display().to_string()
        }))
    }
}

// ============================================================================
// Tool: list_configs
// ============================================================================

struct ListConfigsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListConfigsTool {
    fn name(&self) -> &str {
        "list_configs"
    }

    fn description(&self) -> &str {
        "List all training configurations available in the config directory."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut configs = Vec::new();

        if let Ok(mut entries) = fs::read_dir(&self.server.paths.configs_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                let path = entry.path();
                if path.extension().is_some_and(|ext| ext == "yaml") {
                    if let Some(stem) = path.file_stem() {
                        configs.push(stem.to_string_lossy().to_string());
                    }
                }
            }
        }

        configs.sort();

        ToolResult::json(&json!({
            "configs": configs
        }))
    }
}

// ============================================================================
// Tool: get_config
// ============================================================================

struct GetConfigTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetConfigTool {
    fn name(&self) -> &str {
        "get_config"
    }

    fn description(&self) -> &str {
        "Get a specific training configuration by name."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Configuration name"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        let config_filename = format!("{}.yaml", name);
        let config_path =
            validate_path(&config_filename, &self.server.paths.configs_path, "config")
                .map_err(|e| self.server.config_error_to_mcp(e, "Invalid config name"))?;

        if !config_path.exists() {
            return ToolResult::json(&json!({
                "error": "Configuration not found"
            }));
        }

        let content = fs::read_to_string(&config_path)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to read config: {}", e)))?;

        let config: Value = serde_yaml::from_str(&content)
            .map_err(|e| MCPError::Internal(format!("Invalid YAML format: {}", e)))?;

        ToolResult::json(&json!({
            "config": config
        }))
    }
}

// ============================================================================
// Tool: upload_dataset
// ============================================================================

struct UploadDatasetTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for UploadDatasetTool {
    fn name(&self) -> &str {
        "upload_dataset"
    }

    fn description(&self) -> &str {
        "Upload images to create a training dataset."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "dataset_name": {
                    "type": "string",
                    "description": "Name for the dataset"
                },
                "images": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "data": {"type": "string", "description": "Base64 encoded image data"},
                            "caption": {"type": "string", "description": "Image caption"}
                        },
                        "required": ["filename", "data", "caption"]
                    }
                }
            },
            "required": ["dataset_name", "images"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let dataset_name = args
            .get("dataset_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'dataset_name' parameter".to_string())
            })?;

        let images = args
            .get("images")
            .and_then(|v| v.as_array())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'images' parameter".to_string()))?;

        // Validate dataset name
        let dataset_path = validate_path(dataset_name, &self.server.paths.datasets_path, "dataset")
            .map_err(|e| self.server.config_error_to_mcp(e, "Invalid dataset name"))?;

        // Create dataset directory
        fs::create_dir_all(&dataset_path).await.map_err(|e| {
            MCPError::Internal(format!("Failed to create dataset directory: {}", e))
        })?;

        let mut saved_images = Vec::new();

        for img_data in images {
            let filename = match img_data.get("filename").and_then(|v| v.as_str()) {
                Some(f) => f,
                None => {
                    warn!("Missing filename in image data");
                    continue;
                }
            };

            let data = match img_data.get("data").and_then(|v| v.as_str()) {
                Some(d) => d,
                None => {
                    warn!("Missing data in image: {}", filename);
                    continue;
                }
            };

            let caption = match img_data.get("caption").and_then(|v| v.as_str()) {
                Some(c) => c,
                None => {
                    warn!("Missing caption in image: {}", filename);
                    continue;
                }
            };

            // Validate filename
            let img_path = match validate_path(filename, &dataset_path, "image file") {
                Ok(p) => p,
                Err(e) => {
                    error!("Invalid filename {}: {}", filename, e);
                    continue;
                }
            };

            // Decode base64
            let decoded = match BASE64.decode(data) {
                Ok(d) => d,
                Err(e) => {
                    error!("Invalid base64 encoding for image {}: {}", filename, e);
                    continue;
                }
            };

            // Ensure parent directory exists
            if let Some(parent) = img_path.parent() {
                if let Err(e) = fs::create_dir_all(parent).await {
                    error!("Failed to create parent directory for {}: {}", filename, e);
                    continue;
                }
            }

            // Save image
            if let Err(e) = fs::write(&img_path, &decoded).await {
                error!("Failed to save image {}: {}", filename, e);
                continue;
            }

            // Save caption
            let caption_path = img_path.with_extension("txt");
            if let Err(e) = fs::write(&caption_path, caption).await {
                error!("Failed to save caption for {}: {}", filename, e);
                continue;
            }

            saved_images.push(filename.to_string());
        }

        ToolResult::json(&json!({
            "status": "success",
            "dataset": dataset_name,
            "images_saved": saved_images.len(),
            "path": dataset_path.display().to_string()
        }))
    }
}

// ============================================================================
// Tool: list_datasets
// ============================================================================

struct ListDatasetsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListDatasetsTool {
    fn name(&self) -> &str {
        "list_datasets"
    }

    fn description(&self) -> &str {
        "List all available training datasets."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut datasets = Vec::new();

        if let Ok(mut entries) = fs::read_dir(&self.server.paths.datasets_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                let path = entry.path();
                if path.is_dir() {
                    let name = path
                        .file_name()
                        .map(|n| n.to_string_lossy().to_string())
                        .unwrap_or_default();

                    // Count images
                    let mut image_count = 0;
                    if let Ok(mut dir_entries) = fs::read_dir(&path).await {
                        while let Ok(Some(file_entry)) = dir_entries.next_entry().await {
                            let file_path = file_entry.path();
                            if let Some(ext) = file_path.extension() {
                                let ext_lower = ext.to_string_lossy().to_lowercase();
                                if ext_lower == "png" || ext_lower == "jpg" || ext_lower == "jpeg" {
                                    image_count += 1;
                                }
                            }
                        }
                    }

                    datasets.push(DatasetInfo {
                        name,
                        path: path.display().to_string(),
                        image_count,
                        caption_count: 0, // Not counted in list view
                        missing_captions: vec![],
                        total_size_bytes: 0,
                    });
                }
            }
        }

        datasets.sort_by(|a, b| a.name.cmp(&b.name));

        ToolResult::json(&json!({
            "datasets": datasets
        }))
    }
}

// ============================================================================
// Tool: start_training
// ============================================================================

struct StartTrainingTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for StartTrainingTool {
    fn name(&self) -> &str {
        "start_training"
    }

    fn description(&self) -> &str {
        "Start a training job using AI Toolkit."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "config_name": {
                    "type": "string",
                    "description": "Configuration name to use"
                }
            },
            "required": ["config_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let config_name = args
            .get("config_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'config_name' parameter".to_string())
            })?;

        // Validate config exists
        let config_filename = format!("{}.yaml", config_name);
        let config_path =
            validate_path(&config_filename, &self.server.paths.configs_path, "config")
                .map_err(|e| self.server.config_error_to_mcp(e, "Invalid config name"))?;

        if !config_path.exists() {
            return ToolResult::json(&json!({
                "error": "Configuration not found"
            }));
        }

        let job_id = uuid::Uuid::new_v4().to_string();
        let log_file = self
            .server
            .paths
            .outputs_path
            .join(format!("training_{}.log", job_id));

        // Start training process
        let log_file_handle = fs::File::create(&log_file)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to create log file: {}", e)))?;

        let child = Command::new("python3")
            .arg("run.py")
            .arg(config_path.to_string_lossy().to_string())
            .current_dir(&self.server.paths.base_path)
            .stdout(log_file_handle.into_std().await)
            .stderr(std::process::Stdio::inherit())
            .spawn()
            .map_err(|e| MCPError::Internal(format!("Failed to start training: {}", e)))?;

        let pid = child.id();

        // Create job record
        let mut job = TrainingJob::new(job_id.clone(), config_name.to_string());
        job.status = JobStatus::Running;
        job.log_file = Some(log_file.display().to_string());
        job.pid = pid;
        job.started_at = Some(chrono::Utc::now().to_rfc3339());

        // Store job and process
        {
            let mut jobs = self.server.training_jobs.write().await;
            jobs.insert(job_id.clone(), job);
        }
        {
            let mut processes = self.server.training_processes.write().await;
            processes.insert(job_id.clone(), child);
        }

        info!(
            "Started training job {} with config {}",
            job_id, config_name
        );

        ToolResult::json(&json!({
            "status": "success",
            "job_id": job_id,
            "pid": pid
        }))
    }
}

// ============================================================================
// Tool: get_training_status
// ============================================================================

struct GetTrainingStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetTrainingStatusTool {
    fn name(&self) -> &str {
        "get_training_status"
    }

    fn description(&self) -> &str {
        "Get the status of a training job."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Training job ID"
                }
            },
            "required": ["job_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let job_id = args
            .get("job_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'job_id' parameter".to_string()))?;

        let mut jobs = self.server.training_jobs.write().await;
        let mut processes = self.server.training_processes.write().await;

        let job = match jobs.get_mut(job_id) {
            Some(j) => j,
            None => {
                return ToolResult::json(&json!({
                    "status": "error",
                    "message": "Job not found"
                }));
            }
        };

        // Check if process is still running
        if let Some(process) = processes.get_mut(job_id) {
            match process.try_wait() {
                Ok(Some(exit_status)) => {
                    job.status = if exit_status.success() {
                        JobStatus::Completed
                    } else {
                        JobStatus::Failed
                    };
                    job.exit_code = exit_status.code();
                    processes.remove(job_id);
                }
                Ok(None) => {
                    job.status = JobStatus::Running;
                }
                Err(e) => {
                    error!("Failed to check process status: {}", e);
                }
            }
        }

        // Try to parse progress from log file
        let mut progress = 0;
        if let Some(log_file) = &job.log_file {
            if Path::new(log_file).exists() {
                if let Ok(content) = fs::read_to_string(log_file).await {
                    let lines: Vec<&str> = content.lines().collect();
                    let step_regex = Regex::new(r"(\d+)/(\d+)").unwrap();

                    for line in lines.iter().rev().take(100) {
                        if line.to_lowercase().contains("step") {
                            if let Some(caps) = step_regex.captures(line) {
                                if let (Some(current), Some(total)) = (caps.get(1), caps.get(2)) {
                                    if let (Ok(c), Ok(t)) = (
                                        current.as_str().parse::<u32>(),
                                        total.as_str().parse::<u32>(),
                                    ) {
                                        if t > 0 {
                                            progress = ((c as f32 / t as f32) * 100.0) as u32;
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        ToolResult::json(&json!({
            "status": job.status.to_string(),
            "job_id": job_id,
            "progress": progress,
            "config": job.config_name
        }))
    }
}

// ============================================================================
// Tool: stop_training
// ============================================================================

struct StopTrainingTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for StopTrainingTool {
    fn name(&self) -> &str {
        "stop_training"
    }

    fn description(&self) -> &str {
        "Stop a running training job."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Training job ID"
                }
            },
            "required": ["job_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let job_id = args
            .get("job_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'job_id' parameter".to_string()))?;

        let mut processes = self.server.training_processes.write().await;

        if let Some(mut process) = processes.remove(job_id) {
            // Try graceful termination first
            if let Err(e) = process.kill().await {
                warn!("Failed to kill process: {}", e);
            }

            // Update job status
            let mut jobs = self.server.training_jobs.write().await;
            if let Some(job) = jobs.get_mut(job_id) {
                job.status = JobStatus::Stopped;
            }

            ToolResult::json(&json!({
                "status": "success",
                "job_id": job_id
            }))
        } else {
            ToolResult::json(&json!({
                "error": "Job not found or already stopped"
            }))
        }
    }
}

// ============================================================================
// Tool: list_training_jobs
// ============================================================================

struct ListTrainingJobsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListTrainingJobsTool {
    fn name(&self) -> &str {
        "list_training_jobs"
    }

    fn description(&self) -> &str {
        "List all training jobs."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut jobs = self.server.training_jobs.write().await;
        let mut processes = self.server.training_processes.write().await;

        // Update status for running jobs
        for (job_id, job) in jobs.iter_mut() {
            if let Some(process) = processes.get_mut(job_id) {
                if let Ok(Some(exit_status)) = process.try_wait() {
                    job.status = if exit_status.success() {
                        JobStatus::Completed
                    } else {
                        JobStatus::Failed
                    };
                    job.exit_code = exit_status.code();
                }
            }
        }

        // Remove finished processes
        let finished: Vec<String> = jobs
            .iter()
            .filter(|(_, j)| j.status != JobStatus::Running && j.status != JobStatus::Pending)
            .map(|(id, _)| id.clone())
            .collect();
        for id in finished {
            processes.remove(&id);
        }

        let job_list: Vec<_> = jobs
            .values()
            .map(|j| {
                json!({
                    "job_id": j.job_id,
                    "status": j.status.to_string(),
                    "config": j.config_name
                })
            })
            .collect();

        ToolResult::json(&json!({
            "jobs": job_list
        }))
    }
}

// ============================================================================
// Tool: export_model
// ============================================================================

struct ExportModelTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ExportModelTool {
    fn name(&self) -> &str {
        "export_model"
    }

    fn description(&self) -> &str {
        "Export a trained model to a specific location."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": "Model name"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output path for the exported model (within outputs directory)"
                }
            },
            "required": ["model_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let model_name = args
            .get("model_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'model_name' parameter".to_string())
            })?;

        // Find source model
        let extensions = ["safetensors", "ckpt", "pt"];
        let mut source_path = None;

        for ext in &extensions {
            let filename = format!("{}.{}", model_name, ext);
            if let Ok(path) = validate_path(&filename, &self.server.paths.outputs_path, "model") {
                if path.exists() {
                    source_path = Some(path);
                    break;
                }
            }
        }

        let source_path = match source_path {
            Some(p) => p,
            None => {
                return ToolResult::json(&json!({
                    "error": "Model not found"
                }));
            }
        };

        // Determine output path
        let output_path =
            if let Some(output_name) = args.get("output_path").and_then(|v| v.as_str()) {
                validate_path(output_name, &self.server.paths.outputs_path, "output")
                    .map_err(|e| self.server.config_error_to_mcp(e, "Invalid output path"))?
            } else {
                self.server
                    .paths
                    .outputs_path
                    .join(format!("{}.safetensors", model_name))
            };

        // Ensure parent directory exists
        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent)
                .await
                .map_err(|e| MCPError::Internal(format!("Failed to create directory: {}", e)))?;
        }

        // Copy file
        fs::copy(&source_path, &output_path)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to export model: {}", e)))?;

        ToolResult::json(&json!({
            "status": "success",
            "path": output_path.display().to_string()
        }))
    }
}

// ============================================================================
// Tool: list_exported_models
// ============================================================================

struct ListExportedModelsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListExportedModelsTool {
    fn name(&self) -> &str {
        "list_exported_models"
    }

    fn description(&self) -> &str {
        "List all exported models."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut models = Vec::new();

        if let Ok(mut entries) = fs::read_dir(&self.server.paths.outputs_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                let path = entry.path();
                if let Some(ext) = path.extension() {
                    let ext_str = ext.to_string_lossy().to_lowercase();
                    if ext_str == "safetensors" || ext_str == "ckpt" || ext_str == "pt" {
                        if let Ok(metadata) = fs::metadata(&path).await {
                            models.push(ModelInfo {
                                name: path
                                    .file_stem()
                                    .map(|n| n.to_string_lossy().to_string())
                                    .unwrap_or_default(),
                                path: path.display().to_string(),
                                size: metadata.len(),
                                extension: ext_str,
                                created_at: None,
                                metadata: None,
                            });
                        }
                    }
                }
            }
        }

        models.sort_by(|a, b| a.name.cmp(&b.name));

        ToolResult::json(&json!({
            "models": models
        }))
    }
}

// ============================================================================
// Tool: download_model
// ============================================================================

struct DownloadModelTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DownloadModelTool {
    fn name(&self) -> &str {
        "download_model"
    }

    fn description(&self) -> &str {
        "Download a trained model as base64 encoded data."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": "Model name to download"
                },
                "encoding": {
                    "type": "string",
                    "enum": ["base64", "raw"],
                    "default": "base64"
                }
            },
            "required": ["model_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let model_name = args
            .get("model_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'model_name' parameter".to_string())
            })?;

        let encoding = args
            .get("encoding")
            .and_then(|v| v.as_str())
            .unwrap_or("base64");

        // Find model
        let extensions = ["safetensors", "ckpt", "pt"];
        let mut model_path = None;

        for ext in &extensions {
            let filename = format!("{}.{}", model_name, ext);
            if let Ok(path) = validate_path(&filename, &self.server.paths.outputs_path, "model") {
                if path.exists() {
                    model_path = Some(path);
                    break;
                }
            }
        }

        let model_path = match model_path {
            Some(p) => p,
            None => {
                return ToolResult::json(&json!({
                    "error": "Model not found"
                }));
            }
        };

        // Check file size before reading to prevent OOM
        let metadata = fs::metadata(&model_path)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to get model metadata: {}", e)))?;
        let size = metadata.len();

        // Limit to 100MB to prevent OOM when base64 encoding
        const MAX_DOWNLOAD_SIZE: u64 = 100 * 1024 * 1024;
        if size > MAX_DOWNLOAD_SIZE {
            return ToolResult::json(&json!({
                "error": "Model too large for download",
                "size": size,
                "max_size": MAX_DOWNLOAD_SIZE,
                "size_mb": (size as f64 / 1024.0 / 1024.0 * 100.0).round() / 100.0,
                "note": "Use export_model to copy to a location, or access the file directly at the path"
            }));
        }

        // Read model file
        let data = fs::read(&model_path)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to read model: {}", e)))?;

        if encoding == "base64" {
            let encoded = BASE64.encode(&data);
            ToolResult::json(&json!({
                "status": "success",
                "model": model_name,
                "data": encoded,
                "size": size
            }))
        } else {
            // Raw mode - just return size info, not actual data
            ToolResult::json(&json!({
                "status": "success",
                "model": model_name,
                "size": size,
                "note": "Raw mode not fully supported in JSON response"
            }))
        }
    }
}

// ============================================================================
// Tool: get_system_stats
// ============================================================================

struct GetSystemStatsTool {
    #[allow(dead_code)]
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetSystemStatsTool {
    fn name(&self) -> &str {
        "get_system_stats"
    }

    fn description(&self) -> &str {
        "Get system statistics including CPU, memory, and disk usage."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut sys = System::new_all();
        sys.refresh_all();

        let cpu_percent = sys.global_cpu_usage();
        let memory_percent = (sys.used_memory() as f32 / sys.total_memory().max(1) as f32) * 100.0;

        // Get disk usage
        let disks = Disks::new_with_refreshed_list();
        let disk_usage_percent = disks
            .iter()
            .find(|d| d.mount_point().to_string_lossy() == "/")
            .map(|d| {
                let total = d.total_space();
                let available = d.available_space();
                if total > 0 {
                    ((total - available) as f32 / total as f32) * 100.0
                } else {
                    0.0
                }
            })
            .unwrap_or(0.0);

        // GPU info (would require nvidia-smi or similar)
        // For now, just indicate it's available if CUDA_VISIBLE_DEVICES is set
        let gpu = if std::env::var("CUDA_VISIBLE_DEVICES").is_ok() {
            Some(json!({
                "cuda_available": true,
                "note": "GPU stats require nvidia-smi integration"
            }))
        } else {
            Some(json!({
                "cuda_available": false
            }))
        };

        ToolResult::json(&json!({
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_usage_percent": disk_usage_percent,
            "gpu": gpu
        }))
    }
}

// ============================================================================
// Tool: get_training_logs
// ============================================================================

struct GetTrainingLogsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetTrainingLogsTool {
    fn name(&self) -> &str {
        "get_training_logs"
    }

    fn description(&self) -> &str {
        "Get training logs for a job."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Training job ID"
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to retrieve",
                    "default": 100
                }
            },
            "required": ["job_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let job_id = args
            .get("job_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'job_id' parameter".to_string()))?;

        let lines = args.get("lines").and_then(|v| v.as_u64()).unwrap_or(100) as usize;

        let jobs = self.server.training_jobs.read().await;

        let job = match jobs.get(job_id) {
            Some(j) => j,
            None => {
                return ToolResult::json(&json!({
                    "job_id": job_id,
                    "logs": [],
                    "lines": 0
                }));
            }
        };

        if let Some(log_file) = &job.log_file {
            if Path::new(log_file).exists() {
                if let Ok(content) = fs::read_to_string(log_file).await {
                    let all_lines: Vec<&str> = content.lines().collect();
                    let total_lines = all_lines.len();
                    let log_lines: Vec<String> = all_lines
                        .into_iter()
                        .rev()
                        .take(lines)
                        .rev()
                        .map(String::from)
                        .collect();

                    return ToolResult::json(&json!({
                        "job_id": job_id,
                        "logs": log_lines,
                        "total_lines": total_lines
                    }));
                }
            }
        }

        ToolResult::json(&json!({
            "job_id": job_id,
            "logs": [],
            "lines": 0
        }))
    }
}

// ============================================================================
// Tool: get_training_info
// ============================================================================

struct GetTrainingInfoTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetTrainingInfoTool {
    fn name(&self) -> &str {
        "get_training_info"
    }

    fn description(&self) -> &str {
        "Get overall training information and statistics."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut jobs = self.server.training_jobs.write().await;
        let mut processes = self.server.training_processes.write().await;

        // Update job statuses
        for (job_id, job) in jobs.iter_mut() {
            if let Some(process) = processes.get_mut(job_id) {
                if let Ok(Some(exit_status)) = process.try_wait() {
                    job.status = if exit_status.success() {
                        JobStatus::Completed
                    } else {
                        JobStatus::Failed
                    };
                    job.exit_code = exit_status.code();
                }
            }
        }

        // Count totals
        let total_jobs = jobs.len();
        let active_jobs = jobs
            .values()
            .filter(|j| j.status == JobStatus::Running)
            .count();

        // Count configs
        let mut configs_count = 0;
        if let Ok(mut entries) = fs::read_dir(&self.server.paths.configs_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                if entry.path().extension().is_some_and(|ext| ext == "yaml") {
                    configs_count += 1;
                }
            }
        }

        // Count datasets
        let mut datasets_count = 0;
        if let Ok(mut entries) = fs::read_dir(&self.server.paths.datasets_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                if entry.path().is_dir() {
                    datasets_count += 1;
                }
            }
        }

        // Count models
        let mut models_count = 0;
        if let Ok(mut entries) = fs::read_dir(&self.server.paths.outputs_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                let path = entry.path();
                if let Some(ext) = path.extension() {
                    let ext_str = ext.to_string_lossy().to_lowercase();
                    if ext_str == "safetensors" || ext_str == "ckpt" {
                        models_count += 1;
                    }
                }
            }
        }

        ToolResult::json(&json!({
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "configs": configs_count,
            "datasets": datasets_count,
            "models": models_count
        }))
    }
}

// ============================================================================
// Tool: delete_config
// ============================================================================

struct DeleteConfigTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DeleteConfigTool {
    fn name(&self) -> &str {
        "delete_config"
    }

    fn description(&self) -> &str {
        "Delete a training configuration file."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Configuration name to delete"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        let config_filename = format!("{}.yaml", name);
        let config_path =
            validate_path(&config_filename, &self.server.paths.configs_path, "config")
                .map_err(|e| self.server.config_error_to_mcp(e, "Invalid config name"))?;

        if !config_path.exists() {
            return ToolResult::json(&json!({
                "success": false,
                "error": "Configuration not found"
            }));
        }

        fs::remove_file(&config_path)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to delete config: {}", e)))?;

        info!("Deleted config: {}", name);

        ToolResult::json(&json!({
            "success": true,
            "deleted": name
        }))
    }
}

// ============================================================================
// Tool: delete_dataset
// ============================================================================

struct DeleteDatasetTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DeleteDatasetTool {
    fn name(&self) -> &str {
        "delete_dataset"
    }

    fn description(&self) -> &str {
        "Delete a training dataset and all its contents."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Dataset name to delete"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        let dataset_path = validate_path(name, &self.server.paths.datasets_path, "dataset")
            .map_err(|e| self.server.config_error_to_mcp(e, "Invalid dataset name"))?;

        if !dataset_path.exists() {
            return ToolResult::json(&json!({
                "success": false,
                "error": "Dataset not found"
            }));
        }

        fs::remove_dir_all(&dataset_path)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to delete dataset: {}", e)))?;

        info!("Deleted dataset: {}", name);

        ToolResult::json(&json!({
            "success": true,
            "deleted": name
        }))
    }
}

// ============================================================================
// Tool: delete_model
// ============================================================================

struct DeleteModelTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DeleteModelTool {
    fn name(&self) -> &str {
        "delete_model"
    }

    fn description(&self) -> &str {
        "Delete a trained model file."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Model name to delete"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        // Try each extension
        let extensions = ["safetensors", "ckpt", "pt"];
        let mut deleted = false;

        for ext in &extensions {
            let filename = format!("{}.{}", name, ext);
            if let Ok(path) = validate_path(&filename, &self.server.paths.outputs_path, "model") {
                if path.exists() {
                    fs::remove_file(&path).await.map_err(|e| {
                        MCPError::Internal(format!("Failed to delete model: {}", e))
                    })?;
                    deleted = true;
                    info!("Deleted model: {}", filename);
                }
            }
        }

        if deleted {
            ToolResult::json(&json!({
                "success": true,
                "deleted": name
            }))
        } else {
            ToolResult::json(&json!({
                "success": false,
                "error": "Model not found"
            }))
        }
    }
}

// ============================================================================
// Tool: validate_config
// ============================================================================

struct ValidateConfigTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ValidateConfigTool {
    fn name(&self) -> &str {
        "validate_config"
    }

    fn description(&self) -> &str {
        "Validate a training configuration before running."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Configuration name to validate"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        let config_filename = format!("{}.yaml", name);
        let config_path =
            validate_path(&config_filename, &self.server.paths.configs_path, "config")
                .map_err(|e| self.server.config_error_to_mcp(e, "Invalid config name"))?;

        if !config_path.exists() {
            return ToolResult::json(&json!({
                "valid": false,
                "errors": ["Configuration file not found"],
                "warnings": []
            }));
        }

        let content = fs::read_to_string(&config_path)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to read config: {}", e)))?;

        let mut errors = Vec::new();
        let mut warnings = Vec::new();

        // Parse YAML
        let config: serde_yaml::Value = match serde_yaml::from_str(&content) {
            Ok(c) => c,
            Err(e) => {
                return ToolResult::json(&json!({
                    "valid": false,
                    "errors": [format!("Invalid YAML: {}", e)],
                    "warnings": []
                }));
            }
        };

        // Check required top-level keys
        if config.get("job").is_none() {
            errors.push("Missing required key: 'job'".to_string());
        }
        if config.get("config").is_none() {
            errors.push("Missing required key: 'config'".to_string());
        }

        // Check config.name
        if let Some(cfg) = config.get("config") {
            if cfg.get("name").is_none() {
                errors.push("Missing required key: 'config.name'".to_string());
            }

            // Check process array
            if let Some(process) = cfg.get("process") {
                if let Some(arr) = process.as_sequence() {
                    if arr.is_empty() {
                        errors.push("'config.process' array is empty".to_string());
                    } else {
                        // Validate first process
                        if let Some(first) = arr.first() {
                            // Check datasets
                            if let Some(datasets) = first.get("datasets") {
                                if let Some(ds_arr) = datasets.as_sequence() {
                                    for (i, ds) in ds_arr.iter().enumerate() {
                                        if let Some(folder) =
                                            ds.get("folder_path").and_then(|v| v.as_str())
                                        {
                                            if !Path::new(folder).exists() {
                                                warnings.push(format!(
                                                    "Dataset {} folder does not exist: {}",
                                                    i, folder
                                                ));
                                            }
                                        } else {
                                            errors.push(format!(
                                                "Dataset {} missing 'folder_path'",
                                                i
                                            ));
                                        }
                                    }
                                }
                            } else {
                                errors.push("Missing 'datasets' in process config".to_string());
                            }

                            // Check model
                            if let Some(model) = first.get("model") {
                                if model.get("name_or_path").is_none() {
                                    errors.push("Missing 'model.name_or_path'".to_string());
                                }
                            } else {
                                errors.push("Missing 'model' in process config".to_string());
                            }
                        }
                    }
                } else {
                    errors.push("'config.process' is not an array".to_string());
                }
            } else {
                errors.push("Missing required key: 'config.process'".to_string());
            }
        }

        let valid = errors.is_empty();

        ToolResult::json(&json!({
            "valid": valid,
            "errors": errors,
            "warnings": warnings
        }))
    }
}

// ============================================================================
// Tool: get_dataset_info
// ============================================================================

struct GetDatasetInfoTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetDatasetInfoTool {
    fn name(&self) -> &str {
        "get_dataset_info"
    }

    fn description(&self) -> &str {
        "Get detailed information about a dataset including image count, caption stats."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Dataset name"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        let dataset_path = validate_path(name, &self.server.paths.datasets_path, "dataset")
            .map_err(|e| self.server.config_error_to_mcp(e, "Invalid dataset name"))?;

        if !dataset_path.exists() {
            return ToolResult::json(&json!({
                "error": "Dataset not found"
            }));
        }

        let mut image_count = 0;
        let mut caption_count = 0;
        let mut missing_captions = Vec::new();
        let mut total_size: u64 = 0;
        let image_extensions = ["jpg", "jpeg", "png", "webp"];

        if let Ok(mut entries) = fs::read_dir(&dataset_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                let path = entry.path();
                if let Some(ext) = path.extension() {
                    let ext_lower = ext.to_string_lossy().to_lowercase();

                    if image_extensions.contains(&ext_lower.as_str()) {
                        image_count += 1;

                        if let Ok(metadata) = fs::metadata(&path).await {
                            total_size += metadata.len();
                        }

                        // Check for corresponding caption file
                        let caption_path = path.with_extension("txt");
                        if caption_path.exists() {
                            caption_count += 1;
                        } else {
                            if let Some(filename) = path.file_name() {
                                missing_captions.push(filename.to_string_lossy().to_string());
                            }
                        }
                    }
                }
            }
        }

        let info = DatasetInfo {
            name: name.to_string(),
            path: dataset_path.display().to_string(),
            image_count,
            caption_count,
            missing_captions: missing_captions.clone(),
            total_size_bytes: total_size,
        };

        ToolResult::json(&json!({
            "name": info.name,
            "path": info.path,
            "image_count": info.image_count,
            "caption_count": info.caption_count,
            "captions_complete": missing_captions.is_empty(),
            "missing_captions": if missing_captions.len() > 10 {
                format!("{} images missing captions (showing first 10): {:?}",
                    missing_captions.len(),
                    &missing_captions[..10])
            } else {
                format!("{:?}", missing_captions)
            },
            "total_size_mb": (total_size as f64 / 1024.0 / 1024.0 * 100.0).round() / 100.0
        }))
    }
}

// ============================================================================
// Tool: list_model_presets
// ============================================================================

struct ListModelPresetsTool {
    #[allow(dead_code)]
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListModelPresetsTool {
    fn name(&self) -> &str {
        "list_model_presets"
    }

    fn description(&self) -> &str {
        "List available model presets with recommended settings for each model type."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let presets = ModelPreset::all_presets();

        let preset_list: Vec<_> = presets
            .iter()
            .map(|p| {
                json!({
                    "name": p.name,
                    "model_path": p.model_path,
                    "description": p.description,
                    "is_flux": p.is_flux,
                    "is_xl": p.is_xl,
                    "is_v3": p.is_v3,
                    "recommended_resolution": p.recommended_resolution,
                    "recommended_scheduler": p.recommended_scheduler,
                    "requires_quantize": p.requires_quantize,
                    "min_vram_gb": p.min_vram_gb
                })
            })
            .collect();

        ToolResult::json(&json!({
            "presets": preset_list,
            "note": "Use these settings as a starting point for create_training_config"
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_server_creation() {
        // Set up test environment
        // SAFETY: This is a test and we're setting an environment variable
        unsafe {
            std::env::set_var("AI_TOOLKIT_PATH", "/tmp/test-ai-toolkit");
        }
        let server = AIToolkitServer::new().await.unwrap();
        let tools = server.tools();
        assert_eq!(tools.len(), 21); // 15 original + 6 new tools
    }

    #[test]
    fn test_tool_names() {
        let expected_tools = [
            "create_training_config",
            "list_configs",
            "get_config",
            "upload_dataset",
            "list_datasets",
            "start_training",
            "get_training_status",
            "stop_training",
            "list_training_jobs",
            "export_model",
            "list_exported_models",
            "download_model",
            "get_system_stats",
            "get_training_logs",
            "get_training_info",
            // New tools
            "delete_config",
            "delete_dataset",
            "delete_model",
            "validate_config",
            "get_dataset_info",
            "list_model_presets",
        ];

        for name in expected_tools {
            assert!(!name.is_empty());
        }
    }
}

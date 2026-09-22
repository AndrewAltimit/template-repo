//! MCP tool definitions for the AI Toolkit server.
//!
//! Every tool deserializes its arguments into a typed struct (missing or
//! mistyped arguments become a clean `InvalidParameters` error, never a
//! panic) and returns either a JSON result or an `isError` result carrying a
//! human-readable message. Blocking filesystem work runs on the blocking pool.

use async_trait::async_trait;
use base64::{Engine, engine::general_purpose::STANDARD as BASE64};
use mcp_core::prelude::*;
use regex::Regex;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::collections::{BTreeMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::{Arc, LazyLock};
use std::time::Duration;
use tokio::fs;
use tracing::{info, warn};

use crate::config::{AIToolkitPaths, validate_name};
use crate::datasets::{self, ImageUpload, scan_dataset};
use crate::jobs::{JobManager, JobStatus, LaunchSpec, default_state_file};
use crate::logs::{self, LOG_TAIL_BYTES, PROGRESS_TAIL_BYTES};
use crate::models::{self, list_models, resolve_model};
use crate::system;
use crate::training_config::{
    CreateConfigArgs, build_config, summarize_config, validate_config_yaml,
};
use crate::types::ModelPreset;

/// Whole-file `download_model` limit (legacy, non-chunked mode).
const MAX_DOWNLOAD_SIZE: u64 = 100 * 1024 * 1024;
/// Default chunk size for chunked downloads.
const DEFAULT_CHUNK_SIZE: u64 = 8 * 1024 * 1024;
/// Maximum chunk size for chunked downloads.
const MAX_CHUNK_SIZE: u64 = 32 * 1024 * 1024;
/// Maximum number of sample images returned inline.
const MAX_SAMPLES: usize = 16;
/// Per-image and total byte budgets for inline sample images.
const MAX_SAMPLE_IMAGE_BYTES: u64 = 5 * 1024 * 1024;
const MAX_SAMPLE_TOTAL_BYTES: u64 = 16 * 1024 * 1024;

/// Shared state handed to every tool.
pub struct Ctx {
    pub paths: AIToolkitPaths,
    pub jobs: Arc<JobManager>,
}

/// AI Toolkit MCP server: owns the shared context and builds the tool set.
pub struct AIToolkitServer {
    ctx: Arc<Ctx>,
}

impl AIToolkitServer {
    /// Create a server from environment configuration.
    pub fn from_env() -> Self {
        Self::with_paths(AIToolkitPaths::from_env())
    }

    /// Create a server for an explicit filesystem layout.
    pub fn with_paths(paths: AIToolkitPaths) -> Self {
        if let Err(e) = paths.ensure_directories() {
            warn!("Could not create AI Toolkit directories: {e}. Server will still start.");
        }
        if !paths.run_script().is_file() {
            warn!(
                "AI Toolkit entry point not found at {} - start_training will fail until AI_TOOLKIT_PATH points at an ai-toolkit checkout",
                paths.run_script().display()
            );
        }
        let jobs = Arc::new(JobManager::new(Some(default_state_file(
            &paths.outputs_path,
        ))));
        Self {
            ctx: Arc::new(Ctx { paths, jobs }),
        }
    }

    /// All tools as boxed trait objects.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let c = || self.ctx.clone();
        vec![
            Arc::new(CreateTrainingConfigTool { ctx: c() }),
            Arc::new(ListConfigsTool { ctx: c() }),
            Arc::new(GetConfigTool { ctx: c() }),
            Arc::new(UploadDatasetTool { ctx: c() }),
            Arc::new(ListDatasetsTool { ctx: c() }),
            Arc::new(StartTrainingTool { ctx: c() }),
            Arc::new(GetTrainingStatusTool { ctx: c() }),
            Arc::new(StopTrainingTool { ctx: c() }),
            Arc::new(ListTrainingJobsTool { ctx: c() }),
            Arc::new(ExportModelTool { ctx: c() }),
            Arc::new(ListExportedModelsTool { ctx: c() }),
            Arc::new(DownloadModelTool { ctx: c() }),
            Arc::new(GetSystemStatsTool { ctx: c() }),
            Arc::new(GetTrainingLogsTool { ctx: c() }),
            Arc::new(GetTrainingInfoTool { ctx: c() }),
            Arc::new(DeleteConfigTool { ctx: c() }),
            Arc::new(DeleteDatasetTool { ctx: c() }),
            Arc::new(DeleteModelTool { ctx: c() }),
            Arc::new(ValidateConfigTool { ctx: c() }),
            Arc::new(GetDatasetInfoTool { ctx: c() }),
            Arc::new(ListModelPresetsTool { ctx: c() }),
            Arc::new(GetTrainingSamplesTool { ctx: c() }),
        ]
    }
}

// ============================================================================
// Plumbing
// ============================================================================

/// Handler outcome: a tool result, or a message returned as an `isError` result.
type Outcome = std::result::Result<ToolResult, String>;

fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

fn ok(v: Value) -> Outcome {
    ToolResult::json(&v).map_err(|e| format!("Failed to serialize result: {e}"))
}

/// Run blocking work on the blocking thread pool.
async fn blocking<T: Send + 'static>(
    f: impl FnOnce() -> T + Send + 'static,
) -> std::result::Result<T, String> {
    tokio::task::spawn_blocking(f)
        .await
        .map_err(|e| format!("Internal task failed: {e}"))
}

fn mb(bytes: u64) -> f64 {
    (bytes as f64 / 1024.0 / 1024.0 * 100.0).round() / 100.0
}

/// Defines a tool struct whose `execute` parses `$args` and calls `$handler`.
macro_rules! tool {
    ($ty:ident, $name:literal, $args:ty, $handler:ident, $desc:expr, $schema:expr $(,)?) => {
        struct $ty {
            ctx: Arc<Ctx>,
        }

        #[async_trait]
        impl Tool for $ty {
            fn name(&self) -> &str {
                $name
            }
            fn description(&self) -> &str {
                $desc
            }
            fn schema(&self) -> Value {
                $schema
            }
            async fn execute(&self, args: Value) -> Result<ToolResult> {
                let args: $args = parse_args(args)?;
                Ok($handler(&self.ctx, args)
                    .await
                    .unwrap_or_else(ToolResult::error))
            }
        }
    };
}

/// Arguments for tools that take none (unknown keys are ignored).
#[derive(Deserialize)]
struct NoArgs {}

#[derive(Deserialize)]
struct NameArgs {
    name: String,
}

fn empty_schema() -> Value {
    json!({"type": "object", "properties": {}})
}

fn name_schema(desc: &str) -> Value {
    json!({
        "type": "object",
        "properties": {"name": {"type": "string", "description": desc}},
        "required": ["name"]
    })
}

// ============================================================================
// Configs
// ============================================================================

tool!(
    CreateTrainingConfigTool,
    "create_training_config",
    CreateConfigArgs,
    create_training_config,
    r#"Create an AI Toolkit LoRA training config (<configs>/<name>.yaml).

Model-aware defaults are derived from `preset` or `model_name`:
- Flux.1-dev/schnell, SD 3.5: flowmatch scheduler, adamw8bit, bf16, quantize, multi-resolution [512,768,1024]
- SDXL: 1024px; SD 1.5: 512px, ddpm, adamw

`dataset_path` may be a dataset name from list_datasets (recommended), an absolute path, or a path relative to the AI Toolkit directory.
Trained weights are written to <outputs>/<name>/. Use list_model_presets for presets and validate_config before start_training."#,
    json!({
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Config name ([A-Za-z0-9._-]); also the output folder and LoRA file name"},
            "dataset_path": {"type": "string", "description": "Dataset name (e.g. 'my_dataset'), or absolute path to a folder of images + .txt captions"},
            "preset": {"type": "string", "enum": ["flux-dev", "flux-schnell", "sd15", "sdxl", "sd35-large"], "description": "Model preset; sets model_name and architecture flags"},
            "model_name": {"type": "string", "description": "Base model HF id or path (overrides preset). Default: runwayml/stable-diffusion-v1-5"},
            "resolution": {
                "oneOf": [
                    {"type": "integer"},
                    {"type": "array", "items": {"type": "integer"}}
                ],
                "description": "Training resolution (128-4096) - single value or array like [512, 768, 1024]. Default depends on model"
            },
            "steps": {"type": "integer", "minimum": 1, "description": "Total training steps (500-4000 typical)", "default": 2000},
            "batch_size": {"type": "integer", "minimum": 1, "maximum": 64, "default": 1},
            "rank": {"type": "integer", "minimum": 1, "maximum": 1024, "description": "LoRA rank (linear dimension)", "default": 16},
            "alpha": {"type": "integer", "minimum": 1, "maximum": 1024, "description": "LoRA alpha (defaults to rank)"},
            "lr": {"type": "number", "description": "Learning rate", "default": 0.0001},
            "optimizer": {"type": "string", "enum": ["adamw", "adamw8bit", "prodigy", "lion", "adafactor"], "description": "Default: adamw8bit for Flux/SD3, adamw otherwise"},
            "noise_scheduler": {"type": "string", "enum": ["ddpm", "ddim", "flowmatch", "euler", "euler_a"], "description": "Default: flowmatch for Flux/SD3, ddpm otherwise"},
            "trigger_word": {"type": "string", "description": "Trigger word (added to captions that lack it, and to default sample prompts)"},
            "prompts": {"type": "array", "items": {"type": "string"}, "description": "Sample prompts rendered during training"},
            "is_flux": {"type": "boolean", "description": "Force Flux architecture (auto-detected from model_name)"},
            "is_xl": {"type": "boolean", "description": "Force SDXL architecture (auto-detected)"},
            "is_v3": {"type": "boolean", "description": "Force SD 3.x architecture (auto-detected)"},
            "quantize": {"type": "boolean", "description": "8-bit quantize the base model (default true for Flux/SD3)"},
            "gradient_checkpointing": {"type": "boolean", "default": true},
            "cache_latents": {"type": "boolean", "description": "Cache latents to disk", "default": true},
            "caption_dropout_rate": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.05},
            "save_every": {"type": "integer", "minimum": 1, "description": "Checkpoint interval in steps", "default": 250},
            "sample_every": {"type": "integer", "minimum": 1, "description": "Sample image interval in steps", "default": 250},
            "disable_sampling": {"type": "boolean", "description": "Skip sample generation (faster)", "default": false},
            "low_vram": {"type": "boolean", "description": "AI Toolkit low-VRAM mode (slower)", "default": false},
            "overwrite": {"type": "boolean", "description": "Replace an existing config with the same name", "default": true}
        },
        "required": ["name", "dataset_path"]
    }),
);

async fn create_training_config(ctx: &Ctx, args: CreateConfigArgs) -> Outcome {
    let name = args.name.clone();
    let overwrite = args.overwrite.unwrap_or(true);
    let paths = ctx.paths.clone();
    let built = blocking(move || build_config(&paths, &args)).await??;

    let path = ctx.paths.config_file(&name).map_err(|e| e.to_string())?;
    let existed = fs::try_exists(&path).await.unwrap_or(false);
    if existed && !overwrite {
        return Err(format!(
            "Config '{name}' already exists (pass overwrite: true to replace it)"
        ));
    }
    let yaml = serde_yaml::to_string(&built.config)
        .map_err(|e| format!("Failed to serialize config: {e}"))?;
    fs::create_dir_all(&ctx.paths.configs_path)
        .await
        .map_err(|e| format!("Failed to create config directory: {e}"))?;
    fs::write(&path, yaml)
        .await
        .map_err(|e| format!("Failed to write config: {e}"))?;
    info!("Created training config: {}", path.display());

    let process = &built.config.config.process[0];
    ok(json!({
        "status": "success",
        "config": name,
        "path": path.display().to_string(),
        "overwritten": existed,
        "dataset_folder": built.dataset_folder.display().to_string(),
        "output_folder": ctx.paths.outputs_path.join(&name).display().to_string(),
        "model": process.model.name_or_path,
        "architecture": {
            "is_flux": built.arch.is_flux,
            "is_xl": built.arch.is_xl,
            "is_v3": built.arch.is_v3
        },
        "steps": process.train.steps,
        "warnings": built.warnings
    }))
}

tool!(
    ListConfigsTool,
    "list_configs",
    NoArgs,
    list_configs,
    "List training config names (YAML files in the configs directory).",
    empty_schema(),
);

async fn config_names(dir: &Path) -> Vec<String> {
    let mut names = Vec::new();
    if let Ok(mut entries) = fs::read_dir(dir).await {
        while let Ok(Some(entry)) = entries.next_entry().await {
            let path = entry.path();
            if path.extension().is_some_and(|e| e == "yaml")
                && let Some(stem) = path.file_stem()
            {
                names.push(stem.to_string_lossy().to_string());
            }
        }
    }
    names.sort();
    names
}

async fn list_configs(ctx: &Ctx, _: NoArgs) -> Outcome {
    let configs = config_names(&ctx.paths.configs_path).await;
    ok(json!({"configs": configs, "count": configs.len()}))
}

tool!(
    GetConfigTool,
    "get_config",
    NameArgs,
    get_config,
    "Get a training config by name, parsed from YAML into JSON.",
    name_schema("Configuration name"),
);

async fn read_config(ctx: &Ctx, name: &str) -> std::result::Result<(PathBuf, String), String> {
    let path = ctx
        .paths
        .config_file(name)
        .map_err(|e| format!("Invalid config name: {e}"))?;
    match fs::read_to_string(&path).await {
        Ok(text) => Ok((path, text)),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Err(format!(
            "Configuration '{name}' not found (see list_configs)"
        )),
        Err(e) => Err(format!("Failed to read config '{name}': {e}")),
    }
}

async fn get_config(ctx: &Ctx, a: NameArgs) -> Outcome {
    let (path, text) = read_config(ctx, &a.name).await?;
    let config: Value =
        serde_yaml::from_str(&text).map_err(|e| format!("Config is not valid YAML: {e}"))?;
    ok(json!({"name": a.name, "path": path.display().to_string(), "config": config}))
}

tool!(
    DeleteConfigTool,
    "delete_config",
    NameArgs,
    delete_config,
    "Delete a training config file.",
    name_schema("Configuration name to delete"),
);

async fn delete_config(ctx: &Ctx, a: NameArgs) -> Outcome {
    let path = ctx
        .paths
        .config_file(&a.name)
        .map_err(|e| format!("Invalid config name: {e}"))?;
    match fs::remove_file(&path).await {
        Ok(()) => {
            info!("Deleted config: {}", a.name);
            ok(json!({"success": true, "deleted": a.name}))
        },
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            Err(format!("Configuration '{}' not found", a.name))
        },
        Err(e) => Err(format!("Failed to delete config: {e}")),
    }
}

tool!(
    ValidateConfigTool,
    "validate_config",
    NameArgs,
    validate_config,
    "Validate a training config before running: structure, architecture flags, hyper-parameters, and that every dataset folder exists and contains images. Returns {valid, errors, warnings}.",
    name_schema("Configuration name to validate"),
);

async fn validate_config(ctx: &Ctx, a: NameArgs) -> Outcome {
    let text = match read_config(ctx, &a.name).await {
        Ok((_, t)) => t,
        Err(e) => return ok(json!({"valid": false, "errors": [e], "warnings": []})),
    };
    let cfg: serde_yaml::Value = match serde_yaml::from_str(&text) {
        Ok(c) => c,
        Err(e) => {
            return ok(
                json!({"valid": false, "errors": [format!("Invalid YAML: {e}")], "warnings": []}),
            );
        },
    };
    let paths = ctx.paths.clone();
    let (validation, summary) = blocking(move || {
        (
            validate_config_yaml(&paths, &cfg),
            summarize_config(&paths, &cfg),
        )
    })
    .await?;
    ok(json!({
        "valid": validation.valid,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "run_name": summary.run_name,
        "steps": summary.steps,
        "training_folder": summary.training_folder.map(|p| p.display().to_string())
    }))
}

// ============================================================================
// Datasets
// ============================================================================

#[derive(Deserialize)]
struct UploadArgs {
    dataset_name: String,
    images: Vec<ImageUpload>,
    #[serde(default = "default_true")]
    overwrite: bool,
}

fn default_true() -> bool {
    true
}

tool!(
    UploadDatasetTool,
    "upload_dataset",
    UploadArgs,
    upload_dataset,
    "Upload base64 images (PNG/JPEG/WebP, max 50 MB each) with optional captions into <datasets>/<dataset_name>/. Each caption is saved as a same-named .txt file. Appends to an existing dataset. Returns per-image failures; errors only if nothing was saved.",
    json!({
        "type": "object",
        "properties": {
            "dataset_name": {"type": "string", "description": "Dataset name ([A-Za-z0-9._-])"},
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Plain file name with .png/.jpg/.jpeg/.webp extension"},
                        "data": {"type": "string", "description": "Base64 image data (a data: URL prefix is accepted)"},
                        "caption": {"type": "string", "description": "Caption text (recommended; include the trigger word)"}
                    },
                    "required": ["filename", "data"]
                }
            },
            "overwrite": {"type": "boolean", "description": "Replace files that already exist", "default": true}
        },
        "required": ["dataset_name", "images"]
    }),
);

async fn upload_dataset(ctx: &Ctx, a: UploadArgs) -> Outcome {
    if a.images.is_empty() {
        return Err("'images' must contain at least one image".into());
    }
    let dir = ctx
        .paths
        .dataset_dir(&a.dataset_name)
        .map_err(|e| format!("Invalid dataset name: {e}"))?;
    fs::create_dir_all(&dir)
        .await
        .map_err(|e| format!("Failed to create dataset directory: {e}"))?;

    // Decode and validate off the async runtime (base64 of large images is CPU work).
    let images = a.images;
    let prepared = blocking(move || {
        images
            .iter()
            .map(|u| (u.filename.clone(), datasets::prepare_image(u)))
            .collect::<Vec<_>>()
    })
    .await?;

    let mut saved = Vec::new();
    let mut failed = Vec::new();
    let mut seen = HashSet::new();
    for (filename, result) in prepared {
        let img = match result {
            Ok(img) => img,
            Err(e) => {
                failed.push(json!({"filename": filename, "error": e}));
                continue;
            },
        };
        let stem_key = Path::new(&img.filename)
            .file_stem()
            .map(|s| s.to_string_lossy().to_ascii_lowercase())
            .unwrap_or_default();
        if !seen.insert(stem_key) {
            failed.push(json!({"filename": filename, "error": "duplicate file name (captions would collide)"}));
            continue;
        }
        let img_path = dir.join(&img.filename);
        if !a.overwrite && fs::try_exists(&img_path).await.unwrap_or(false) {
            failed.push(
                json!({"filename": filename, "error": "already exists (overwrite is false)"}),
            );
            continue;
        }
        if let Err(e) = fs::write(&img_path, &img.bytes).await {
            failed.push(json!({"filename": filename, "error": format!("write failed: {e}")}));
            continue;
        }
        if let Some(caption) = &img.caption
            && let Err(e) = fs::write(img_path.with_extension("txt"), caption).await
        {
            failed
                .push(json!({"filename": filename, "error": format!("caption write failed: {e}")}));
            continue;
        }
        saved.push(json!({"filename": img.filename, "format": img.format, "bytes": img.bytes.len(), "captioned": img.caption.is_some()}));
    }

    if saved.is_empty() {
        return Err(format!(
            "No images were saved to dataset '{}': {}",
            a.dataset_name,
            Value::Array(failed)
        ));
    }
    let scan_dir = dir.clone();
    let stats = blocking(move || scan_dataset(&scan_dir, 0)).await?.ok();
    ok(json!({
        "status": if failed.is_empty() { "success" } else { "partial" },
        "dataset": a.dataset_name,
        "images_saved": saved.len(),
        "saved": saved,
        "failed": failed,
        "path": dir.display().to_string(),
        "dataset_image_count": stats.as_ref().map(|s| s.image_count),
        "dataset_missing_captions": stats.as_ref().map(|s| s.missing_caption_count)
    }))
}

tool!(
    ListDatasetsTool,
    "list_datasets",
    NoArgs,
    list_datasets,
    "List datasets with image/caption counts and sizes.",
    empty_schema(),
);

async fn list_datasets(ctx: &Ctx, _: NoArgs) -> Outcome {
    let root = ctx.paths.datasets_path.clone();
    let datasets = blocking(move || {
        let mut out = Vec::new();
        let Ok(entries) = std::fs::read_dir(&root) else {
            return out;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if !entry.file_type().is_ok_and(|t| t.is_dir()) {
                continue;
            }
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with('.') {
                continue;
            }
            let stats = scan_dataset(&path, 0).unwrap_or_default();
            out.push(json!({
                "name": name,
                "path": path.display().to_string(),
                "image_count": stats.image_count,
                "caption_count": stats.caption_count,
                "missing_caption_count": stats.missing_caption_count,
                "total_size_bytes": stats.total_size_bytes
            }));
        }
        out.sort_by(|a, b| a["name"].as_str().cmp(&b["name"].as_str()));
        out
    })
    .await?;
    ok(json!({"datasets": datasets, "count": datasets.len()}))
}

#[derive(Deserialize)]
struct DatasetInfoArgs {
    name: String,
    #[serde(default = "default_max_missing")]
    max_missing: usize,
}

fn default_max_missing() -> usize {
    50
}

tool!(
    GetDatasetInfoTool,
    "get_dataset_info",
    DatasetInfoArgs,
    get_dataset_info,
    "Get dataset details: image count, caption coverage (with the images lacking captions), and total size.",
    json!({
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Dataset name"},
            "max_missing": {"type": "integer", "minimum": 0, "description": "Max uncaptioned file names to list", "default": 50}
        },
        "required": ["name"]
    }),
);

async fn get_dataset_info(ctx: &Ctx, a: DatasetInfoArgs) -> Outcome {
    let dir = ctx
        .paths
        .dataset_dir(&a.name)
        .map_err(|e| format!("Invalid dataset name: {e}"))?;
    if !fs::metadata(&dir).await.is_ok_and(|m| m.is_dir()) {
        return Err(format!(
            "Dataset '{}' not found (see list_datasets)",
            a.name
        ));
    }
    let scan_dir = dir.clone();
    let max = a.max_missing.min(1000);
    let stats = blocking(move || scan_dataset(&scan_dir, max))
        .await?
        .map_err(|e| format!("Failed to scan dataset: {e}"))?;
    ok(json!({
        "name": a.name,
        "path": dir.display().to_string(),
        "image_count": stats.image_count,
        "caption_count": stats.caption_count,
        "captions_complete": stats.missing_caption_count == 0,
        "missing_caption_count": stats.missing_caption_count,
        "missing_captions": stats.missing_captions,
        "total_size_bytes": stats.total_size_bytes,
        "total_size_mb": mb(stats.total_size_bytes)
    }))
}

tool!(
    DeleteDatasetTool,
    "delete_dataset",
    NameArgs,
    delete_dataset,
    "Delete a dataset directory and all its contents.",
    name_schema("Dataset name to delete"),
);

async fn delete_dataset(ctx: &Ctx, a: NameArgs) -> Outcome {
    let dir = ctx
        .paths
        .dataset_dir(&a.name)
        .map_err(|e| format!("Invalid dataset name: {e}"))?;
    match fs::symlink_metadata(&dir).await {
        Ok(m) if m.is_dir() => {},
        Ok(_) => return Err(format!("'{}' is not a dataset directory", a.name)),
        Err(_) => return Err(format!("Dataset '{}' not found", a.name)),
    }
    fs::remove_dir_all(&dir)
        .await
        .map_err(|e| format!("Failed to delete dataset: {e}"))?;
    info!("Deleted dataset: {}", a.name);
    ok(json!({"success": true, "deleted": a.name}))
}

// ============================================================================
// Training
// ============================================================================

#[derive(Deserialize)]
struct StartArgs {
    config_name: String,
    #[serde(default)]
    allow_concurrent: bool,
    #[serde(default)]
    skip_validation: bool,
}

tool!(
    StartTrainingTool,
    "start_training",
    StartArgs,
    start_training,
    "Start a training job (`python run.py <config>` in the AI Toolkit directory). The config is validated first, and a new job is refused while another is running unless allow_concurrent is true (one GPU). Returns a job_id for get_training_status / get_training_logs / stop_training.",
    json!({
        "type": "object",
        "properties": {
            "config_name": {"type": "string", "description": "Configuration name to train"},
            "allow_concurrent": {"type": "boolean", "description": "Allow starting while another job is running", "default": false},
            "skip_validation": {"type": "boolean", "description": "Start even if validate_config reports errors", "default": false}
        },
        "required": ["config_name"]
    }),
);

async fn start_training(ctx: &Ctx, a: StartArgs) -> Outcome {
    let (config_path, text) = read_config(ctx, &a.config_name).await?;
    let run_script = ctx.paths.run_script();
    if !fs::metadata(&run_script).await.is_ok_and(|m| m.is_file()) {
        return Err(format!(
            "AI Toolkit entry point not found at {} (set AI_TOOLKIT_PATH to the ai-toolkit checkout)",
            run_script.display()
        ));
    }
    let cfg: serde_yaml::Value =
        serde_yaml::from_str(&text).map_err(|e| format!("Config is not valid YAML: {e}"))?;
    let paths = ctx.paths.clone();
    let (validation, summary) = blocking(move || {
        (
            validate_config_yaml(&paths, &cfg),
            summarize_config(&paths, &cfg),
        )
    })
    .await?;
    if !validation.valid && !a.skip_validation {
        return Err(format!(
            "Config '{}' failed validation: {}",
            a.config_name,
            validation.errors.join("; ")
        ));
    }

    let active = ctx.jobs.active().await;
    if !active.is_empty() && !a.allow_concurrent {
        let ids: Vec<_> = active
            .iter()
            .map(|j| format!("{} ({})", j.job_id, j.config_name))
            .collect();
        return Err(format!(
            "Another training job is running: {}. Stop it first or pass allow_concurrent: true",
            ids.join(", ")
        ));
    }

    let output_folder = match (&summary.training_folder, &summary.run_name) {
        (Some(folder), Some(run)) => Some(folder.join(run)),
        _ => None,
    };
    let job = ctx
        .jobs
        .start(LaunchSpec {
            program: ctx.paths.python.clone(),
            args: vec![
                run_script.display().to_string(),
                config_path.display().to_string(),
            ],
            cwd: ctx.paths.base_path.clone(),
            log_dir: ctx.paths.outputs_path.clone(),
            config_name: a.config_name.clone(),
            output_folder,
            total_steps: summary.steps,
            env: vec![],
        })
        .await?;

    ok(json!({
        "status": "success",
        "job_id": job.job_id,
        "pid": job.pid,
        "config": job.config_name,
        "log_file": job.log_file,
        "output_folder": job.output_folder,
        "total_steps": job.total_steps,
        "warnings": validation.warnings,
        "validation_errors_ignored": if validation.valid { Value::Null } else { json!(validation.errors) }
    }))
}

#[derive(Deserialize)]
struct JobArgs {
    job_id: String,
}

fn job_schema() -> Value {
    json!({
        "type": "object",
        "properties": {"job_id": {"type": "string", "description": "Training job ID"}},
        "required": ["job_id"]
    })
}

tool!(
    GetTrainingStatusTool,
    "get_training_status",
    JobArgs,
    get_training_status,
    "Get a training job's status and progress (step, percent, loss, lr, ETA parsed from the log). Failed jobs include an error_hint extracted from the log.",
    job_schema(),
);

async fn get_training_status(ctx: &Ctx, a: JobArgs) -> Outcome {
    let job = ctx
        .jobs
        .get(&a.job_id)
        .await
        .ok_or_else(|| format!("Job '{}' not found (see list_training_jobs)", a.job_id))?;

    let mut progress = None;
    let mut error_hint = None;
    if let Some(log) = &job.log_file
        && let Ok((text, _, _)) = logs::read_tail(Path::new(log), PROGRESS_TAIL_BYTES).await
    {
        progress = logs::parse_progress(&text, job.total_steps);
        if matches!(job.status, JobStatus::Failed | JobStatus::Unknown) {
            error_hint = logs::find_error_hint(&text);
        }
    }
    let percent = if job.status == JobStatus::Completed {
        100
    } else {
        progress.as_ref().map(|p| p.percent).unwrap_or(0)
    };

    ok(json!({
        "status": job.status.to_string(),
        "job_id": job.job_id,
        "config": job.config_name,
        "progress": percent,
        "current_step": progress.as_ref().map(|p| p.current_step),
        "total_steps": progress.as_ref().map(|p| p.total_steps).or(job.total_steps),
        "loss": progress.as_ref().and_then(|p| p.loss),
        "lr": progress.as_ref().and_then(|p| p.lr),
        "eta": progress.as_ref().and_then(|p| p.eta.clone()),
        "pid": job.pid,
        "exit_code": job.exit_code,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "log_file": job.log_file,
        "output_folder": job.output_folder,
        "error_hint": error_hint
    }))
}

#[derive(Deserialize)]
struct StopArgs {
    job_id: String,
    #[serde(default = "default_grace")]
    grace_seconds: u64,
    #[serde(default)]
    force: bool,
}

fn default_grace() -> u64 {
    15
}

tool!(
    StopTrainingTool,
    "stop_training",
    StopArgs,
    stop_training,
    "Stop a running training job. Sends SIGTERM to the job's process group, then SIGKILL after grace_seconds (force: true kills immediately).",
    json!({
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "Training job ID"},
            "grace_seconds": {"type": "integer", "minimum": 0, "maximum": 300, "description": "Seconds to wait after SIGTERM before SIGKILL", "default": 15},
            "force": {"type": "boolean", "description": "Kill immediately", "default": false}
        },
        "required": ["job_id"]
    }),
);

async fn stop_training(ctx: &Ctx, a: StopArgs) -> Outcome {
    let grace = if a.force {
        Duration::ZERO
    } else {
        Duration::from_secs(a.grace_seconds.min(300))
    };
    let outcome = ctx.jobs.stop(&a.job_id, grace).await?;
    ok(json!({
        "status": "success",
        "job_id": outcome.job_id,
        "job_status": outcome.status.to_string(),
        "exit_code": outcome.exit_code,
        "forced": outcome.forced
    }))
}

#[derive(Deserialize)]
struct ListJobsArgs {
    status: Option<String>,
}

tool!(
    ListTrainingJobsTool,
    "list_training_jobs",
    ListJobsArgs,
    list_training_jobs,
    "List training jobs (newest first). Job history persists across server restarts; jobs that were running during a restart report status 'unknown'.",
    json!({
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["pending", "running", "completed", "failed", "stopped", "unknown"], "description": "Only return jobs with this status"}
        }
    }),
);

async fn list_training_jobs(ctx: &Ctx, a: ListJobsArgs) -> Outcome {
    let jobs: Vec<Value> = ctx
        .jobs
        .list()
        .await
        .into_iter()
        .filter(|j| {
            a.status
                .as_deref()
                .is_none_or(|s| j.status.to_string().eq_ignore_ascii_case(s))
        })
        .map(|j| {
            json!({
                "job_id": j.job_id,
                "status": j.status.to_string(),
                "config": j.config_name,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "exit_code": j.exit_code
            })
        })
        .collect();
    ok(json!({"count": jobs.len(), "jobs": jobs}))
}

#[derive(Deserialize)]
struct LogsArgs {
    job_id: String,
    #[serde(default = "default_lines")]
    lines: usize,
}

fn default_lines() -> usize {
    100
}

tool!(
    GetTrainingLogsTool,
    "get_training_logs",
    LogsArgs,
    get_training_logs,
    "Get the last N lines of a training job's log (stdout + stderr). Progress-bar redraws are collapsed to their latest state.",
    json!({
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "Training job ID"},
            "lines": {"type": "integer", "minimum": 1, "maximum": 5000, "description": "Number of lines to return", "default": 100}
        },
        "required": ["job_id"]
    }),
);

async fn get_training_logs(ctx: &Ctx, a: LogsArgs) -> Outcome {
    let job = ctx
        .jobs
        .get(&a.job_id)
        .await
        .ok_or_else(|| format!("Job '{}' not found (see list_training_jobs)", a.job_id))?;
    let log = job
        .log_file
        .as_ref()
        .ok_or_else(|| format!("Job '{}' has no log file", a.job_id))?;
    let (text, size, truncated) = logs::read_tail(Path::new(log), LOG_TAIL_BYTES)
        .await
        .map_err(|e| format!("Failed to read log {log}: {e}"))?;
    let all = logs::display_lines(&text);
    let n = a.lines.clamp(1, 5000);
    let start = all.len().saturating_sub(n);
    let lines = &all[start..];
    ok(json!({
        "job_id": job.job_id,
        "status": job.status.to_string(),
        "logs": lines,
        "returned": lines.len(),
        "total_lines": all.len(),
        "truncated": truncated,
        "log_size_bytes": size,
        "log_file": log
    }))
}

tool!(
    GetTrainingInfoTool,
    "get_training_info",
    NoArgs,
    get_training_info,
    "Overview: job counts by status, number of configs/datasets/models, configured paths, and whether the AI Toolkit entry point was found.",
    empty_schema(),
);

async fn get_training_info(ctx: &Ctx, _: NoArgs) -> Outcome {
    let jobs = ctx.jobs.list().await;
    let mut by_status: BTreeMap<String, usize> = BTreeMap::new();
    for j in &jobs {
        *by_status.entry(j.status.to_string()).or_default() += 1;
    }
    let configs = config_names(&ctx.paths.configs_path).await.len();
    let paths = ctx.paths.clone();
    let (datasets, models) = blocking(move || {
        let datasets = std::fs::read_dir(&paths.datasets_path)
            .map(|it| {
                it.flatten()
                    .filter(|e| e.file_type().is_ok_and(|t| t.is_dir()))
                    .count()
            })
            .unwrap_or(0);
        (datasets, list_models(&paths.outputs_path).len())
    })
    .await?;
    ok(json!({
        "total_jobs": jobs.len(),
        "active_jobs": jobs.iter().filter(|j| j.status.is_active()).count(),
        "jobs_by_status": by_status,
        "configs": configs,
        "datasets": datasets,
        "models": models,
        "paths": {
            "base": ctx.paths.base_path.display().to_string(),
            "configs": ctx.paths.configs_path.display().to_string(),
            "datasets": ctx.paths.datasets_path.display().to_string(),
            "outputs": ctx.paths.outputs_path.display().to_string()
        },
        "run_script_found": fs::metadata(ctx.paths.run_script()).await.is_ok_and(|m| m.is_file()),
        "python": ctx.paths.python
    }))
}

// ============================================================================
// Samples
// ============================================================================

#[derive(Deserialize)]
struct SamplesArgs {
    name: Option<String>,
    job_id: Option<String>,
    #[serde(default = "default_sample_limit")]
    limit: usize,
    #[serde(default = "default_true")]
    include_images: bool,
}

fn default_sample_limit() -> usize {
    4
}

static SAMPLE_STEP_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"__(\d+)_\d+\.").expect("static sample regex is valid"));

tool!(
    GetTrainingSamplesTool,
    "get_training_samples",
    SamplesArgs,
    get_training_samples,
    "Get the most recent sample images AI Toolkit rendered during training (<output>/<run>/samples), newest first, as inline images plus metadata (file, step). Identify the run by job_id or by training name.",
    json!({
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "Training job ID (uses the job's output folder)"},
            "name": {"type": "string", "description": "Training run name (config.name) under the outputs directory"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 16, "description": "Number of samples", "default": 4},
            "include_images": {"type": "boolean", "description": "Return image data (false = metadata only)", "default": true}
        }
    }),
);

fn image_mime(path: &Path) -> Option<&'static str> {
    match path
        .extension()?
        .to_string_lossy()
        .to_ascii_lowercase()
        .as_str()
    {
        "jpg" | "jpeg" => Some("image/jpeg"),
        "png" => Some("image/png"),
        "webp" => Some("image/webp"),
        _ => None,
    }
}

async fn get_training_samples(ctx: &Ctx, a: SamplesArgs) -> Outcome {
    let folder = match (&a.job_id, &a.name) {
        (Some(id), _) => {
            let job = ctx
                .jobs
                .get(id)
                .await
                .ok_or_else(|| format!("Job '{id}' not found"))?;
            let folder = job
                .output_folder
                .ok_or_else(|| format!("Job '{id}' has no known output folder"))?;
            PathBuf::from(folder)
        },
        (None, Some(name)) => {
            validate_name(name, "training").map_err(|e| format!("Invalid name: {e}"))?;
            ctx.paths.outputs_path.join(name)
        },
        (None, None) => return Err("Provide either job_id or name".into()),
    };
    let samples_dir = folder.join("samples");
    let limit = a.limit.clamp(1, MAX_SAMPLES);

    let dir = samples_dir.clone();
    let (total, picked) = blocking(move || {
        let mut files: Vec<(std::time::SystemTime, PathBuf, u64)> = std::fs::read_dir(&dir)
            .map(|it| {
                it.flatten()
                    .filter_map(|e| {
                        let p = e.path();
                        let m = e.metadata().ok()?;
                        (m.is_file() && image_mime(&p).is_some())
                            .then(|| (m.modified().unwrap_or(std::time::UNIX_EPOCH), p, m.len()))
                    })
                    .collect()
            })
            .unwrap_or_default();
        files.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| b.1.cmp(&a.1)));
        let total = files.len();
        files.truncate(limit);
        (total, files)
    })
    .await?;

    if total == 0 {
        return Err(format!(
            "No sample images found in {} (sampling may be disabled or no sample step reached yet)",
            samples_dir.display()
        ));
    }

    let mut meta = Vec::new();
    let mut contents = Vec::new();
    let mut budget = MAX_SAMPLE_TOTAL_BYTES;
    for (modified, path, size) in &picked {
        let file = path
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        let step = SAMPLE_STEP_RE
            .captures(&file)
            .and_then(|c| c[1].parse::<u64>().ok());
        let mut inlined = false;
        if a.include_images && *size <= MAX_SAMPLE_IMAGE_BYTES && *size <= budget {
            match fs::read(path).await {
                Ok(bytes) => {
                    budget -= *size;
                    inlined = true;
                    contents.push(Content::Image {
                        data: BASE64.encode(&bytes),
                        mime_type: image_mime(path).unwrap_or("image/jpeg").to_string(),
                    });
                },
                Err(e) => warn!("Failed to read sample {}: {e}", path.display()),
            }
        }
        meta.push(json!({
            "file": file,
            "path": path.display().to_string(),
            "step": step,
            "size": size,
            "modified_at": chrono::DateTime::<chrono::Utc>::from(*modified).to_rfc3339(),
            "inlined": inlined
        }));
    }
    let summary = json!({
        "samples_dir": samples_dir.display().to_string(),
        "total_samples": total,
        "returned": meta
    });
    let text = serde_json::to_string_pretty(&summary)
        .map_err(|e| format!("Failed to serialize result: {e}"))?;
    let mut all = vec![Content::text(text)];
    all.extend(contents);
    Ok(ToolResult::with_content(all))
}

// ============================================================================
// Models
// ============================================================================

#[derive(Deserialize)]
struct ExportArgs {
    model_name: String,
    output_path: Option<String>,
    #[serde(default)]
    overwrite: bool,
}

tool!(
    ExportModelTool,
    "export_model",
    ExportArgs,
    export_model,
    "Copy trained weights to <outputs>/exports/ (default) or to output_path (relative to the outputs directory). model_name is a name from list_exported_models, e.g. 'my_lora' (final weights of run my_lora) or 'my_lora/my_lora_000000500'.",
    json!({
        "type": "object",
        "properties": {
            "model_name": {"type": "string", "description": "Model name from list_exported_models"},
            "output_path": {"type": "string", "description": "Destination relative to the outputs directory (extension added if missing)"},
            "overwrite": {"type": "boolean", "description": "Replace an existing destination file", "default": false}
        },
        "required": ["model_name"]
    }),
);

async fn export_model(ctx: &Ctx, a: ExportArgs) -> Outcome {
    let outputs = ctx.paths.outputs_path.clone();
    let exports = ctx.paths.exports_path();
    let name = a.model_name.clone();
    let out_path = a.output_path.clone();
    let (source, dest) = blocking(move || {
        let source = resolve_model(&outputs, &name)?;
        let dest = models::export_destination(&outputs, &exports, &source, out_path.as_deref())?;
        Ok::<_, String>((source, dest))
    })
    .await??;

    if !a.overwrite && fs::try_exists(&dest).await.unwrap_or(false) {
        return Err(format!(
            "Destination {} already exists (pass overwrite: true to replace it)",
            dest.display()
        ));
    }
    if let Some(parent) = dest.parent() {
        fs::create_dir_all(parent)
            .await
            .map_err(|e| format!("Failed to create directory: {e}"))?;
    }
    let size = fs::copy(&source, &dest)
        .await
        .map_err(|e| format!("Failed to export model: {e}"))?;
    info!("Exported {} -> {}", source.display(), dest.display());
    ok(json!({
        "status": "success",
        "source": source.display().to_string(),
        "path": dest.display().to_string(),
        "size": size
    }))
}

tool!(
    ListExportedModelsTool,
    "list_exported_models",
    NoArgs,
    list_exported_models,
    "List model weight files (.safetensors/.ckpt/.pt) under the outputs directory, including training runs (<run>/<run>, step checkpoints) and exports (exports/<name>). The returned name works with export_model, download_model and delete_model.",
    empty_schema(),
);

async fn list_exported_models(ctx: &Ctx, _: NoArgs) -> Outcome {
    let outputs = ctx.paths.outputs_path.clone();
    let models = blocking(move || list_models(&outputs)).await?;
    ok(json!({"count": models.len(), "models": models}))
}

#[derive(Deserialize)]
struct DownloadArgs {
    model_name: String,
    #[serde(default = "default_encoding")]
    encoding: String,
    offset: Option<u64>,
    chunk_size: Option<u64>,
}

fn default_encoding() -> String {
    "base64".into()
}

tool!(
    DownloadModelTool,
    "download_model",
    DownloadArgs,
    download_model,
    "Download model weights as base64. Without offset/chunk_size the whole file is returned (max 100 MB). For larger files pass offset (and optionally chunk_size, max 32 MB) and repeat with next_offset until complete; the final chunk includes the file sha256. encoding 'raw' returns metadata only (size, path, sha256) without content.",
    json!({
        "type": "object",
        "properties": {
            "model_name": {"type": "string", "description": "Model name from list_exported_models"},
            "encoding": {"type": "string", "enum": ["base64", "raw"], "description": "'raw' = metadata only", "default": "base64"},
            "offset": {"type": "integer", "minimum": 0, "description": "Byte offset for chunked download"},
            "chunk_size": {"type": "integer", "minimum": 1, "maximum": 33554432, "description": "Chunk size in bytes (default 8 MB)"}
        },
        "required": ["model_name"]
    }),
);

async fn download_model(ctx: &Ctx, a: DownloadArgs) -> Outcome {
    let outputs = ctx.paths.outputs_path.clone();
    let name = a.model_name.clone();
    let path = blocking(move || resolve_model(&outputs, &name)).await??;
    let size = fs::metadata(&path)
        .await
        .map_err(|e| format!("Failed to stat model: {e}"))?
        .len();

    match a.encoding.as_str() {
        "raw" => {
            let p = path.clone();
            let sha = blocking(move || models::sha256_file(&p))
                .await?
                .map_err(|e| format!("Failed to hash model: {e}"))?;
            return ok(json!({
                "status": "success",
                "model": a.model_name,
                "path": path.display().to_string(),
                "size": size,
                "size_mb": mb(size),
                "sha256": sha,
                "note": "encoding 'raw' returns metadata only; use encoding 'base64' (optionally with offset/chunk_size) to transfer content"
            }));
        },
        "base64" => {},
        other => {
            return Err(format!(
                "Unsupported encoding '{other}' (use 'base64' or 'raw')"
            ));
        },
    }

    if a.offset.is_some() || a.chunk_size.is_some() {
        let offset = a.offset.unwrap_or(0);
        if offset > size {
            return Err(format!("offset {offset} is beyond the file size {size}"));
        }
        let chunk = a
            .chunk_size
            .unwrap_or(DEFAULT_CHUNK_SIZE)
            .clamp(1, MAX_CHUNK_SIZE);
        let p = path.clone();
        let data = blocking(move || models::read_chunk(&p, offset, chunk as usize))
            .await?
            .map_err(|e| format!("Failed to read model: {e}"))?;
        let next = offset + data.len() as u64;
        let complete = next >= size;
        let file_sha = if complete {
            let p = path.clone();
            blocking(move || models::sha256_file(&p)).await?.ok()
        } else {
            None
        };
        return ok(json!({
            "status": "success",
            "model": a.model_name,
            "size": size,
            "offset": offset,
            "chunk_bytes": data.len(),
            "next_offset": if complete { Value::Null } else { json!(next) },
            "complete": complete,
            "chunk_sha256": models::sha256_bytes(&data),
            "sha256": file_sha,
            "data": BASE64.encode(&data)
        }));
    }

    if size > MAX_DOWNLOAD_SIZE {
        return Err(format!(
            "Model is {} MB, above the {} MB single-response limit. Download in chunks by passing offset: 0 (and chunk_size), or use export_model and fetch the file directly from {}",
            mb(size),
            MAX_DOWNLOAD_SIZE / 1024 / 1024,
            path.display()
        ));
    }
    let data = fs::read(&path)
        .await
        .map_err(|e| format!("Failed to read model: {e}"))?;
    ok(json!({
        "status": "success",
        "model": a.model_name,
        "size": size,
        "sha256": models::sha256_bytes(&data),
        "data": BASE64.encode(&data)
    }))
}

tool!(
    DeleteModelTool,
    "delete_model",
    NameArgs,
    delete_model,
    "Delete a model weight file (name from list_exported_models; a bare run name deletes that run's final weights).",
    name_schema("Model name to delete"),
);

async fn delete_model(ctx: &Ctx, a: NameArgs) -> Outcome {
    let outputs = ctx.paths.outputs_path.clone();
    let name = a.name.clone();
    let path = blocking(move || resolve_model(&outputs, &name)).await??;
    fs::remove_file(&path)
        .await
        .map_err(|e| format!("Failed to delete model: {e}"))?;
    info!("Deleted model: {}", path.display());
    ok(json!({"success": true, "deleted": a.name, "path": path.display().to_string()}))
}

// ============================================================================
// Utilities
// ============================================================================

tool!(
    GetSystemStatsTool,
    "get_system_stats",
    NoArgs,
    get_system_stats,
    "Host statistics: CPU, memory, disk holding the AI Toolkit directory, and NVIDIA GPU memory/utilization/temperature via nvidia-smi.",
    empty_schema(),
);

async fn get_system_stats(ctx: &Ctx, _: NoArgs) -> Outcome {
    let base = ctx.paths.base_path.clone();
    let (host, gpu) = tokio::join!(
        blocking(move || system::host_stats(&base)),
        system::gpu_report()
    );
    let host = host?;
    let mut v = serde_json::to_value(&host).map_err(|e| e.to_string())?;
    v["gpu"] = serde_json::to_value(&gpu).map_err(|e| e.to_string())?;
    v["active_training_jobs"] = json!(ctx.jobs.active().await.len());
    ok(v)
}

tool!(
    ListModelPresetsTool,
    "list_model_presets",
    NoArgs,
    list_model_presets,
    "List base-model presets with recommended settings. Pass a preset id to create_training_config's `preset` parameter.",
    empty_schema(),
);

async fn list_model_presets(_ctx: &Ctx, _: NoArgs) -> Outcome {
    ok(json!({
        "presets": ModelPreset::all_presets(),
        "note": "Pass `preset: <id>` to create_training_config, or use these values as a starting point"
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    const EXPECTED_TOOLS: &[&str] = &[
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
        "delete_config",
        "delete_dataset",
        "delete_model",
        "validate_config",
        "get_dataset_info",
        "list_model_presets",
        "get_training_samples",
    ];

    const PNG: &[u8] = &[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A, 1, 2, 3];

    struct Fixture {
        _tmp: tempfile::TempDir,
        server: AIToolkitServer,
        paths: AIToolkitPaths,
    }

    fn fixture() -> Fixture {
        let tmp = tempfile::tempdir().unwrap();
        let paths = AIToolkitPaths::from_base(tmp.path());
        let server = AIToolkitServer::with_paths(paths.clone());
        Fixture {
            _tmp: tmp,
            server,
            paths,
        }
    }

    impl Fixture {
        fn tool(&self, name: &str) -> BoxedTool {
            self.server
                .tools()
                .into_iter()
                .find(|t| t.name() == name)
                .unwrap_or_else(|| panic!("tool {name} missing"))
        }

        async fn call(&self, name: &str, args: Value) -> ToolResult {
            self.tool(name).execute(args).await.unwrap()
        }

        async fn call_ok(&self, name: &str, args: Value) -> Value {
            let r = self.call(name, args).await;
            assert!(!r.is_error, "{name} failed: {}", text(&r));
            serde_json::from_str(&text(&r)).unwrap()
        }

        async fn call_err(&self, name: &str, args: Value) -> String {
            let r = self.call(name, args).await;
            assert!(r.is_error, "{name} unexpectedly succeeded: {}", text(&r));
            text(&r)
        }
    }

    fn text(r: &ToolResult) -> String {
        match &r.content[0] {
            Content::Text { text } => text.clone(),
            other => panic!("expected text, got {other:?}"),
        }
    }

    #[test]
    fn tool_names_are_stable_and_unique() {
        let f = fixture();
        let names: Vec<String> = f
            .server
            .tools()
            .iter()
            .map(|t| t.name().to_string())
            .collect();
        assert_eq!(names.len(), EXPECTED_TOOLS.len());
        for expected in EXPECTED_TOOLS {
            assert!(names.iter().any(|n| n == expected), "missing {expected}");
        }
        let unique: HashSet<_> = names.iter().collect();
        assert_eq!(unique.len(), names.len());
        for t in f.server.tools() {
            let s = t.schema();
            assert_eq!(s["type"], "object", "{}", t.name());
            assert!(!t.description().is_empty());
        }
    }

    #[tokio::test]
    async fn schema_required_params_are_backward_compatible() {
        let f = fixture();
        let req = |name: &str| -> Vec<String> {
            f.tool(name).schema()["required"]
                .as_array()
                .map(|a| a.iter().map(|v| v.as_str().unwrap().to_string()).collect())
                .unwrap_or_default()
        };
        assert_eq!(req("create_training_config"), vec!["name", "dataset_path"]);
        assert_eq!(req("upload_dataset"), vec!["dataset_name", "images"]);
        assert_eq!(req("start_training"), vec!["config_name"]);
        assert_eq!(req("get_training_logs"), vec!["job_id"]);
        assert_eq!(req("download_model"), vec!["model_name"]);
        assert_eq!(req("delete_model"), vec!["name"]);
    }

    #[tokio::test]
    async fn bad_args_are_invalid_parameters_not_panics() {
        let f = fixture();
        let err = f.tool("get_config").execute(json!({})).await.unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)), "{err}");
        let err = f
            .tool("create_training_config")
            .execute(json!({"name": "x", "dataset_path": "d", "steps": -5}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)), "{err}");
        let err = f
            .tool("upload_dataset")
            .execute(json!({"dataset_name": "d", "images": "nope"}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)), "{err}");
        // Tools without args tolerate null / extra keys.
        assert!(!f.call("list_configs", Value::Null).await.is_error);
        assert!(!f.call("list_configs", json!({"extra": 1})).await.is_error);
    }

    #[tokio::test]
    async fn dataset_config_workflow() {
        let f = fixture();
        let b64 = BASE64.encode(PNG);

        // Upload: one good image, one bad, one traversal attempt.
        let r = f
            .call_ok(
                "upload_dataset",
                json!({
                    "dataset_name": "cats",
                    "images": [
                        {"filename": "a.png", "data": b64, "caption": "ohwx cat"},
                        {"filename": "b.png", "data": BASE64.encode(b"not an image"), "caption": "x"},
                        {"filename": "../evil.png", "data": b64, "caption": "x"}
                    ]
                }),
            )
            .await;
        assert_eq!(r["status"], "partial");
        assert_eq!(r["images_saved"], 1);
        assert_eq!(r["failed"].as_array().unwrap().len(), 2);
        assert!(f.paths.datasets_path.join("cats").join("a.txt").is_file());
        assert!(!f.paths.datasets_path.join("evil.png").exists());

        // Nothing saved -> isError
        let e = f
            .call_err(
                "upload_dataset",
                json!({"dataset_name": "cats", "images": [{"filename": "z.gif", "data": b64}]}),
            )
            .await;
        assert!(e.contains("No images were saved"), "{e}");
        f.call_err(
            "upload_dataset",
            json!({"dataset_name": "../x", "images": [{"filename": "a.png", "data": b64}]}),
        )
        .await;

        let info = f.call_ok("get_dataset_info", json!({"name": "cats"})).await;
        assert_eq!(info["image_count"], 1);
        assert_eq!(info["captions_complete"], true);
        assert!(info["missing_captions"].is_array());

        let list = f.call_ok("list_datasets", json!({})).await;
        assert_eq!(list["datasets"][0]["name"], "cats");
        assert_eq!(list["datasets"][0]["caption_count"], 1);

        // Config
        let c = f
            .call_ok(
                "create_training_config",
                json!({"name": "cat_lora", "dataset_path": "cats", "preset": "sdxl", "steps": 100}),
            )
            .await;
        assert_eq!(c["architecture"]["is_xl"], true);
        assert_eq!(c["overwritten"], false);
        assert!(c["warnings"].as_array().unwrap().is_empty(), "{c}");

        let e = f
            .call_err(
                "create_training_config",
                json!({"name": "cat_lora", "dataset_path": "cats", "overwrite": false}),
            )
            .await;
        assert!(e.contains("already exists"));

        let list = f.call_ok("list_configs", json!({})).await;
        assert_eq!(list["configs"], json!(["cat_lora"]));
        let got = f.call_ok("get_config", json!({"name": "cat_lora"})).await;
        assert_eq!(got["config"]["config"]["process"][0]["train"]["steps"], 100);

        let v = f
            .call_ok("validate_config", json!({"name": "cat_lora"}))
            .await;
        assert_eq!(v["valid"], true, "{v}");
        assert_eq!(v["run_name"], "cat_lora");
        let v = f
            .call_ok("validate_config", json!({"name": "missing"}))
            .await;
        assert_eq!(v["valid"], false);

        // start_training fails cleanly without an AI Toolkit checkout
        let e = f
            .call_err("start_training", json!({"config_name": "cat_lora"}))
            .await;
        assert!(e.contains("run.py"), "{e}");
        let e = f
            .call_err("start_training", json!({"config_name": "nope"}))
            .await;
        assert!(e.contains("not found"), "{e}");

        f.call_ok("delete_config", json!({"name": "cat_lora"}))
            .await;
        f.call_err("delete_config", json!({"name": "cat_lora"}))
            .await;
        f.call_err("get_config", json!({"name": "cat_lora"})).await;
        f.call_ok("delete_dataset", json!({"name": "cats"})).await;
        f.call_err("delete_dataset", json!({"name": "cats"})).await;
        f.call_err("get_dataset_info", json!({"name": "cats"}))
            .await;
    }

    #[tokio::test]
    async fn model_workflow() {
        let f = fixture();
        let run = f.paths.outputs_path.join("cat_lora");
        std::fs::create_dir_all(run.join("samples")).unwrap();
        std::fs::write(run.join("cat_lora.safetensors"), b"weights").unwrap();
        std::fs::write(run.join("optimizer.pt"), b"opt").unwrap();

        let list = f.call_ok("list_exported_models", json!({})).await;
        assert_eq!(list["count"], 1);
        assert_eq!(list["models"][0]["name"], "cat_lora/cat_lora");

        let ex = f
            .call_ok("export_model", json!({"model_name": "cat_lora"}))
            .await;
        assert!(ex["path"].as_str().unwrap().contains("exports"));
        f.call_err("export_model", json!({"model_name": "cat_lora"}))
            .await; // exists, no overwrite
        f.call_ok(
            "export_model",
            json!({"model_name": "cat_lora", "overwrite": true}),
        )
        .await;
        f.call_err(
            "export_model",
            json!({"model_name": "cat_lora", "output_path": "cat_lora/cat_lora.safetensors", "overwrite": true}),
        )
        .await; // self-copy would truncate
        f.call_err(
            "export_model",
            json!({"model_name": "cat_lora", "output_path": "../../etc/x"}),
        )
        .await;

        // Whole download
        let d = f
            .call_ok("download_model", json!({"model_name": "cat_lora"}))
            .await;
        assert_eq!(
            BASE64.decode(d["data"].as_str().unwrap()).unwrap(),
            b"weights"
        );
        assert_eq!(d["sha256"], models::sha256_bytes(b"weights"));

        // Chunked download reassembles the file
        let mut offset = 0u64;
        let mut buf = Vec::new();
        loop {
            let c = f
                .call_ok(
                    "download_model",
                    json!({"model_name": "cat_lora", "offset": offset, "chunk_size": 3}),
                )
                .await;
            buf.extend(BASE64.decode(c["data"].as_str().unwrap()).unwrap());
            if c["complete"] == true {
                assert_eq!(c["sha256"], models::sha256_bytes(b"weights"));
                break;
            }
            offset = c["next_offset"].as_u64().unwrap();
        }
        assert_eq!(buf, b"weights");
        f.call_err(
            "download_model",
            json!({"model_name": "cat_lora", "offset": 999}),
        )
        .await;

        let raw = f
            .call_ok(
                "download_model",
                json!({"model_name": "cat_lora", "encoding": "raw"}),
            )
            .await;
        assert!(raw.get("data").is_none());
        assert_eq!(raw["size"], 7);
        f.call_err(
            "download_model",
            json!({"model_name": "cat_lora", "encoding": "hex"}),
        )
        .await;

        // Samples
        f.call_err("get_training_samples", json!({"name": "cat_lora"}))
            .await;
        std::fs::write(run.join("samples").join("1700000000__000000250_0.png"), PNG).unwrap();
        let r = f
            .call("get_training_samples", json!({"name": "cat_lora"}))
            .await;
        assert!(!r.is_error, "{}", text(&r));
        assert_eq!(r.content.len(), 2);
        let meta: Value = serde_json::from_str(&text(&r)).unwrap();
        assert_eq!(meta["returned"][0]["step"], 250);
        assert!(matches!(r.content[1], Content::Image { .. }));
        f.call_err("get_training_samples", json!({})).await;
        f.call_err("get_training_samples", json!({"name": "../x"}))
            .await;

        f.call_ok("delete_model", json!({"name": "cat_lora"})).await;
        f.call_err("delete_model", json!({"name": "cat_lora"}))
            .await;
    }

    #[tokio::test]
    async fn job_tools_handle_unknown_jobs() {
        let f = fixture();
        for tool in ["get_training_status", "get_training_logs", "stop_training"] {
            let e = f.call_err(tool, json!({"job_id": "nope"})).await;
            assert!(e.contains("not found"), "{tool}: {e}");
        }
        let l = f.call_ok("list_training_jobs", json!({})).await;
        assert_eq!(l["count"], 0);
        let info = f.call_ok("get_training_info", json!({})).await;
        assert_eq!(info["run_script_found"], false);
        let p = f.call_ok("list_model_presets", json!({})).await;
        assert_eq!(p["presets"].as_array().unwrap().len(), 5);
    }

    /// End-to-end training lifecycle using a shell script in place of Python.
    #[cfg(unix)]
    #[tokio::test]
    async fn training_lifecycle_with_fake_run_py() {
        let tmp = tempfile::tempdir().unwrap();
        let mut paths = AIToolkitPaths::from_base(tmp.path());
        paths.python = "sh".into();
        std::fs::create_dir_all(&paths.base_path).unwrap();
        std::fs::write(
            paths.run_script(),
            "printf 'loading\\n'\n\
             printf 'lora:  50%%|##   | 50/100 [00:05<00:05, 1.0it/s, lr: 1.0e-04 loss: 2.5e-01]\\r' 1>&2\n\
             sleep 30\n",
        )
        .unwrap();
        let f = Fixture {
            server: AIToolkitServer::with_paths(paths.clone()),
            paths,
            _tmp: tmp,
        };
        let ds = f.paths.datasets_path.join("d");
        std::fs::create_dir_all(&ds).unwrap();
        std::fs::write(ds.join("a.png"), PNG).unwrap();
        f.call_ok(
            "create_training_config",
            json!({"name": "lora", "dataset_path": "d", "steps": 100}),
        )
        .await;

        let s = f
            .call_ok("start_training", json!({"config_name": "lora"}))
            .await;
        let job_id = s["job_id"].as_str().unwrap().to_string();
        assert_eq!(s["total_steps"], 100);

        // Single-GPU guard
        let e = f
            .call_err("start_training", json!({"config_name": "lora"}))
            .await;
        assert!(e.contains("Another training job"), "{e}");

        // Wait for progress to appear in the log.
        let mut status = Value::Null;
        for _ in 0..100 {
            status = f
                .call_ok("get_training_status", json!({"job_id": job_id}))
                .await;
            if status["current_step"] == 50 {
                break;
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        assert_eq!(status["status"], "running");
        assert_eq!(status["progress"], 50, "{status}");
        assert_eq!(status["loss"], 0.25);
        assert_eq!(status["eta"], "00:05");

        let logs = f
            .call_ok("get_training_logs", json!({"job_id": job_id, "lines": 10}))
            .await;
        assert!(
            logs["logs"]
                .as_array()
                .unwrap()
                .iter()
                .any(|l| l == "loading")
        );

        let stop = f
            .call_ok(
                "stop_training",
                json!({"job_id": job_id, "grace_seconds": 5}),
            )
            .await;
        assert_eq!(stop["job_status"], "stopped");
        let l = f
            .call_ok("list_training_jobs", json!({"status": "stopped"}))
            .await;
        assert_eq!(l["count"], 1);
        f.call_err("stop_training", json!({"job_id": job_id})).await;
    }
}

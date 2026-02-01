//! Types for AI Toolkit MCP server.
//!
//! These types match the AI Toolkit configuration format from:
//! https://github.com/ostris/ai-toolkit

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Training job status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum JobStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Stopped,
}

impl std::fmt::Display for JobStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            JobStatus::Pending => write!(f, "pending"),
            JobStatus::Running => write!(f, "running"),
            JobStatus::Completed => write!(f, "completed"),
            JobStatus::Failed => write!(f, "failed"),
            JobStatus::Stopped => write!(f, "stopped"),
        }
    }
}

/// Training job information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingJob {
    pub job_id: String,
    pub status: JobStatus,
    pub config_name: String,
    pub log_file: Option<String>,
    pub pid: Option<u32>,
    pub exit_code: Option<i32>,
    pub started_at: Option<String>,
    /// Path to the training output folder
    pub output_folder: Option<String>,
}

impl TrainingJob {
    pub fn new(job_id: String, config_name: String) -> Self {
        Self {
            job_id,
            status: JobStatus::Pending,
            config_name,
            log_file: None,
            pid: None,
            exit_code: None,
            started_at: None,
            output_folder: None,
        }
    }
}

/// Dataset information with detailed stats
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatasetInfo {
    pub name: String,
    pub path: String,
    pub image_count: usize,
    pub caption_count: usize,
    pub missing_captions: Vec<String>,
    pub total_size_bytes: u64,
}

/// Model information with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub name: String,
    pub path: String,
    pub size: u64,
    pub extension: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, serde_json::Value>>,
}

// ============================================================================
// AI Toolkit Configuration Types
// These match the actual config format from ostris/ai-toolkit
// ============================================================================

/// Top-level AI Toolkit training config
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingConfig {
    pub job: String,
    pub config: ConfigDetails,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub meta: Option<ConfigMeta>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigDetails {
    pub name: String,
    pub process: Vec<ProcessConfig>,
}

/// Process configuration - the main training config block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessConfig {
    #[serde(rename = "type")]
    pub process_type: String,

    /// Root folder to save training sessions/samples/weights
    pub training_folder: String,

    /// Device to train on (e.g., "cuda:0")
    pub device: String,

    /// Trigger word - added to captions if not present
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trigger_word: Option<String>,

    /// Performance logging interval
    #[serde(skip_serializing_if = "Option::is_none")]
    pub performance_log_every: Option<u32>,

    /// Network configuration (LoRA, LoCoN, etc.)
    pub network: NetworkConfig,

    /// Save configuration
    pub save: SaveConfig,

    /// Dataset configurations
    pub datasets: Vec<DatasetConfig>,

    /// Training parameters
    pub train: TrainConfig,

    /// Model configuration
    pub model: ModelConfig,

    /// Sampling configuration
    pub sample: SampleConfig,

    /// Logging configuration
    #[serde(skip_serializing_if = "Option::is_none")]
    pub logging: Option<LoggingConfig>,
}

/// Network type for LoRA variants
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[allow(dead_code)]
pub enum NetworkType {
    #[default]
    Lora,
    Locon,
    Lorm,
    Lokr,
}

/// Network configuration (LoRA, LoCoN, etc.)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    #[serde(rename = "type")]
    pub network_type: String,

    /// LoRA rank for linear layers
    pub linear: u32,

    /// LoRA alpha for linear layers
    pub linear_alpha: u32,

    /// LoRA rank for conv layers (for LoCoN)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub conv: Option<u32>,

    /// LoRA alpha for conv layers (for LoCoN)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub conv_alpha: Option<u32>,

    /// Network dropout
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dropout: Option<f32>,

    /// Only apply to transformer layers
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transformer_only: Option<bool>,
}

/// Save configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaveConfig {
    /// Precision to save (float16, bfloat16, float32)
    #[serde(default = "default_save_dtype")]
    pub dtype: String,

    /// Save every N steps
    #[serde(default = "default_save_every")]
    pub save_every: u32,

    /// How many intermediate saves to keep
    #[serde(default = "default_max_saves")]
    pub max_step_saves_to_keep: u32,

    /// Push to Hugging Face Hub
    #[serde(default)]
    pub push_to_hub: bool,

    /// Hugging Face repo ID
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hf_repo_id: Option<String>,

    /// Whether the HF repo is private
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hf_private: Option<bool>,
}

fn default_save_dtype() -> String {
    "float16".to_string()
}
fn default_save_every() -> u32 {
    250
}
fn default_max_saves() -> u32 {
    4
}

/// Dataset configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatasetConfig {
    /// Path to the dataset folder
    pub folder_path: String,

    /// Caption file extension
    #[serde(default = "default_caption_ext")]
    pub caption_ext: String,

    /// Caption dropout rate (0.0-1.0)
    #[serde(default)]
    pub caption_dropout_rate: f32,

    /// Shuffle caption tokens (split by commas)
    #[serde(default)]
    pub shuffle_tokens: bool,

    /// Cache latents to disk
    #[serde(default = "default_true")]
    pub cache_latents_to_disk: bool,

    /// Training resolution(s) - can be single value or array
    #[serde(default = "default_resolution")]
    pub resolution: Resolution,

    /// Default caption if none exists
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_caption: Option<String>,

    /// Is this a regularization dataset
    #[serde(default)]
    pub is_reg: bool,

    /// Network weight for this dataset
    #[serde(skip_serializing_if = "Option::is_none")]
    pub network_weight: Option<f32>,
}

fn default_caption_ext() -> String {
    "txt".to_string()
}
fn default_true() -> bool {
    true
}
fn default_resolution() -> Resolution {
    Resolution::Single(512)
}

/// Resolution can be a single value or array of values
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Resolution {
    Single(u32),
    Multiple(Vec<u32>),
}

/// Training configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainConfig {
    /// Batch size
    #[serde(default = "default_batch_size")]
    pub batch_size: u32,

    /// Total training steps
    pub steps: u32,

    /// Gradient accumulation steps
    #[serde(default = "default_one")]
    pub gradient_accumulation_steps: u32,

    /// Train UNet/transformer
    #[serde(default = "default_true")]
    pub train_unet: bool,

    /// Train text encoder
    #[serde(default)]
    pub train_text_encoder: bool,

    /// Enable gradient checkpointing
    #[serde(default = "default_true")]
    pub gradient_checkpointing: bool,

    /// Noise scheduler (ddpm, ddim, flowmatch, etc.)
    #[serde(default = "default_noise_scheduler")]
    pub noise_scheduler: String,

    /// Optimizer (adamw, adamw8bit, prodigy, lion, etc.)
    #[serde(default = "default_optimizer")]
    pub optimizer: String,

    /// Learning rate
    #[serde(default = "default_lr")]
    pub lr: f64,

    /// Skip the first sample
    #[serde(default)]
    pub skip_first_sample: bool,

    /// Disable sampling entirely
    #[serde(default)]
    pub disable_sampling: bool,

    /// Use linear timestep weighting
    #[serde(default)]
    pub linear_timesteps: bool,

    /// Training dtype (float32, float16/fp16, bfloat16/bf16)
    #[serde(default = "default_train_dtype")]
    pub dtype: String,

    /// EMA configuration
    #[serde(default)]
    pub ema_config: EmaConfig,

    /// Max gradient norm for clipping
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_grad_norm: Option<f32>,

    /// Noise offset
    #[serde(skip_serializing_if = "Option::is_none")]
    pub noise_offset: Option<f32>,
}

fn default_batch_size() -> u32 {
    1
}
fn default_one() -> u32 {
    1
}
fn default_noise_scheduler() -> String {
    "ddpm".to_string()
}
fn default_optimizer() -> String {
    "adamw8bit".to_string()
}
fn default_lr() -> f64 {
    1e-4
}
fn default_train_dtype() -> String {
    "bf16".to_string()
}

/// EMA configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct EmaConfig {
    #[serde(default = "default_true")]
    pub use_ema: bool,

    #[serde(default = "default_ema_decay")]
    pub ema_decay: f64,
}

fn default_ema_decay() -> f64 {
    0.99
}

/// Model configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelConfig {
    /// Hugging Face model name or path
    pub name_or_path: String,

    /// Is Flux model
    #[serde(default)]
    pub is_flux: bool,

    /// Is SD 2.x model
    #[serde(default)]
    pub is_v2: bool,

    /// Is SD 3.x model
    #[serde(default)]
    pub is_v3: bool,

    /// Is SDXL model
    #[serde(default)]
    pub is_xl: bool,

    /// Is v-prediction model
    #[serde(default)]
    pub is_v_pred: bool,

    /// Enable 8-bit quantization
    #[serde(default)]
    pub quantize: bool,

    /// Low VRAM mode (slower but uses less memory)
    #[serde(default)]
    pub low_vram: bool,
}

/// Sample configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SampleConfig {
    /// Sampler (must match noise_scheduler for some models)
    #[serde(default = "default_noise_scheduler")]
    pub sampler: String,

    /// Sample every N steps
    #[serde(default = "default_sample_every")]
    pub sample_every: u32,

    /// Sample width
    #[serde(default = "default_sample_size")]
    pub width: u32,

    /// Sample height
    #[serde(default = "default_sample_size")]
    pub height: u32,

    /// Sample prompts
    #[serde(default)]
    pub prompts: Vec<String>,

    /// Negative prompt
    #[serde(default)]
    pub neg: String,

    /// Random seed
    #[serde(default = "default_seed")]
    pub seed: u64,

    /// Walk seed (increment per sample)
    #[serde(default)]
    pub walk_seed: bool,

    /// Guidance scale
    #[serde(default = "default_guidance")]
    pub guidance_scale: f64,

    /// Number of sampling steps
    #[serde(default = "default_sample_steps")]
    pub sample_steps: u32,
}

fn default_sample_every() -> u32 {
    250
}
fn default_sample_size() -> u32 {
    1024
}
fn default_seed() -> u64 {
    42
}
fn default_guidance() -> f64 {
    4.0
}
fn default_sample_steps() -> u32 {
    20
}

/// Logging configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct LoggingConfig {
    /// Log every N steps
    #[serde(default = "default_log_every")]
    pub log_every: u32,

    /// Verbose output
    #[serde(default)]
    pub verbose: bool,

    /// Use Weights & Biases
    #[serde(default)]
    pub use_wandb: bool,

    /// Use local UI logger (SQLite)
    #[serde(default)]
    pub use_ui_logger: bool,

    /// WandB project name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_name: Option<String>,

    /// WandB run name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub run_name: Option<String>,
}

fn default_log_every() -> u32 {
    100
}

/// Config metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigMeta {
    pub name: String,
    #[serde(default = "default_version")]
    pub version: String,
}

fn default_version() -> String {
    "1.0".to_string()
}

// ============================================================================
// Validation Types
// ============================================================================

/// Config validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct ConfigValidation {
    pub valid: bool,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
}

/// Dataset validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct DatasetValidation {
    pub valid: bool,
    pub image_count: usize,
    pub caption_count: usize,
    pub missing_captions: Vec<String>,
    pub invalid_images: Vec<String>,
    pub warnings: Vec<String>,
}

/// Known model presets
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelPreset {
    pub name: String,
    pub model_path: String,
    pub description: String,
    pub is_flux: bool,
    pub is_xl: bool,
    pub is_v2: bool,
    pub is_v3: bool,
    pub recommended_resolution: Vec<u32>,
    pub recommended_scheduler: String,
    pub requires_quantize: bool,
    pub min_vram_gb: u32,
}

impl ModelPreset {
    pub fn flux_dev() -> Self {
        Self {
            name: "Flux.1-dev".to_string(),
            model_path: "black-forest-labs/FLUX.1-dev".to_string(),
            description: "Flux 1.0 Dev - High quality, requires 24GB+ VRAM".to_string(),
            is_flux: true,
            is_xl: false,
            is_v2: false,
            is_v3: false,
            recommended_resolution: vec![512, 768, 1024],
            recommended_scheduler: "flowmatch".to_string(),
            requires_quantize: true,
            min_vram_gb: 24,
        }
    }

    pub fn flux_schnell() -> Self {
        Self {
            name: "Flux.1-schnell".to_string(),
            model_path: "black-forest-labs/FLUX.1-schnell".to_string(),
            description: "Flux 1.0 Schnell - Faster, Apache 2.0 license".to_string(),
            is_flux: true,
            is_xl: false,
            is_v2: false,
            is_v3: false,
            recommended_resolution: vec![512, 768, 1024],
            recommended_scheduler: "flowmatch".to_string(),
            requires_quantize: true,
            min_vram_gb: 24,
        }
    }

    pub fn sd15() -> Self {
        Self {
            name: "Stable Diffusion 1.5".to_string(),
            model_path: "runwayml/stable-diffusion-v1-5".to_string(),
            description: "SD 1.5 - Classic model, works on 8GB+ VRAM".to_string(),
            is_flux: false,
            is_xl: false,
            is_v2: false,
            is_v3: false,
            recommended_resolution: vec![512],
            recommended_scheduler: "ddpm".to_string(),
            requires_quantize: false,
            min_vram_gb: 8,
        }
    }

    pub fn sdxl() -> Self {
        Self {
            name: "Stable Diffusion XL".to_string(),
            model_path: "stabilityai/stable-diffusion-xl-base-1.0".to_string(),
            description: "SDXL - Higher resolution, requires 12GB+ VRAM".to_string(),
            is_flux: false,
            is_xl: true,
            is_v2: false,
            is_v3: false,
            recommended_resolution: vec![1024],
            recommended_scheduler: "ddpm".to_string(),
            requires_quantize: false,
            min_vram_gb: 12,
        }
    }

    pub fn sd35_large() -> Self {
        Self {
            name: "Stable Diffusion 3.5 Large".to_string(),
            model_path: "stabilityai/stable-diffusion-3.5-large".to_string(),
            description: "SD 3.5 Large - Latest architecture, requires 24GB+ VRAM".to_string(),
            is_flux: false,
            is_xl: false,
            is_v2: false,
            is_v3: true,
            recommended_resolution: vec![1024],
            recommended_scheduler: "flowmatch".to_string(),
            requires_quantize: true,
            min_vram_gb: 24,
        }
    }

    pub fn all_presets() -> Vec<Self> {
        vec![
            Self::flux_dev(),
            Self::flux_schnell(),
            Self::sd15(),
            Self::sdxl(),
            Self::sd35_large(),
        ]
    }
}

/// System statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct SystemStats {
    pub cpu_percent: f32,
    pub memory_percent: f32,
    pub memory_used_gb: f32,
    pub memory_total_gb: f32,
    pub disk_usage_percent: f32,
    pub disk_free_gb: f32,
    #[serde(default)]
    pub gpu: Option<GpuStats>,
}

/// GPU statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuStats {
    pub available: bool,
    pub name: Option<String>,
    pub memory_used_gb: Option<f32>,
    pub memory_total_gb: Option<f32>,
    pub utilization_percent: Option<f32>,
}

/// Image upload data
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct ImageUpload {
    pub filename: String,
    pub data: String, // base64 encoded
    pub caption: String,
}

/// Training metrics from log
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct TrainingMetrics {
    pub step: u32,
    pub loss: Option<f64>,
    pub lr: Option<f64>,
    pub epoch: Option<u32>,
    pub samples_generated: Option<u32>,
}

//! AI Toolkit training-config types and model presets.
//!
//! The config structs serialize to the YAML format consumed by
//! `python run.py <config>` in <https://github.com/ostris/ai-toolkit>
//! (`job: extension` / `type: sd_trainer`).

use serde::{Deserialize, Serialize};

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
// Model presets
// ============================================================================

/// A known base model with recommended training settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelPreset {
    /// Short identifier accepted by `create_training_config`'s `preset` param.
    pub id: String,
    pub name: String,
    pub model_path: String,
    pub description: String,
    pub is_flux: bool,
    pub is_xl: bool,
    pub is_v2: bool,
    pub is_v3: bool,
    pub recommended_resolution: Vec<u32>,
    pub recommended_scheduler: String,
    pub recommended_optimizer: String,
    pub requires_quantize: bool,
    pub min_vram_gb: u32,
}

impl ModelPreset {
    #[allow(clippy::too_many_arguments)]
    fn new(
        id: &str,
        name: &str,
        model_path: &str,
        description: &str,
        arch: (bool, bool, bool),
        recommended_resolution: Vec<u32>,
        requires_quantize: bool,
        min_vram_gb: u32,
    ) -> Self {
        let (is_flux, is_xl, is_v3) = arch;
        let flow = is_flux || is_v3;
        Self {
            id: id.to_string(),
            name: name.to_string(),
            model_path: model_path.to_string(),
            description: description.to_string(),
            is_flux,
            is_xl,
            is_v2: false,
            is_v3,
            recommended_resolution,
            recommended_scheduler: if flow { "flowmatch" } else { "ddpm" }.to_string(),
            recommended_optimizer: if flow { "adamw8bit" } else { "adamw" }.to_string(),
            requires_quantize,
            min_vram_gb,
        }
    }

    /// All built-in presets.
    pub fn all_presets() -> Vec<Self> {
        vec![
            Self::new(
                "flux-dev",
                "Flux.1-dev",
                "black-forest-labs/FLUX.1-dev",
                "Flux 1.0 Dev - High quality, requires 24GB+ VRAM (gated model, needs HF_TOKEN)",
                (true, false, false),
                vec![512, 768, 1024],
                true,
                24,
            ),
            Self::new(
                "flux-schnell",
                "Flux.1-schnell",
                "black-forest-labs/FLUX.1-schnell",
                "Flux 1.0 Schnell - Faster, Apache 2.0 license",
                (true, false, false),
                vec![512, 768, 1024],
                true,
                24,
            ),
            Self::new(
                "sd15",
                "Stable Diffusion 1.5",
                "runwayml/stable-diffusion-v1-5",
                "SD 1.5 - Classic model, works on 8GB+ VRAM",
                (false, false, false),
                vec![512],
                false,
                8,
            ),
            Self::new(
                "sdxl",
                "Stable Diffusion XL",
                "stabilityai/stable-diffusion-xl-base-1.0",
                "SDXL - Higher resolution, requires 12GB+ VRAM",
                (false, true, false),
                vec![1024],
                false,
                12,
            ),
            Self::new(
                "sd35-large",
                "Stable Diffusion 3.5 Large",
                "stabilityai/stable-diffusion-3.5-large",
                "SD 3.5 Large - requires 24GB+ VRAM (gated model, needs HF_TOKEN)",
                (false, false, true),
                vec![1024],
                true,
                24,
            ),
        ]
    }

    /// Look up a preset by `id` (case-insensitive).
    pub fn by_id(id: &str) -> Option<Self> {
        Self::all_presets()
            .into_iter()
            .find(|p| p.id.eq_ignore_ascii_case(id))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preset_lookup() {
        let p = ModelPreset::by_id("FLUX-DEV").unwrap();
        assert!(p.is_flux && p.requires_quantize);
        assert_eq!(p.recommended_scheduler, "flowmatch");
        assert!(ModelPreset::by_id("nope").is_none());
        let ids: Vec<_> = ModelPreset::all_presets()
            .into_iter()
            .map(|p| p.id)
            .collect();
        assert_eq!(ids.len(), 5);
    }

    #[test]
    fn resolution_untagged_roundtrip() {
        let single: Resolution = serde_json::from_value(serde_json::json!(512)).unwrap();
        assert!(matches!(single, Resolution::Single(512)));
        let multi: Resolution = serde_json::from_value(serde_json::json!([512, 1024])).unwrap();
        assert!(matches!(multi, Resolution::Multiple(ref v) if v == &vec![512, 1024]));
    }
}

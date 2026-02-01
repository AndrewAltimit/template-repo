//! Types for AI Toolkit MCP server.

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
        }
    }
}

/// Dataset information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatasetInfo {
    pub name: String,
    pub images: usize,
    pub path: String,
}

/// Model information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub name: String,
    pub path: String,
    pub size: u64,
    pub extension: String,
}

/// AI Toolkit training config structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingConfig {
    pub job: String,
    pub config: ConfigDetails,
    pub meta: ConfigMeta,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigDetails {
    pub name: String,
    pub process: Vec<ProcessConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessConfig {
    #[serde(rename = "type")]
    pub process_type: String,
    pub training_folder: String,
    pub output_name: String,
    pub save_root: String,
    pub device: String,
    pub network: NetworkConfig,
    pub train: TrainConfig,
    pub model: ModelConfig,
    pub sample: SampleConfig,
    #[serde(default)]
    pub trigger_word: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    #[serde(rename = "type")]
    pub network_type: String,
    pub linear: u32,
    pub linear_alpha: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainConfig {
    pub noise_scheduler: String,
    pub steps: u32,
    pub lr: f64,
    pub gradient_accumulation_steps: u32,
    pub train_unet: bool,
    pub train_text_encoder: bool,
    pub content_or_style: String,
    pub clip_skip: u32,
    pub ema_config: EmaConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmaConfig {
    pub use_ema: bool,
    pub ema_decay: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelConfig {
    pub name_or_path: String,
    pub is_v2: bool,
    pub is_v_pred: bool,
    pub quantize: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SampleConfig {
    pub sampler: String,
    pub sample_every: u32,
    pub width: u32,
    pub height: u32,
    #[serde(default)]
    pub prompts: Vec<String>,
    #[serde(default)]
    pub neg: String,
    pub seed: u64,
    pub walk_seed: bool,
    pub guidance_scale: f64,
    pub sample_steps: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigMeta {
    pub name: String,
    pub version: String,
}

/// System statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct SystemStats {
    pub cpu_percent: f32,
    pub memory_percent: f32,
    pub disk_usage_percent: f32,
    #[serde(default)]
    pub gpu: Option<HashMap<String, serde_json::Value>>,
}

/// Image upload data
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct ImageUpload {
    pub filename: String,
    pub data: String, // base64 encoded
    pub caption: String,
}

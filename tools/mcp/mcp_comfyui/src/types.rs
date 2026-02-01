//! Type definitions for ComfyUI MCP server

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Image output from ComfyUI
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageOutput {
    pub filename: String,
    pub subfolder: String,
    #[serde(rename = "type")]
    pub output_type: String,
}

/// Generation job tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationJob {
    pub prompt_id: String,
    pub status: JobStatus,
    pub prompt: Option<String>,
    pub images: Vec<ImageOutput>,
}

/// Job status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed,
    Timeout,
}

/// ComfyUI prompt queue response
#[derive(Debug, Deserialize)]
pub struct PromptQueueResponse {
    pub prompt_id: String,
}

/// ComfyUI history entry
#[derive(Debug, Clone, Deserialize)]
pub struct HistoryEntry {
    pub outputs: HashMap<String, NodeOutput>,
}

/// Node output containing images
#[derive(Debug, Clone, Deserialize)]
pub struct NodeOutput {
    #[serde(default)]
    pub images: Vec<ImageInfo>,
}

/// Image info from history
#[derive(Debug, Clone, Deserialize)]
pub struct ImageInfo {
    pub filename: String,
    #[serde(default)]
    pub subfolder: String,
    #[serde(rename = "type", default = "default_output_type")]
    pub output_type: String,
}

fn default_output_type() -> String {
    "output".to_string()
}

/// ComfyUI system stats
#[derive(Debug, Deserialize, Serialize)]
pub struct SystemStats {
    #[serde(default)]
    pub system: SystemInfo,
    #[serde(default)]
    pub devices: Vec<DeviceInfo>,
}

/// System information
#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SystemInfo {
    #[serde(default)]
    pub python_version: String,
    #[serde(default)]
    pub embedded_python: bool,
}

/// Device information
#[derive(Debug, Deserialize, Serialize)]
pub struct DeviceInfo {
    pub name: String,
    #[serde(rename = "type")]
    pub device_type: String,
    #[serde(default)]
    pub vram_total: u64,
    #[serde(default)]
    pub vram_free: u64,
}

/// Workflow template metadata
#[derive(Debug, Clone, Serialize)]
pub struct WorkflowTemplate {
    pub name: String,
    pub description: String,
    pub model_type: String,
}

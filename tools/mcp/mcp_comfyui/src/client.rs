//! ComfyUI HTTP client

use crate::types::{HistoryEntry, ImageOutput, PromptQueueResponse, SystemStats};
use base64::{Engine, engine::general_purpose::STANDARD as BASE64};
use reqwest::Client;
use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Duration;
use tokio::time::sleep;
use tracing::{debug, info};

/// ComfyUI HTTP client for API communication
pub struct ComfyUIClient {
    client: Client,
    base_url: String,
    client_id: String,
    models_path: PathBuf,
}

impl ComfyUIClient {
    /// Create a new ComfyUI client
    pub fn new(host: &str, port: u16, client_id: String, comfyui_path: &str) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(300))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            client,
            base_url: format!("http://{}:{}", host, port),
            client_id,
            models_path: PathBuf::from(comfyui_path).join("models"),
        }
    }

    /// Queue a prompt for execution
    pub async fn queue_prompt(&self, workflow: &Value) -> Result<String, String> {
        let payload = serde_json::json!({
            "prompt": workflow,
            "client_id": self.client_id
        });

        let response = self
            .client
            .post(format!("{}/prompt", self.base_url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| format!("Failed to queue prompt: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(format!("ComfyUI returned error {}: {}", status, body));
        }

        let result: PromptQueueResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;

        info!("Queued prompt with ID: {}", result.prompt_id);
        Ok(result.prompt_id)
    }

    /// Get generation history for a prompt
    pub async fn get_history(&self, prompt_id: &str) -> Result<Option<HistoryEntry>, String> {
        let response = self
            .client
            .get(format!("{}/history/{}", self.base_url, prompt_id))
            .send()
            .await
            .map_err(|e| format!("Failed to get history: {}", e))?;

        if !response.status().is_success() {
            return Ok(None);
        }

        let history: HashMap<String, HistoryEntry> = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse history: {}", e))?;

        Ok(history.get(prompt_id).cloned())
    }

    /// Wait for a prompt to complete
    pub async fn wait_for_completion(
        &self,
        prompt_id: &str,
        timeout_secs: u64,
    ) -> Result<Vec<ImageOutput>, String> {
        let start = std::time::Instant::now();
        let timeout = Duration::from_secs(timeout_secs);

        while start.elapsed() < timeout {
            if let Some(entry) = self.get_history(prompt_id).await? {
                // Check if there are outputs
                let images: Vec<ImageOutput> = entry
                    .outputs
                    .values()
                    .flat_map(|output| {
                        output.images.iter().map(|img| ImageOutput {
                            filename: img.filename.clone(),
                            subfolder: img.subfolder.clone(),
                            output_type: img.output_type.clone(),
                        })
                    })
                    .collect();

                if !images.is_empty() {
                    debug!("Generation complete with {} images", images.len());
                    return Ok(images);
                }
            }

            sleep(Duration::from_secs(1)).await;
        }

        Err("Generation timed out".to_string())
    }

    /// Get object info (available nodes and models)
    pub async fn get_object_info(&self) -> Result<Value, String> {
        let response = self
            .client
            .get(format!("{}/object_info", self.base_url))
            .send()
            .await
            .map_err(|e| format!("Failed to get object info: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("Failed to get object info: {}", response.status()));
        }

        response
            .json()
            .await
            .map_err(|e| format!("Failed to parse object info: {}", e))
    }

    /// Get system stats
    pub async fn get_system_stats(&self) -> Result<SystemStats, String> {
        let response = self
            .client
            .get(format!("{}/system_stats", self.base_url))
            .send()
            .await
            .map_err(|e| format!("Failed to get system stats: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("Failed to get system stats: {}", response.status()));
        }

        response
            .json()
            .await
            .map_err(|e| format!("Failed to parse system stats: {}", e))
    }

    /// Get available models of a specific type
    pub async fn get_models(&self, model_type: &str) -> Result<Vec<String>, String> {
        let object_info = self.get_object_info().await?;

        let models = match model_type {
            "checkpoint" => object_info
                .get("CheckpointLoaderSimple")
                .and_then(|v| v.get("input"))
                .and_then(|v| v.get("required"))
                .and_then(|v| v.get("ckpt_name"))
                .and_then(|v| v.get(0))
                .and_then(|v| v.as_array()),
            "lora" => object_info
                .get("LoraLoader")
                .and_then(|v| v.get("input"))
                .and_then(|v| v.get("required"))
                .and_then(|v| v.get("lora_name"))
                .and_then(|v| v.get(0))
                .and_then(|v| v.as_array()),
            "vae" => object_info
                .get("VAELoader")
                .and_then(|v| v.get("input"))
                .and_then(|v| v.get("required"))
                .and_then(|v| v.get("vae_name"))
                .and_then(|v| v.get(0))
                .and_then(|v| v.as_array()),
            _ => None,
        };

        Ok(models
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default())
    }

    /// Upload a LoRA model
    pub async fn upload_lora(
        &self,
        filename: &str,
        data: &[u8],
        metadata: Option<&Value>,
    ) -> Result<PathBuf, String> {
        // Sanitize filename to prevent path traversal attacks
        let safe_filename = std::path::Path::new(filename)
            .file_name()
            .ok_or_else(|| {
                "Invalid filename: must not be empty or contain path separators".to_string()
            })?
            .to_str()
            .ok_or_else(|| "Invalid filename: contains non-UTF8 characters".to_string())?;

        let lora_dir = self.models_path.join("loras");
        tokio::fs::create_dir_all(&lora_dir)
            .await
            .map_err(|e| format!("Failed to create lora directory: {}", e))?;

        let lora_path = lora_dir.join(safe_filename);
        tokio::fs::write(&lora_path, data)
            .await
            .map_err(|e| format!("Failed to write LoRA file: {}", e))?;

        // Save metadata if provided
        if let Some(meta) = metadata {
            let meta_path = lora_path.with_extension("json");
            let meta_json = serde_json::to_string_pretty(meta)
                .map_err(|e| format!("Failed to serialize metadata: {}", e))?;
            tokio::fs::write(&meta_path, meta_json)
                .await
                .map_err(|e| format!("Failed to write metadata: {}", e))?;
        }

        info!("Uploaded LoRA: {}", filename);
        Ok(lora_path)
    }

    /// List available LoRA models
    pub async fn list_loras(&self) -> Result<Vec<LoraInfo>, String> {
        let lora_dir = self.models_path.join("loras");

        if !lora_dir.exists() {
            return Ok(Vec::new());
        }

        let mut loras = Vec::new();
        let mut entries = tokio::fs::read_dir(&lora_dir)
            .await
            .map_err(|e| format!("Failed to read lora directory: {}", e))?;

        while let Ok(Some(entry)) = entries.next_entry().await {
            let path = entry.path();
            if let Some(ext) = path.extension()
                && (ext == "safetensors" || ext == "ckpt")
                && let Ok(metadata) = entry.metadata().await
            {
                loras.push(LoraInfo {
                    name: path
                        .file_stem()
                        .map(|s| s.to_string_lossy().to_string())
                        .unwrap_or_default(),
                    filename: path
                        .file_name()
                        .map(|s| s.to_string_lossy().to_string())
                        .unwrap_or_default(),
                    size: metadata.len(),
                });
            }
        }

        Ok(loras)
    }

    /// Download a LoRA model
    pub async fn download_lora(&self, filename: &str) -> Result<Vec<u8>, String> {
        // Sanitize filename to prevent path traversal attacks
        let safe_filename = std::path::Path::new(filename)
            .file_name()
            .ok_or_else(|| {
                "Invalid filename: must not be empty or contain path separators".to_string()
            })?
            .to_str()
            .ok_or_else(|| "Invalid filename: contains non-UTF8 characters".to_string())?;

        let lora_path = self.models_path.join("loras").join(safe_filename);

        if !lora_path.exists() {
            return Err(format!("LoRA not found: {}", safe_filename));
        }

        tokio::fs::read(&lora_path)
            .await
            .map_err(|e| format!("Failed to read LoRA file: {}", e))
    }

    /// Encode bytes to base64
    pub fn encode_base64(data: &[u8]) -> String {
        BASE64.encode(data)
    }

    /// Decode base64 to bytes
    pub fn decode_base64(data: &str) -> Result<Vec<u8>, String> {
        BASE64
            .decode(data)
            .map_err(|e| format!("Invalid base64 data: {}", e))
    }
}

/// LoRA model information
#[derive(Debug, Clone)]
pub struct LoraInfo {
    pub name: String,
    pub filename: String,
    pub size: u64,
}

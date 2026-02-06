//! ElevenLabs API client

use crate::types::{
    ModelInfo, OutputFormat, SynthesisConfig, SynthesisResult, UserInfo, Voice, VoicesResponse,
};
use reqwest::Client;
use serde_json::json;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

const BASE_URL: &str = "https://api.elevenlabs.io/v1";

/// ElevenLabs API client
pub struct ElevenLabsClient {
    client: Client,
    api_key: String,
    output_dir: Arc<RwLock<PathBuf>>,
    cache_dir: PathBuf,
}

impl ElevenLabsClient {
    /// Create a new ElevenLabs client
    pub fn new(api_key: String, output_dir: Option<PathBuf>) -> Self {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(60))
            .build()
            .expect("Failed to create HTTP client");

        let output_dir = output_dir.unwrap_or_else(|| {
            dirs::home_dir()
                .unwrap_or_else(|| PathBuf::from("."))
                .join("elevenlabs_outputs")
        });

        let cache_dir = PathBuf::from("/tmp/elevenlabs_cache");

        // Create directories
        std::fs::create_dir_all(&output_dir).ok();
        std::fs::create_dir_all(&cache_dir).ok();

        Self {
            client,
            api_key,
            output_dir: Arc::new(RwLock::new(output_dir)),
            cache_dir,
        }
    }

    /// Check if API key is configured
    pub fn has_api_key(&self) -> bool {
        !self.api_key.is_empty()
    }

    /// Get the cache directory path
    pub fn cache_dir(&self) -> &PathBuf {
        &self.cache_dir
    }

    /// Synthesize speech from text
    pub async fn synthesize_speech(&self, config: &SynthesisConfig) -> SynthesisResult {
        if !self.has_api_key() {
            return SynthesisResult::error(
                "No ElevenLabs API key configured".to_string(),
                config.text.len(),
            );
        }

        let voice_id = &config.voice_id;
        let url = format!("{}/text-to-speech/{}", BASE_URL, voice_id);

        let body = json!({
            "text": config.text,
            "model_id": config.model.as_str(),
            "voice_settings": {
                "stability": config.voice_settings.stability,
                "similarity_boost": config.voice_settings.similarity_boost,
                "style": config.voice_settings.style,
                "use_speaker_boost": config.voice_settings.use_speaker_boost
            }
        });

        debug!(
            "Synthesizing {} characters with voice {}",
            config.text.len(),
            voice_id
        );

        let response = match self
            .client
            .post(&url)
            .header("xi-api-key", &self.api_key)
            .header("Content-Type", "application/json")
            .query(&[("output_format", config.output_format.as_str())])
            .json(&body)
            .send()
            .await
        {
            Ok(resp) => resp,
            Err(e) => {
                error!("Request failed: {}", e);
                return SynthesisResult::error(format!("Request failed: {}", e), config.text.len());
            },
        };

        let status = response.status();
        if !status.is_success() {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            error!("API error {}: {}", status, error_text);
            return SynthesisResult::error(
                format!("API error {}: {}", status, error_text),
                config.text.len(),
            );
        }

        let audio_data = match response.bytes().await {
            Ok(data) => data.to_vec(),
            Err(e) => {
                error!("Failed to read response: {}", e);
                return SynthesisResult::error(
                    format!("Failed to read audio data: {}", e),
                    config.text.len(),
                );
            },
        };

        // Save to file
        let local_path = match self
            .save_audio(&audio_data, &config.output_format, "speech_")
            .await
        {
            Ok(path) => path,
            Err(e) => {
                error!("Failed to save audio: {}", e);
                return SynthesisResult::error(
                    format!("Failed to save audio: {}", e),
                    config.text.len(),
                );
            },
        };

        info!(
            "Synthesized {} chars, saved to {}",
            config.text.len(),
            local_path
        );

        SynthesisResult::success(
            local_path,
            config.text.len(),
            config.model.as_str(),
            voice_id,
        )
    }

    /// Generate a sound effect from a text prompt
    pub async fn generate_sound_effect(
        &self,
        prompt: &str,
        duration_seconds: f32,
    ) -> SynthesisResult {
        if !self.has_api_key() {
            return SynthesisResult::error(
                "No ElevenLabs API key configured".to_string(),
                prompt.len(),
            );
        }

        // Clamp duration to valid range
        let duration = duration_seconds.clamp(0.5, 22.0);

        let url = format!("{}/sound-generation", BASE_URL);
        let body = json!({
            "text": prompt,
            "duration_seconds": duration
        });

        debug!("Generating sound effect: {} ({:.1}s)", prompt, duration);

        let response = match self
            .client
            .post(&url)
            .header("xi-api-key", &self.api_key)
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
        {
            Ok(resp) => resp,
            Err(e) => {
                error!("Sound effect request failed: {}", e);
                return SynthesisResult::error(format!("Request failed: {}", e), prompt.len());
            },
        };

        let status = response.status();
        if !status.is_success() {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            error!("Sound effect API error {}: {}", status, error_text);
            return SynthesisResult::error(
                format!("API error {}: {}", status, error_text),
                prompt.len(),
            );
        }

        let audio_data = match response.bytes().await {
            Ok(data) => data.to_vec(),
            Err(e) => {
                return SynthesisResult::error(
                    format!("Failed to read audio data: {}", e),
                    prompt.len(),
                );
            },
        };

        // Save to file (sound effects are MP3)
        let local_path = match self
            .save_audio(&audio_data, &OutputFormat::Mp3_44100_128, "sfx_")
            .await
        {
            Ok(path) => path,
            Err(e) => {
                return SynthesisResult::error(
                    format!("Failed to save audio: {}", e),
                    prompt.len(),
                );
            },
        };

        info!("Generated sound effect, saved to {}", local_path);

        let mut result = SynthesisResult::success(local_path, prompt.len(), "sound_generation", "");
        result.duration_seconds = Some(duration);
        result
    }

    /// Get available voices
    pub async fn get_voices(&self) -> Result<Vec<Voice>, String> {
        if !self.has_api_key() {
            return Err("No ElevenLabs API key configured".to_string());
        }

        let url = format!("{}/voices", BASE_URL);

        let response = match self
            .client
            .get(&url)
            .header("xi-api-key", &self.api_key)
            .send()
            .await
        {
            Ok(resp) => resp,
            Err(e) => return Err(format!("Request failed: {}", e)),
        };

        if !response.status().is_success() {
            return Err(format!("API error: {}", response.status()));
        }

        let voices_response: VoicesResponse = match response.json().await {
            Ok(v) => v,
            Err(e) => return Err(format!("Failed to parse response: {}", e)),
        };

        Ok(voices_response.voices)
    }

    /// Get user subscription info
    pub async fn get_user_info(&self) -> Result<UserInfo, String> {
        if !self.has_api_key() {
            return Err("No ElevenLabs API key configured".to_string());
        }

        let url = format!("{}/user", BASE_URL);

        let response = match self
            .client
            .get(&url)
            .header("xi-api-key", &self.api_key)
            .send()
            .await
        {
            Ok(resp) => resp,
            Err(e) => return Err(format!("Request failed: {}", e)),
        };

        if !response.status().is_success() {
            return Err(format!("API error: {}", response.status()));
        }

        match response.json().await {
            Ok(info) => Ok(info),
            Err(e) => Err(format!("Failed to parse response: {}", e)),
        }
    }

    /// Get available models
    pub async fn get_models(&self) -> Result<Vec<ModelInfo>, String> {
        if !self.has_api_key() {
            return Err("No ElevenLabs API key configured".to_string());
        }

        let url = format!("{}/models", BASE_URL);

        let response = match self
            .client
            .get(&url)
            .header("xi-api-key", &self.api_key)
            .send()
            .await
        {
            Ok(resp) => resp,
            Err(e) => return Err(format!("Request failed: {}", e)),
        };

        if !response.status().is_success() {
            return Err(format!("API error: {}", response.status()));
        }

        match response.json().await {
            Ok(models) => Ok(models),
            Err(e) => Err(format!("Failed to parse response: {}", e)),
        }
    }

    /// Save audio data to file
    async fn save_audio(
        &self,
        audio_data: &[u8],
        format: &OutputFormat,
        prefix: &str,
    ) -> Result<String, String> {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis();

        let date = chrono::Local::now().format("%Y%m%d_%H%M%S");
        let filename = format!("{}{}_{}.{}", prefix, date, timestamp, format.extension());

        // Save to cache directory
        let cache_path = self.cache_dir.join(&filename);
        if let Err(e) = tokio::fs::write(&cache_path, audio_data).await {
            return Err(format!("Failed to write cache file: {}", e));
        }

        // Also save to output directory
        let output_dir = self.output_dir.read().await;
        let date_dir = output_dir.join(chrono::Local::now().format("%Y-%m-%d").to_string());
        tokio::fs::create_dir_all(&date_dir).await.ok();

        let output_path = date_dir.join(&filename);
        if let Err(e) = tokio::fs::write(&output_path, audio_data).await {
            warn!("Failed to write output file: {}", e);
        }

        Ok(cache_path.to_string_lossy().to_string())
    }

    /// Clear the cache directory
    pub async fn clear_cache(&self) -> Result<(), String> {
        if self.cache_dir.exists() {
            tokio::fs::remove_dir_all(&self.cache_dir)
                .await
                .map_err(|e| format!("Failed to clear cache: {}", e))?;
            tokio::fs::create_dir_all(&self.cache_dir)
                .await
                .map_err(|e| format!("Failed to recreate cache dir: {}", e))?;
        }
        Ok(())
    }
}

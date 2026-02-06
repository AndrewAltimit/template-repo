//! ElevenLabs Speech MCP Server implementation

use crate::client::ElevenLabsClient;
use crate::types::{
    OutputFormat, SynthesisConfig, VOICE_PRESETS, VoiceModel, VoiceSettings, get_preset,
    resolve_voice_id,
};
use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::env;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

/// ElevenLabs Speech MCP Server
pub struct ElevenLabsSpeechServer {
    client: Arc<RwLock<Option<ElevenLabsClient>>>,
    default_model: String,
    default_voice: String,
}

impl ElevenLabsSpeechServer {
    /// Create a new ElevenLabs Speech server
    pub fn new() -> Self {
        let api_key = env::var("ELEVENLABS_API_KEY").unwrap_or_default();
        let default_model =
            env::var("ELEVENLABS_DEFAULT_MODEL").unwrap_or_else(|_| "eleven_v3".to_string());
        let default_voice =
            env::var("ELEVENLABS_DEFAULT_VOICE").unwrap_or_else(|_| "rachel".to_string());

        let client = if !api_key.is_empty() {
            info!("ElevenLabs API key configured");
            Some(ElevenLabsClient::new(api_key, None))
        } else {
            info!("No ElevenLabs API key - some features will be limited");
            None
        };

        Self {
            client: Arc::new(RwLock::new(client)),
            default_model,
            default_voice,
        }
    }

    /// Get all tools provided by this server
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(SynthesizeSpeechTool {
                client: self.client.clone(),
                default_model: self.default_model.clone(),
                default_voice: self.default_voice.clone(),
            }),
            Arc::new(GenerateSoundEffectTool {
                client: self.client.clone(),
            }),
            Arc::new(ListVoicesTool {
                client: self.client.clone(),
            }),
            Arc::new(GetUserSubscriptionTool {
                client: self.client.clone(),
            }),
            Arc::new(GetModelsTool {
                client: self.client.clone(),
            }),
            Arc::new(ListPresetsTool),
            Arc::new(ClearCacheTool {
                client: self.client.clone(),
            }),
        ]
    }
}

impl Default for ElevenLabsSpeechServer {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tool: synthesize_speech
// ============================================================================

struct SynthesizeSpeechTool {
    client: Arc<RwLock<Option<ElevenLabsClient>>>,
    default_model: String,
    default_voice: String,
}

#[async_trait]
impl Tool for SynthesizeSpeechTool {
    fn name(&self) -> &str {
        "synthesize_speech"
    }

    fn description(&self) -> &str {
        "Synthesize speech with ElevenLabs. Supports audio tags like [laughs], [whisper], [excited] (v3 model only). Returns path to saved audio file."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesize. Can include audio tags like [laughs], [whisper], [sighs] for expressive speech (v3 model only)."
                },
                "voice_id": {
                    "type": "string",
                    "description": "Voice ID or name (e.g., 'rachel', 'george', 'sarah'). Defaults to configured default voice."
                },
                "model": {
                    "type": "string",
                    "description": "Model to use: eleven_v3 (most expressive), eleven_multilingual_v2 (29 languages), eleven_flash_v2_5 (low latency)",
                    "enum": ["eleven_v3", "eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_turbo_v2_5"]
                },
                "output_format": {
                    "type": "string",
                    "description": "Audio format: mp3_44100_128 (default), mp3_44100_192, pcm_24000, pcm_44100",
                    "enum": ["mp3_44100_128", "mp3_44100_192", "mp3_44100_96", "mp3_44100_64", "pcm_24000", "pcm_44100", "pcm_48000"]
                },
                "preset": {
                    "type": "string",
                    "description": "Voice preset: audiobook, character_performance, news_reading, emotional_dialogue, github_review, tutorial_narration, podcast, meditation, storytelling, customer_service"
                },
                "stability": {
                    "type": "number",
                    "description": "Stability (0.0-1.0). Higher = more consistent, lower = more expressive. Default: 0.5"
                },
                "similarity_boost": {
                    "type": "number",
                    "description": "Similarity boost (0.0-1.0). Higher = closer to original voice. Default: 0.75"
                },
                "style": {
                    "type": "number",
                    "description": "Style exaggeration (0.0-1.0). Higher = more dramatic. Default: 0.0"
                },
                "language_code": {
                    "type": "string",
                    "description": "Language code for multilingual models (e.g., 'en', 'ja', 'de'). Auto-detected if not provided."
                },
                "use_speaker_boost": {
                    "type": "boolean",
                    "description": "Enable speaker boost for enhanced clarity and presence. Default: false"
                }
            },
            "required": ["text"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let client_guard = self.client.read().await;
        let client = client_guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("ElevenLabs API key not configured".to_string()))?;

        let text = args.get("text").and_then(|v| v.as_str()).ok_or_else(|| {
            MCPError::InvalidParameters("Missing required 'text' parameter".to_string())
        })?;

        // Get voice ID
        let voice_input = args
            .get("voice_id")
            .and_then(|v| v.as_str())
            .unwrap_or(&self.default_voice);
        let voice_id = resolve_voice_id(voice_input);

        // Get model
        let model_str = args
            .get("model")
            .and_then(|v| v.as_str())
            .unwrap_or(&self.default_model);
        let model = VoiceModel::from_str(model_str).unwrap_or(VoiceModel::ElevenV3);

        // Get output format
        let format_str = args
            .get("output_format")
            .and_then(|v| v.as_str())
            .unwrap_or("mp3_44100_128");
        let output_format =
            OutputFormat::from_str(format_str).unwrap_or(OutputFormat::Mp3_44100_128);

        // Get voice settings (preset or individual params)
        let voice_settings = if let Some(preset_name) = args.get("preset").and_then(|v| v.as_str())
        {
            get_preset(preset_name).unwrap_or_default()
        } else {
            VoiceSettings {
                stability: args
                    .get("stability")
                    .and_then(|v| v.as_f64())
                    .map(|f| f as f32)
                    .unwrap_or(0.5),
                similarity_boost: args
                    .get("similarity_boost")
                    .and_then(|v| v.as_f64())
                    .map(|f| f as f32)
                    .unwrap_or(0.75),
                style: args
                    .get("style")
                    .and_then(|v| v.as_f64())
                    .map(|f| f as f32)
                    .unwrap_or(0.0),
                use_speaker_boost: args
                    .get("use_speaker_boost")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false),
            }
        };

        let language_code = args
            .get("language_code")
            .and_then(|v| v.as_str())
            .map(String::from);

        let config = SynthesisConfig {
            text: text.to_string(),
            voice_id,
            model,
            voice_settings,
            output_format,
            language_code,
        };

        let result = client.synthesize_speech(&config).await;

        let response = serde_json::to_value(result)
            .unwrap_or_else(|_| json!({"error": "Serialization failed"}));
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: generate_sound_effect
// ============================================================================

struct GenerateSoundEffectTool {
    client: Arc<RwLock<Option<ElevenLabsClient>>>,
}

#[async_trait]
impl Tool for GenerateSoundEffectTool {
    fn name(&self) -> &str {
        "generate_sound_effect"
    }

    fn description(&self) -> &str {
        "Generate a sound effect from a text description. Maximum duration is 22 seconds."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Description of the sound effect to generate (e.g., 'door creaking open', 'rain on a window', 'keyboard typing')"
                },
                "duration_seconds": {
                    "type": "number",
                    "description": "Duration in seconds (0.5 to 22.0). Default: 5.0"
                }
            },
            "required": ["prompt"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let client_guard = self.client.read().await;
        let client = client_guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("ElevenLabs API key not configured".to_string()))?;

        let prompt = args.get("prompt").and_then(|v| v.as_str()).ok_or_else(|| {
            MCPError::InvalidParameters("Missing required 'prompt' parameter".to_string())
        })?;

        let duration = args
            .get("duration_seconds")
            .and_then(|v| v.as_f64())
            .map(|f| f as f32)
            .unwrap_or(5.0);

        let result = client.generate_sound_effect(prompt, duration).await;

        let response = serde_json::to_value(result)
            .unwrap_or_else(|_| json!({"error": "Serialization failed"}));
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: list_voices
// ============================================================================

struct ListVoicesTool {
    client: Arc<RwLock<Option<ElevenLabsClient>>>,
}

#[async_trait]
impl Tool for ListVoicesTool {
    fn name(&self) -> &str {
        "list_voices"
    }

    fn description(&self) -> &str {
        "List all available ElevenLabs voices including their IDs, names, and categories."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let client_guard = self.client.read().await;
        let client = client_guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("ElevenLabs API key not configured".to_string()))?;

        match client.get_voices().await {
            Ok(voices) => {
                let formatted: Vec<Value> = voices
                    .iter()
                    .map(|v| {
                        json!({
                            "voice_id": v.voice_id,
                            "name": v.name,
                            "category": v.category,
                            "labels": v.labels,
                            "preview_url": v.preview_url
                        })
                    })
                    .collect();

                let response = json!({
                    "success": true,
                    "voices": formatted,
                    "count": voices.len()
                });
                ToolResult::json(&response)
            },
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            },
        }
    }
}

// ============================================================================
// Tool: get_user_subscription
// ============================================================================

struct GetUserSubscriptionTool {
    client: Arc<RwLock<Option<ElevenLabsClient>>>,
}

#[async_trait]
impl Tool for GetUserSubscriptionTool {
    fn name(&self) -> &str {
        "get_user_subscription"
    }

    fn description(&self) -> &str {
        "Get ElevenLabs user subscription information including character usage and limits."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let client_guard = self.client.read().await;
        let client = client_guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("ElevenLabs API key not configured".to_string()))?;

        match client.get_user_info().await {
            Ok(info) => {
                let response = json!({
                    "success": true,
                    "subscription": info.subscription,
                    "character_count": info.character_count,
                    "character_limit": info.character_limit
                });
                ToolResult::json(&response)
            },
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            },
        }
    }
}

// ============================================================================
// Tool: get_models
// ============================================================================

struct GetModelsTool {
    client: Arc<RwLock<Option<ElevenLabsClient>>>,
}

#[async_trait]
impl Tool for GetModelsTool {
    fn name(&self) -> &str {
        "get_models"
    }

    fn description(&self) -> &str {
        "Get available ElevenLabs models and their capabilities."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let client_guard = self.client.read().await;
        let client = client_guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("ElevenLabs API key not configured".to_string()))?;

        match client.get_models().await {
            Ok(models) => {
                let formatted: Vec<Value> = models
                    .iter()
                    .map(|m| {
                        json!({
                            "model_id": m.model_id,
                            "name": m.name,
                            "description": m.description,
                            "can_do_text_to_speech": m.can_do_text_to_speech
                        })
                    })
                    .collect();

                let response = json!({
                    "success": true,
                    "models": formatted,
                    "count": models.len()
                });
                ToolResult::json(&response)
            },
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            },
        }
    }
}

// ============================================================================
// Tool: list_presets
// ============================================================================

struct ListPresetsTool;

#[async_trait]
impl Tool for ListPresetsTool {
    fn name(&self) -> &str {
        "list_presets"
    }

    fn description(&self) -> &str {
        "List available voice presets with their settings."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let presets: Vec<Value> = VOICE_PRESETS
            .iter()
            .map(|(name, settings)| {
                json!({
                    "name": name,
                    "stability": settings.stability,
                    "similarity_boost": settings.similarity_boost,
                    "style": settings.style,
                    "use_speaker_boost": settings.use_speaker_boost
                })
            })
            .collect();

        let response = json!({
            "success": true,
            "presets": presets,
            "count": presets.len()
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: clear_cache
// ============================================================================

struct ClearCacheTool {
    client: Arc<RwLock<Option<ElevenLabsClient>>>,
}

#[async_trait]
impl Tool for ClearCacheTool {
    fn name(&self) -> &str {
        "clear_cache"
    }

    fn description(&self) -> &str {
        "Clear the local audio cache directory."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let client_guard = self.client.read().await;
        let client = client_guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("ElevenLabs API key not configured".to_string()))?;

        match client.clear_cache().await {
            Ok(()) => {
                let response = json!({
                    "success": true,
                    "message": format!("Cleared cache at {}", client.cache_dir().display())
                });
                ToolResult::json(&response)
            },
            Err(e) => {
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = ElevenLabsSpeechServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 7);
    }

    #[test]
    fn test_tool_names() {
        let server = ElevenLabsSpeechServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"synthesize_speech"));
        assert!(names.contains(&"generate_sound_effect"));
        assert!(names.contains(&"list_voices"));
        assert!(names.contains(&"get_user_subscription"));
        assert!(names.contains(&"get_models"));
        assert!(names.contains(&"list_presets"));
        assert!(names.contains(&"clear_cache"));
    }
}

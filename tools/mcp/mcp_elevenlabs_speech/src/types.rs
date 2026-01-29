//! Type definitions for ElevenLabs Speech MCP Server

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Voice model options
#[derive(Debug, Clone, Copy, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum VoiceModel {
    /// Latest v3 model - most expressive, supports audio tags
    #[default]
    #[serde(rename = "eleven_v3")]
    ElevenV3,
    /// Multilingual v2 - 29 languages
    #[serde(rename = "eleven_multilingual_v2")]
    ElevenMultilingualV2,
    /// Flash v2.5 - low latency ~75ms
    #[serde(rename = "eleven_flash_v2_5")]
    ElevenFlashV25,
    /// Turbo v2.5 - real-time optimized
    #[serde(rename = "eleven_turbo_v2_5")]
    ElevenTurboV25,
    /// Flash v2 - 32 languages
    #[serde(rename = "eleven_flash_v2")]
    ElevenFlashV2,
    /// Turbo v2 - real-time
    #[serde(rename = "eleven_turbo_v2")]
    ElevenTurboV2,
}

impl VoiceModel {
    pub fn as_str(&self) -> &'static str {
        match self {
            VoiceModel::ElevenV3 => "eleven_v3",
            VoiceModel::ElevenMultilingualV2 => "eleven_multilingual_v2",
            VoiceModel::ElevenFlashV25 => "eleven_flash_v2_5",
            VoiceModel::ElevenTurboV25 => "eleven_turbo_v2_5",
            VoiceModel::ElevenFlashV2 => "eleven_flash_v2",
            VoiceModel::ElevenTurboV2 => "eleven_turbo_v2",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "eleven_v3" => Some(VoiceModel::ElevenV3),
            "eleven_multilingual_v2" => Some(VoiceModel::ElevenMultilingualV2),
            "eleven_flash_v2_5" => Some(VoiceModel::ElevenFlashV25),
            "eleven_turbo_v2_5" => Some(VoiceModel::ElevenTurboV25),
            "eleven_flash_v2" => Some(VoiceModel::ElevenFlashV2),
            "eleven_turbo_v2" => Some(VoiceModel::ElevenTurboV2),
            _ => None,
        }
    }
}

/// Output audio format options
#[derive(Debug, Clone, Copy, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum OutputFormat {
    /// MP3 128kbps 44.1kHz - default high quality
    #[default]
    #[serde(rename = "mp3_44100_128")]
    Mp3_44100_128,
    /// MP3 192kbps 44.1kHz
    #[serde(rename = "mp3_44100_192")]
    Mp3_44100_192,
    /// MP3 96kbps 44.1kHz
    #[serde(rename = "mp3_44100_96")]
    Mp3_44100_96,
    /// MP3 64kbps 44.1kHz
    #[serde(rename = "mp3_44100_64")]
    Mp3_44100_64,
    /// MP3 32kbps 22.05kHz - small size
    #[serde(rename = "mp3_22050_32")]
    Mp3_22050_32,
    /// PCM 24kHz - good for streaming
    #[serde(rename = "pcm_24000")]
    Pcm24000,
    /// PCM 44.1kHz
    #[serde(rename = "pcm_44100")]
    Pcm44100,
    /// PCM 48kHz - highest quality
    #[serde(rename = "pcm_48000")]
    Pcm48000,
}

impl OutputFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            OutputFormat::Mp3_44100_128 => "mp3_44100_128",
            OutputFormat::Mp3_44100_192 => "mp3_44100_192",
            OutputFormat::Mp3_44100_96 => "mp3_44100_96",
            OutputFormat::Mp3_44100_64 => "mp3_44100_64",
            OutputFormat::Mp3_22050_32 => "mp3_22050_32",
            OutputFormat::Pcm24000 => "pcm_24000",
            OutputFormat::Pcm44100 => "pcm_44100",
            OutputFormat::Pcm48000 => "pcm_48000",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "mp3_44100_128" => Some(OutputFormat::Mp3_44100_128),
            "mp3_44100_192" => Some(OutputFormat::Mp3_44100_192),
            "mp3_44100_96" => Some(OutputFormat::Mp3_44100_96),
            "mp3_44100_64" => Some(OutputFormat::Mp3_44100_64),
            "mp3_22050_32" => Some(OutputFormat::Mp3_22050_32),
            "pcm_24000" => Some(OutputFormat::Pcm24000),
            "pcm_44100" => Some(OutputFormat::Pcm44100),
            "pcm_48000" => Some(OutputFormat::Pcm48000),
            _ => None,
        }
    }

    pub fn extension(&self) -> &'static str {
        match self {
            OutputFormat::Mp3_44100_128
            | OutputFormat::Mp3_44100_192
            | OutputFormat::Mp3_44100_96
            | OutputFormat::Mp3_44100_64
            | OutputFormat::Mp3_22050_32 => "mp3",
            OutputFormat::Pcm24000 | OutputFormat::Pcm44100 | OutputFormat::Pcm48000 => "pcm",
        }
    }
}

/// Voice settings for synthesis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoiceSettings {
    /// Stability (0.0 to 1.0) - higher = more consistent but less expressive
    #[serde(default = "default_stability")]
    pub stability: f32,
    /// Similarity boost (0.0 to 1.0) - higher = closer to original voice
    #[serde(default = "default_similarity")]
    pub similarity_boost: f32,
    /// Style exaggeration (0.0 to 1.0) - higher = more dramatic
    #[serde(default)]
    pub style: f32,
    /// Use speaker boost - increases similarity but adds latency
    #[serde(default)]
    pub use_speaker_boost: bool,
}

fn default_stability() -> f32 {
    0.5
}
fn default_similarity() -> f32 {
    0.75
}

impl Default for VoiceSettings {
    fn default() -> Self {
        Self {
            stability: 0.5,
            similarity_boost: 0.75,
            style: 0.0,
            use_speaker_boost: false,
        }
    }
}

/// Synthesis configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SynthesisConfig {
    /// Text to synthesize (can include audio tags like [laughs], [whisper])
    pub text: String,
    /// Voice ID or name
    pub voice_id: String,
    /// Model to use
    #[serde(default)]
    pub model: VoiceModel,
    /// Voice settings
    #[serde(default)]
    pub voice_settings: VoiceSettings,
    /// Output format
    #[serde(default)]
    pub output_format: OutputFormat,
    /// Language code (auto-detect if not provided)
    pub language_code: Option<String>,
}

/// Synthesis result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SynthesisResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub audio_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub audio_data_base64: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_seconds: Option<f32>,
    pub character_count: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_used: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voice_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, serde_json::Value>>,
}

impl SynthesisResult {
    pub fn error(message: String, char_count: usize) -> Self {
        Self {
            success: false,
            local_path: None,
            audio_url: None,
            audio_data_base64: None,
            duration_seconds: None,
            character_count: char_count,
            model_used: None,
            voice_id: None,
            error: Some(message),
            metadata: None,
        }
    }

    pub fn success(local_path: String, char_count: usize, model: &str, voice_id: &str) -> Self {
        Self {
            success: true,
            local_path: Some(local_path),
            audio_url: None,
            audio_data_base64: None,
            duration_seconds: None,
            character_count: char_count,
            model_used: Some(model.to_string()),
            voice_id: Some(voice_id.to_string()),
            error: None,
            metadata: None,
        }
    }
}

/// Voice information from API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Voice {
    pub voice_id: String,
    pub name: String,
    #[serde(default)]
    pub category: Option<String>,
    #[serde(default)]
    pub labels: HashMap<String, String>,
    #[serde(default)]
    pub preview_url: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
}

/// Voices list response from API
#[derive(Debug, Deserialize)]
pub struct VoicesResponse {
    pub voices: Vec<Voice>,
}

/// User subscription info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserInfo {
    pub subscription: SubscriptionInfo,
    #[serde(default)]
    pub character_count: Option<i64>,
    #[serde(default)]
    pub character_limit: Option<i64>,
}

/// Subscription details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubscriptionInfo {
    #[serde(default)]
    pub tier: Option<String>,
    #[serde(default)]
    pub character_count: Option<i64>,
    #[serde(default)]
    pub character_limit: Option<i64>,
    #[serde(default)]
    pub can_extend_character_limit: Option<bool>,
    #[serde(default)]
    pub allowed_to_extend_character_limit: Option<bool>,
    #[serde(default)]
    pub next_character_count_reset_unix: Option<i64>,
    #[serde(default)]
    pub voice_limit: Option<i32>,
    #[serde(default)]
    pub professional_voice_limit: Option<i32>,
}

/// Model info from API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub model_id: String,
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub can_be_finetuned: Option<bool>,
    #[serde(default)]
    pub can_do_text_to_speech: Option<bool>,
    #[serde(default)]
    pub can_do_voice_conversion: Option<bool>,
    #[serde(default)]
    pub languages: Option<Vec<LanguageInfo>>,
}

/// Language info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LanguageInfo {
    pub language_id: String,
    pub name: String,
}

/// Voice preset definitions
pub const VOICE_PRESETS: &[(&str, VoiceSettings)] = &[
    (
        "audiobook",
        VoiceSettings {
            stability: 0.75,
            similarity_boost: 0.75,
            style: 0.0,
            use_speaker_boost: false,
        },
    ),
    (
        "character_performance",
        VoiceSettings {
            stability: 0.3,
            similarity_boost: 0.8,
            style: 0.6,
            use_speaker_boost: true,
        },
    ),
    (
        "news_reading",
        VoiceSettings {
            stability: 0.9,
            similarity_boost: 0.7,
            style: 0.0,
            use_speaker_boost: false,
        },
    ),
    (
        "emotional_dialogue",
        VoiceSettings {
            stability: 0.5,
            similarity_boost: 0.85,
            style: 0.3,
            use_speaker_boost: true,
        },
    ),
    (
        "github_review",
        VoiceSettings {
            stability: 0.6,
            similarity_boost: 0.8,
            style: 0.2,
            use_speaker_boost: false,
        },
    ),
    (
        "tutorial_narration",
        VoiceSettings {
            stability: 0.7,
            similarity_boost: 0.75,
            style: 0.1,
            use_speaker_boost: false,
        },
    ),
    (
        "podcast",
        VoiceSettings {
            stability: 0.5,
            similarity_boost: 0.8,
            style: 0.4,
            use_speaker_boost: true,
        },
    ),
    (
        "meditation",
        VoiceSettings {
            stability: 0.85,
            similarity_boost: 0.7,
            style: 0.0,
            use_speaker_boost: false,
        },
    ),
    (
        "storytelling",
        VoiceSettings {
            stability: 0.4,
            similarity_boost: 0.75,
            style: 0.5,
            use_speaker_boost: true,
        },
    ),
    (
        "customer_service",
        VoiceSettings {
            stability: 0.8,
            similarity_boost: 0.75,
            style: 0.0,
            use_speaker_boost: false,
        },
    ),
];

/// Get voice settings from preset name
pub fn get_preset(name: &str) -> Option<VoiceSettings> {
    VOICE_PRESETS
        .iter()
        .find(|(n, _)| *n == name)
        .map(|(_, s)| s.clone())
}

/// Default voice IDs for common voices
pub mod default_voices {
    /// Rachel - female, American, warm and clear
    pub const RACHEL: &str = "21m00Tcm4TlvDq8ikWAM";
    /// George - male, British, warm narrator
    pub const GEORGE: &str = "JBFqnCBsd6RMkjVDRZzb";
    /// Sarah - female, American, soft and friendly
    pub const SARAH: &str = "EXAVITQu4vr4xnSDxMaL";
    /// Charlie - male, Australian, casual and natural
    pub const CHARLIE: &str = "IKne3meq5aSn9XLyUdCD";
    /// Emily - female, American, calm narrator
    pub const EMILY: &str = "LcfcDJNUP1GQjkzn1xUU";
}

/// Try to resolve a voice name to an ID
pub fn resolve_voice_id(voice_input: &str) -> String {
    // If it looks like a voice ID (long alphanumeric), return as-is
    if voice_input.len() > 15 && !voice_input.contains(' ') {
        return voice_input.to_string();
    }

    // Try to match common voice names (case-insensitive)
    match voice_input.to_lowercase().as_str() {
        "rachel" => default_voices::RACHEL.to_string(),
        "george" => default_voices::GEORGE.to_string(),
        "sarah" => default_voices::SARAH.to_string(),
        "charlie" => default_voices::CHARLIE.to_string(),
        "emily" => default_voices::EMILY.to_string(),
        _ => voice_input.to_string(), // Return as-is, might be a valid ID
    }
}

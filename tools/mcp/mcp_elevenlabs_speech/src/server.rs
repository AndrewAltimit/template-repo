//! MCP tool implementations for the ElevenLabs Speech server.
//!
//! Each tool deserializes its arguments into a typed `serde` struct (no
//! hand-rolled `args.get(..)` chains, so wrong types or missing required
//! fields become a clean `InvalidParameters` error instead of being silently
//! defaulted) while keeping a hand-written JSON schema that documents enums
//! and numeric ranges for the calling model.
//!
//! Error conventions:
//! - invalid input -> `MCPError::InvalidParameters` (JSON-RPC error)
//! - upstream/API/IO failures -> `isError` tool result whose text is a JSON
//!   object `{"success": false, "error": "..."}` (same shape as before)

use crate::client::{ApiError, ElevenLabsClient, SoundBody, TtsBody};
use crate::config::Config;
use crate::storage;
use crate::types::{
    AudioResult, DEFAULT_OUTPUT_FORMAT, KNOWN_MODELS, OUTPUT_FORMATS, OutputFormat, SPEED_RANGE,
    VOICE_PRESETS, VoiceSettings, VoiceSettingsOverrides, get_preset, known_model, preset_names,
    validate_model_id, validate_text_normalization,
};
use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

/// Minimum / maximum sound effect duration accepted by the API (seconds).
pub const SFX_DURATION_RANGE: (f32, f32) = (0.5, 30.0);
/// Default sound effect duration (seconds).
pub const SFX_DEFAULT_DURATION: f32 = 5.0;

/// ElevenLabs Speech MCP server: owns the shared client and configuration.
pub struct ElevenLabsSpeechServer {
    client: Arc<ElevenLabsClient>,
    config: Arc<Config>,
    legacy_cache_dir: PathBuf,
}

impl ElevenLabsSpeechServer {
    /// Create a server from configuration (no network I/O).
    pub fn new(config: Config) -> Self {
        let client = Arc::new(ElevenLabsClient::new(&config));
        Self {
            client,
            config: Arc::new(config),
            legacy_cache_dir: std::env::temp_dir().join("elevenlabs_cache"),
        }
    }

    /// Override the legacy cache directory cleaned by `clear_cache`.
    #[cfg(test)]
    fn with_legacy_cache_dir(mut self, dir: PathBuf) -> Self {
        self.legacy_cache_dir = dir;
        self
    }

    /// Whether an API key is configured.
    pub fn has_api_key(&self) -> bool {
        self.client.has_api_key()
    }

    /// All tools provided by this server.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let c = || self.client.clone();
        vec![
            Arc::new(SynthesizeSpeechTool {
                client: c(),
                config: self.config.clone(),
            }),
            Arc::new(GenerateSoundEffectTool { client: c() }),
            Arc::new(ListVoicesTool { client: c() }),
            Arc::new(GetUserSubscriptionTool { client: c() }),
            Arc::new(GetModelsTool { client: c() }),
            Arc::new(ListPresetsTool),
            Arc::new(ClearCacheTool {
                client: c(),
                legacy_dir: self.legacy_cache_dir.clone(),
            }),
        ]
    }
}

// ============================================================================
// Helpers
// ============================================================================

/// Deserialize tool arguments into `T`. `null`/absent arguments are treated
/// as an empty object so tools without required params accept them.
fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

fn invalid(msg: impl Into<String>) -> MCPError {
    MCPError::InvalidParameters(msg.into())
}

/// Build an `isError` result carrying `{"success": false, "error": msg}`.
fn failure(msg: impl Into<String>) -> ToolResult {
    let body = json!({"success": false, "error": msg.into()});
    ToolResult {
        content: vec![Content::text(
            serde_json::to_string_pretty(&body).unwrap_or_else(|_| body.to_string()),
        )],
        is_error: true,
    }
}

/// Map a client error: input problems become `InvalidParameters`, everything
/// else an `isError` result.
fn api_failure(e: ApiError) -> Result<ToolResult> {
    match e {
        ApiError::InvalidInput(m) => Err(invalid(m)),
        other => Ok(failure(other.to_string())),
    }
}

fn parse_format(s: Option<&str>) -> Result<OutputFormat> {
    OutputFormat::parse(s.unwrap_or(DEFAULT_OUTPUT_FORMAT)).map_err(invalid)
}

/// True if `text` contains something shaped like an audio tag, e.g. `[laughs]`.
fn contains_audio_tag(text: &str) -> bool {
    let mut rest = text;
    while let Some(start) = rest.find('[') {
        let after = &rest[start + 1..];
        match after.find(']') {
            Some(end) => {
                let inner = &after[..end];
                if !inner.is_empty()
                    && inner.len() <= 40
                    && inner
                        .chars()
                        .all(|c| c.is_alphabetic() || c == ' ' || c == '-' || c == '\'')
                {
                    return true;
                }
                rest = &after[end + 1..];
            },
            None => return false,
        }
    }
    false
}

fn validate_language_code(code: &str) -> Result<String> {
    let c = code.trim().to_ascii_lowercase();
    if (2..=3).contains(&c.len()) && c.chars().all(|ch| ch.is_ascii_lowercase()) {
        Ok(c)
    } else {
        Err(invalid(format!(
            "Invalid language_code '{code}': expected an ISO 639-1 code such as 'en', 'ja', 'de'"
        )))
    }
}

fn non_empty(opt: Option<String>) -> Option<String> {
    opt.filter(|s| !s.trim().is_empty())
}

// ============================================================================
// Tool: synthesize_speech
// ============================================================================

#[derive(Debug, Deserialize)]
struct SynthesizeArgs {
    text: String,
    voice_id: Option<String>,
    model: Option<String>,
    output_format: Option<String>,
    preset: Option<String>,
    stability: Option<f32>,
    similarity_boost: Option<f32>,
    style: Option<f32>,
    speed: Option<f32>,
    use_speaker_boost: Option<bool>,
    language_code: Option<String>,
    seed: Option<u32>,
    previous_text: Option<String>,
    next_text: Option<String>,
    apply_text_normalization: Option<String>,
}

/// A fully validated synthesis request (voice not yet resolved).
#[derive(Debug)]
struct PreparedTts {
    voice_input: String,
    body: TtsBody,
    format: OutputFormat,
    warnings: Vec<String>,
}

/// Validate synthesis arguments and build the request body. Pure; unit tested.
fn prepare_tts(args: SynthesizeArgs, config: &Config) -> Result<PreparedTts> {
    let mut warnings = Vec::new();

    if args.text.trim().is_empty() {
        return Err(invalid("'text' must not be empty"));
    }
    let model_id = non_empty(args.model).unwrap_or_else(|| config.default_model.clone());
    validate_model_id(&model_id).map_err(invalid)?;
    let known = known_model(&model_id);

    let char_count = args.text.chars().count();
    if let Some(m) = known {
        if char_count > m.max_chars {
            return Err(invalid(format!(
                "Text is {char_count} characters; {} accepts at most {} per request. Split the text or use eleven_flash_v2_5 (40,000).",
                m.id, m.max_chars
            )));
        }
        if let Some(repl) = m.deprecated_by {
            warnings.push(format!(
                "Model {} is deprecated by ElevenLabs; use {repl} instead.",
                m.id
            ));
        }
        if !m.supports_audio_tags && contains_audio_tag(&args.text) {
            warnings.push(format!(
                "Text contains audio tags like [laughs]; {} does not interpret them and may read them aloud. Use eleven_v3.",
                m.id
            ));
        }
    }

    let format = parse_format(args.output_format.as_deref())?;

    let base = match non_empty(args.preset) {
        Some(name) => get_preset(&name).ok_or_else(|| {
            invalid(format!(
                "Unknown preset '{name}'. Available: {}",
                preset_names()
            ))
        })?,
        None => VoiceSettings::default(),
    };
    let mut voice_settings = base
        .with_overrides(VoiceSettingsOverrides {
            stability: args.stability,
            similarity_boost: args.similarity_boost,
            style: args.style,
            use_speaker_boost: args.use_speaker_boost,
            speed: args.speed,
        })
        .map_err(invalid)?;
    if model_id == "eleven_v3"
        && let Some(orig) = voice_settings.snap_stability_for_v3()
    {
        warnings.push(format!(
            "eleven_v3 only accepts stability 0.0 (creative), 0.5 (natural) or 1.0 (robust); {orig} was rounded to {}.",
            voice_settings.stability
        ));
    }

    let language_code = non_empty(args.language_code)
        .map(|c| validate_language_code(&c))
        .transpose()?;

    let apply_text_normalization = non_empty(args.apply_text_normalization)
        .map(|v| {
            let v = v.trim().to_ascii_lowercase();
            validate_text_normalization(&v).map(|_| v)
        })
        .transpose()
        .map_err(invalid)?;

    let voice_input = non_empty(args.voice_id).unwrap_or_else(|| config.default_voice.clone());

    Ok(PreparedTts {
        voice_input,
        body: TtsBody {
            text: args.text,
            model_id,
            voice_settings,
            language_code,
            seed: args.seed,
            previous_text: non_empty(args.previous_text),
            next_text: non_empty(args.next_text),
            apply_text_normalization,
        },
        format,
        warnings,
    })
}

struct SynthesizeSpeechTool {
    client: Arc<ElevenLabsClient>,
    config: Arc<Config>,
}

#[async_trait]
impl Tool for SynthesizeSpeechTool {
    fn name(&self) -> &str {
        "synthesize_speech"
    }

    fn description(&self) -> &str {
        "Synthesize speech with ElevenLabs text-to-speech and save it to a local audio file. \
         eleven_v3 supports inline audio tags like [laughs], [whispers], [excited]. \
         Returns the absolute path of the saved file plus request metadata."
    }

    fn schema(&self) -> Value {
        let models: Vec<String> = KNOWN_MODELS
            .iter()
            .map(|m| format!("{} ({}, max {} chars)", m.id, m.description, m.max_chars))
            .collect();
        json!({
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesize. With eleven_v3 it may include audio tags such as [laughs], [whispers], [sighs], [excited]."
                },
                "voice_id": {
                    "type": "string",
                    "description": "Voice ID (20-char ID from list_voices) or voice name from your account (e.g. 'George'). Defaults to ELEVENLABS_DEFAULT_VOICE."
                },
                "model": {
                    "type": "string",
                    "description": format!("Model ID. Defaults to ELEVENLABS_DEFAULT_MODEL. Known: {}. Other valid ElevenLabs model IDs are passed through.", models.join("; "))
                },
                "output_format": {
                    "type": "string",
                    "description": "Audio format (codec_samplerate[_bitrate]). Default mp3_44100_128. Use wav_* for directly playable uncompressed audio; pcm_*/ulaw/alaw are raw headerless streams. Some formats require a paid tier.",
                    "enum": OUTPUT_FORMATS
                },
                "preset": {
                    "type": "string",
                    "description": "Voice settings preset. Explicit stability/similarity_boost/style/speed/use_speaker_boost values override the preset.",
                    "enum": VOICE_PRESETS.iter().map(|(n, _, _)| *n).collect::<Vec<_>>()
                },
                "stability": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0,
                    "description": "Higher = more consistent, lower = more expressive. Default 0.5. eleven_v3 accepts only 0.0, 0.5 or 1.0 (other values are rounded)."
                },
                "similarity_boost": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0,
                    "description": "Higher = closer to the original voice. Default 0.75."
                },
                "style": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0,
                    "description": "Style exaggeration; higher = more dramatic (adds latency). Default 0.0."
                },
                "speed": {
                    "type": "number", "minimum": SPEED_RANGE.0, "maximum": SPEED_RANGE.1,
                    "description": "Speaking speed, 1.0 = normal. Omit to use the voice default."
                },
                "use_speaker_boost": {
                    "type": "boolean",
                    "description": "Boost similarity to the original speaker (slight latency cost). Default false."
                },
                "language_code": {
                    "type": "string",
                    "description": "ISO 639-1 language code (e.g. 'en', 'ja', 'de') to enforce language and text normalization. Auto-detected if omitted."
                },
                "seed": {
                    "type": "integer", "minimum": 0, "maximum": 4294967295u64,
                    "description": "Seed for best-effort deterministic output."
                },
                "previous_text": {
                    "type": "string",
                    "description": "Text that comes before this request, for continuity when splitting long content."
                },
                "next_text": {
                    "type": "string",
                    "description": "Text that comes after this request, for continuity when splitting long content."
                },
                "apply_text_normalization": {
                    "type": "string",
                    "enum": ["auto", "on", "off"],
                    "description": "Spell out numbers/abbreviations. Default auto."
                }
            },
            "required": ["text"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: SynthesizeArgs = parse_args(args)?;
        let mut prepared = prepare_tts(args, &self.config)?;

        let resolved = match self.client.resolve_voice(&prepared.voice_input).await {
            Ok(r) => r,
            Err(e) => return api_failure(e),
        };
        if let Some(w) = resolved.warning {
            prepared.warnings.push(w);
        }

        match self
            .client
            .text_to_speech(&resolved.voice_id, &prepared.body, prepared.format)
            .await
        {
            Ok(saved) => ToolResult::json(&AudioResult {
                success: true,
                local_path: saved.path.to_string_lossy().to_string(),
                output_format: prepared.format.as_str().to_string(),
                file_size_bytes: saved.size_bytes,
                character_count: prepared.body.text.chars().count(),
                model_used: Some(prepared.body.model_id.clone()),
                voice_id: Some(resolved.voice_id),
                duration_seconds: None,
                request_id: saved.request_id,
                warnings: prepared.warnings,
            }),
            Err(e) => api_failure(e),
        }
    }
}

// ============================================================================
// Tool: generate_sound_effect
// ============================================================================

#[derive(Debug, Deserialize)]
struct SoundEffectArgs {
    prompt: String,
    duration_seconds: Option<f32>,
    prompt_influence: Option<f32>,
    #[serde(rename = "loop")]
    looping: Option<bool>,
    output_format: Option<String>,
}

/// Validate sound effect arguments. Pure; unit tested.
fn prepare_sound(args: SoundEffectArgs) -> Result<(SoundBody, OutputFormat)> {
    if args.prompt.trim().is_empty() {
        return Err(invalid("'prompt' must not be empty"));
    }
    let duration = args.duration_seconds.unwrap_or(SFX_DEFAULT_DURATION);
    let (lo, hi) = SFX_DURATION_RANGE;
    if !(duration.is_finite() && (lo..=hi).contains(&duration)) {
        return Err(invalid(format!(
            "'duration_seconds' must be between {lo} and {hi} (got {duration})"
        )));
    }
    if let Some(p) = args.prompt_influence
        && !(p.is_finite() && (0.0..=1.0).contains(&p))
    {
        return Err(invalid(format!(
            "'prompt_influence' must be between 0.0 and 1.0 (got {p})"
        )));
    }
    let format = parse_format(args.output_format.as_deref())?;
    Ok((
        SoundBody {
            text: args.prompt,
            duration_seconds: Some(duration),
            prompt_influence: args.prompt_influence,
            looping: args.looping.unwrap_or(false),
        },
        format,
    ))
}

struct GenerateSoundEffectTool {
    client: Arc<ElevenLabsClient>,
}

#[async_trait]
impl Tool for GenerateSoundEffectTool {
    fn name(&self) -> &str {
        "generate_sound_effect"
    }

    fn description(&self) -> &str {
        "Generate a sound effect from a text description (0.5-30 seconds) and save it to a local audio file."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Description of the sound (e.g. 'door creaking open', 'rain on a window')."
                },
                "duration_seconds": {
                    "type": "number", "minimum": SFX_DURATION_RANGE.0, "maximum": SFX_DURATION_RANGE.1,
                    "description": "Length in seconds. Default 5.0."
                },
                "prompt_influence": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0,
                    "description": "How strictly to follow the prompt; higher = less variation. API default 0.3."
                },
                "loop": {
                    "type": "boolean",
                    "description": "Create a seamlessly looping sound. Default false."
                },
                "output_format": {
                    "type": "string",
                    "enum": OUTPUT_FORMATS,
                    "description": "Audio format. Default mp3_44100_128."
                }
            },
            "required": ["prompt"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: SoundEffectArgs = parse_args(args)?;
        let (body, format) = prepare_sound(args)?;
        match self.client.sound_generation(&body, format).await {
            Ok(saved) => ToolResult::json(&AudioResult {
                success: true,
                local_path: saved.path.to_string_lossy().to_string(),
                output_format: format.as_str().to_string(),
                file_size_bytes: saved.size_bytes,
                character_count: body.text.chars().count(),
                model_used: Some("sound_generation".to_string()),
                voice_id: None,
                duration_seconds: body.duration_seconds,
                request_id: saved.request_id,
                warnings: Vec::new(),
            }),
            Err(e) => api_failure(e),
        }
    }
}

// ============================================================================
// Tool: list_voices
// ============================================================================

#[derive(Debug, Default, Deserialize)]
struct ListVoicesArgs {
    search: Option<String>,
    category: Option<String>,
    #[serde(default)]
    refresh: bool,
}

struct ListVoicesTool {
    client: Arc<ElevenLabsClient>,
}

#[async_trait]
impl Tool for ListVoicesTool {
    fn name(&self) -> &str {
        "list_voices"
    }

    fn description(&self) -> &str {
        "List the ElevenLabs voices available to this account (IDs, names, categories, labels). Optionally filter by text or category."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Case-insensitive substring matched against name, description and labels (e.g. 'british', 'narration')."
                },
                "category": {
                    "type": "string",
                    "description": "Only voices in this category, e.g. premade, cloned, generated, professional."
                },
                "refresh": {
                    "type": "boolean",
                    "description": "Bypass the 10-minute voice list cache. Default false."
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: ListVoicesArgs = parse_args(args)?;
        let voices = match self.client.voices(args.refresh).await {
            Ok(v) => v,
            Err(e) => return api_failure(e),
        };
        let needle = non_empty(args.search).map(|s| s.to_lowercase());
        let category = non_empty(args.category);
        let formatted: Vec<Value> = voices
            .iter()
            .filter(|v| needle.as_deref().is_none_or(|n| v.search_matches(n)))
            .filter(|v| {
                category.as_deref().is_none_or(|c| {
                    v.category
                        .as_deref()
                        .is_some_and(|vc| vc.eq_ignore_ascii_case(c))
                })
            })
            .map(|v| {
                json!({
                    "voice_id": v.voice_id,
                    "name": v.name,
                    "category": v.category,
                    "labels": v.labels,
                    "description": v.description,
                    "preview_url": v.preview_url
                })
            })
            .collect();
        ToolResult::json(&json!({
            "success": true,
            "count": formatted.len(),
            "total_available": voices.len(),
            "voices": formatted
        }))
    }
}

// ============================================================================
// Tool: get_user_subscription
// ============================================================================

struct GetUserSubscriptionTool {
    client: Arc<ElevenLabsClient>,
}

#[async_trait]
impl Tool for GetUserSubscriptionTool {
    fn name(&self) -> &str {
        "get_user_subscription"
    }

    fn description(&self) -> &str {
        "Get ElevenLabs subscription info: tier, characters used/limit/remaining and next reset time."
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.client.user_info().await {
            Ok(info) => {
                let s = &info.subscription;
                let next_reset = s
                    .next_character_count_reset_unix
                    .and_then(|t| chrono::DateTime::from_timestamp(t, 0))
                    .map(|d| d.to_rfc3339());
                ToolResult::json(&json!({
                    "success": true,
                    "tier": s.tier,
                    "character_count": s.character_count,
                    "character_limit": s.character_limit,
                    "characters_remaining": s.characters_remaining(),
                    "next_reset": next_reset,
                    "subscription": s
                }))
            },
            Err(e) => api_failure(e),
        }
    }
}

// ============================================================================
// Tool: get_models
// ============================================================================

#[derive(Debug, Default, Deserialize)]
struct GetModelsArgs {
    #[serde(default)]
    tts_only: bool,
}

struct GetModelsTool {
    client: Arc<ElevenLabsClient>,
}

#[async_trait]
impl Tool for GetModelsTool {
    fn name(&self) -> &str {
        "get_models"
    }

    fn description(&self) -> &str {
        "Get the ElevenLabs models available to this account with capabilities, max text length and supported languages."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "tts_only": {
                    "type": "boolean",
                    "description": "Only return models that can do text-to-speech. Default false."
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: GetModelsArgs = parse_args(args)?;
        match self.client.models().await {
            Ok(models) => {
                let formatted: Vec<Value> = models
                    .iter()
                    .filter(|m| !args.tts_only || m.can_do_text_to_speech == Some(true))
                    .map(|m| {
                        json!({
                            "model_id": m.model_id,
                            "name": m.name,
                            "description": m.description,
                            "can_do_text_to_speech": m.can_do_text_to_speech,
                            "can_use_style": m.can_use_style,
                            "can_use_speaker_boost": m.can_use_speaker_boost,
                            "maximum_text_length_per_request": m.maximum_text_length_per_request,
                            "deprecated_by": known_model(&m.model_id).and_then(|k| k.deprecated_by),
                            "languages": m.languages.as_ref().map(|l| {
                                l.iter().map(|x| x.language_id.as_str()).collect::<Vec<_>>()
                            })
                        })
                    })
                    .collect();
                ToolResult::json(&json!({
                    "success": true,
                    "count": formatted.len(),
                    "models": formatted
                }))
            },
            Err(e) => api_failure(e),
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
        "List the built-in voice settings presets usable with synthesize_speech's 'preset' parameter. Works without an API key."
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let presets: Vec<Value> = VOICE_PRESETS
            .iter()
            .map(|(name, s, use_case)| {
                json!({
                    "name": name,
                    "use_case": use_case,
                    "stability": s.stability,
                    "similarity_boost": s.similarity_boost,
                    "style": s.style,
                    "use_speaker_boost": s.use_speaker_boost
                })
            })
            .collect();
        ToolResult::json(&json!({
            "success": true,
            "count": presets.len(),
            "presets": presets
        }))
    }
}

// ============================================================================
// Tool: clear_cache
// ============================================================================

#[derive(Debug, Default, Deserialize)]
struct ClearCacheArgs {
    older_than_days: Option<f64>,
    #[serde(default)]
    dry_run: bool,
}

struct ClearCacheTool {
    client: Arc<ElevenLabsClient>,
    /// `<temp>/elevenlabs_cache`: versions <= 2.0 wrote a duplicate copy of
    /// every file there. Still cleaned so upgrading does not strand old audio.
    legacy_dir: PathBuf,
}

#[async_trait]
impl Tool for ClearCacheTool {
    fn name(&self) -> &str {
        "clear_cache"
    }

    fn description(&self) -> &str {
        "Delete audio files previously generated by this server (speech_*/sfx_* files in the output directory and the legacy temp cache). Other files are never touched. Supports dry_run and an age filter. Works without an API key."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "older_than_days": {
                    "type": "number", "minimum": 0,
                    "description": "Only delete files at least this many days old. Default: delete all generated files."
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Report what would be deleted without deleting. Default false."
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: ClearCacheArgs = parse_args(args)?;
        let older_than = match args.older_than_days {
            None => None,
            Some(d) if (0.0..=36_500.0).contains(&d) => Some(Duration::from_secs_f64(d * 86_400.0)),
            Some(d) => {
                return Err(invalid(format!(
                    "'older_than_days' must be between 0 and 36500 (got {d})"
                )));
            },
        };

        let out_dir = self.client.output_dir().to_path_buf();
        let out = storage::clear_generated(&out_dir, older_than, args.dry_run).await;
        let legacy = storage::clear_generated(&self.legacy_dir, older_than, args.dry_run).await;

        let files = out.files_removed + legacy.files_removed;
        let verb = if args.dry_run {
            "Would remove"
        } else {
            "Removed"
        };
        let response = json!({
            "success": out.errors.is_empty() && legacy.errors.is_empty(),
            "message": format!("{verb} {files} generated audio file(s) from {}", out_dir.display()),
            "output_dir": out,
            "legacy_cache_dir": legacy,
        });
        if out.errors.is_empty() && legacy.errors.is_empty() {
            ToolResult::json(&response)
        } else {
            let mut r = ToolResult::json(&response)?;
            r.is_error = true;
            Ok(r)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use wiremock::matchers::{method, path};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    fn config(base: &str, out: &std::path::Path, key: Option<&str>) -> Config {
        Config {
            api_key: key.map(str::to_string),
            base_url: base.to_string(),
            output_dir: out.to_path_buf(),
            default_model: "eleven_v3".into(),
            default_voice: "george".into(),
            timeout: Duration::from_secs(5),
        }
    }

    fn offline_server(out: &std::path::Path) -> ElevenLabsSpeechServer {
        ElevenLabsSpeechServer::new(config("http://127.0.0.1:9", out, None))
            .with_legacy_cache_dir(out.join("legacy_cache"))
    }

    fn tool(server: &ElevenLabsSpeechServer, name: &str) -> BoxedTool {
        server
            .tools()
            .into_iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("tool {name} missing"))
    }

    fn text_of(r: &ToolResult) -> String {
        match &r.content[0] {
            Content::Text { text } => text.clone(),
            _ => panic!("expected text"),
        }
    }

    fn synth_args(v: Value) -> SynthesizeArgs {
        serde_json::from_value(v).unwrap()
    }

    #[test]
    fn tool_names_are_stable() {
        let tmp = tempfile::tempdir().unwrap();
        let server = offline_server(tmp.path());
        let names: Vec<String> = server
            .tools()
            .iter()
            .map(|t| t.name().to_string())
            .collect();
        assert_eq!(
            names,
            [
                "synthesize_speech",
                "generate_sound_effect",
                "list_voices",
                "get_user_subscription",
                "get_models",
                "list_presets",
                "clear_cache"
            ]
        );
        for t in server.tools() {
            assert_eq!(t.schema()["type"], "object", "{}", t.name());
        }
    }

    #[test]
    fn prepare_tts_defaults() {
        let tmp = tempfile::tempdir().unwrap();
        let c = config("http://x", tmp.path(), None);
        let p = prepare_tts(synth_args(json!({"text": "hi"})), &c).unwrap();
        assert_eq!(p.voice_input, "george");
        assert_eq!(p.body.model_id, "eleven_v3");
        assert_eq!(p.format.as_str(), "mp3_44100_128");
        assert_eq!(p.body.voice_settings, VoiceSettings::default());
        assert!(p.warnings.is_empty());
    }

    #[test]
    fn prepare_tts_explicit_params_override_preset() {
        let tmp = tempfile::tempdir().unwrap();
        let c = config("http://x", tmp.path(), None);
        let p = prepare_tts(
            synth_args(json!({
                "text": "hi", "preset": "podcast", "style": 0.9,
                "model": "eleven_multilingual_v2", "language_code": "EN",
                "seed": 7, "apply_text_normalization": "OFF"
            })),
            &c,
        )
        .unwrap();
        assert_eq!(p.body.voice_settings.style, 0.9);
        assert_eq!(p.body.voice_settings.similarity_boost, 0.8); // from preset
        assert!(p.body.voice_settings.use_speaker_boost); // from preset
        assert_eq!(p.body.language_code.as_deref(), Some("en"));
        assert_eq!(p.body.seed, Some(7));
        assert_eq!(p.body.apply_text_normalization.as_deref(), Some("off"));
    }

    #[test]
    fn prepare_tts_rejects_bad_input() {
        let tmp = tempfile::tempdir().unwrap();
        let c = config("http://x", tmp.path(), None);
        for (args, needle) in [
            (json!({"text": "  "}), "must not be empty"),
            (json!({"text": "a", "model": "bad model"}), "Invalid model"),
            (
                json!({"text": "a", "output_format": "flac"}),
                "Invalid output_format",
            ),
            (json!({"text": "a", "preset": "nope"}), "Unknown preset"),
            (json!({"text": "a", "stability": 3.0}), "stability"),
            (json!({"text": "a", "speed": 5.0}), "speed"),
            (
                json!({"text": "a", "language_code": "english"}),
                "language_code",
            ),
            (
                json!({"text": "a", "apply_text_normalization": "maybe"}),
                "apply_text_normalization",
            ),
            (json!({"text": "x".repeat(5001)}), "at most 5000"),
        ] {
            let err = prepare_tts(synth_args(args.clone()), &c).unwrap_err();
            assert!(err.to_string().contains(needle), "{args}: {err}");
        }
    }

    #[test]
    fn prepare_tts_warnings() {
        let tmp = tempfile::tempdir().unwrap();
        let c = config("http://x", tmp.path(), None);
        let p = prepare_tts(
            synth_args(json!({"text": "[laughs] hi", "model": "eleven_turbo_v2_5"})),
            &c,
        )
        .unwrap();
        assert_eq!(p.warnings.len(), 2, "{:?}", p.warnings);

        // Preset stability 0.75 is not valid for v3 -> rounded with a warning.
        let p = prepare_tts(synth_args(json!({"text": "hi", "preset": "audiobook"})), &c).unwrap();
        assert!(p.body.voice_settings.stability != 0.75);
        assert!(p.warnings[0].contains("eleven_v3"));
    }

    #[test]
    fn audio_tag_detection() {
        assert!(contains_audio_tag("[laughs] ok"));
        assert!(contains_audio_tag("so [long pause] then"));
        assert!(!contains_audio_tag("array[0] and [1]"));
        assert!(!contains_audio_tag("no tags"));
        assert!(!contains_audio_tag("unclosed [tag"));
    }

    #[test]
    fn prepare_sound_validation() {
        let parse = |v: Value| prepare_sound(serde_json::from_value(v).unwrap());
        let (b, f) = parse(json!({"prompt": "rain"})).unwrap();
        assert_eq!(b.duration_seconds, Some(5.0));
        assert!(!b.looping);
        assert_eq!(f.as_str(), "mp3_44100_128");
        let (b, _) =
            parse(json!({"prompt": "rain", "duration_seconds": 30, "loop": true})).unwrap();
        assert_eq!(b.duration_seconds, Some(30.0));
        assert!(b.looping);
        assert!(parse(json!({"prompt": "rain", "duration_seconds": 0.1})).is_err());
        assert!(parse(json!({"prompt": "rain", "duration_seconds": 31})).is_err());
        assert!(parse(json!({"prompt": "rain", "prompt_influence": 2})).is_err());
        assert!(parse(json!({"prompt": ""})).is_err());
    }

    #[tokio::test]
    async fn missing_required_and_wrong_types_are_invalid_params() {
        let tmp = tempfile::tempdir().unwrap();
        let server = offline_server(tmp.path());
        let t = tool(&server, "synthesize_speech");
        let err = t.execute(json!({})).await.unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));
        let err = t.execute(json!({"text": 5})).await.unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));
        let err = tool(&server, "generate_sound_effect")
            .execute(json!({"prompt": "x", "duration_seconds": "long"}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));
    }

    #[tokio::test]
    async fn api_tools_without_key_return_clear_error() {
        let tmp = tempfile::tempdir().unwrap();
        let server = offline_server(tmp.path());
        assert!(!server.has_api_key());
        for (name, args) in [
            ("synthesize_speech", json!({"text": "hi"})),
            ("generate_sound_effect", json!({"prompt": "rain"})),
            ("list_voices", json!({})),
            ("get_user_subscription", json!({})),
            ("get_models", Value::Null),
        ] {
            let r = tool(&server, name).execute(args).await.unwrap();
            assert!(r.is_error, "{name}");
            assert!(text_of(&r).contains("ELEVENLABS_API_KEY"), "{name}");
        }
    }

    #[tokio::test]
    async fn presets_and_clear_cache_work_offline() {
        let tmp = tempfile::tempdir().unwrap();
        let server = offline_server(tmp.path());
        let r = tool(&server, "list_presets")
            .execute(json!({}))
            .await
            .unwrap();
        assert!(!r.is_error);
        assert!(text_of(&r).contains("\"count\": 10"));

        storage::save_audio(tmp.path(), storage::SFX_PREFIX, "mp3", b"abc")
            .await
            .unwrap();
        let t = tool(&server, "clear_cache");
        let r = t.execute(json!({"dry_run": true})).await.unwrap();
        assert!(text_of(&r).contains("Would remove 1"), "{}", text_of(&r));
        let r = t.execute(json!({})).await.unwrap();
        assert!(!r.is_error);
        assert!(text_of(&r).contains("Removed 1"), "{}", text_of(&r));
        assert!(t.execute(json!({"older_than_days": -1})).await.is_err());
    }

    #[tokio::test]
    async fn synthesize_end_to_end_with_mock_api() {
        let api = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("GET"))
            .and(path("/v1/voices"))
            .respond_with(ResponseTemplate::new(200).set_body_json(json!({"voices": [
                {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George - Storyteller", "category": "premade"},
                {"voice_id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda", "category": "premade", "labels": {"accent": "american"}}
            ]})))
            .mount(&api)
            .await;
        Mock::given(method("POST"))
            .and(path("/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb"))
            .respond_with(ResponseTemplate::new(200).set_body_bytes(b"ID3audio".to_vec()))
            .expect(1)
            .mount(&api)
            .await;
        let server = ElevenLabsSpeechServer::new(config(&api.uri(), tmp.path(), Some("sk_k")));

        let r = tool(&server, "synthesize_speech")
            .execute(json!({"text": "[excited] It works!"}))
            .await
            .unwrap();
        assert!(!r.is_error, "{}", text_of(&r));
        let v: Value = serde_json::from_str(&text_of(&r)).unwrap();
        assert_eq!(v["success"], true);
        assert_eq!(v["voice_id"], "JBFqnCBsd6RMkjVDRZzb");
        assert_eq!(v["file_size_bytes"], 8);
        assert!(std::path::Path::new(v["local_path"].as_str().unwrap()).exists());

        let r = tool(&server, "list_voices")
            .execute(json!({"search": "AMERICAN"}))
            .await
            .unwrap();
        let v: Value = serde_json::from_str(&text_of(&r)).unwrap();
        assert_eq!(v["count"], 1);
        assert_eq!(v["total_available"], 2);
        assert_eq!(v["voices"][0]["name"], "Matilda");

        // Unknown voice name -> invalid params listing available voices.
        let err = tool(&server, "synthesize_speech")
            .execute(json!({"text": "hi", "voice_id": "Nobody"}))
            .await
            .unwrap_err();
        assert!(err.to_string().contains("Matilda"));
    }

    #[tokio::test]
    async fn upstream_error_is_is_error_result() {
        let api = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("POST"))
            .and(path("/v1/sound-generation"))
            .respond_with(ResponseTemplate::new(429).set_body_json(
                json!({"detail": {"status": "too_many_concurrent_requests", "message": "slow down"}}),
            ))
            .mount(&api)
            .await;
        let server = ElevenLabsSpeechServer::new(config(&api.uri(), tmp.path(), Some("sk_k")));
        let r = tool(&server, "generate_sound_effect")
            .execute(json!({"prompt": "rain"}))
            .await
            .unwrap();
        assert!(r.is_error);
        let v: Value = serde_json::from_str(&text_of(&r)).unwrap();
        assert_eq!(v["success"], false);
        assert!(v["error"].as_str().unwrap().contains("429"));
        assert!(v["error"].as_str().unwrap().contains("slow down"));
    }

    #[tokio::test]
    async fn subscription_output_shape() {
        let api = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("GET"))
            .and(path("/v1/user"))
            .respond_with(ResponseTemplate::new(200).set_body_json(json!({
                "subscription": {"tier": "pro", "character_count": 250, "character_limit": 1000,
                                 "next_character_count_reset_unix": 1_800_000_000}
            })))
            .mount(&api)
            .await;
        let server = ElevenLabsSpeechServer::new(config(&api.uri(), tmp.path(), Some("sk_k")));
        let r = tool(&server, "get_user_subscription")
            .execute(json!({}))
            .await
            .unwrap();
        let v: Value = serde_json::from_str(&text_of(&r)).unwrap();
        assert_eq!(v["character_count"], 250);
        assert_eq!(v["characters_remaining"], 750);
        assert_eq!(v["subscription"]["tier"], "pro");
        assert!(v["next_reset"].as_str().unwrap().starts_with("2027"));
    }
}

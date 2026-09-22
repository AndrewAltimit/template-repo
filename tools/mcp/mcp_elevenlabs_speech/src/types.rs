//! Domain types for the ElevenLabs Speech MCP server: models, output formats,
//! voice settings/presets, API response shapes, and input validation helpers.
//!
//! Everything in this module is pure (no I/O) so it can be unit tested
//! offline.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ============================================================================
// Models
// ============================================================================

/// Static information about a known ElevenLabs text-to-speech model.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct KnownModel {
    /// API model identifier (e.g. `eleven_v3`).
    pub id: &'static str,
    /// Maximum characters accepted in a single request.
    pub max_chars: usize,
    /// Short human description.
    pub description: &'static str,
    /// Whether the model supports inline audio tags such as `[laughs]`.
    pub supports_audio_tags: bool,
    /// Replacement model when ElevenLabs has deprecated this one.
    pub deprecated_by: Option<&'static str>,
}

/// Text-to-speech models known to this server (per the ElevenLabs model
/// documentation, 2026). Unknown but well-formed model IDs are still passed
/// through to the API so newly released models work without a code change.
pub const KNOWN_MODELS: &[KnownModel] = &[
    KnownModel {
        id: "eleven_v3",
        max_chars: 5_000,
        description: "Most expressive, 70+ languages, supports audio tags",
        supports_audio_tags: true,
        deprecated_by: None,
    },
    KnownModel {
        id: "eleven_multilingual_v2",
        max_chars: 10_000,
        description: "Stable long-form quality, 29 languages",
        supports_audio_tags: false,
        deprecated_by: None,
    },
    KnownModel {
        id: "eleven_flash_v2_5",
        max_chars: 40_000,
        description: "Ultra low latency (~75ms), 32 languages",
        supports_audio_tags: false,
        deprecated_by: None,
    },
    KnownModel {
        id: "eleven_flash_v2",
        max_chars: 30_000,
        description: "Ultra low latency, English only",
        supports_audio_tags: false,
        deprecated_by: None,
    },
    KnownModel {
        id: "eleven_turbo_v2_5",
        max_chars: 40_000,
        description: "Deprecated low-latency model, 32 languages",
        supports_audio_tags: false,
        deprecated_by: Some("eleven_flash_v2_5"),
    },
    KnownModel {
        id: "eleven_turbo_v2",
        max_chars: 30_000,
        description: "Deprecated low-latency model, English only",
        supports_audio_tags: false,
        deprecated_by: Some("eleven_flash_v2"),
    },
];

/// Look up a known model by ID.
pub fn known_model(id: &str) -> Option<&'static KnownModel> {
    KNOWN_MODELS.iter().find(|m| m.id == id)
}

/// Validate a model ID. Known IDs are always accepted; unknown IDs must be a
/// plausible identifier (`[a-z0-9_]`, <= 64 chars) and are forwarded to the
/// API, which returns an authoritative error if the model does not exist.
pub fn validate_model_id(id: &str) -> Result<(), String> {
    if known_model(id).is_some() {
        return Ok(());
    }
    let ok = !id.is_empty()
        && id.len() <= 64
        && id
            .chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_');
    if ok {
        Ok(())
    } else {
        Err(format!(
            "Invalid model '{}'. Known models: {}",
            id,
            KNOWN_MODELS
                .iter()
                .map(|m| m.id)
                .collect::<Vec<_>>()
                .join(", ")
        ))
    }
}

// ============================================================================
// Output formats
// ============================================================================

/// Output formats accepted by the ElevenLabs `output_format` query parameter.
///
/// Some formats (192kbps MP3, 44.1kHz+ PCM/WAV) require a paid tier; the API
/// reports that as an error which is surfaced verbatim.
pub const OUTPUT_FORMATS: &[&str] = &[
    "mp3_22050_32",
    "mp3_24000_48",
    "mp3_44100_32",
    "mp3_44100_64",
    "mp3_44100_96",
    "mp3_44100_128",
    "mp3_44100_192",
    "opus_48000_32",
    "opus_48000_64",
    "opus_48000_96",
    "opus_48000_128",
    "opus_48000_192",
    "pcm_8000",
    "pcm_16000",
    "pcm_22050",
    "pcm_24000",
    "pcm_32000",
    "pcm_44100",
    "pcm_48000",
    "wav_8000",
    "wav_16000",
    "wav_22050",
    "wav_24000",
    "wav_32000",
    "wav_44100",
    "wav_48000",
    "ulaw_8000",
    "alaw_8000",
];

/// Default output format.
pub const DEFAULT_OUTPUT_FORMAT: &str = "mp3_44100_128";

/// A validated output format string.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct OutputFormat(&'static str);

impl OutputFormat {
    /// Parse a format name, returning a descriptive error for unknown formats.
    pub fn parse(s: &str) -> Result<Self, String> {
        OUTPUT_FORMATS
            .iter()
            .find(|f| **f == s)
            .map(|f| OutputFormat(f))
            .ok_or_else(|| {
                format!(
                    "Invalid output_format '{}'. Supported: {}",
                    s,
                    OUTPUT_FORMATS.join(", ")
                )
            })
    }

    /// The API identifier.
    pub fn as_str(&self) -> &'static str {
        self.0
    }

    /// File extension for audio written in this format. `pcm`, `ulaw` and
    /// `alaw` are headerless raw streams; use a `wav_*` format for a file that
    /// plays directly in common players.
    pub fn extension(&self) -> &'static str {
        match self.0.split('_').next().unwrap_or("") {
            "mp3" => "mp3",
            "opus" => "opus",
            "wav" => "wav",
            "ulaw" => "ulaw",
            "alaw" => "alaw",
            _ => "pcm",
        }
    }
}

impl Default for OutputFormat {
    fn default() -> Self {
        OutputFormat(DEFAULT_OUTPUT_FORMAT)
    }
}

// ============================================================================
// Voice settings and presets
// ============================================================================

/// Voice settings sent with a synthesis request.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct VoiceSettings {
    /// Stability (0.0-1.0): higher = more consistent, lower = more expressive.
    pub stability: f32,
    /// Similarity boost (0.0-1.0): higher = closer to the original voice.
    pub similarity_boost: f32,
    /// Style exaggeration (0.0-1.0): higher = more dramatic, adds latency.
    pub style: f32,
    /// Speaker boost: increases similarity at a small latency cost.
    pub use_speaker_boost: bool,
    /// Speaking speed (0.7-1.2, 1.0 = normal). Omitted from the request when
    /// unset so the voice's own default applies.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed: Option<f32>,
}

impl Default for VoiceSettings {
    fn default() -> Self {
        Self {
            stability: 0.5,
            similarity_boost: 0.75,
            style: 0.0,
            use_speaker_boost: false,
            speed: None,
        }
    }
}

/// Allowed range for `speed`.
pub const SPEED_RANGE: (f32, f32) = (0.7, 1.2);

/// Optional per-request overrides applied on top of a preset/defaults.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct VoiceSettingsOverrides {
    pub stability: Option<f32>,
    pub similarity_boost: Option<f32>,
    pub style: Option<f32>,
    pub use_speaker_boost: Option<bool>,
    pub speed: Option<f32>,
}

fn check_unit(name: &str, v: f32) -> Result<(), String> {
    if v.is_finite() && (0.0..=1.0).contains(&v) {
        Ok(())
    } else {
        Err(format!("'{name}' must be between 0.0 and 1.0 (got {v})"))
    }
}

impl VoiceSettings {
    /// Apply explicit overrides on top of these settings, validating ranges.
    pub fn with_overrides(mut self, o: VoiceSettingsOverrides) -> Result<Self, String> {
        if let Some(v) = o.stability {
            check_unit("stability", v)?;
            self.stability = v;
        }
        if let Some(v) = o.similarity_boost {
            check_unit("similarity_boost", v)?;
            self.similarity_boost = v;
        }
        if let Some(v) = o.style {
            check_unit("style", v)?;
            self.style = v;
        }
        if let Some(v) = o.use_speaker_boost {
            self.use_speaker_boost = v;
        }
        if let Some(v) = o.speed {
            if !(v.is_finite() && (SPEED_RANGE.0..=SPEED_RANGE.1).contains(&v)) {
                return Err(format!(
                    "'speed' must be between {} and {} (got {v})",
                    SPEED_RANGE.0, SPEED_RANGE.1
                ));
            }
            self.speed = Some(v);
        }
        Ok(self)
    }

    /// `eleven_v3` only accepts the discrete stability values 0.0 (Creative),
    /// 0.5 (Natural) and 1.0 (Robust). Snap to the nearest one and return the
    /// original value when an adjustment was made.
    pub fn snap_stability_for_v3(&mut self) -> Option<f32> {
        let snapped = [0.0_f32, 0.5, 1.0]
            .into_iter()
            .min_by(|a, b| {
                (a - self.stability)
                    .abs()
                    .total_cmp(&(b - self.stability).abs())
            })
            .unwrap_or(0.5);
        if (snapped - self.stability).abs() > f32::EPSILON {
            let original = self.stability;
            self.stability = snapped;
            Some(original)
        } else {
            None
        }
    }
}

const fn preset(stability: f32, similarity_boost: f32, style: f32, boost: bool) -> VoiceSettings {
    VoiceSettings {
        stability,
        similarity_boost,
        style,
        use_speaker_boost: boost,
        speed: None,
    }
}

/// Named voice presets: `(name, settings, use case)`.
pub const VOICE_PRESETS: &[(&str, VoiceSettings, &str)] = &[
    (
        "audiobook",
        preset(0.75, 0.75, 0.0, false),
        "Long-form narration",
    ),
    (
        "character_performance",
        preset(0.3, 0.8, 0.6, true),
        "Expressive characters",
    ),
    (
        "news_reading",
        preset(0.9, 0.7, 0.0, false),
        "Professional delivery",
    ),
    (
        "emotional_dialogue",
        preset(0.5, 0.85, 0.3, true),
        "Dramatic conversations",
    ),
    (
        "github_review",
        preset(0.6, 0.8, 0.2, false),
        "Code review narration",
    ),
    (
        "tutorial_narration",
        preset(0.7, 0.75, 0.1, false),
        "Educational content",
    ),
    (
        "podcast",
        preset(0.5, 0.8, 0.4, true),
        "Conversational content",
    ),
    (
        "meditation",
        preset(0.85, 0.7, 0.0, false),
        "Calm, steady delivery",
    ),
    (
        "storytelling",
        preset(0.4, 0.75, 0.5, true),
        "Narrative content",
    ),
    (
        "customer_service",
        preset(0.8, 0.75, 0.0, false),
        "Professional, neutral",
    ),
];

/// Get voice settings for a preset name (case-insensitive).
pub fn get_preset(name: &str) -> Option<VoiceSettings> {
    VOICE_PRESETS
        .iter()
        .find(|(n, _, _)| n.eq_ignore_ascii_case(name))
        .map(|(_, s, _)| *s)
}

/// Comma-separated preset names, for error messages.
pub fn preset_names() -> String {
    VOICE_PRESETS
        .iter()
        .map(|(n, _, _)| *n)
        .collect::<Vec<_>>()
        .join(", ")
}

// ============================================================================
// Voices
// ============================================================================

/// Built-in name -> voice ID aliases, used only when a name cannot be found
/// in the account's own voice list (e.g. the list request failed).
///
/// Note: ElevenLabs retired the "legacy" voices (Rachel, Emily, ...) and
/// silently remaps their IDs; all premade "Default" voices expire on
/// 2026-12-31. Prefer passing an explicit voice ID or a name from
/// `list_voices`.
pub const VOICE_ALIASES: &[(&str, &str)] = &[
    ("rachel", "21m00Tcm4TlvDq8ikWAM"),
    ("george", "JBFqnCBsd6RMkjVDRZzb"),
    ("sarah", "EXAVITQu4vr4xnSDxMaL"),
    ("charlie", "IKne3meq5aSn9XLyUdCD"),
    ("emily", "LcfcDJNUP1GQjkzn1xUU"),
];

/// Look up a built-in alias (case-insensitive).
pub fn alias_voice_id(name: &str) -> Option<&'static str> {
    VOICE_ALIASES
        .iter()
        .find(|(n, _)| n.eq_ignore_ascii_case(name.trim()))
        .map(|(_, id)| *id)
}

/// True when `s` looks like an ElevenLabs voice ID (ASCII alphanumeric,
/// 20+ characters). Such values are used verbatim without a name lookup.
pub fn looks_like_voice_id(s: &str) -> bool {
    s.len() >= 20 && s.len() <= 64 && s.chars().all(|c| c.is_ascii_alphanumeric())
}

/// Validate a string before it is interpolated into a URL path segment.
/// Rejects anything but ASCII alphanumerics so a crafted "voice id" such as
/// `../../user` cannot redirect the request to another API endpoint.
pub fn validate_path_id(s: &str) -> Result<(), String> {
    if !s.is_empty() && s.len() <= 64 && s.chars().all(|c| c.is_ascii_alphanumeric()) {
        Ok(())
    } else {
        Err(format!(
            "Invalid voice ID '{s}': must be 1-64 ASCII letters/digits"
        ))
    }
}

/// Voice information returned by `GET /v1/voices`.
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

impl Voice {
    /// The short name, e.g. `George` for `George - Warm, Captivating Storyteller`.
    pub fn short_name(&self) -> &str {
        self.name.split(" - ").next().unwrap_or(&self.name).trim()
    }

    /// Whether this voice's full or short name equals `query` (case-insensitive).
    pub fn name_matches(&self, query: &str) -> bool {
        let q = query.trim();
        self.name.trim().eq_ignore_ascii_case(q) || self.short_name().eq_ignore_ascii_case(q)
    }

    /// Case-insensitive substring match on name, description and label values.
    pub fn search_matches(&self, needle_lower: &str) -> bool {
        self.name.to_lowercase().contains(needle_lower)
            || self
                .description
                .as_deref()
                .is_some_and(|d| d.to_lowercase().contains(needle_lower))
            || self
                .labels
                .values()
                .any(|v| v.to_lowercase().contains(needle_lower))
    }
}

/// Find a voice by name in a voice list.
pub fn find_voice_by_name<'a>(voices: &'a [Voice], name: &str) -> Option<&'a Voice> {
    voices.iter().find(|v| v.name_matches(name))
}

/// Voices list response from the API.
#[derive(Debug, Deserialize)]
pub struct VoicesResponse {
    pub voices: Vec<Voice>,
}

// ============================================================================
// Account / models responses
// ============================================================================

/// `GET /v1/user` response (only the fields this server uses).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserInfo {
    pub subscription: SubscriptionInfo,
}

/// Subscription details.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SubscriptionInfo {
    #[serde(default)]
    pub tier: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
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
    pub voice_limit: Option<i64>,
    #[serde(default)]
    pub professional_voice_limit: Option<i64>,
}

impl SubscriptionInfo {
    /// Characters left in the current period, when both counts are known.
    pub fn characters_remaining(&self) -> Option<i64> {
        match (self.character_limit, self.character_count) {
            (Some(limit), Some(count)) => Some((limit - count).max(0)),
            _ => None,
        }
    }
}

/// Model info from `GET /v1/models`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub model_id: String,
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub can_do_text_to_speech: Option<bool>,
    #[serde(default)]
    pub can_do_voice_conversion: Option<bool>,
    #[serde(default)]
    pub can_use_style: Option<bool>,
    #[serde(default)]
    pub can_use_speaker_boost: Option<bool>,
    #[serde(default)]
    pub maximum_text_length_per_request: Option<i64>,
    #[serde(default)]
    pub languages: Option<Vec<LanguageInfo>>,
}

/// Language info.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LanguageInfo {
    pub language_id: String,
    pub name: String,
}

// ============================================================================
// Results
// ============================================================================

/// Result of a successful audio generation.
#[derive(Debug, Clone, Serialize)]
pub struct AudioResult {
    pub success: bool,
    /// Absolute path of the saved audio file.
    pub local_path: String,
    pub output_format: String,
    pub file_size_bytes: u64,
    pub character_count: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_used: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voice_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_seconds: Option<f32>,
    /// ElevenLabs request ID (useful for request stitching and support).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    /// Non-fatal adjustments made to the request.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub warnings: Vec<String>,
}

/// Validate the `apply_text_normalization` value.
pub fn validate_text_normalization(v: &str) -> Result<(), String> {
    match v {
        "auto" | "on" | "off" => Ok(()),
        other => Err(format!(
            "Invalid apply_text_normalization '{other}': expected auto, on or off"
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn model_validation() {
        assert!(validate_model_id("eleven_v3").is_ok());
        assert!(validate_model_id("eleven_v4_future").is_ok());
        assert!(validate_model_id("").is_err());
        assert!(validate_model_id("../x").is_err());
        assert!(validate_model_id("Eleven V3").is_err());
        assert_eq!(known_model("eleven_v3").map(|m| m.max_chars), Some(5_000));
        assert_eq!(
            known_model("eleven_turbo_v2_5").and_then(|m| m.deprecated_by),
            Some("eleven_flash_v2_5")
        );
    }

    #[test]
    fn output_format_parse_and_extension() {
        assert_eq!(OutputFormat::default().as_str(), "mp3_44100_128");
        assert_eq!(
            OutputFormat::parse("mp3_44100_192").unwrap().extension(),
            "mp3"
        );
        assert_eq!(OutputFormat::parse("wav_44100").unwrap().extension(), "wav");
        assert_eq!(OutputFormat::parse("pcm_24000").unwrap().extension(), "pcm");
        assert_eq!(
            OutputFormat::parse("opus_48000_64").unwrap().extension(),
            "opus"
        );
        assert_eq!(
            OutputFormat::parse("ulaw_8000").unwrap().extension(),
            "ulaw"
        );
        let err = OutputFormat::parse("flac").unwrap_err();
        assert!(err.contains("Supported"));
    }

    #[test]
    fn overrides_apply_and_validate() {
        let base = get_preset("audiobook").unwrap();
        let s = base
            .with_overrides(VoiceSettingsOverrides {
                style: Some(0.4),
                speed: Some(1.1),
                ..Default::default()
            })
            .unwrap();
        assert_eq!(s.stability, 0.75);
        assert_eq!(s.style, 0.4);
        assert_eq!(s.speed, Some(1.1));

        for bad in [
            VoiceSettingsOverrides {
                stability: Some(1.5),
                ..Default::default()
            },
            VoiceSettingsOverrides {
                style: Some(-0.1),
                ..Default::default()
            },
            VoiceSettingsOverrides {
                similarity_boost: Some(f32::NAN),
                ..Default::default()
            },
            VoiceSettingsOverrides {
                speed: Some(2.0),
                ..Default::default()
            },
        ] {
            assert!(VoiceSettings::default().with_overrides(bad).is_err());
        }
    }

    #[test]
    fn v3_stability_snapping() {
        let mut s = VoiceSettings {
            stability: 0.75,
            ..Default::default()
        };
        // 0.75 is equidistant; either neighbour is acceptable but it must snap.
        assert_eq!(s.snap_stability_for_v3(), Some(0.75));
        assert!(s.stability == 0.5 || s.stability == 1.0);

        let mut s = VoiceSettings {
            stability: 0.3,
            ..Default::default()
        };
        assert_eq!(s.snap_stability_for_v3(), Some(0.3));
        assert_eq!(s.stability, 0.5);

        let mut s = VoiceSettings {
            stability: 1.0,
            ..Default::default()
        };
        assert_eq!(s.snap_stability_for_v3(), None);
    }

    #[test]
    fn presets_case_insensitive_and_complete() {
        assert_eq!(VOICE_PRESETS.len(), 10);
        assert!(get_preset("PODCAST").is_some());
        assert!(get_preset("nope").is_none());
        for (_, s, _) in VOICE_PRESETS {
            assert!(
                VoiceSettings::default()
                    .with_overrides(VoiceSettingsOverrides {
                        stability: Some(s.stability),
                        similarity_boost: Some(s.similarity_boost),
                        style: Some(s.style),
                        ..Default::default()
                    })
                    .is_ok()
            );
        }
    }

    #[test]
    fn voice_id_heuristics() {
        assert!(looks_like_voice_id("21m00Tcm4TlvDq8ikWAM"));
        assert!(!looks_like_voice_id("rachel"));
        assert!(!looks_like_voice_id("George - Warm Storyteller"));
        assert!(validate_path_id("21m00Tcm4TlvDq8ikWAM").is_ok());
        assert!(validate_path_id("../../user").is_err());
        assert!(validate_path_id("abc?x=1").is_err());
        assert!(validate_path_id("").is_err());
        assert_eq!(alias_voice_id(" Rachel "), Some("21m00Tcm4TlvDq8ikWAM"));
    }

    #[test]
    fn voice_name_matching() {
        let v = Voice {
            voice_id: "JBFqnCBsd6RMkjVDRZzb".into(),
            name: "George - Warm, Captivating Storyteller".into(),
            category: Some("premade".into()),
            labels: HashMap::from([("accent".into(), "british".into())]),
            preview_url: None,
            description: None,
        };
        assert_eq!(v.short_name(), "George");
        assert!(v.name_matches("george"));
        assert!(v.name_matches("George - Warm, Captivating Storyteller"));
        assert!(!v.name_matches("geo"));
        assert!(v.search_matches("british"));
        assert!(v.search_matches("storyteller"));
        assert!(!v.search_matches("french"));
        let list = vec![v];
        assert!(find_voice_by_name(&list, "GEORGE").is_some());
    }

    #[test]
    fn subscription_remaining() {
        let s = SubscriptionInfo {
            character_count: Some(300),
            character_limit: Some(1000),
            ..Default::default()
        };
        assert_eq!(s.characters_remaining(), Some(700));
        assert_eq!(SubscriptionInfo::default().characters_remaining(), None);
    }

    #[test]
    fn text_normalization_values() {
        assert!(validate_text_normalization("auto").is_ok());
        assert!(validate_text_normalization("off").is_ok());
        assert!(validate_text_normalization("yes").is_err());
    }
}

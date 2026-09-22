//! Type definitions for the video editor MCP server: tool arguments, analysis
//! results and edit decision lists.
//!
//! All tool arguments are deserialized into these typed structs. A malformed
//! argument produces an `InvalidParameters` error naming the offending field
//! instead of silently falling back to defaults.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::ffmpeg::MediaInfo;

fn default_true() -> bool {
    true
}

// ============================================================================
// Analysis
// ============================================================================

/// Video analysis options. Every analysis is enabled by default.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisOptions {
    /// Run Whisper speech-to-text.
    #[serde(default = "default_true")]
    pub transcribe: bool,
    /// Identify speakers (energy-based, requires one time-synced video per speaker).
    #[serde(default = "default_true")]
    pub identify_speakers: bool,
    /// Detect scene changes.
    #[serde(default = "default_true")]
    pub detect_scenes: bool,
    /// Derive highlight moments from audio peaks and transcript keywords.
    #[serde(default = "default_true")]
    pub extract_highlights: bool,
    /// Scene-change sensitivity in (0, 1]; lower detects more cuts.
    #[serde(default = "default_scene_threshold")]
    pub scene_threshold: f64,
    /// Transcription language hint (ISO code such as `en`); auto-detect if absent.
    #[serde(default)]
    pub language: Option<String>,
}

fn default_scene_threshold() -> f64 {
    0.3
}

impl Default for AnalysisOptions {
    fn default() -> Self {
        Self {
            transcribe: true,
            identify_speakers: true,
            detect_scenes: true,
            extract_highlights: true,
            scene_threshold: default_scene_threshold(),
            language: None,
        }
    }
}

/// Result of analysing one video.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoAnalysis {
    pub file: String,
    pub file_size: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub video_info: Option<MediaInfo>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transcript: Option<Transcript>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speakers: Option<Vec<Speaker>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub segments_with_speakers: Option<Vec<TranscriptSegmentWithSpeaker>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub audio_analysis: Option<AudioAnalysis>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scene_changes: Option<Vec<f64>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub highlights: Option<Vec<Highlight>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggested_edits: Option<Vec<EditSuggestion>>,
    /// Non-fatal problems (e.g. transcription unavailable).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub warnings: Vec<String>,
}

impl VideoAnalysis {
    /// An empty analysis for `file`.
    pub fn new(file: &str, file_size: u64) -> Self {
        Self {
            file: file.to_string(),
            file_size,
            video_info: None,
            transcript: None,
            speakers: None,
            segments_with_speakers: None,
            audio_analysis: None,
            scene_changes: None,
            highlights: None,
            suggested_edits: None,
            warnings: Vec::new(),
        }
    }
}

/// Transcript from speech recognition.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transcript {
    pub text: String,
    pub language: String,
    pub segments: Vec<TranscriptSegment>,
}

/// A segment of the transcript.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptSegment {
    pub id: u32,
    pub start: f64,
    pub end: f64,
    pub text: String,
    #[serde(default)]
    pub words: Vec<Word>,
}

/// Word-level timestamp.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Word {
    pub word: String,
    pub start: f64,
    pub end: f64,
    #[serde(default = "default_probability")]
    pub probability: f64,
}

fn default_probability() -> f64 {
    1.0
}

/// Transcript segment annotated with the active speaker.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptSegmentWithSpeaker {
    pub id: u32,
    pub start: f64,
    pub end: f64,
    pub text: String,
    pub speaker: Option<String>,
}

/// Speaker summary.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Speaker {
    pub id: String,
    pub total_speaking_time: f64,
    pub segment_count: u32,
    pub segments: Vec<(f64, f64)>,
    /// Video the speaker was detected on (energy-based detection only).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
}

/// A contiguous interval where one speaker is active.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SpeakerTurn {
    pub speaker: String,
    pub start: f64,
    pub end: f64,
}

/// Audio analysis results.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioAnalysis {
    pub duration: f64,
    pub sample_rate: u32,
    /// Silent intervals `[start, end]` at least `silence_threshold` long.
    pub silence_segments: Vec<(f64, f64)>,
    /// Downsampled loudness curve (at most a few hundred points).
    pub volume_profile: Vec<VolumePoint>,
    /// Times of the loudest local peaks.
    pub peak_moments: Vec<f64>,
    /// Mean loudness in dBFS.
    #[serde(default)]
    pub mean_db: f64,
    /// Peak window loudness in dBFS.
    #[serde(default)]
    pub max_db: f64,
}

/// A point in the volume profile.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumePoint {
    pub time: f64,
    /// Linear RMS amplitude in [0, 1].
    pub rms: f64,
    /// RMS in dBFS.
    pub db: f64,
}

/// A highlight in the video.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Highlight {
    pub time: f64,
    #[serde(rename = "type")]
    pub highlight_type: String,
    #[serde(default)]
    pub confidence: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub keyword: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
}

/// An edit suggestion.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EditSuggestion {
    #[serde(rename = "type")]
    pub suggestion_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub end: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub time: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub effect: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transition: Option<String>,
    pub reason: String,
}

// ============================================================================
// Editing
// ============================================================================

/// Editing rules as supplied by the caller; unset fields fall back to the
/// server's configured defaults (see [`EditingRules`]).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EditingRulesInput {
    pub switch_on_speaker: Option<bool>,
    pub speaker_switch_delay: Option<f64>,
    pub picture_in_picture: Option<String>,
    pub zoom_on_emphasis: Option<bool>,
    pub remove_silence: Option<bool>,
    pub silence_threshold: Option<f64>,
    pub pip_size: Option<f64>,
    pub transition_duration: Option<f64>,
    pub transition_type: Option<String>,
}

/// Picture-in-picture mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PipMode {
    /// Currently equivalent to `never`; reserved for smarter heuristics.
    Auto,
    Always,
    Never,
}

impl PipMode {
    /// Parse a PiP mode string (lenient: on/off/true/false accepted).
    pub fn parse(s: &str) -> Result<Self, String> {
        match s.trim().to_ascii_lowercase().as_str() {
            "auto" | "" => Ok(Self::Auto),
            "always" | "on" | "true" | "yes" => Ok(Self::Always),
            "never" | "off" | "false" | "no" | "none" => Ok(Self::Never),
            other => Err(format!(
                "Invalid picture_in_picture '{other}' (expected auto, always or never)"
            )),
        }
    }
}

/// Fully resolved editing rules.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EditingRules {
    pub switch_on_speaker: bool,
    pub speaker_switch_delay: f64,
    pub picture_in_picture: PipMode,
    pub zoom_on_emphasis: bool,
    pub remove_silence: bool,
    pub silence_threshold: f64,
    pub pip_size: f64,
    pub transition_duration: f64,
    pub transition_type: String,
}

impl Default for EditingRules {
    fn default() -> Self {
        Self {
            switch_on_speaker: true,
            speaker_switch_delay: 0.5,
            picture_in_picture: PipMode::Auto,
            zoom_on_emphasis: true,
            remove_silence: true,
            silence_threshold: 2.0,
            pip_size: 0.25,
            transition_duration: 0.5,
            transition_type: "cross_dissolve".to_string(),
        }
    }
}

/// An edit decision in the EDL.
///
/// `timestamp` is the in-point in `source` (seconds); `duration` is the
/// length taken from that source. Decisions are played back in order.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EditDecision {
    pub timestamp: f64,
    pub duration: f64,
    pub source: String,
    /// `show` (first shot), `transition` (cross-fade from previous), or `cut`.
    #[serde(default = "default_action")]
    pub action: String,
    /// Transition into this decision (`cross_dissolve`, `fade`, `wipeleft`,
    /// ... or `cut`). `None` means a hard cut.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transition_type: Option<String>,
    /// Transition length in seconds (defaults to the server default).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transition_duration: Option<f64>,
    /// Effects applied to this shot. Supported: `zoom_in`.
    #[serde(default)]
    pub effects: Vec<String>,
    /// Picture-in-picture size as a fraction of output width.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pip_size: Option<f64>,
    /// Secondary video shown as picture-in-picture (same timestamp).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pip_source: Option<String>,
}

fn default_action() -> String {
    "show".to_string()
}

impl EditDecision {
    /// A plain shot with no transition or effects.
    pub fn shot(source: &str, timestamp: f64, duration: f64) -> Self {
        Self {
            timestamp,
            duration,
            source: source.to_string(),
            action: "show".to_string(),
            transition_type: None,
            transition_duration: None,
            effects: Vec::new(),
            pip_size: None,
            pip_source: None,
        }
    }
}

/// Output settings for video rendering.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputSettings {
    #[serde(default = "default_format")]
    pub format: String,
    #[serde(default = "default_resolution")]
    pub resolution: String,
    #[serde(default = "default_fps")]
    pub fps: u32,
    #[serde(default = "default_bitrate")]
    pub bitrate: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub codec: Option<String>,
}

fn default_format() -> String {
    "mp4".to_string()
}

fn default_resolution() -> String {
    "1920x1080".to_string()
}

fn default_fps() -> u32 {
    30
}

fn default_bitrate() -> String {
    "8M".to_string()
}

impl Default for OutputSettings {
    fn default() -> Self {
        Self {
            format: default_format(),
            resolution: default_resolution(),
            fps: default_fps(),
            bitrate: default_bitrate(),
            output_path: None,
            codec: None,
        }
    }
}

/// Render options.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenderOptions {
    #[serde(default = "default_true")]
    pub hardware_acceleration: bool,
    #[serde(default)]
    pub preview_mode: bool,
    #[serde(default)]
    pub add_captions: bool,
    #[serde(default)]
    pub add_speaker_labels: bool,
}

impl Default for RenderOptions {
    fn default() -> Self {
        Self {
            hardware_acceleration: true,
            preview_mode: false,
            add_captions: false,
            add_speaker_labels: false,
        }
    }
}

/// Clip extraction criteria.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractionCriteria {
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub speakers: Vec<String>,
    #[serde(default)]
    pub time_ranges: Vec<(f64, f64)>,
    #[serde(default = "default_min_clip")]
    pub min_clip_length: f64,
    #[serde(default = "default_max_clip")]
    pub max_clip_length: f64,
    #[serde(default = "default_padding")]
    pub padding: f64,
}

fn default_min_clip() -> f64 {
    3.0
}

fn default_max_clip() -> f64 {
    60.0
}

fn default_padding() -> f64 {
    0.5
}

impl Default for ExtractionCriteria {
    fn default() -> Self {
        Self {
            keywords: Vec::new(),
            speakers: Vec::new(),
            time_ranges: Vec::new(),
            min_clip_length: default_min_clip(),
            max_clip_length: default_max_clip(),
            padding: default_padding(),
        }
    }
}

/// Caption style settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptionStyle {
    #[serde(default = "default_font")]
    pub font: String,
    /// Font size in output-video pixels.
    #[serde(default = "default_font_size")]
    pub size: u32,
    /// Text colour, `#RRGGBB` or `#RRGGBBAA`.
    #[serde(default = "default_color")]
    pub color: String,
    /// Box colour behind the text, `#RRGGBB[AA]`, or `none` for an outline only.
    #[serde(default = "default_background")]
    pub background: String,
    /// `bottom`, `top` or `middle`.
    #[serde(default = "default_position")]
    pub position: String,
    #[serde(default = "default_max_chars")]
    pub max_chars_per_line: u32,
    /// Prefix captions with speaker names when speaker labels are known.
    #[serde(default = "default_true")]
    pub display_speaker_names: bool,
}

fn default_font() -> String {
    "Arial".to_string()
}

fn default_font_size() -> u32 {
    42
}

fn default_color() -> String {
    "#FFFFFF".to_string()
}

fn default_background() -> String {
    "#000000".to_string()
}

fn default_position() -> String {
    "bottom".to_string()
}

fn default_max_chars() -> u32 {
    40
}

impl Default for CaptionStyle {
    fn default() -> Self {
        Self {
            font: default_font(),
            size: default_font_size(),
            color: default_color(),
            background: default_background(),
            position: default_position(),
            max_chars_per_line: default_max_chars(),
            display_speaker_names: true,
        }
    }
}

/// Extracted clip information.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedClip {
    pub output_path: String,
    pub start_time: f64,
    pub end_time: f64,
    pub duration: f64,
    pub criteria: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub keyword: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speaker: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
}

// ============================================================================
// Tool arguments
// ============================================================================

/// Arguments for `video_editor/analyze`.
#[derive(Debug, Deserialize)]
pub struct AnalyzeArgs {
    pub video_inputs: Vec<String>,
    #[serde(default)]
    pub analysis_options: Option<AnalysisOptions>,
    #[serde(default)]
    pub background: bool,
}

/// Arguments for `video_editor/create_edit`.
#[derive(Debug, Deserialize)]
pub struct CreateEditArgs {
    pub video_inputs: Vec<String>,
    #[serde(default)]
    pub editing_rules: Option<EditingRulesInput>,
    #[serde(default)]
    pub speaker_mapping: Option<HashMap<String, String>>,
    #[serde(default)]
    pub background: bool,
}

/// Arguments for `video_editor/render`.
#[derive(Debug, Deserialize)]
pub struct RenderArgs {
    pub video_inputs: Vec<String>,
    #[serde(default)]
    pub edit_decision_list: Option<Vec<EditDecision>>,
    #[serde(default)]
    pub output_settings: Option<OutputSettings>,
    #[serde(default)]
    pub render_options: Option<RenderOptions>,
    #[serde(default)]
    pub editing_rules: Option<EditingRulesInput>,
    #[serde(default)]
    pub speaker_mapping: Option<HashMap<String, String>>,
    #[serde(default)]
    pub background: bool,
}

/// Arguments for `video_editor/extract_clips`.
#[derive(Debug, Deserialize)]
pub struct ExtractClipsArgs {
    pub video_input: String,
    #[serde(default)]
    pub extraction_criteria: Option<ExtractionCriteria>,
    #[serde(default)]
    pub output_dir: Option<String>,
    #[serde(default)]
    pub stream_copy: bool,
    #[serde(default)]
    pub max_clips: Option<usize>,
    #[serde(default)]
    pub background: bool,
}

/// Arguments for `video_editor/add_captions`.
#[derive(Debug, Deserialize)]
pub struct AddCaptionsArgs {
    pub video_input: String,
    #[serde(default)]
    pub caption_style: Option<CaptionStyle>,
    #[serde(default)]
    pub languages: Option<Vec<String>>,
    #[serde(default)]
    pub output_path: Option<String>,
    #[serde(default = "default_true")]
    pub burn_in: bool,
    #[serde(default)]
    pub background: bool,
}

/// Arguments for tools that take a single job id.
#[derive(Debug, Deserialize)]
pub struct JobIdArgs {
    pub job_id: String,
}

/// Arguments for `video_editor/list_jobs`.
#[derive(Debug, Default, Deserialize)]
pub struct ListJobsArgs {
    #[serde(default)]
    pub status: Option<String>,
}

/// Arguments for `video_editor/get_video_info`.
#[derive(Debug, Deserialize)]
pub struct VideoInfoArgs {
    pub video_input: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn analysis_options_defaults_agree() {
        let from_default = AnalysisOptions::default();
        let from_serde: AnalysisOptions = serde_json::from_str("{}").unwrap();
        for o in [from_default, from_serde] {
            assert!(o.transcribe && o.identify_speakers && o.detect_scenes && o.extract_highlights);
            assert_eq!(o.scene_threshold, 0.3);
        }
    }

    #[test]
    fn analysis_options_partial() {
        let o: AnalysisOptions = serde_json::from_str(r#"{"transcribe": false}"#).unwrap();
        assert!(!o.transcribe);
        assert!(o.detect_scenes);
    }

    #[test]
    fn analysis_options_wrong_type_is_error() {
        assert!(serde_json::from_str::<AnalysisOptions>(r#"{"transcribe": "yes"}"#).is_err());
    }

    #[test]
    fn extraction_criteria_defaults_agree() {
        let d = ExtractionCriteria::default();
        let s: ExtractionCriteria = serde_json::from_str("{}").unwrap();
        for c in [d, s] {
            assert_eq!(c.min_clip_length, 3.0);
            assert_eq!(c.max_clip_length, 60.0);
            assert_eq!(c.padding, 0.5);
            assert!(c.keywords.is_empty() && c.speakers.is_empty() && c.time_ranges.is_empty());
        }
    }

    #[test]
    fn extraction_criteria_time_ranges() {
        let c: ExtractionCriteria =
            serde_json::from_str(r#"{"time_ranges": [[1.0, 5.5], [10, 20]]}"#).unwrap();
        assert_eq!(c.time_ranges, vec![(1.0, 5.5), (10.0, 20.0)]);
        assert!(serde_json::from_str::<ExtractionCriteria>(r#"{"time_ranges": [[1.0]]}"#).is_err());
    }

    #[test]
    fn edit_decision_roundtrip_and_legacy_shape() {
        let d = EditDecision {
            timestamp: 10.5,
            duration: 5.0,
            source: "/v.mp4".into(),
            action: "transition".into(),
            transition_type: Some("cross_dissolve".into()),
            transition_duration: None,
            effects: vec!["zoom_in".into()],
            pip_size: Some(0.25),
            pip_source: None,
        };
        let json = serde_json::to_string(&d).unwrap();
        assert_eq!(serde_json::from_str::<EditDecision>(&json).unwrap(), d);
        // Minimal legacy decision (as produced by older versions) still parses.
        let legacy: EditDecision = serde_json::from_str(
            r#"{"timestamp":0,"duration":2,"source":"a.mp4","action":"show"}"#,
        )
        .unwrap();
        assert!(legacy.effects.is_empty());
        assert!(legacy.pip_source.is_none());
    }

    #[test]
    fn output_settings_defaults() {
        let s: OutputSettings = serde_json::from_str("{}").unwrap();
        assert_eq!(s.format, "mp4");
        assert_eq!(s.resolution, "1920x1080");
        assert_eq!(s.fps, 30);
        assert_eq!(s.bitrate, "8M");
        assert!(s.output_path.is_none() && s.codec.is_none());
    }

    #[test]
    fn render_options_defaults() {
        let o: RenderOptions = serde_json::from_str("{}").unwrap();
        assert!(o.hardware_acceleration && !o.preview_mode && !o.add_captions);
    }

    #[test]
    fn caption_style_defaults_agree() {
        let d = CaptionStyle::default();
        let s: CaptionStyle = serde_json::from_str("{}").unwrap();
        assert_eq!(d.font, s.font);
        assert_eq!(d.size, 42);
        assert_eq!(s.max_chars_per_line, 40);
    }

    #[test]
    fn pip_mode_parsing() {
        assert_eq!(PipMode::parse("auto").unwrap(), PipMode::Auto);
        assert_eq!(PipMode::parse("ON").unwrap(), PipMode::Always);
        assert_eq!(PipMode::parse("never").unwrap(), PipMode::Never);
        assert!(PipMode::parse("sometimes").is_err());
    }

    #[test]
    fn add_captions_args_burn_in_default() {
        let a: AddCaptionsArgs = serde_json::from_str(r#"{"video_input":"a.mp4"}"#).unwrap();
        assert!(a.burn_in);
        assert!(!a.background);
    }
}

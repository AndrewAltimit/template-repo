//! Type definitions for video editor MCP server.

use serde::{Deserialize, Serialize};

/// Video analysis options
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AnalysisOptions {
    #[serde(default = "default_true")]
    pub transcribe: bool,
    #[serde(default = "default_true")]
    pub identify_speakers: bool,
    #[serde(default = "default_true")]
    pub detect_scenes: bool,
    #[serde(default = "default_true")]
    pub extract_highlights: bool,
}

fn default_true() -> bool {
    true
}

/// Result of video analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoAnalysis {
    pub file: String,
    pub file_size: u64,
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
}

/// Transcript from speech recognition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transcript {
    pub text: String,
    pub language: String,
    pub segments: Vec<TranscriptSegment>,
}

/// A segment of the transcript
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptSegment {
    pub id: u32,
    pub start: f64,
    pub end: f64,
    pub text: String,
    #[serde(default)]
    pub words: Vec<Word>,
}

/// Word-level timestamp
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

/// Transcript segment with speaker identification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptSegmentWithSpeaker {
    pub id: u32,
    pub start: f64,
    pub end: f64,
    pub text: String,
    pub speaker: Option<String>,
}

/// Speaker information from diarization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Speaker {
    pub id: String,
    pub total_speaking_time: f64,
    pub segment_count: u32,
    pub segments: Vec<(f64, f64)>,
}

/// Audio analysis results
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioAnalysis {
    pub duration: f64,
    pub sample_rate: u32,
    pub silence_segments: Vec<(f64, f64)>,
    pub volume_profile: Vec<VolumePoint>,
    pub peak_moments: Vec<f64>,
}

/// A point in the volume profile
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumePoint {
    pub time: f64,
    pub rms: f64,
    pub db: f64,
}

/// A highlight in the video
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

/// An edit suggestion
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

/// Editing rules for video composition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EditingRules {
    #[serde(default = "default_true")]
    pub switch_on_speaker: bool,
    #[serde(default = "default_speaker_delay")]
    pub speaker_switch_delay: f64,
    #[serde(default = "default_pip")]
    pub picture_in_picture: String,
    #[serde(default = "default_true")]
    pub zoom_on_emphasis: bool,
    #[serde(default = "default_true")]
    pub remove_silence: bool,
    #[serde(default = "default_silence_threshold")]
    pub silence_threshold: f64,
    #[serde(default = "default_pip_size")]
    pub pip_size: f64,
}

fn default_speaker_delay() -> f64 {
    0.5
}

fn default_pip() -> String {
    "auto".to_string()
}

fn default_silence_threshold() -> f64 {
    2.0
}

fn default_pip_size() -> f64 {
    0.25
}

impl Default for EditingRules {
    fn default() -> Self {
        Self {
            switch_on_speaker: true,
            speaker_switch_delay: 0.5,
            picture_in_picture: "auto".to_string(),
            zoom_on_emphasis: true,
            remove_silence: true,
            silence_threshold: 2.0,
            pip_size: 0.25,
        }
    }
}

/// An edit decision in the EDL
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EditDecision {
    pub timestamp: f64,
    pub duration: f64,
    pub source: String,
    pub action: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transition_type: Option<String>,
    #[serde(default)]
    pub effects: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pip_size: Option<f64>,
}

/// Output settings for video rendering
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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
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
            format: "mp4".to_string(),
            resolution: "1920x1080".to_string(),
            fps: 30,
            bitrate: "8M".to_string(),
            output_path: None,
            codec: None,
        }
    }
}

/// Render options
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

/// Clip extraction criteria
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
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

/// Caption style settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptionStyle {
    #[serde(default = "default_font")]
    pub font: String,
    #[serde(default = "default_font_size")]
    pub size: u32,
    #[serde(default = "default_color")]
    pub color: String,
    #[serde(default = "default_background")]
    pub background: String,
    #[serde(default = "default_position")]
    pub position: String,
    #[serde(default = "default_max_chars")]
    pub max_chars_per_line: u32,
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
            font: "Arial".to_string(),
            size: 42,
            color: "#FFFFFF".to_string(),
            background: "#000000".to_string(),
            position: "bottom".to_string(),
            max_chars_per_line: 40,
            display_speaker_names: true,
        }
    }
}

/// Extracted clip information
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

/// Server configuration
#[derive(Debug, Clone)]
pub struct ServerConfig {
    pub output_dir: String,
    pub cache_dir: String,
    pub temp_dir: String,
    pub models: ModelConfig,
    #[allow(dead_code)]
    pub defaults: DefaultConfig,
    pub performance: PerformanceConfig,
}

/// Model configuration
#[derive(Debug, Clone)]
pub struct ModelConfig {
    pub whisper_model: String,
    #[allow(dead_code)]
    pub whisper_device: String,
    #[allow(dead_code)]
    pub diart_device: String,
}

/// Default editing parameters
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct DefaultConfig {
    pub transition_duration: f64,
    pub speaker_switch_delay: f64,
    pub silence_threshold: f64,
    pub zoom_factor: f64,
    pub pip_size: f64,
}

/// Performance configuration
#[derive(Debug, Clone)]
pub struct PerformanceConfig {
    #[allow(dead_code)]
    pub max_parallel_jobs: u32,
    #[allow(dead_code)]
    pub video_cache_size: String,
    pub enable_gpu: bool,
    #[allow(dead_code)]
    pub chunk_size: u32,
}

impl Default for ServerConfig {
    fn default() -> Self {
        let output_dir =
            std::env::var("MCP_VIDEO_OUTPUT_DIR").unwrap_or_else(|_| "/app/output".to_string());
        let cache_dir = std::env::var("MCP_VIDEO_CACHE_DIR").unwrap_or_else(|_| {
            dirs::cache_dir()
                .map(|d| d.join("mcp-video-editor").to_string_lossy().to_string())
                .unwrap_or_else(|| "/tmp/mcp-video-editor/cache".to_string())
        });
        let temp_dir =
            std::env::var("MCP_VIDEO_TEMP_DIR").unwrap_or_else(|_| "/tmp/video_editor".to_string());

        Self {
            output_dir,
            cache_dir,
            temp_dir,
            models: ModelConfig {
                whisper_model: std::env::var("WHISPER_MODEL")
                    .unwrap_or_else(|_| "medium".to_string()),
                whisper_device: std::env::var("WHISPER_DEVICE")
                    .unwrap_or_else(|_| "cpu".to_string()),
                diart_device: std::env::var("DIART_DEVICE").unwrap_or_else(|_| "cpu".to_string()),
            },
            defaults: DefaultConfig {
                transition_duration: std::env::var("TRANSITION_DURATION")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(0.5),
                speaker_switch_delay: std::env::var("SPEAKER_SWITCH_DELAY")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(0.8),
                silence_threshold: std::env::var("SILENCE_THRESHOLD")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(2.0),
                zoom_factor: std::env::var("ZOOM_FACTOR")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(1.3),
                pip_size: std::env::var("PIP_SIZE")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(0.25),
            },
            performance: PerformanceConfig {
                max_parallel_jobs: std::env::var("MAX_PARALLEL_JOBS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(2),
                video_cache_size: std::env::var("VIDEO_CACHE_SIZE")
                    .unwrap_or_else(|_| "2GB".to_string()),
                enable_gpu: std::env::var("ENABLE_GPU")
                    .map(|v| v.to_lowercase() == "true")
                    .unwrap_or(true),
                chunk_size: std::env::var("CHUNK_SIZE")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(300),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_analysis_options_default() {
        // Note: #[derive(Default)] uses bool::default() = false
        // The serde defaults only apply during deserialization
        let options = AnalysisOptions::default();
        assert!(!options.transcribe);
        assert!(!options.identify_speakers);
        assert!(!options.detect_scenes);
        assert!(!options.extract_highlights);
    }

    #[test]
    fn test_analysis_options_serde_default() {
        // When deserializing empty JSON, serde defaults kick in
        let options: AnalysisOptions = serde_json::from_str("{}").unwrap();
        assert!(options.transcribe);
        assert!(options.identify_speakers);
        assert!(options.detect_scenes);
        assert!(options.extract_highlights);
    }

    #[test]
    fn test_analysis_options_serialize() {
        let options = AnalysisOptions {
            transcribe: true,
            identify_speakers: false,
            detect_scenes: true,
            extract_highlights: false,
        };

        let json = serde_json::to_string(&options).unwrap();
        let parsed: AnalysisOptions = serde_json::from_str(&json).unwrap();

        assert_eq!(options.transcribe, parsed.transcribe);
        assert_eq!(options.identify_speakers, parsed.identify_speakers);
        assert_eq!(options.detect_scenes, parsed.detect_scenes);
        assert_eq!(options.extract_highlights, parsed.extract_highlights);
    }

    #[test]
    fn test_edit_decision_serialize() {
        let decision = EditDecision {
            timestamp: 10.5,
            duration: 5.0,
            source: "/path/to/video.mp4".to_string(),
            action: "show".to_string(),
            transition_type: Some("cross_dissolve".to_string()),
            effects: vec!["zoom".to_string()],
            pip_size: Some(0.25),
        };

        let json = serde_json::to_string(&decision).unwrap();
        let parsed: EditDecision = serde_json::from_str(&json).unwrap();

        assert_eq!(decision.timestamp, parsed.timestamp);
        assert_eq!(decision.duration, parsed.duration);
        assert_eq!(decision.source, parsed.source);
        assert_eq!(decision.action, parsed.action);
        assert_eq!(decision.transition_type, parsed.transition_type);
        assert_eq!(decision.effects, parsed.effects);
        assert_eq!(decision.pip_size, parsed.pip_size);
    }

    #[test]
    fn test_editing_rules_default() {
        let rules = EditingRules::default();

        assert!(rules.switch_on_speaker);
        assert!(rules.remove_silence);
        assert!(rules.zoom_on_emphasis);
        assert_eq!(rules.speaker_switch_delay, 0.5);
        assert_eq!(rules.picture_in_picture, "auto");
        assert_eq!(rules.silence_threshold, 2.0);
        assert_eq!(rules.pip_size, 0.25);
    }

    #[test]
    fn test_output_settings_default() {
        let settings = OutputSettings::default();

        assert_eq!(settings.format, "mp4");
        assert_eq!(settings.resolution, "1920x1080");
        assert_eq!(settings.fps, 30);
        assert_eq!(settings.bitrate, "8M");
        assert!(settings.output_path.is_none());
        assert!(settings.codec.is_none());
    }

    #[test]
    fn test_output_settings_serialize() {
        let settings = OutputSettings {
            format: "mp4".to_string(),
            resolution: "3840x2160".to_string(),
            fps: 60,
            bitrate: "20M".to_string(),
            output_path: Some("/output/video.mp4".to_string()),
            codec: Some("h264".to_string()),
        };

        let json = serde_json::to_string(&settings).unwrap();
        let parsed: OutputSettings = serde_json::from_str(&json).unwrap();

        assert_eq!(settings.resolution, parsed.resolution);
        assert_eq!(settings.fps, parsed.fps);
        assert_eq!(settings.bitrate, parsed.bitrate);
        assert_eq!(settings.output_path, parsed.output_path);
        assert_eq!(settings.codec, parsed.codec);
    }

    #[test]
    fn test_transcript_segment_serialize() {
        let segment = TranscriptSegment {
            id: 1,
            start: 0.0,
            end: 5.5,
            text: "Hello, world!".to_string(),
            words: vec![
                Word {
                    word: "Hello,".to_string(),
                    start: 0.0,
                    end: 0.5,
                    probability: 0.95,
                },
                Word {
                    word: "world!".to_string(),
                    start: 0.6,
                    end: 1.0,
                    probability: 0.98,
                },
            ],
        };

        let json = serde_json::to_string(&segment).unwrap();
        let parsed: TranscriptSegment = serde_json::from_str(&json).unwrap();

        assert_eq!(segment.start, parsed.start);
        assert_eq!(segment.end, parsed.end);
        assert_eq!(segment.text, parsed.text);
        assert_eq!(parsed.words.len(), 2);
    }

    #[test]
    fn test_extraction_criteria_default() {
        // Note: #[derive(Default)] uses f64::default() = 0.0
        // The serde defaults only apply during deserialization
        let criteria = ExtractionCriteria::default();

        assert!(criteria.keywords.is_empty());
        assert!(criteria.speakers.is_empty());
        assert!(criteria.time_ranges.is_empty());
        assert_eq!(criteria.min_clip_length, 0.0);
        assert_eq!(criteria.max_clip_length, 0.0);
        assert_eq!(criteria.padding, 0.0);
    }

    #[test]
    fn test_extraction_criteria_serde_default() {
        // When deserializing empty JSON, serde defaults kick in
        let criteria: ExtractionCriteria = serde_json::from_str("{}").unwrap();

        assert!(criteria.keywords.is_empty());
        assert!(criteria.speakers.is_empty());
        assert!(criteria.time_ranges.is_empty());
        assert_eq!(criteria.min_clip_length, 3.0);
        assert_eq!(criteria.max_clip_length, 60.0);
        assert_eq!(criteria.padding, 0.5);
    }

    #[test]
    fn test_extraction_criteria_serialize() {
        let criteria = ExtractionCriteria {
            keywords: vec!["important".to_string(), "key".to_string()],
            time_ranges: vec![(0.0, 10.0), (20.0, 30.0)],
            speakers: vec!["Speaker 1".to_string()],
            min_clip_length: 5.0,
            max_clip_length: 120.0,
            padding: 2.0,
        };

        let json = serde_json::to_string(&criteria).unwrap();
        let parsed: ExtractionCriteria = serde_json::from_str(&json).unwrap();

        assert_eq!(criteria.keywords, parsed.keywords);
        assert_eq!(criteria.time_ranges.len(), parsed.time_ranges.len());
        assert_eq!(criteria.min_clip_length, parsed.min_clip_length);
        assert_eq!(criteria.max_clip_length, parsed.max_clip_length);
        assert_eq!(criteria.padding, parsed.padding);
    }

    #[test]
    fn test_server_config_default() {
        let config = ServerConfig::default();

        assert!(!config.output_dir.is_empty());
        assert!(!config.cache_dir.is_empty());
        assert!(!config.temp_dir.is_empty());
        assert!(!config.models.whisper_model.is_empty());
        assert!(config.performance.enable_gpu);
    }

    #[test]
    fn test_caption_style_default() {
        let style = CaptionStyle::default();

        assert_eq!(style.font, "Arial");
        assert_eq!(style.size, 42);
        assert_eq!(style.color, "#FFFFFF");
        assert_eq!(style.background, "#000000");
        assert_eq!(style.position, "bottom");
        assert_eq!(style.max_chars_per_line, 40);
        assert!(style.display_speaker_names);
    }

    #[test]
    fn test_word_serialize() {
        let word = Word {
            word: "test".to_string(),
            start: 0.0,
            end: 0.5,
            probability: 0.99,
        };

        let json = serde_json::to_string(&word).unwrap();
        let parsed: Word = serde_json::from_str(&json).unwrap();

        assert_eq!(word.word, parsed.word);
        assert_eq!(word.start, parsed.start);
        assert_eq!(word.end, parsed.end);
        assert_eq!(word.probability, parsed.probability);
    }
}

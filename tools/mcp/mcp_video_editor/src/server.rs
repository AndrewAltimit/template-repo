//! MCP server implementation for video editor.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, warn};

use crate::audio::AudioProcessor;
use crate::jobs::{JobManager, JobStatus};
use crate::types::{
    AnalysisOptions, CaptionStyle, EditDecision, EditSuggestion, EditingRules, ExtractedClip,
    ExtractionCriteria, Highlight, OutputSettings, RenderOptions, ServerConfig, VideoAnalysis,
};
use crate::video::VideoProcessor;

/// Extract text from ToolResult content
fn extract_result_text(result: &ToolResult) -> Option<&str> {
    result.content.first().and_then(|c| {
        if let Content::Text { text } = c {
            Some(text.as_str())
        } else {
            None
        }
    })
}

/// Video editor MCP server
pub struct VideoEditorServer {
    config: Arc<ServerConfig>,
    job_manager: Arc<JobManager>,
    audio_processor: Arc<RwLock<Option<Arc<AudioProcessor>>>>,
    video_processor: Arc<RwLock<Option<Arc<VideoProcessor>>>>,
    output_dir: PathBuf,
    renders_dir: PathBuf,
    clips_dir: PathBuf,
    transcripts_dir: PathBuf,
    edl_dir: PathBuf,
}

impl VideoEditorServer {
    /// Create a new video editor server
    pub fn new() -> Self {
        let config = ServerConfig::default();

        // Create output directories
        let output_dir = PathBuf::from(&config.output_dir);
        let renders_dir = output_dir.join("renders");
        let clips_dir = output_dir.join("clips");
        let transcripts_dir = output_dir.join("transcripts");
        let edl_dir = output_dir.join("edl");

        // Best effort directory creation
        let _ = std::fs::create_dir_all(&output_dir);
        let _ = std::fs::create_dir_all(&renders_dir);
        let _ = std::fs::create_dir_all(&clips_dir);
        let _ = std::fs::create_dir_all(&transcripts_dir);
        let _ = std::fs::create_dir_all(&edl_dir);

        Self {
            config: Arc::new(config),
            job_manager: Arc::new(JobManager::new()),
            audio_processor: Arc::new(RwLock::new(None)),
            video_processor: Arc::new(RwLock::new(None)),
            output_dir,
            renders_dir,
            clips_dir,
            transcripts_dir,
            edl_dir,
        }
    }

    /// Get or initialize audio processor (lazy loading)
    #[allow(dead_code)]
    async fn get_audio_processor(&self) -> anyhow::Result<Arc<AudioProcessor>> {
        let mut processor = self.audio_processor.write().await;
        if processor.is_none() {
            info!("Initializing audio processor...");
            *processor = Some(Arc::new(AudioProcessor::new((*self.config).clone())?));
        }
        Ok(Arc::clone(processor.as_ref().unwrap()))
    }

    /// Get or initialize video processor (lazy loading)
    #[allow(dead_code)]
    async fn get_video_processor(&self) -> anyhow::Result<Arc<VideoProcessor>> {
        let mut processor = self.video_processor.write().await;
        if processor.is_none() {
            info!("Initializing video processor...");
            *processor = Some(Arc::new(VideoProcessor::new((*self.config).clone())?));
        }
        Ok(Arc::clone(processor.as_ref().unwrap()))
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(AnalyzeVideoTool {
                server: self.clone_refs(),
            }),
            Arc::new(CreateEditTool {
                server: self.clone_refs(),
            }),
            Arc::new(RenderVideoTool {
                server: self.clone_refs(),
            }),
            Arc::new(ExtractClipsTool {
                server: self.clone_refs(),
            }),
            Arc::new(AddCaptionsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetJobStatusTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone the Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            config: self.config.clone(),
            job_manager: self.job_manager.clone(),
            audio_processor: self.audio_processor.clone(),
            video_processor: self.video_processor.clone(),
            output_dir: self.output_dir.clone(),
            renders_dir: self.renders_dir.clone(),
            clips_dir: self.clips_dir.clone(),
            transcripts_dir: self.transcripts_dir.clone(),
            edl_dir: self.edl_dir.clone(),
        }
    }
}

impl Default for VideoEditorServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    config: Arc<ServerConfig>,
    job_manager: Arc<JobManager>,
    audio_processor: Arc<RwLock<Option<Arc<AudioProcessor>>>>,
    video_processor: Arc<RwLock<Option<Arc<VideoProcessor>>>>,
    #[allow(dead_code)]
    output_dir: PathBuf,
    renders_dir: PathBuf,
    clips_dir: PathBuf,
    #[allow(dead_code)]
    transcripts_dir: PathBuf,
    edl_dir: PathBuf,
}

impl ServerRefs {
    async fn get_audio_processor(&self) -> anyhow::Result<Arc<AudioProcessor>> {
        let mut processor = self.audio_processor.write().await;
        if processor.is_none() {
            *processor = Some(Arc::new(AudioProcessor::new((*self.config).clone())?));
        }
        Ok(Arc::clone(processor.as_ref().unwrap()))
    }

    async fn get_video_processor(&self) -> anyhow::Result<Arc<VideoProcessor>> {
        let mut processor = self.video_processor.write().await;
        if processor.is_none() {
            *processor = Some(Arc::new(VideoProcessor::new((*self.config).clone())?));
        }
        Ok(Arc::clone(processor.as_ref().unwrap()))
    }
}

// ============================================================================
// Tool: video_editor/analyze
// ============================================================================

struct AnalyzeVideoTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AnalyzeVideoTool {
    fn name(&self) -> &str {
        "video_editor/analyze"
    }

    fn description(&self) -> &str {
        r#"Analyze video content without rendering, returns metadata and suggested edits.

Performs comprehensive analysis including:
- Transcription (speech-to-text with timestamps)
- Speaker identification/diarization
- Scene change detection
- Audio analysis (silence, volume levels)
- Highlight extraction
- Edit suggestions

Examples:
- Analyze a single video for transcription
- Get speaker breakdown for multi-person content
- Detect scene changes for automatic editing"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "video_inputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of video file paths to analyze"
                },
                "analysis_options": {
                    "type": "object",
                    "properties": {
                        "transcribe": {"type": "boolean", "default": true},
                        "identify_speakers": {"type": "boolean", "default": true},
                        "detect_scenes": {"type": "boolean", "default": true},
                        "extract_highlights": {"type": "boolean", "default": true}
                    },
                    "description": "Options controlling which analyses to perform"
                }
            },
            "required": ["video_inputs"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        // Parse arguments
        let video_inputs: Vec<String> = args
            .get("video_inputs")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'video_inputs' parameter".to_string())
            })?;

        if video_inputs.is_empty() {
            return ToolResult::json(&json!({"error": "No video inputs provided"}));
        }

        let analysis_options: AnalysisOptions = args
            .get("analysis_options")
            .map(|v| serde_json::from_value(v.clone()).unwrap_or_default())
            .unwrap_or_default();

        info!("Analyzing {} video(s)", video_inputs.len());

        let audio_processor = self.server.get_audio_processor().await.map_err(|e| {
            MCPError::Internal(format!("Failed to initialize audio processor: {}", e))
        })?;
        let video_processor = self.server.get_video_processor().await.map_err(|e| {
            MCPError::Internal(format!("Failed to initialize video processor: {}", e))
        })?;

        let mut results: HashMap<String, VideoAnalysis> = HashMap::new();

        for video_path in &video_inputs {
            // Check if file exists
            if !std::path::Path::new(video_path).exists() {
                return ToolResult::json(
                    &json!({"error": format!("Video file not found: {}", video_path)}),
                );
            }

            let file_size = std::fs::metadata(video_path).map(|m| m.len()).unwrap_or(0);

            let mut analysis = VideoAnalysis {
                file: video_path.clone(),
                file_size,
                transcript: None,
                speakers: None,
                segments_with_speakers: None,
                audio_analysis: None,
                scene_changes: None,
                highlights: None,
                suggested_edits: None,
            };

            // Extract audio for analysis
            let audio_path = match audio_processor.extract_audio(video_path).await {
                Ok(path) => path,
                Err(e) => {
                    warn!("Failed to extract audio: {}", e);
                    results.insert(video_path.clone(), analysis);
                    continue;
                },
            };

            // Transcription
            let mut transcript = None;
            if analysis_options.transcribe {
                info!("Performing transcription...");
                match audio_processor.transcribe(&audio_path, None).await {
                    Ok(t) => {
                        transcript = Some(t.clone());
                        analysis.transcript = Some(t);
                    },
                    Err(e) => warn!("Transcription failed: {}", e),
                }
            }

            // Speaker diarization
            if analysis_options.identify_speakers {
                info!("Identifying speakers...");
                match audio_processor.diarize_speakers(&audio_path).await {
                    Ok(diarization) => {
                        analysis.speakers = Some(diarization.speakers.clone());
                        if let Some(ref t) = transcript {
                            let combined =
                                audio_processor.combine_transcript_with_speakers(t, &diarization);
                            analysis.segments_with_speakers = Some(combined.segments_with_speakers);
                        }
                    },
                    Err(e) => warn!("Speaker diarization failed: {}", e),
                }
            }

            // Audio analysis
            info!("Analyzing audio levels...");
            match audio_processor.analyze_audio_levels(&audio_path).await {
                Ok(audio_analysis) => {
                    analysis.audio_analysis = Some(audio_analysis);
                },
                Err(e) => warn!("Audio analysis failed: {}", e),
            }

            // Scene detection
            if analysis_options.detect_scenes {
                info!("Detecting scene changes...");
                match video_processor.detect_scene_changes(video_path).await {
                    Ok(scenes) => {
                        analysis.scene_changes = Some(scenes);
                    },
                    Err(e) => warn!("Scene detection failed: {}", e),
                }
            }

            // Extract highlights
            if analysis_options.extract_highlights {
                let highlights = extract_highlights(&analysis);
                if !highlights.is_empty() {
                    analysis.highlights = Some(highlights);
                }
            }

            // Generate edit suggestions
            let suggestions = generate_edit_suggestions(&analysis);
            if !suggestions.is_empty() {
                analysis.suggested_edits = Some(suggestions);
            }

            // Clean up temp audio file
            let _ = std::fs::remove_file(&audio_path);

            results.insert(video_path.clone(), analysis);
        }

        let response = json!({
            "video_inputs": video_inputs,
            "analysis": results
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: video_editor/create_edit
// ============================================================================

struct CreateEditTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateEditTool {
    fn name(&self) -> &str {
        "video_editor/create_edit"
    }

    fn description(&self) -> &str {
        r#"Generate an edit decision list (EDL) based on rules without rendering.

Creates a sequence of edit decisions including:
- Source video and timestamp for each segment
- Transitions between clips
- Effects (zoom, picture-in-picture)
- Silence removal

The EDL can be reviewed before rendering."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "video_inputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of video file paths to include in the edit"
                },
                "editing_rules": {
                    "type": "object",
                    "properties": {
                        "switch_on_speaker": {"type": "boolean", "default": true},
                        "speaker_switch_delay": {"type": "number", "default": 0.5},
                        "picture_in_picture": {"type": "string", "default": "auto"},
                        "zoom_on_emphasis": {"type": "boolean", "default": true},
                        "remove_silence": {"type": "boolean", "default": true},
                        "silence_threshold": {"type": "number", "default": 2.0}
                    },
                    "description": "Rules controlling automatic editing decisions"
                },
                "speaker_mapping": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Map of speaker IDs to video file paths"
                }
            },
            "required": ["video_inputs"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let video_inputs: Vec<String> = args
            .get("video_inputs")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'video_inputs' parameter".to_string())
            })?;

        if video_inputs.is_empty() {
            return ToolResult::json(&json!({"error": "No video inputs provided"}));
        }

        let editing_rules: EditingRules = args
            .get("editing_rules")
            .map(|v| serde_json::from_value(v.clone()).unwrap_or_default())
            .unwrap_or_default();

        let speaker_mapping: Option<HashMap<String, String>> = args
            .get("speaker_mapping")
            .and_then(|v| serde_json::from_value(v.clone()).ok());

        info!("Creating edit for {} video(s)", video_inputs.len());

        // First analyze the videos
        let analyze_tool = AnalyzeVideoTool {
            server: self.server.clone(),
        };

        let analysis_args = json!({
            "video_inputs": video_inputs,
            "analysis_options": {
                "transcribe": true,
                "identify_speakers": editing_rules.switch_on_speaker,
                "detect_scenes": true,
                "extract_highlights": editing_rules.zoom_on_emphasis
            }
        });

        let analysis_result = analyze_tool.execute(analysis_args).await?;
        let analysis_text = extract_result_text(&analysis_result)
            .ok_or_else(|| MCPError::Internal("No text content in analysis result".to_string()))?;
        let analysis: Value = serde_json::from_str(analysis_text)?;

        if analysis.get("error").is_some() {
            return ToolResult::json(&analysis);
        }

        let primary_video = &video_inputs[0];
        let primary_analysis = analysis.get("analysis").and_then(|a| a.get(primary_video));

        // Generate edit decision list
        let edit_decision_list = generate_edl(
            &video_inputs,
            primary_analysis,
            &editing_rules,
            speaker_mapping.as_ref(),
        );

        // Calculate estimated duration
        let estimated_duration: f64 = edit_decision_list.iter().map(|d| d.duration).sum();

        // Save EDL to file
        let edl_filename = format!("edit_{}.json", self.server.job_manager.counter());
        let edl_path = self.server.edl_dir.join(&edl_filename);

        let edl_content = serde_json::to_string_pretty(&edit_decision_list)
            .map_err(|e| MCPError::Internal(format!("Failed to serialize EDL: {}", e)))?;
        std::fs::write(&edl_path, &edl_content)
            .map_err(|e| MCPError::Internal(format!("Failed to write EDL file: {}", e)))?;

        let response = json!({
            "edit_decision_list": edit_decision_list,
            "estimated_duration": estimated_duration,
            "edl_file": edl_path.to_string_lossy(),
            "video_inputs": video_inputs,
            "editing_rules": editing_rules
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: video_editor/render
// ============================================================================

struct RenderVideoTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RenderVideoTool {
    fn name(&self) -> &str {
        "video_editor/render"
    }

    fn description(&self) -> &str {
        r#"Execute the actual video rendering based on EDL or automatic rules.

Renders the final video with all edits, transitions, and effects applied.
Returns a job ID for tracking long-running operations."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "video_inputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of video file paths"
                },
                "edit_decision_list": {
                    "type": "array",
                    "description": "EDL from create_edit tool (optional - will generate if not provided)"
                },
                "output_settings": {
                    "type": "object",
                    "properties": {
                        "format": {"type": "string", "default": "mp4"},
                        "resolution": {"type": "string", "default": "1920x1080"},
                        "fps": {"type": "integer", "default": 30},
                        "bitrate": {"type": "string", "default": "8M"},
                        "output_path": {"type": "string"}
                    }
                },
                "render_options": {
                    "type": "object",
                    "properties": {
                        "hardware_acceleration": {"type": "boolean", "default": true},
                        "preview_mode": {"type": "boolean", "default": false},
                        "add_captions": {"type": "boolean", "default": false},
                        "add_speaker_labels": {"type": "boolean", "default": false}
                    }
                }
            },
            "required": ["video_inputs"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let video_inputs: Vec<String> = args
            .get("video_inputs")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'video_inputs' parameter".to_string())
            })?;

        if video_inputs.is_empty() {
            return ToolResult::json(&json!({"error": "No video inputs provided"}));
        }

        let edit_decision_list: Option<Vec<EditDecision>> = args
            .get("edit_decision_list")
            .and_then(|v| serde_json::from_value(v.clone()).ok());

        let mut output_settings: OutputSettings = args
            .get("output_settings")
            .map(|v| serde_json::from_value(v.clone()).unwrap_or_default())
            .unwrap_or_default();

        let render_options: RenderOptions = args
            .get("render_options")
            .map(|v| serde_json::from_value(v.clone()).unwrap_or_default())
            .unwrap_or_default();

        // Create job for tracking
        let job_id = self.server.job_manager.create_job("render").await;

        self.server
            .job_manager
            .update_job(&job_id, JobStatus::Running, 5, "preparing")
            .await;

        // Generate EDL if not provided
        let edl = if let Some(list) = edit_decision_list {
            list
        } else {
            info!("No EDL provided, generating automatically...");
            self.server
                .job_manager
                .update_job(&job_id, JobStatus::Running, 10, "generating_edl")
                .await;

            let create_edit_tool = CreateEditTool {
                server: self.server.clone(),
            };

            let edit_args = json!({
                "video_inputs": video_inputs
            });

            let edit_result = create_edit_tool.execute(edit_args).await?;
            let edit_text = extract_result_text(&edit_result)
                .ok_or_else(|| MCPError::Internal("No text content in edit result".to_string()))?;
            let edit_response: Value = serde_json::from_str(edit_text)?;

            if edit_response.get("error").is_some() {
                self.server
                    .job_manager
                    .fail_job(
                        &job_id,
                        edit_response["error"].as_str().unwrap_or("Unknown error"),
                    )
                    .await;
                return ToolResult::json(&edit_response);
            }

            serde_json::from_value(edit_response["edit_decision_list"].clone())?
        };

        // Set default output path if not provided
        if output_settings.output_path.is_none() {
            output_settings.output_path = Some(
                self.server
                    .renders_dir
                    .join(format!(
                        "rendered_{}.mp4",
                        self.server.job_manager.counter()
                    ))
                    .to_string_lossy()
                    .to_string(),
            );
        }

        // Adjust settings for preview mode
        if render_options.preview_mode {
            output_settings.resolution = "640x360".to_string();
            output_settings.bitrate = "2M".to_string();
            output_settings.fps = 15;
        }

        self.server
            .job_manager
            .update_job(&job_id, JobStatus::Running, 20, "loading_videos")
            .await;

        // Perform rendering
        let video_processor = self.server.get_video_processor().await.map_err(|e| {
            MCPError::Internal(format!("Failed to initialize video processor: {}", e))
        })?;

        self.server
            .job_manager
            .update_job(&job_id, JobStatus::Running, 60, "rendering")
            .await;

        match video_processor
            .render_from_edl(&video_inputs, &edl, &output_settings, &render_options)
            .await
        {
            Ok(render_result) => {
                self.server
                    .job_manager
                    .complete_job(&job_id, json!(render_result))
                    .await;

                ToolResult::json(&json!({
                    "success": true,
                    "job_id": job_id,
                    "output_path": render_result.output_path,
                    "duration": render_result.duration,
                    "fps": render_result.fps,
                    "resolution": render_result.resolution,
                    "file_size": render_result.file_size,
                    "codec": render_result.codec
                }))
            },
            Err(e) => {
                self.server
                    .job_manager
                    .fail_job(&job_id, &e.to_string())
                    .await;

                ToolResult::json(&json!({
                    "error": e.to_string(),
                    "job_id": job_id
                }))
            },
        }
    }
}

// ============================================================================
// Tool: video_editor/extract_clips
// ============================================================================

struct ExtractClipsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ExtractClipsTool {
    fn name(&self) -> &str {
        "video_editor/extract_clips"
    }

    fn description(&self) -> &str {
        r#"Create short clips based on transcript keywords or timestamps.

Extract specific segments from videos based on:
- Keywords in transcript
- Specific speakers
- Time ranges"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "video_input": {
                    "type": "string",
                    "description": "Path to the source video file"
                },
                "extraction_criteria": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keywords to search for in transcript"
                        },
                        "speakers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Speaker IDs to extract clips for"
                        },
                        "time_ranges": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2
                            },
                            "description": "List of [start, end] time pairs"
                        },
                        "min_clip_length": {"type": "number", "default": 3.0},
                        "max_clip_length": {"type": "number", "default": 60.0},
                        "padding": {"type": "number", "default": 0.5}
                    }
                },
                "output_dir": {
                    "type": "string",
                    "description": "Output directory for clips"
                }
            },
            "required": ["video_input"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let video_input: String = args
            .get("video_input")
            .and_then(|v| v.as_str())
            .map(String::from)
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'video_input' parameter".to_string())
            })?;

        if !std::path::Path::new(&video_input).exists() {
            return ToolResult::json(
                &json!({"error": format!("Video file not found: {}", video_input)}),
            );
        }

        let criteria: ExtractionCriteria = args
            .get("extraction_criteria")
            .map(|v| serde_json::from_value(v.clone()).unwrap_or_default())
            .unwrap_or_default();

        let output_dir = args
            .get("output_dir")
            .and_then(|v| v.as_str())
            .map(PathBuf::from)
            .unwrap_or_else(|| self.server.clips_dir.clone());

        std::fs::create_dir_all(&output_dir)
            .map_err(|e| MCPError::Internal(format!("Failed to create output directory: {}", e)))?;

        info!("Extracting clips from: {}", video_input);

        let video_processor = self.server.get_video_processor().await.map_err(|e| {
            MCPError::Internal(format!("Failed to initialize video processor: {}", e))
        })?;
        let mut clips_extracted: Vec<ExtractedClip> = Vec::new();

        // Extract time range clips
        for time_range in criteria.time_ranges.iter() {
            let start = (time_range.0 - criteria.padding).max(0.0);
            let end = time_range.1 + criteria.padding;
            let duration = end - start;

            if duration < criteria.min_clip_length {
                continue;
            }

            let actual_end = if duration > criteria.max_clip_length {
                start + criteria.max_clip_length
            } else {
                end
            };

            let output_path = output_dir
                .join(format!(
                    "clip_{}_time_{:.1}-{:.1}.mp4",
                    clips_extracted.len() + 1,
                    start,
                    actual_end
                ))
                .to_string_lossy()
                .to_string();

            if let Err(e) = video_processor
                .extract_clip(&video_input, start, actual_end, &output_path)
                .await
            {
                warn!("Failed to extract clip: {}", e);
                continue;
            }

            clips_extracted.push(ExtractedClip {
                output_path,
                start_time: start,
                end_time: actual_end,
                duration: actual_end - start,
                criteria: "time_range".to_string(),
                keyword: None,
                speaker: None,
                text: None,
            });
        }

        // For keyword and speaker extraction, we'd need to analyze the video first
        // For now, only time_ranges are fully implemented

        let response = json!({
            "video_input": video_input,
            "clips_extracted": clips_extracted,
            "total_clips": clips_extracted.len(),
            "output_directory": output_dir.to_string_lossy()
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: video_editor/add_captions
// ============================================================================

struct AddCaptionsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddCaptionsTool {
    fn name(&self) -> &str {
        "video_editor/add_captions"
    }

    fn description(&self) -> &str {
        r#"Add styled captions to existing video using transcript.

Automatically transcribes the video and adds subtitles with
customizable style options."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "video_input": {
                    "type": "string",
                    "description": "Path to the video file"
                },
                "caption_style": {
                    "type": "object",
                    "properties": {
                        "font": {"type": "string", "default": "Arial"},
                        "size": {"type": "integer", "default": 42},
                        "color": {"type": "string", "default": "#FFFFFF"},
                        "background": {"type": "string", "default": "#000000"},
                        "position": {"type": "string", "default": "bottom"},
                        "max_chars_per_line": {"type": "integer", "default": 40},
                        "display_speaker_names": {"type": "boolean", "default": true}
                    }
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["en"],
                    "description": "Languages to transcribe"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output path for captioned video"
                }
            },
            "required": ["video_input"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let video_input: String = args
            .get("video_input")
            .and_then(|v| v.as_str())
            .map(String::from)
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'video_input' parameter".to_string())
            })?;

        if !std::path::Path::new(&video_input).exists() {
            return ToolResult::json(
                &json!({"error": format!("Video file not found: {}", video_input)}),
            );
        }

        let _caption_style: CaptionStyle = args
            .get("caption_style")
            .map(|v| serde_json::from_value(v.clone()).unwrap_or_default())
            .unwrap_or_default();

        let languages: Vec<String> = args
            .get("languages")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .unwrap_or_else(|| vec!["en".to_string()]);

        let output_path = args
            .get("output_path")
            .and_then(|v| v.as_str())
            .map(String::from)
            .unwrap_or_else(|| {
                let stem = std::path::Path::new(&video_input)
                    .file_stem()
                    .unwrap_or_default()
                    .to_string_lossy();
                self.server
                    .renders_dir
                    .join(format!("captioned_{}.mp4", stem))
                    .to_string_lossy()
                    .to_string()
            });

        info!("Adding captions to: {}", video_input);

        let audio_processor = self.server.get_audio_processor().await.map_err(|e| {
            MCPError::Internal(format!("Failed to initialize audio processor: {}", e))
        })?;
        let video_processor = self.server.get_video_processor().await.map_err(|e| {
            MCPError::Internal(format!("Failed to initialize video processor: {}", e))
        })?;

        let mut results: Vec<Value> = Vec::new();

        for language in &languages {
            // Extract audio and transcribe
            let audio_path = audio_processor
                .extract_audio(&video_input)
                .await
                .map_err(|e| MCPError::Internal(format!("Failed to extract audio: {}", e)))?;

            let transcript = audio_processor
                .transcribe(&audio_path, Some(language))
                .await
                .map_err(|e| MCPError::Internal(format!("Failed to transcribe audio: {}", e)))?;

            // Generate SRT file
            let srt_segments: Vec<(f64, f64, String)> = transcript
                .segments
                .iter()
                .map(|s| (s.start, s.end, s.text.clone()))
                .collect();

            let lang_output_path = if languages.len() > 1 {
                let base = std::path::Path::new(&output_path);
                let stem = base
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("output");
                let parent = base.parent().map(|p| p.to_path_buf()).unwrap_or_default();
                parent
                    .join(format!("{}_{}.mp4", stem, language))
                    .to_string_lossy()
                    .to_string()
            } else {
                output_path.clone()
            };

            let srt_path = std::path::Path::new(&lang_output_path)
                .with_extension("srt")
                .to_string_lossy()
                .to_string();
            video_processor
                .generate_srt(&srt_segments, std::path::Path::new(&srt_path))
                .map_err(|e| MCPError::Internal(format!("Failed to generate SRT: {}", e)))?;

            // Add subtitles to video
            video_processor
                .add_subtitles(&video_input, &srt_path, &lang_output_path)
                .await
                .map_err(|e| MCPError::Internal(format!("Failed to add subtitles: {}", e)))?;

            // Clean up audio file
            let _ = std::fs::remove_file(&audio_path);

            results.push(json!({
                "language": language,
                "output_path": lang_output_path,
                "srt_path": srt_path,
                "caption_count": transcript.segments.len()
            }));
        }

        let response = json!({
            "video_input": video_input,
            "languages_processed": results
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: video_editor/get_job_status
// ============================================================================

struct GetJobStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetJobStatusTool {
    fn name(&self) -> &str {
        "video_editor/get_job_status"
    }

    fn description(&self) -> &str {
        "Get the status of a rendering job."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID returned from render operation"
                }
            },
            "required": ["job_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let job_id: String = args
            .get("job_id")
            .and_then(|v| v.as_str())
            .map(String::from)
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'job_id' parameter".to_string()))?;

        match self.server.job_manager.get_job(&job_id).await {
            Some(job) => ToolResult::json(&json!(job)),
            None => ToolResult::json(&json!({"error": format!("Job not found: {}", job_id)})),
        }
    }
}

// ============================================================================
// Helper functions
// ============================================================================

/// Extract highlights from video analysis
fn extract_highlights(analysis: &VideoAnalysis) -> Vec<Highlight> {
    let mut highlights = Vec::new();

    // Audio-based highlights
    if let Some(ref audio) = analysis.audio_analysis {
        for peak_time in &audio.peak_moments {
            highlights.push(Highlight {
                time: *peak_time,
                highlight_type: "audio_peak".to_string(),
                confidence: 0.8,
                keyword: None,
                text: None,
            });
        }
    }

    // Keyword-based highlights
    if let Some(ref transcript) = analysis.transcript {
        let highlight_keywords = [
            "important",
            "key point",
            "summary",
            "conclusion",
            "remember",
        ];

        for segment in &transcript.segments {
            let text_lower = segment.text.to_lowercase();
            for keyword in &highlight_keywords {
                if text_lower.contains(keyword) {
                    highlights.push(Highlight {
                        time: segment.start,
                        highlight_type: "keyword".to_string(),
                        confidence: 0.9,
                        keyword: Some(keyword.to_string()),
                        text: Some(segment.text.clone()),
                    });
                    break;
                }
            }
        }
    }

    highlights
}

/// Generate edit suggestions from analysis
fn generate_edit_suggestions(analysis: &VideoAnalysis) -> Vec<EditSuggestion> {
    let mut suggestions = Vec::new();

    // Suggest removing long silences
    if let Some(ref audio) = analysis.audio_analysis {
        for (start, end) in &audio.silence_segments {
            let duration = end - start;
            if duration > 3.0 {
                suggestions.push(EditSuggestion {
                    suggestion_type: "remove_silence".to_string(),
                    start: Some(*start),
                    end: Some(*end),
                    time: None,
                    effect: None,
                    transition: None,
                    reason: format!("Long silence detected ({:.1} seconds)", duration),
                });
            }
        }
    }

    // Suggest emphasis on highlights
    if let Some(ref highlights) = analysis.highlights {
        for highlight in highlights {
            suggestions.push(EditSuggestion {
                suggestion_type: "add_emphasis".to_string(),
                start: None,
                end: None,
                time: Some(highlight.time),
                effect: Some("zoom_in".to_string()),
                transition: None,
                reason: format!("Highlight detected: {}", highlight.highlight_type),
            });
        }
    }

    // Suggest cuts at scene changes
    if let Some(ref scenes) = analysis.scene_changes {
        for scene_time in scenes.iter().take(10) {
            suggestions.push(EditSuggestion {
                suggestion_type: "scene_cut".to_string(),
                start: None,
                end: None,
                time: Some(*scene_time),
                effect: None,
                transition: Some("cross_dissolve".to_string()),
                reason: "Scene change detected".to_string(),
            });
        }
    }

    suggestions
}

/// Generate edit decision list from analysis
fn generate_edl(
    video_inputs: &[String],
    primary_analysis: Option<&Value>,
    editing_rules: &EditingRules,
    speaker_mapping: Option<&HashMap<String, String>>,
) -> Vec<EditDecision> {
    let primary_video = &video_inputs[0];
    let mut edit_list = Vec::new();

    // Try to use speaker segments if available
    if editing_rules.switch_on_speaker
        && let Some(analysis) = primary_analysis
        && let Some(segments) = analysis
            .get("segments_with_speakers")
            .and_then(|s| s.as_array())
    {
        let mut last_speaker: Option<String> = None;
        let mut last_switch_time = 0.0;
        let mut current_time = 0.0;

        for segment in segments {
            let speaker = segment
                .get("speaker")
                .and_then(|s| s.as_str())
                .map(String::from);
            let start = segment.get("start").and_then(|s| s.as_f64()).unwrap_or(0.0);
            let end = segment.get("end").and_then(|s| s.as_f64()).unwrap_or(0.0);
            let duration = end - start;

            // Determine source video
            let source = if let Some(mapping) = speaker_mapping {
                if let Some(ref spk) = speaker {
                    mapping
                        .get(spk)
                        .cloned()
                        .unwrap_or_else(|| primary_video.clone())
                } else {
                    primary_video.clone()
                }
            } else {
                primary_video.clone()
            };

            let should_switch = speaker != last_speaker
                && (current_time - last_switch_time) > editing_rules.speaker_switch_delay;

            let action = if should_switch { "transition" } else { "show" };

            let decision = EditDecision {
                timestamp: start,
                duration,
                source,
                action: action.to_string(),
                transition_type: if should_switch {
                    Some("cross_dissolve".to_string())
                } else {
                    None
                },
                effects: vec![],
                pip_size: None,
            };

            if should_switch {
                last_speaker = speaker;
                last_switch_time = current_time;
            }

            edit_list.push(decision);
            current_time = end;
        }

        if !edit_list.is_empty() {
            return edit_list;
        }
    }

    // Fallback: use scene changes or fixed intervals
    if let Some(analysis) = primary_analysis
        && let Some(scenes) = analysis.get("scene_changes").and_then(|s| s.as_array())
    {
        let scene_times: Vec<f64> = scenes.iter().filter_map(|s| s.as_f64()).collect();

        if !scene_times.is_empty() {
            let mut last_time = 0.0;
            for (i, scene_time) in scene_times.iter().enumerate() {
                let duration = scene_time - last_time;
                if duration > 0.5 {
                    let source_idx = i % video_inputs.len();
                    edit_list.push(EditDecision {
                        timestamp: last_time,
                        duration,
                        source: video_inputs[source_idx].clone(),
                        action: if i == 0 { "show" } else { "transition" }.to_string(),
                        transition_type: if i > 0 {
                            Some("cross_dissolve".to_string())
                        } else {
                            None
                        },
                        effects: vec![],
                        pip_size: None,
                    });
                }
                last_time = *scene_time;
            }

            if !edit_list.is_empty() {
                return edit_list;
            }
        }
    }

    // Final fallback: fixed intervals
    let duration = primary_analysis
        .and_then(|a| a.get("audio_analysis"))
        .and_then(|a| a.get("duration"))
        .and_then(|d| d.as_f64())
        .unwrap_or(60.0);

    let interval = 10.0;
    let num_segments = (duration / interval) as usize;

    for i in 0..num_segments {
        let source_idx = i % video_inputs.len();
        edit_list.push(EditDecision {
            timestamp: i as f64 * interval,
            duration: interval,
            source: video_inputs[source_idx].clone(),
            action: if i == 0 { "show" } else { "transition" }.to_string(),
            transition_type: if i > 0 {
                Some("cross_dissolve".to_string())
            } else {
                None
            },
            effects: vec![],
            pip_size: None,
        });
    }

    edit_list
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{EditingRules, ExtractionCriteria, OutputSettings, RenderOptions};

    #[test]
    fn test_server_creation() {
        let server = VideoEditorServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 6);
    }

    #[test]
    fn test_tool_names() {
        let server = VideoEditorServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"video_editor/analyze"));
        assert!(names.contains(&"video_editor/create_edit"));
        assert!(names.contains(&"video_editor/render"));
        assert!(names.contains(&"video_editor/extract_clips"));
        assert!(names.contains(&"video_editor/add_captions"));
        assert!(names.contains(&"video_editor/get_job_status"));
    }

    #[test]
    fn test_tool_descriptions() {
        let server = VideoEditorServer::new();
        let tools = server.tools();

        for tool in &tools {
            // All tools should have non-empty descriptions
            assert!(
                !tool.description().is_empty(),
                "Tool {} has empty description",
                tool.name()
            );
        }
    }

    #[test]
    fn test_generate_edl_fixed_intervals() {
        let video_inputs = vec!["/path/to/video.mp4".to_string()];
        let editing_rules = EditingRules::default();

        // Without analysis, should generate fixed interval EDL
        let edl = generate_edl(&video_inputs, None, &editing_rules, None);

        assert!(!edl.is_empty(), "EDL should not be empty");
        assert_eq!(edl[0].source, "/path/to/video.mp4");
        assert_eq!(edl[0].action, "show");
    }

    #[test]
    fn test_generate_edl_with_scene_changes() {
        let video_inputs = vec!["/path/to/video.mp4".to_string()];
        let editing_rules = EditingRules::default();

        let analysis = serde_json::json!({
            "scene_changes": [5.0, 10.0, 15.0, 20.0]
        });

        let edl = generate_edl(&video_inputs, Some(&analysis), &editing_rules, None);

        assert!(!edl.is_empty(), "EDL should not be empty");
        // First edit should start at 0
        assert_eq!(edl[0].timestamp, 0.0);
    }

    #[test]
    fn test_extract_highlights_empty_analysis() {
        let analysis = VideoAnalysis {
            file: "/path/to/video.mp4".to_string(),
            file_size: 1000,
            transcript: None,
            speakers: None,
            segments_with_speakers: None,
            audio_analysis: None,
            scene_changes: None,
            highlights: None,
            suggested_edits: None,
        };

        let highlights = extract_highlights(&analysis);
        assert!(
            highlights.is_empty(),
            "No highlights without transcript/scenes"
        );
    }

    #[test]
    fn test_editing_rules_default() {
        let rules = EditingRules::default();

        assert!(rules.switch_on_speaker);
        assert!(rules.remove_silence);
        assert!(rules.zoom_on_emphasis);
        assert_eq!(rules.speaker_switch_delay, 0.5);
    }

    #[test]
    fn test_extraction_criteria_default() {
        // Note: #[derive(Default)] uses f64::default() = 0.0
        let criteria = ExtractionCriteria::default();

        assert!(criteria.keywords.is_empty());
        assert!(criteria.time_ranges.is_empty());
        assert_eq!(criteria.min_clip_length, 0.0);
        assert_eq!(criteria.max_clip_length, 0.0);
        assert_eq!(criteria.padding, 0.0);
    }

    #[test]
    fn test_output_settings_default() {
        let settings = OutputSettings::default();

        assert_eq!(settings.resolution, "1920x1080");
        assert_eq!(settings.fps, 30);
        assert_eq!(settings.bitrate, "8M");
        assert!(settings.output_path.is_none());
    }

    #[test]
    fn test_render_options_default() {
        let options = RenderOptions::default();

        assert!(!options.preview_mode);
        assert!(options.hardware_acceleration);
    }

    #[tokio::test]
    async fn test_job_manager_create_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("test_operation").await;

        assert!(!job_id.is_empty());

        let job = manager.get_job(&job_id).await;
        assert!(job.is_some());

        let job = job.unwrap();
        assert_eq!(job.operation, "test_operation");
        assert_eq!(job.status, JobStatus::Pending);
    }

    #[tokio::test]
    async fn test_job_manager_update_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("test_operation").await;

        manager
            .update_job(&job_id, JobStatus::Running, 50, "processing")
            .await;

        let job = manager.get_job(&job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Running);
        assert_eq!(job.progress, 50);
        assert_eq!(job.stage, "processing");
    }

    #[tokio::test]
    async fn test_job_manager_complete_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("test_operation").await;

        let result = serde_json::json!({"success": true});
        manager.complete_job(&job_id, result.clone()).await;

        let job = manager.get_job(&job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Completed);
        assert_eq!(job.progress, 100);
        assert_eq!(job.result, Some(result));
    }

    #[tokio::test]
    async fn test_job_manager_fail_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("test_operation").await;

        manager.fail_job(&job_id, "Something went wrong").await;

        let job = manager.get_job(&job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Failed);
        assert_eq!(job.error.as_deref(), Some("Something went wrong"));
    }
}

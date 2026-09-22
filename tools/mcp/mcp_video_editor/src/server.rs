//! MCP tool definitions for the video editor.
//!
//! Every tool parses its arguments into a typed struct (see [`crate::types`]);
//! malformed input is reported as `InvalidParameters` naming the bad field.
//! Operational failures (missing files, ffmpeg errors, ...) are returned as
//! `isError` results whose text is a JSON object with an `error` field.
//!
//! Heavy operations run as jobs (see [`crate::jobs`]) and accept an optional
//! `background` flag: when set the call returns a `job_id` immediately and the
//! result is fetched with `video_editor/get_job_status`.

use std::collections::HashMap;
use std::future::Future;
use std::path::{Path, PathBuf};
use std::pin::Pin;
use std::sync::Arc;

use anyhow::{Context, bail};
use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use tracing::info;

use crate::audio::{self, LevelTrack, Transcriber};
use crate::captions;
use crate::config::ServerConfig;
use crate::edl::{self, EdlInputs};
use crate::ffmpeg::{self, Container};
use crate::jobs::{JobContext, JobManager, JobStatus};
use crate::types::*;
use crate::video::{self, RenderSpec};

/// Maximum number of clips a single extract_clips call will produce by default.
const DEFAULT_MAX_CLIPS: usize = 50;

/// Shared state for all tools.
pub struct State {
    pub config: ServerConfig,
    pub jobs: Arc<JobManager>,
    pub transcriber: Transcriber,
}

/// Video editor MCP server.
pub struct VideoEditorServer {
    state: Arc<State>,
}

impl VideoEditorServer {
    /// Create a server from a configuration. Directory creation failures are
    /// logged; tools report precise errors if they later cannot write.
    pub fn new(config: ServerConfig) -> Self {
        if let Err(e) = config.ensure_dirs() {
            tracing::warn!("{:#}", e);
        }
        let jobs = Arc::new(JobManager::new(
            config.max_parallel_jobs,
            config.max_retained_jobs,
        ));
        let transcriber = Transcriber::new(&config);
        Self {
            state: Arc::new(State {
                config,
                jobs,
                transcriber,
            }),
        }
    }

    /// All tools as boxed trait objects.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let defs: [ToolDef; 9] = [
            (
                "video_editor/analyze",
                ANALYZE_DESC,
                analyze_schema,
                handle_analyze,
            ),
            (
                "video_editor/create_edit",
                CREATE_EDIT_DESC,
                create_edit_schema,
                handle_create_edit,
            ),
            (
                "video_editor/render",
                RENDER_DESC,
                render_schema,
                handle_render,
            ),
            (
                "video_editor/extract_clips",
                EXTRACT_DESC,
                extract_schema,
                handle_extract_clips,
            ),
            (
                "video_editor/add_captions",
                CAPTIONS_DESC,
                captions_schema,
                handle_add_captions,
            ),
            (
                "video_editor/get_video_info",
                INFO_DESC,
                info_schema,
                handle_video_info,
            ),
            (
                "video_editor/get_job_status",
                STATUS_DESC,
                job_id_schema,
                handle_job_status,
            ),
            (
                "video_editor/list_jobs",
                LIST_DESC,
                list_jobs_schema,
                handle_list_jobs,
            ),
            (
                "video_editor/cancel_job",
                CANCEL_DESC,
                job_id_schema,
                handle_cancel_job,
            ),
        ];
        defs.into_iter()
            .map(|(name, description, schema, handler)| {
                Arc::new(EditorTool {
                    name,
                    description,
                    schema,
                    handler,
                    state: Arc::clone(&self.state),
                }) as BoxedTool
            })
            .collect()
    }
}

type BoxFut = Pin<Box<dyn Future<Output = Result<ToolResult>> + Send>>;
type Handler = fn(Arc<State>, Value) -> BoxFut;

/// (name, description, schema builder, handler) for one tool.
type ToolDef = (&'static str, &'static str, fn() -> Value, Handler);

struct EditorTool {
    name: &'static str,
    description: &'static str,
    schema: fn() -> Value,
    handler: Handler,
    state: Arc<State>,
}

#[async_trait]
impl Tool for EditorTool {
    fn name(&self) -> &str {
        self.name
    }

    fn description(&self) -> &str {
        self.description
    }

    fn schema(&self) -> Value {
        (self.schema)()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        (self.handler)(Arc::clone(&self.state), args).await
    }
}

// ============================================================================
// Helpers
// ============================================================================

/// Deserialize tool arguments, mapping failures to `InvalidParameters`.
fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

/// An `isError` result whose text is `{"error": message, ...extra}`.
fn error_result(message: impl Into<String>, extra: Option<Value>) -> ToolResult {
    let mut obj = json!({ "error": message.into() });
    if let (Some(Value::Object(extra)), Value::Object(map)) = (extra, &mut obj) {
        map.extend(extra);
    }
    ToolResult {
        content: vec![Content::text(
            serde_json::to_string_pretty(&obj).unwrap_or_default(),
        )],
        is_error: true,
    }
}

/// Validate that `path` names an existing regular file.
fn input_file(path: &str) -> anyhow::Result<PathBuf> {
    let trimmed = path.trim();
    if trimmed.is_empty() {
        bail!("Empty video path");
    }
    let p = PathBuf::from(trimmed);
    if !p.is_file() {
        bail!("Video file not found: {trimmed}");
    }
    Ok(p)
}

fn input_files(paths: &[String]) -> anyhow::Result<Vec<PathBuf>> {
    if paths.is_empty() {
        bail!("No video inputs provided");
    }
    paths.iter().map(|p| input_file(p)).collect()
}

/// Reject an output path that would overwrite one of the inputs.
fn ensure_not_input(output: &Path, inputs: &[PathBuf]) -> anyhow::Result<()> {
    let out = output.canonicalize().ok();
    for i in inputs {
        if out.is_some() && i.canonicalize().ok() == out {
            bail!(
                "Output path {} would overwrite an input file",
                output.display()
            );
        }
    }
    Ok(())
}

/// Unique-ish file name suffix: UTC timestamp plus a short random id.
fn unique_suffix() -> String {
    let id = uuid::Uuid::new_v4().simple().to_string();
    format!(
        "{}_{}",
        chrono::Utc::now().format("%Y%m%d_%H%M%S"),
        &id[..8]
    )
}

fn file_stem(p: &Path) -> String {
    p.file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "video".to_string())
}

/// Run `work` as a job; in foreground mode wait and return its result.
async fn run_job<F, Fut>(
    state: &Arc<State>,
    operation: &str,
    background: bool,
    work: F,
) -> Result<ToolResult>
where
    F: FnOnce(JobContext) -> Fut + Send + 'static,
    Fut: Future<Output = anyhow::Result<Value>> + Send + 'static,
{
    let (job_id, done) = state.jobs.spawn(operation, work).await;
    if background {
        return ToolResult::json(&json!({
            "job_id": job_id,
            "status": "running",
            "message": "Job started; poll video_editor/get_job_status for progress and the result.",
        }));
    }
    let _ = done.await;
    let Some(job) = state.jobs.get_job(&job_id).await else {
        return Ok(error_result(
            "Job record disappeared",
            Some(json!({ "job_id": job_id })),
        ));
    };
    match job.status {
        JobStatus::Completed => {
            let mut result = job.result.unwrap_or(Value::Null);
            if let Value::Object(map) = &mut result {
                map.insert("job_id".into(), json!(job_id));
            }
            ToolResult::json(&result)
        },
        _ => Ok(error_result(
            job.error
                .unwrap_or_else(|| format!("Job ended with status {:?}", job.status)),
            Some(json!({ "job_id": job_id })),
        )),
    }
}

// ============================================================================
// Analysis core (shared by analyze / create_edit / render)
// ============================================================================

/// Results of analysing a set of inputs.
struct AnalysisBundle {
    per_video: Vec<VideoAnalysis>,
    tracks: Vec<Option<LevelTrack>>,
    speaker_turns: Vec<SpeakerTurn>,
    speakers: Vec<Speaker>,
    warnings: Vec<String>,
}

async fn analyze_videos(
    state: &State,
    inputs: &[String],
    paths: &[PathBuf],
    opts: &AnalysisOptions,
    silence_threshold: f64,
    speaker_switch_delay: f64,
    ctx: &JobContext,
) -> anyhow::Result<AnalysisBundle> {
    if !(opts.scene_threshold > 0.0 && opts.scene_threshold <= 1.0) {
        bail!("analysis_options.scene_threshold must be in (0, 1]");
    }
    if let Some(lang) = &opts.language {
        audio::validate_language(lang)?;
    }
    let cfg = &state.config;
    let n = paths.len();
    let mut per_video = Vec::with_capacity(n);
    let mut tracks: Vec<Option<LevelTrack>> = Vec::with_capacity(n);
    let mut warnings = Vec::new();

    for (i, (name, path)) in inputs.iter().zip(paths).enumerate() {
        let base = (i * 90 / n) as u32;
        let step = |k: u32| base + k * (90 / n as u32) / 4;
        ctx.progress(step(0), &format!("probing {name}")).await;
        let info = ffmpeg::probe(path).await?;
        let mut a = VideoAnalysis::new(name, info.file_size);
        a.video_info = Some(info.clone());

        let mut track = None;
        if info.has_audio {
            ctx.progress(step(1), &format!("analysing audio of {name}"))
                .await;
            let wav = audio::extract_audio(path, &cfg.temp_dir).await?;
            let wav_path = wav.to_path_buf();
            let t = tokio::task::spawn_blocking(move || {
                audio::read_wav_levels(&wav_path, audio::LEVEL_WINDOW_SECS)
            })
            .await
            .context("audio analysis task failed")??;
            a.audio_analysis = Some(audio::analyze_levels(&t, cfg.silence_db, silence_threshold));
            track = Some(t);

            if opts.transcribe {
                ctx.progress(step(2), &format!("transcribing {name}")).await;
                match state
                    .transcriber
                    .transcribe(path, &wav, opts.language.as_deref())
                    .await
                {
                    Ok(t) => a.transcript = Some(t),
                    Err(e) => a.warnings.push(format!("Transcription unavailable: {e:#}")),
                }
            }
        } else {
            a.warnings
                .push("No audio stream: audio analysis and transcription skipped".into());
        }

        if opts.detect_scenes && info.has_video {
            ctx.progress(step(3), &format!("detecting scenes in {name}"))
                .await;
            match video::detect_scene_changes(path, opts.scene_threshold).await {
                Ok(s) => a.scene_changes = Some(s),
                Err(e) => a.warnings.push(format!("Scene detection failed: {e:#}")),
            }
        }
        per_video.push(a);
        tracks.push(track);
    }

    let mut speaker_turns = Vec::new();
    let mut speakers = Vec::new();
    if opts.identify_speakers {
        if n < 2 {
            warnings.push(
                "Speaker identification needs one time-synced video per speaker (energy-based \
                 detection); single-file diarization is not available."
                    .into(),
            );
        } else if tracks.iter().all(Option::is_some) {
            let ts: Vec<LevelTrack> = tracks.iter().flatten().cloned().collect();
            speaker_turns = audio::detect_speaker_turns(&ts, cfg.silence_db, speaker_switch_delay);
            speakers = audio::summarize_speakers(&speaker_turns, inputs);
            for (i, a) in per_video.iter_mut().enumerate() {
                a.speakers = speakers.get(i).cloned().map(|s| vec![s]);
                if let Some(t) = &a.transcript {
                    a.segments_with_speakers = Some(label_segments(&t.segments, &speaker_turns));
                }
            }
        } else {
            warnings
                .push("Speaker identification skipped: every input needs an audio track".into());
        }
    }

    for a in &mut per_video {
        if opts.extract_highlights {
            let h = edl::extract_highlights(a);
            if !h.is_empty() {
                a.highlights = Some(h);
            }
        }
        let s = edl::generate_edit_suggestions(a, silence_threshold);
        if !s.is_empty() {
            a.suggested_edits = Some(s);
        }
    }

    Ok(AnalysisBundle {
        per_video,
        tracks,
        speaker_turns,
        speakers,
        warnings,
    })
}

/// Attach the speaker with the greatest overlap to each transcript segment.
fn label_segments(
    segments: &[TranscriptSegment],
    turns: &[SpeakerTurn],
) -> Vec<TranscriptSegmentWithSpeaker> {
    segments
        .iter()
        .map(|s| {
            let speaker = turns
                .iter()
                .map(|t| (t, (s.end.min(t.end) - s.start.max(t.start)).max(0.0)))
                .filter(|(_, o)| *o > 0.0)
                .max_by(|a, b| a.1.total_cmp(&b.1))
                .map(|(t, _)| t.speaker.clone());
            TranscriptSegmentWithSpeaker {
                id: s.id,
                start: s.start,
                end: s.end,
                text: s.text.clone(),
                speaker,
            }
        })
        .collect()
}

/// Generated edit plus context for the response.
struct EditOutcome {
    plan: edl::EdlPlan,
    rules: EditingRules,
    warnings: Vec<String>,
}

async fn build_edit(
    state: &State,
    inputs: &[String],
    paths: &[PathBuf],
    rules: EditingRules,
    mapping: Option<&HashMap<String, String>>,
    ctx: &JobContext,
) -> anyhow::Result<EditOutcome> {
    if let Some(m) = mapping {
        for (spk, src) in m {
            input_file(src).with_context(|| format!("speaker_mapping[{spk}]"))?;
        }
    }
    let multi_cam = paths.len() > 1 && rules.switch_on_speaker;
    let opts = AnalysisOptions {
        transcribe: rules.zoom_on_emphasis,
        identify_speakers: multi_cam,
        detect_scenes: !multi_cam,
        extract_highlights: rules.zoom_on_emphasis,
        ..AnalysisOptions::default()
    };
    let bundle = analyze_videos(
        state,
        inputs,
        paths,
        &opts,
        rules.silence_threshold,
        rules.speaker_switch_delay,
        ctx,
    )
    .await?;
    let mut warnings = bundle.warnings.clone();
    for a in &bundle.per_video {
        warnings.extend(a.warnings.iter().map(|w| format!("{}: {w}", a.file)));
    }

    let timeline = bundle
        .per_video
        .iter()
        .filter_map(|a| a.video_info.as_ref().map(|i| i.duration))
        .filter(|d| *d > 0.0)
        .fold(f64::INFINITY, f64::min);
    let timeline = if timeline.is_finite() { timeline } else { 0.0 };
    if timeline <= 0.0 {
        bail!("Could not determine the duration of the input video(s)");
    }

    let silence: Vec<(f64, f64)> = if paths.len() > 1 {
        if bundle.tracks.iter().all(Option::is_some) {
            let ts: Vec<LevelTrack> = bundle.tracks.iter().flatten().cloned().collect();
            audio::combine_tracks_max(&ts)
                .map(|c| {
                    audio::detect_silence(&c, state.config.silence_db, rules.silence_threshold)
                })
                .unwrap_or_default()
        } else {
            Vec::new()
        }
    } else {
        bundle.per_video[0]
            .audio_analysis
            .as_ref()
            .map(|a| a.silence_segments.clone())
            .unwrap_or_default()
    };
    let primary = &bundle.per_video[0];
    let scenes = primary.scene_changes.clone().unwrap_or_default();
    let highlights: Vec<f64> = primary
        .highlights
        .as_ref()
        .map(|h| h.iter().map(|h| h.time).collect())
        .unwrap_or_default();

    let plan = edl::generate_edl(
        &EdlInputs {
            video_inputs: inputs,
            timeline_duration: timeline,
            speaker_turns: &bundle.speaker_turns,
            scene_changes: &scenes,
            silence: &silence,
            highlights: &highlights,
            speaker_mapping: mapping,
        },
        &rules,
    );
    if plan.decisions.is_empty() {
        bail!(
            "Edit is empty (the whole timeline was classified as silence?). Try remove_silence=false."
        );
    }
    Ok(EditOutcome {
        plan,
        rules,
        warnings,
    })
}

// ============================================================================
// Tool: video_editor/analyze
// ============================================================================

const ANALYZE_DESC: &str = "Analyze one or more videos without rendering.

Per video: media info (ffprobe), Whisper transcription with timestamps (if the whisper CLI is
installed), audio loudness analysis (silences, volume profile, peaks), scene-change detection,
highlights and edit suggestions. With two or more time-synced inputs (one camera/mic per
speaker), speakers are identified by comparing audio energy across inputs. Non-fatal problems
are reported in per-video `warnings`.";

fn analyze_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "video_inputs": {"type": "array", "items": {"type": "string"}, "minItems": 1,
                "description": "Video file paths to analyze"},
            "analysis_options": {
                "type": "object",
                "properties": {
                    "transcribe": {"type": "boolean", "default": true},
                    "identify_speakers": {"type": "boolean", "default": true,
                        "description": "Energy-based; needs >= 2 time-synced inputs"},
                    "detect_scenes": {"type": "boolean", "default": true},
                    "extract_highlights": {"type": "boolean", "default": true},
                    "scene_threshold": {"type": "number", "default": 0.3, "exclusiveMinimum": 0, "maximum": 1,
                        "description": "Scene-change sensitivity (lower = more cuts)"},
                    "language": {"type": "string", "description": "Transcription language hint, e.g. 'en'"}
                },
                "description": "Which analyses to perform"
            },
            "background": {"type": "boolean", "default": false,
                "description": "Return a job_id immediately instead of waiting"}
        },
        "required": ["video_inputs"]
    })
}

fn handle_analyze(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: AnalyzeArgs = parse_args(args)?;
        let paths = match input_files(&args.video_inputs) {
            Ok(p) => p,
            Err(e) => return Ok(error_result(e.to_string(), None)),
        };
        let opts = args.analysis_options.unwrap_or_default();
        let inputs = args.video_inputs.clone();
        info!("Analyzing {} video(s)", inputs.len());
        let st = Arc::clone(&state);
        run_job(&state, "analyze", args.background, move |ctx| async move {
            let cfg = &st.config;
            let bundle = analyze_videos(
                &st,
                &inputs,
                &paths,
                &opts,
                cfg.silence_threshold,
                cfg.speaker_switch_delay,
                &ctx,
            )
            .await?;
            let analysis: serde_json::Map<String, Value> = bundle
                .per_video
                .iter()
                .map(|a| (a.file.clone(), json!(a)))
                .collect();
            let mut response = json!({ "video_inputs": inputs, "analysis": analysis });
            if !bundle.speaker_turns.is_empty() {
                response["speaker_activity"] = json!({
                    "method": "audio_energy",
                    "speakers": bundle.speakers,
                    "turns": bundle.speaker_turns,
                });
            }
            if !bundle.warnings.is_empty() {
                response["warnings"] = json!(bundle.warnings);
            }
            Ok(response)
        })
        .await
    })
}

// ============================================================================
// Tool: video_editor/create_edit
// ============================================================================

const CREATE_EDIT_DESC: &str = "Generate an edit decision list (EDL) without rendering.

Inputs are treated as time-synced angles of the same recording. Shots come from speaker turns
(>= 2 inputs, energy-based), otherwise scene changes, otherwise fixed 10s rotation (multiple
inputs) or the whole video (single input). Silences longer than silence_threshold are cut,
highlights get a zoom_in effect, source changes get the configured transition, and PiP is
added when picture_in_picture='always'. The EDL is saved as JSON and can be edited and passed
to video_editor/render.";

fn editing_rules_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "switch_on_speaker": {"type": "boolean", "default": true},
            "speaker_switch_delay": {"type": "number", "default": 0.5,
                "description": "Minimum seconds a speaker must talk before the edit switches"},
            "picture_in_picture": {"type": "string", "enum": ["auto", "always", "never"], "default": "auto",
                "description": "'always' overlays another input in the corner; 'auto' currently means never"},
            "zoom_on_emphasis": {"type": "boolean", "default": true},
            "remove_silence": {"type": "boolean", "default": true},
            "silence_threshold": {"type": "number", "default": 2.0,
                "description": "Minimum silence length (seconds) to cut"},
            "pip_size": {"type": "number", "default": 0.25, "minimum": 0.05, "maximum": 0.9},
            "transition_type": {"type": "string", "default": "cross_dissolve",
                "description": "Transition on source changes: cut, cross_dissolve, fade, dissolve, fadeblack, fadewhite, wipeleft, wiperight, wipeup, wipedown, slideleft, slideright, circleopen, circleclose"},
            "transition_duration": {"type": "number", "default": 0.5, "minimum": 0, "maximum": 5}
        },
        "description": "Rules controlling automatic editing decisions"
    })
}

fn create_edit_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "video_inputs": {"type": "array", "items": {"type": "string"}, "minItems": 1,
                "description": "Video file paths (time-synced angles; first is primary)"},
            "editing_rules": editing_rules_schema(),
            "speaker_mapping": {"type": "object", "additionalProperties": {"type": "string"},
                "description": "Override which video to show per speaker ID (e.g. {\"SPEAKER_00\": \"/v/wide.mp4\"})"},
            "background": {"type": "boolean", "default": false}
        },
        "required": ["video_inputs"]
    })
}

fn handle_create_edit(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: CreateEditArgs = parse_args(args)?;
        let paths = match input_files(&args.video_inputs) {
            Ok(p) => p,
            Err(e) => return Ok(error_result(e.to_string(), None)),
        };
        let rules = edl::resolve_rules(args.editing_rules, &state.config)
            .map_err(MCPError::InvalidParameters)?;
        let inputs = args.video_inputs.clone();
        let mapping = args.speaker_mapping;
        let st = Arc::clone(&state);
        run_job(
            &state,
            "create_edit",
            args.background,
            move |ctx| async move {
                let outcome =
                    build_edit(&st, &inputs, &paths, rules, mapping.as_ref(), &ctx).await?;
                let edl_path = st
                    .config
                    .edl_dir()
                    .join(format!("edit_{}.json", unique_suffix()));
                std::fs::create_dir_all(st.config.edl_dir())?;
                std::fs::write(
                    &edl_path,
                    serde_json::to_string_pretty(&outcome.plan.decisions)?,
                )
                .with_context(|| format!("Failed to write {}", edl_path.display()))?;
                let estimated: f64 = outcome.plan.decisions.iter().map(|d| d.duration).sum();
                let mut response = json!({
                    "edit_decision_list": outcome.plan.decisions,
                    "estimated_duration": (estimated * 1000.0).round() / 1000.0,
                    "edl_file": edl_path.to_string_lossy(),
                    "video_inputs": inputs,
                    "editing_rules": outcome.rules,
                    "strategy": outcome.plan.strategy,
                    "silence_removed": outcome.plan.silence_removed,
                });
                if !outcome.warnings.is_empty() {
                    response["warnings"] = json!(outcome.warnings);
                }
                Ok(response)
            },
        )
        .await
    })
}

// ============================================================================
// Tool: video_editor/render
// ============================================================================

const RENDER_DESC: &str =
    "Render a video from an edit decision list (or generate one automatically).

Each decision is encoded to the target resolution/fps (letterboxed, aspect preserved), with
zoom_in and picture-in-picture applied, then joined: losslessly when there are no transitions,
or with xfade/acrossfade cross-fades otherwise. Uses NVENC when hardware_acceleration is on and
a working GPU encoder is detected, else libx264 (libvpx-vp9 for webm). Outputs must be under
the configured output directory. add_captions transcribes the result and burns in captions.
Set background=true for long renders and poll video_editor/get_job_status.";

fn render_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "video_inputs": {"type": "array", "items": {"type": "string"}, "minItems": 1,
                "description": "Video file paths (used to generate an EDL when none is given)"},
            "edit_decision_list": {
                "type": "array",
                "description": "EDL from create_edit (optional - generated if omitted)",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "number", "description": "In-point in the source (s)"},
                        "duration": {"type": "number"},
                        "source": {"type": "string"},
                        "action": {"type": "string"},
                        "transition_type": {"type": "string"},
                        "transition_duration": {"type": "number"},
                        "effects": {"type": "array", "items": {"type": "string", "enum": ["zoom_in"]}},
                        "pip_source": {"type": "string"},
                        "pip_size": {"type": "number"}
                    },
                    "required": ["timestamp", "duration", "source"]
                }
            },
            "output_settings": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["mp4", "mov", "mkv", "webm"], "default": "mp4"},
                    "resolution": {"type": "string", "default": "1920x1080"},
                    "fps": {"type": "integer", "default": 30, "minimum": 1, "maximum": 240},
                    "bitrate": {"type": "string", "default": "8M"},
                    "codec": {"type": "string", "enum": ffmpeg::ALLOWED_VIDEO_CODECS,
                        "description": "Force a video encoder (default: auto)"},
                    "output_path": {"type": "string",
                        "description": "Output file; relative paths resolve under the output directory"}
                }
            },
            "render_options": {
                "type": "object",
                "properties": {
                    "hardware_acceleration": {"type": "boolean", "default": true},
                    "preview_mode": {"type": "boolean", "default": false,
                        "description": "Fast low-res render (640x360, 15fps, 2M)"},
                    "add_captions": {"type": "boolean", "default": false},
                    "add_speaker_labels": {"type": "boolean", "default": false,
                        "description": "Not supported yet; ignored with a warning"}
                }
            },
            "editing_rules": editing_rules_schema(),
            "speaker_mapping": {"type": "object", "additionalProperties": {"type": "string"}},
            "background": {"type": "boolean", "default": false}
        },
        "required": ["video_inputs"]
    })
}

fn handle_render(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: RenderArgs = parse_args(args)?;
        match prepare_render(&state, args) {
            Ok((prep, background)) => {
                let st = Arc::clone(&state);
                run_job(&state, "render", background, move |ctx| {
                    render_job(st, prep, ctx)
                })
                .await
            },
            Err(e) => Ok(error_result(format!("{e:#}"), None)),
        }
    })
}

struct RenderPrep {
    inputs: Vec<String>,
    paths: Vec<PathBuf>,
    edl: Option<Vec<EditDecision>>,
    rules: EditingRules,
    mapping: Option<HashMap<String, String>>,
    settings: OutputSettings,
    options: RenderOptions,
    container: Container,
    output: PathBuf,
    size: (u32, u32),
}

fn prepare_render(state: &State, args: RenderArgs) -> anyhow::Result<(RenderPrep, bool)> {
    let cfg = &state.config;
    let paths = input_files(&args.video_inputs)?;
    let mut settings = args.output_settings.unwrap_or_default();
    let options = args.render_options.unwrap_or_default();
    if options.preview_mode {
        settings.resolution = "640x360".into();
        settings.bitrate = "2M".into();
        settings.fps = 15;
    }
    let size = ffmpeg::parse_resolution(&settings.resolution)?;
    ffmpeg::validate_bitrate(&settings.bitrate)?;
    if !(1..=240).contains(&settings.fps) {
        bail!("fps must be between 1 and 240");
    }
    let requested_container = Container::parse(&settings.format)?;
    let container = settings
        .output_path
        .as_deref()
        .and_then(|p| Container::from_path(Path::new(p)))
        .unwrap_or(requested_container);
    if let Some(codec) = &settings.codec {
        ffmpeg::validate_codec(codec, container)?;
    }
    let output = cfg.resolve_output_path(
        settings.output_path.as_deref(),
        &cfg.renders_dir(),
        &format!("rendered_{}.{}", unique_suffix(), container.extension()),
    )?;
    let mut all_inputs = paths.clone();
    if let Some(edl) = &args.edit_decision_list {
        video::validate_edl(edl)?;
        for (i, d) in edl.iter().enumerate() {
            all_inputs.push(input_file(&d.source).with_context(|| format!("Decision {i} source"))?);
            if let Some(p) = &d.pip_source {
                all_inputs.push(input_file(p).with_context(|| format!("Decision {i} pip_source"))?);
            }
        }
    }
    ensure_not_input(&output, &all_inputs)?;
    if options.add_captions {
        state.transcriber.whisper_path()?;
    }
    let rules = edl::resolve_rules(args.editing_rules, cfg).map_err(anyhow::Error::msg)?;
    Ok((
        RenderPrep {
            inputs: args.video_inputs,
            paths,
            edl: args.edit_decision_list,
            rules,
            mapping: args.speaker_mapping,
            settings,
            options,
            container,
            output,
            size,
        },
        args.background,
    ))
}

async fn render_job(st: Arc<State>, prep: RenderPrep, ctx: JobContext) -> anyhow::Result<Value> {
    let cfg = &st.config;
    let mut warnings = Vec::new();
    let generated = prep.edl.is_none();
    let edl = match prep.edl {
        Some(edl) => edl,
        None => {
            ctx.progress(2, "generating edit decision list").await;
            let outcome = build_edit(
                &st,
                &prep.inputs,
                &prep.paths,
                prep.rules.clone(),
                prep.mapping.as_ref(),
                &ctx,
            )
            .await?;
            warnings.extend(outcome.warnings);
            outcome.plan.decisions
        },
    };
    if prep.options.add_speaker_labels {
        warnings.push("add_speaker_labels is not supported yet and was ignored".into());
    }

    let allow_hw = prep.options.hardware_acceleration && cfg.enable_gpu;
    let codec =
        ffmpeg::select_codec(prep.settings.codec.as_deref(), prep.container, allow_hw).await?;
    let spec = RenderSpec {
        width: prep.size.0,
        height: prep.size.1,
        fps: prep.settings.fps,
        bitrate: prep.settings.bitrate.clone(),
        codec,
        container: prep.container,
        fast: prep.options.preview_mode,
        default_transition: prep.rules.transition_duration,
        zoom_factor: cfg.zoom_factor,
    };

    let mut result = if prep.options.add_captions {
        let work = tempfile::Builder::new()
            .prefix("render_cap_")
            .tempdir_in(&cfg.temp_dir)?;
        let raw = work
            .path()
            .join(format!("uncaptioned.{}", prep.container.extension()));
        let mut r = video::render_edl(&edl, &spec, &raw, &cfg.temp_dir, Some(&ctx)).await?;
        ctx.progress(92, "captioning").await;
        let srt = prep.output.with_extension("srt");
        let count = caption_file(
            &st,
            &raw,
            &prep.output,
            &srt,
            &CaptionStyle::default(),
            None,
            true,
        )
        .await?;
        let info = ffmpeg::probe(&prep.output).await?;
        r.output_path = prep.output.to_string_lossy().to_string();
        r.file_size = info.file_size;
        r.warnings.push(format!(
            "{count} captions burned in; SRT saved to {}",
            srt.display()
        ));
        r
    } else {
        video::render_edl(&edl, &spec, &prep.output, &cfg.temp_dir, Some(&ctx)).await?
    };
    result.warnings.extend(warnings);
    let mut value = serde_json::to_value(&result)?;
    value["edl_generated"] = json!(generated);
    Ok(value)
}

// ============================================================================
// Tool: video_editor/extract_clips
// ============================================================================

const EXTRACT_DESC: &str =
    "Create short clips from a video by time range and/or transcript keyword.

time_ranges are [start, end] pairs in seconds. keywords are matched case-insensitively against
the Whisper transcript (requires the whisper CLI); each matching segment becomes a clip. Clips
are padded, extended to min_clip_length and truncated to max_clip_length; overlapping keyword
matches are merged. Clips are re-encoded for frame-accurate cuts unless stream_copy=true.
Speaker-based extraction is not available (no diarization backend).";

fn extract_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "video_input": {"type": "string", "description": "Path to the source video"},
            "extraction_criteria": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"},
                        "description": "Keywords/phrases to find in the transcript"},
                    "speakers": {"type": "array", "items": {"type": "string"},
                        "description": "Not supported (no diarization); reported as a warning"},
                    "time_ranges": {"type": "array",
                        "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                        "description": "List of [start, end] pairs in seconds"},
                    "min_clip_length": {"type": "number", "default": 3.0},
                    "max_clip_length": {"type": "number", "default": 60.0},
                    "padding": {"type": "number", "default": 0.5}
                }
            },
            "output_dir": {"type": "string",
                "description": "Directory for clips (relative paths resolve under the output directory)"},
            "stream_copy": {"type": "boolean", "default": false,
                "description": "Copy streams instead of re-encoding (fast, keyframe-aligned cuts)"},
            "max_clips": {"type": "integer", "default": DEFAULT_MAX_CLIPS, "minimum": 1},
            "background": {"type": "boolean", "default": false}
        },
        "required": ["video_input"]
    })
}

/// A planned clip range.
#[derive(Debug, Clone, PartialEq)]
struct ClipPlan {
    start: f64,
    end: f64,
    criteria: &'static str,
    keyword: Option<String>,
    text: Option<String>,
}

/// Validate extraction criteria numbers.
fn validate_criteria(c: &ExtractionCriteria) -> anyhow::Result<()> {
    let non_negative = |v: f64| v.is_finite() && v >= 0.0;
    let valid = non_negative(c.padding)
        && non_negative(c.min_clip_length)
        && c.max_clip_length.is_finite()
        && c.max_clip_length > 0.0;
    if !valid {
        bail!("padding/min_clip_length must be >= 0 and max_clip_length > 0");
    }
    if c.min_clip_length > c.max_clip_length {
        bail!(
            "min_clip_length ({}) exceeds max_clip_length ({})",
            c.min_clip_length,
            c.max_clip_length
        );
    }
    for (i, (s, e)) in c.time_ranges.iter().enumerate() {
        if !(s.is_finite() && e.is_finite() && *s >= 0.0 && e > s) {
            bail!("time_ranges[{i}] must satisfy 0 <= start < end");
        }
    }
    Ok(())
}

/// Pad, extend to the minimum, clamp to the video and truncate to the maximum.
fn shape_range(start: f64, end: f64, c: &ExtractionCriteria, duration: f64) -> Option<(f64, f64)> {
    let limit = if duration > 0.0 {
        duration
    } else {
        f64::INFINITY
    };
    let mut s = (start - c.padding).max(0.0);
    let mut e = (end + c.padding).min(limit);
    if e - s < c.min_clip_length {
        let grow = (c.min_clip_length - (e - s)) / 2.0;
        s = (s - grow).max(0.0);
        e = (s + c.min_clip_length).min(limit);
        s = (e - c.min_clip_length).max(0.0);
    }
    if e - s > c.max_clip_length {
        e = s + c.max_clip_length;
    }
    let (s, e) = ((s * 1000.0).round() / 1000.0, (e * 1000.0).round() / 1000.0);
    (e - s >= 0.1).then_some((s, e))
}

/// Plan clips from time ranges and keyword matches.
fn plan_clips(
    c: &ExtractionCriteria,
    transcript: Option<&Transcript>,
    duration: f64,
) -> Vec<ClipPlan> {
    let mut plans = Vec::new();
    for &(s, e) in &c.time_ranges {
        if s >= duration && duration > 0.0 {
            continue;
        }
        if let Some((s, e)) = shape_range(s, e, c, duration) {
            plans.push(ClipPlan {
                start: s,
                end: e,
                criteria: "time_range",
                keyword: None,
                text: None,
            });
        }
    }
    if let Some(t) = transcript {
        let keywords: Vec<(String, String)> = c
            .keywords
            .iter()
            .map(|k| (k.clone(), k.trim().to_lowercase()))
            .filter(|(_, k)| !k.is_empty())
            .collect();
        let mut kw_plans: Vec<ClipPlan> = Vec::new();
        for seg in &t.segments {
            let lower = seg.text.to_lowercase();
            let Some((orig, _)) = keywords.iter().find(|(_, k)| lower.contains(k.as_str())) else {
                continue;
            };
            let Some((s, e)) = shape_range(seg.start, seg.end, c, duration) else {
                continue;
            };
            match kw_plans.last_mut() {
                // Merge overlapping keyword matches (respecting the max length).
                Some(last) if s <= last.end && e - last.start <= c.max_clip_length => {
                    last.end = last.end.max(e);
                    if let Some(text) = &mut last.text {
                        text.push(' ');
                        text.push_str(seg.text.trim());
                    }
                },
                _ => kw_plans.push(ClipPlan {
                    start: s,
                    end: e,
                    criteria: "keyword",
                    keyword: Some(orig.clone()),
                    text: Some(seg.text.trim().to_string()),
                }),
            }
        }
        plans.extend(kw_plans);
    }
    plans
}

fn handle_extract_clips(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: ExtractClipsArgs = parse_args(args)?;
        let cfg = &state.config;
        let prep = (|| -> anyhow::Result<_> {
            let path = input_file(&args.video_input)?;
            let criteria = args.extraction_criteria.clone().unwrap_or_default();
            validate_criteria(&criteria)?;
            let out_dir = cfg.resolve_output_dir(args.output_dir.as_deref(), &cfg.clips_dir())?;
            if criteria.time_ranges.is_empty()
                && criteria.keywords.is_empty()
                && criteria.speakers.is_empty()
            {
                bail!("extraction_criteria needs at least one of time_ranges or keywords");
            }
            if criteria.time_ranges.is_empty() && !criteria.keywords.is_empty() {
                state.transcriber.whisper_path()?;
            }
            Ok((path, criteria, out_dir))
        })();
        let (path, criteria, out_dir) = match prep {
            Ok(p) => p,
            Err(e) => return Ok(error_result(format!("{e:#}"), None)),
        };
        let max_clips = args.max_clips.unwrap_or(DEFAULT_MAX_CLIPS).max(1);
        let video_input = args.video_input.clone();
        let stream_copy = args.stream_copy;
        let st = Arc::clone(&state);
        run_job(
            &state,
            "extract_clips",
            args.background,
            move |ctx| async move {
                let mut warnings = Vec::new();
                let info = ffmpeg::probe(&path).await?;
                if !criteria.speakers.is_empty() {
                    warnings.push(
                        "Speaker-based extraction is not available (no single-file diarization); \
                     'speakers' was ignored"
                            .to_string(),
                    );
                }
                let transcript = if criteria.keywords.is_empty() {
                    None
                } else if !info.has_audio {
                    warnings.push("Video has no audio; keyword search skipped".into());
                    None
                } else {
                    ctx.progress(5, "transcribing for keyword search").await;
                    let wav = audio::extract_audio(&path, &st.config.temp_dir).await?;
                    match st.transcriber.transcribe(&path, &wav, None).await {
                        Ok(t) => Some(t),
                        Err(e) => {
                            warnings.push(format!("Keyword search skipped: {e:#}"));
                            None
                        },
                    }
                };

                let mut plans = plan_clips(&criteria, transcript.as_ref(), info.duration);
                if plans.len() > max_clips {
                    warnings.push(format!(
                        "{} clips matched; only the first {max_clips} were extracted",
                        plans.len()
                    ));
                    plans.truncate(max_clips);
                }
                let stem = file_stem(&path);
                let mut clips = Vec::new();
                let mut failed = Vec::new();
                let total = plans.len().max(1);
                for (i, p) in plans.into_iter().enumerate() {
                    ctx.progress(
                        20 + (i * 75 / total) as u32,
                        &format!("extracting clip {}", i + 1),
                    )
                    .await;
                    let out = out_dir.join(format!(
                        "{stem}_clip_{:02}_{}_{:.1}-{:.1}.mp4",
                        i + 1,
                        p.criteria,
                        p.start,
                        p.end
                    ));
                    match video::extract_clip(&path, p.start, p.end, &out, stream_copy).await {
                        Ok(()) => clips.push(ExtractedClip {
                            output_path: out.to_string_lossy().to_string(),
                            start_time: p.start,
                            end_time: p.end,
                            duration: ((p.end - p.start) * 1000.0).round() / 1000.0,
                            criteria: p.criteria.to_string(),
                            keyword: p.keyword,
                            speaker: None,
                            text: p.text,
                        }),
                        Err(e) => failed.push(
                            json!({"start": p.start, "end": p.end, "error": format!("{e:#}")}),
                        ),
                    }
                }
                let mut response = json!({
                    "video_input": video_input,
                    "clips_extracted": clips,
                    "total_clips": clips.len(),
                    "output_directory": out_dir.to_string_lossy(),
                });
                if !failed.is_empty() {
                    response["failed_clips"] = json!(failed);
                }
                if !warnings.is_empty() {
                    response["warnings"] = json!(warnings);
                }
                Ok(response)
            },
        )
        .await
    })
}

// ============================================================================
// Tool: video_editor/add_captions
// ============================================================================

const CAPTIONS_DESC: &str = "Transcribe a video with Whisper and add captions.

By default captions are burned in (re-encoded) using caption_style: font, pixel size, text
colour, background box colour (or 'none' for an outline), position (bottom/middle/top) and
line wrapping at max_chars_per_line (long segments are split into several captions). With
burn_in=false the SRT is muxed as a selectable subtitle track without re-encoding. One output
per language; the SRT file is saved next to each output. Requires the whisper CLI.";

fn captions_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "video_input": {"type": "string", "description": "Path to the video file"},
            "caption_style": {
                "type": "object",
                "properties": {
                    "font": {"type": "string", "default": "Arial"},
                    "size": {"type": "integer", "default": 42, "description": "Font size in video pixels"},
                    "color": {"type": "string", "default": "#FFFFFF", "description": "#RRGGBB or #RRGGBBAA"},
                    "background": {"type": "string", "default": "#000000",
                        "description": "#RRGGBB[AA] box colour, or 'none'"},
                    "position": {"type": "string", "enum": ["bottom", "middle", "top"], "default": "bottom"},
                    "max_chars_per_line": {"type": "integer", "default": 40},
                    "display_speaker_names": {"type": "boolean", "default": true,
                        "description": "Only has an effect when speaker labels are known (not for single files)"}
                }
            },
            "languages": {"type": "array", "items": {"type": "string"}, "default": ["en"],
                "description": "Languages to transcribe (Whisper language codes)"},
            "output_path": {"type": "string",
                "description": "Output video path (relative paths resolve under the output directory)"},
            "burn_in": {"type": "boolean", "default": true,
                "description": "false = add a soft subtitle track instead of re-encoding"},
            "background": {"type": "boolean", "default": false}
        },
        "required": ["video_input"]
    })
}

/// Transcribe `video`, write `srt`, and produce `output` with captions.
/// Returns the number of captions.
async fn caption_file(
    st: &State,
    video: &Path,
    output: &Path,
    srt: &Path,
    style: &CaptionStyle,
    language: Option<&str>,
    burn_in: bool,
) -> anyhow::Result<usize> {
    let info = ffmpeg::probe(video).await?;
    if !info.has_audio {
        bail!("{} has no audio track to transcribe", video.display());
    }
    let wav = audio::extract_audio(video, &st.config.temp_dir).await?;
    let transcript = st.transcriber.transcribe(video, &wav, language).await?;
    drop(wav);
    let segments: Vec<TranscriptSegmentWithSpeaker> = transcript
        .segments
        .iter()
        .map(|s| TranscriptSegmentWithSpeaker {
            id: s.id,
            start: s.start,
            end: s.end,
            text: s.text.clone(),
            speaker: None,
        })
        .collect();
    let cues = captions::build_cues(
        &segments,
        style.max_chars_per_line.max(8) as usize,
        style.display_speaker_names,
    );
    if cues.is_empty() {
        bail!(
            "No speech detected in {}; nothing to caption",
            video.display()
        );
    }
    std::fs::write(srt, captions::render_srt(&cues))
        .with_context(|| format!("Failed to write {}", srt.display()))?;
    if burn_in {
        let fs = captions::force_style(style, info.height)?;
        video::burn_subtitles(video, srt, &fs, output).await?;
    } else {
        video::mux_subtitles(video, srt, output, language).await?;
    }
    Ok(cues.len())
}

fn handle_add_captions(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: AddCaptionsArgs = parse_args(args)?;
        let cfg = &state.config;
        let style = args.caption_style.clone().unwrap_or_default();
        let languages = args
            .languages
            .clone()
            .filter(|l| !l.is_empty())
            .unwrap_or_else(|| vec!["en".to_string()]);
        let prep = (|| -> anyhow::Result<_> {
            let path = input_file(&args.video_input)?;
            for l in &languages {
                audio::validate_language(l)?;
            }
            // Validate style up front (height only affects the size scaling).
            captions::force_style(&style, 1080)?;
            state.transcriber.whisper_path()?;
            let stem = file_stem(&path);
            let base = cfg.resolve_output_path(
                args.output_path.as_deref(),
                &cfg.renders_dir(),
                &format!("captioned_{stem}.mp4"),
            )?;
            let container = Container::from_path(&base).unwrap_or(Container::Mp4);
            let base = base.with_extension(container.extension());
            let mut outputs = Vec::new();
            for lang in &languages {
                let out = if languages.len() > 1 {
                    base.with_file_name(format!(
                        "{}_{lang}.{}",
                        file_stem(&base),
                        container.extension()
                    ))
                } else {
                    base.clone()
                };
                ensure_not_input(&out, std::slice::from_ref(&path))?;
                outputs.push((lang.clone(), out));
            }
            Ok((path, outputs))
        })();
        let (path, outputs) = match prep {
            Ok(p) => p,
            Err(e) => return Ok(error_result(format!("{e:#}"), None)),
        };
        let video_input = args.video_input.clone();
        let burn_in = args.burn_in;
        let st = Arc::clone(&state);
        run_job(
            &state,
            "add_captions",
            args.background,
            move |ctx| async move {
                let mut results = Vec::new();
                let total = outputs.len() as u32;
                for (i, (lang, out)) in outputs.iter().enumerate() {
                    ctx.progress(5 + i as u32 * 90 / total, &format!("captioning ({lang})"))
                        .await;
                    let srt = out.with_extension("srt");
                    let count =
                        caption_file(&st, &path, out, &srt, &style, Some(lang), burn_in).await?;
                    results.push(json!({
                        "language": lang,
                        "output_path": out.to_string_lossy(),
                        "srt_path": srt.to_string_lossy(),
                        "caption_count": count,
                        "burned_in": burn_in,
                    }));
                }
                Ok(json!({ "video_input": video_input, "languages_processed": results }))
            },
        )
        .await
    })
}

// ============================================================================
// Small tools: get_video_info / get_job_status / list_jobs / cancel_job
// ============================================================================

const INFO_DESC: &str = "Get media information for a video (duration, resolution, fps, codecs, audio presence, size, bitrate) via ffprobe.";

fn info_schema() -> Value {
    json!({
        "type": "object",
        "properties": {"video_input": {"type": "string", "description": "Path to the video file"}},
        "required": ["video_input"]
    })
}

fn handle_video_info(_state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: VideoInfoArgs = parse_args(args)?;
        let result = async {
            let path = input_file(&args.video_input)?;
            ffmpeg::probe(&path).await
        }
        .await;
        match result {
            Ok(info) => ToolResult::json(&json!({ "video_input": args.video_input, "info": info })),
            Err(e) => Ok(error_result(format!("{e:#}"), None)),
        }
    })
}

const STATUS_DESC: &str =
    "Get the status, progress, stage and (when finished) result or error of a job.";

fn job_id_schema() -> Value {
    json!({
        "type": "object",
        "properties": {"job_id": {"type": "string", "description": "Job ID returned by a tool call"}},
        "required": ["job_id"]
    })
}

fn handle_job_status(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: JobIdArgs = parse_args(args)?;
        match state.jobs.get_job(&args.job_id).await {
            Some(job) => ToolResult::json(&job),
            None => Ok(error_result(
                format!("Job not found: {}", args.job_id),
                None,
            )),
        }
    })
}

const LIST_DESC: &str =
    "List recent jobs (newest first, results omitted), optionally filtered by status.";

fn list_jobs_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["pending", "running", "completed", "failed", "cancelled"]}
        }
    })
}

fn handle_list_jobs(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: ListJobsArgs = parse_args(args)?;
        let status =
            match args.status.as_deref() {
                None => None,
                Some(s) => Some(JobStatus::parse(s).ok_or_else(|| {
                    MCPError::InvalidParameters(format!("Unknown job status '{s}'"))
                })?),
            };
        let jobs = state.jobs.list(status).await;
        ToolResult::json(&json!({ "count": jobs.len(), "jobs": jobs }))
    })
}

const CANCEL_DESC: &str = "Cancel a pending or running job; any running ffmpeg/whisper process is killed and temp files are removed.";

fn handle_cancel_job(state: Arc<State>, args: Value) -> BoxFut {
    Box::pin(async move {
        let args: JobIdArgs = parse_args(args)?;
        match state.jobs.cancel(&args.job_id).await {
            Some(job) => ToolResult::json(&job),
            None => Ok(error_result(
                format!("Job not found: {}", args.job_id),
                None,
            )),
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn server(tmp: &Path) -> VideoEditorServer {
        VideoEditorServer::new(ServerConfig::for_root(tmp))
    }

    fn tool(s: &VideoEditorServer, name: &str) -> BoxedTool {
        s.tools()
            .into_iter()
            .find(|t| t.name() == name)
            .expect("tool exists")
    }

    fn text(r: &ToolResult) -> String {
        match &r.content[0] {
            Content::Text { text } => text.clone(),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn all_tools_registered_with_schemas() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let tools = s.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        for expected in [
            "video_editor/analyze",
            "video_editor/create_edit",
            "video_editor/render",
            "video_editor/extract_clips",
            "video_editor/add_captions",
            "video_editor/get_job_status",
            "video_editor/get_video_info",
            "video_editor/list_jobs",
            "video_editor/cancel_job",
        ] {
            assert!(names.contains(&expected), "missing {expected}");
        }
        for t in &tools {
            assert!(!t.description().is_empty());
            let schema = t.schema();
            assert_eq!(schema["type"], "object", "{}", t.name());
            if let Some(req) = schema["required"].as_array() {
                for r in req {
                    assert!(schema["properties"].get(r.as_str().unwrap()).is_some());
                }
            }
        }
    }

    #[tokio::test]
    async fn missing_required_param_is_invalid_parameters() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        for name in [
            "video_editor/analyze",
            "video_editor/render",
            "video_editor/extract_clips",
        ] {
            let err = tool(&s, name).execute(json!({})).await.unwrap_err();
            assert!(
                matches!(err, MCPError::InvalidParameters(_)),
                "{name}: {err}"
            );
        }
    }

    #[tokio::test]
    async fn wrong_type_is_invalid_parameters_not_silent_default() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let err = tool(&s, "video_editor/analyze")
            .execute(json!({"video_inputs": ["a.mp4"], "analysis_options": {"transcribe": "yes"}}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));
    }

    #[tokio::test]
    async fn missing_file_is_error_result() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let r = tool(&s, "video_editor/analyze")
            .execute(json!({"video_inputs": ["/definitely/not/here.mp4"]}))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(text(&r).contains("Video file not found"));
        let r = tool(&s, "video_editor/analyze")
            .execute(json!({"video_inputs": []}))
            .await
            .unwrap();
        assert!(r.is_error);
    }

    #[tokio::test]
    async fn render_rejects_output_outside_roots() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(&tmp.path().join("srv"));
        let input = tmp.path().join("in.mp4");
        std::fs::write(&input, b"x").unwrap();
        let outside = tmp.path().join("elsewhere.mp4");
        let r = tool(&s, "video_editor/render")
            .execute(json!({
                "video_inputs": [input],
                "output_settings": {"output_path": outside}
            }))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(text(&r).contains("outside the allowed"), "{}", text(&r));
    }

    #[tokio::test]
    async fn render_validates_settings() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let input = tmp.path().join("in.mp4");
        std::fs::write(&input, b"x").unwrap();
        for (settings, needle) in [
            (json!({"resolution": "999x1"}), "Resolution"),
            (json!({"bitrate": "lots"}), "bitrate"),
            (json!({"format": "avi"}), "Unsupported output format"),
            (json!({"codec": "prores"}), "Unsupported codec"),
        ] {
            let r = tool(&s, "video_editor/render")
                .execute(json!({"video_inputs": [input], "output_settings": settings}))
                .await
                .unwrap();
            assert!(r.is_error);
            assert!(text(&r).contains(needle), "{needle}: {}", text(&r));
        }
    }

    #[tokio::test]
    async fn render_rejects_bad_edl() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let input = tmp.path().join("in.mp4");
        std::fs::write(&input, b"x").unwrap();
        let r = tool(&s, "video_editor/render")
            .execute(json!({
                "video_inputs": [input],
                "edit_decision_list": [{"timestamp": 0, "duration": -1, "source": input}]
            }))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(text(&r).contains("duration"));
        let r = tool(&s, "video_editor/render")
            .execute(json!({
                "video_inputs": [input],
                "edit_decision_list": [{"timestamp": 0, "duration": 1, "source": "/nope.mp4"}]
            }))
            .await
            .unwrap();
        assert!(r.is_error);
    }

    #[tokio::test]
    async fn captions_require_whisper() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let input = tmp.path().join("in.mp4");
        std::fs::write(&input, b"x").unwrap();
        let r = tool(&s, "video_editor/add_captions")
            .execute(json!({"video_input": input}))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(text(&r).contains("Whisper CLI"), "{}", text(&r));
        let r = tool(&s, "video_editor/add_captions")
            .execute(json!({"video_input": input, "caption_style": {"color": "red"}}))
            .await
            .unwrap();
        assert!(text(&r).contains("Invalid colour"));
    }

    #[tokio::test]
    async fn extract_clips_requires_criteria() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let input = tmp.path().join("in.mp4");
        std::fs::write(&input, b"x").unwrap();
        let r = tool(&s, "video_editor/extract_clips")
            .execute(json!({"video_input": input}))
            .await
            .unwrap();
        assert!(r.is_error);
        let r = tool(&s, "video_editor/extract_clips")
            .execute(
                json!({"video_input": input, "extraction_criteria": {"time_ranges": [[5, 1]]}}),
            )
            .await
            .unwrap();
        assert!(text(&r).contains("time_ranges[0]"));
    }

    #[tokio::test]
    async fn job_tools_roundtrip() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let r = tool(&s, "video_editor/get_job_status")
            .execute(json!({"job_id": "nope"}))
            .await
            .unwrap();
        assert!(r.is_error);
        let (id, done) = s
            .state
            .jobs
            .spawn("unit", |_| async { Ok(json!({"x": 1})) })
            .await;
        done.await.unwrap();
        let r = tool(&s, "video_editor/get_job_status")
            .execute(json!({"job_id": id}))
            .await
            .unwrap();
        let v: Value = serde_json::from_str(&text(&r)).unwrap();
        assert_eq!(v["status"], "completed");
        let r = tool(&s, "video_editor/list_jobs")
            .execute(json!({"status": "completed"}))
            .await
            .unwrap();
        let v: Value = serde_json::from_str(&text(&r)).unwrap();
        assert_eq!(v["count"], 1);
        let err = tool(&s, "video_editor/list_jobs")
            .execute(json!({"status": "bogus"}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));
        let r = tool(&s, "video_editor/cancel_job")
            .execute(json!({"job_id": id}))
            .await
            .unwrap();
        let v: Value = serde_json::from_str(&text(&r)).unwrap();
        assert_eq!(v["status"], "completed", "finished jobs are not cancelled");
    }

    #[tokio::test]
    async fn run_job_background_returns_immediately() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let r = run_job(&s.state, "bg", true, |_| async {
            tokio::time::sleep(std::time::Duration::from_secs(10)).await;
            Ok(json!(null))
        })
        .await
        .unwrap();
        let v: Value = serde_json::from_str(&text(&r)).unwrap();
        let id = v["job_id"].as_str().unwrap().to_string();
        assert!(s.state.jobs.cancel(&id).await.is_some());
    }

    #[tokio::test]
    async fn run_job_foreground_failure_is_error_result() {
        let tmp = tempfile::tempdir().unwrap();
        let s = server(tmp.path());
        let r = run_job(&s.state, "fg", false, |_| async { anyhow::bail!("nope") })
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(text(&r).contains("nope"));
        assert!(text(&r).contains("job_id"));
    }

    fn criteria() -> ExtractionCriteria {
        ExtractionCriteria::default()
    }

    #[test]
    fn range_shaping() {
        let c = criteria();
        assert_eq!(shape_range(10.0, 20.0, &c, 100.0), Some((9.5, 20.5)));
        // Extended to the minimum length, centred.
        assert_eq!(shape_range(10.0, 10.5, &c, 100.0), Some((8.75, 11.75)));
        // Truncated to the maximum.
        assert_eq!(shape_range(0.0, 500.0, &c, 1000.0), Some((0.0, 60.0)));
        // Clamped to the video.
        assert_eq!(shape_range(90.0, 120.0, &c, 100.0), Some((89.5, 100.0)));
        // Minimum extension near the end shifts left.
        assert_eq!(shape_range(99.5, 99.9, &c, 100.0), Some((97.0, 100.0)));
    }

    #[test]
    fn clip_planning_with_keywords_merges_overlaps() {
        let transcript = Transcript {
            text: String::new(),
            language: "en".into(),
            segments: vec![
                TranscriptSegment {
                    id: 0,
                    start: 1.0,
                    end: 4.0,
                    text: "This is Important".into(),
                    words: vec![],
                },
                TranscriptSegment {
                    id: 1,
                    start: 4.2,
                    end: 6.0,
                    text: "also important".into(),
                    words: vec![],
                },
                TranscriptSegment {
                    id: 2,
                    start: 30.0,
                    end: 33.0,
                    text: "nothing".into(),
                    words: vec![],
                },
                TranscriptSegment {
                    id: 3,
                    start: 40.0,
                    end: 42.0,
                    text: "IMPORTANT again".into(),
                    words: vec![],
                },
            ],
        };
        let c = ExtractionCriteria {
            keywords: vec!["important".into()],
            time_ranges: vec![(50.0, 55.0), (500.0, 510.0)],
            ..criteria()
        };
        let plans = plan_clips(&c, Some(&transcript), 100.0);
        let kw: Vec<&ClipPlan> = plans.iter().filter(|p| p.criteria == "keyword").collect();
        assert_eq!(kw.len(), 2, "{plans:?}");
        assert_eq!(kw[0].start, 0.5);
        assert_eq!(kw[0].end, 6.6);
        assert!(kw[0].text.as_ref().unwrap().contains("also important"));
        let tr: Vec<&ClipPlan> = plans
            .iter()
            .filter(|p| p.criteria == "time_range")
            .collect();
        assert_eq!(tr.len(), 1, "range beyond the video is skipped");
    }

    #[test]
    fn criteria_validation() {
        assert!(validate_criteria(&criteria()).is_ok());
        let c = ExtractionCriteria {
            min_clip_length: 100.0,
            ..criteria()
        };
        assert!(validate_criteria(&c).is_err());
        let c = ExtractionCriteria {
            padding: -1.0,
            ..criteria()
        };
        assert!(validate_criteria(&c).is_err());
        let c = ExtractionCriteria {
            time_ranges: vec![(f64::NAN, 1.0)],
            ..criteria()
        };
        assert!(validate_criteria(&c).is_err());
    }

    #[test]
    fn segments_labelled_by_overlap() {
        let segs = vec![
            TranscriptSegment {
                id: 0,
                start: 0.0,
                end: 2.0,
                text: "a".into(),
                words: vec![],
            },
            TranscriptSegment {
                id: 1,
                start: 2.5,
                end: 5.0,
                text: "b".into(),
                words: vec![],
            },
            TranscriptSegment {
                id: 2,
                start: 50.0,
                end: 51.0,
                text: "c".into(),
                words: vec![],
            },
        ];
        let turns = vec![
            SpeakerTurn {
                speaker: "SPEAKER_00".into(),
                start: 0.0,
                end: 3.0,
            },
            SpeakerTurn {
                speaker: "SPEAKER_01".into(),
                start: 3.0,
                end: 10.0,
            },
        ];
        let l = label_segments(&segs, &turns);
        assert_eq!(l[0].speaker.as_deref(), Some("SPEAKER_00"));
        assert_eq!(l[1].speaker.as_deref(), Some("SPEAKER_01"));
        assert_eq!(l[2].speaker, None);
    }

    #[test]
    fn error_result_shape() {
        let r = error_result("bad", Some(json!({"job_id": "j"})));
        assert!(r.is_error);
        let v: Value = serde_json::from_str(&text(&r)).unwrap();
        assert_eq!(v["error"], "bad");
        assert_eq!(v["job_id"], "j");
    }
}

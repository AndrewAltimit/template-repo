//! Video operations built on ffmpeg: scene detection, clip extraction,
//! EDL rendering (with transitions, zoom and picture-in-picture) and
//! subtitle burn-in / muxing.
//!
//! # Rendering pipeline
//!
//! 1. Every decision is encoded to a uniform intermediate segment (target
//!    resolution with letterboxing, target fps, yuv420p, 48 kHz stereo audio;
//!    sources without audio get silence). Effects and PiP are applied here.
//! 2. Segments are joined. Without transitions this is a lossless concat
//!    (`-c copy`); with transitions an `xfade`/`acrossfade` chain re-encodes
//!    the joined result.
//!
//! Intermediates live in a [`tempfile::TempDir`] under the server temp dir and
//! are removed when rendering finishes, fails or is cancelled.

use std::collections::HashMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use tracing::info;

use crate::edl::{SUPPORTED_EFFECTS, xfade_transition};
use crate::ffmpeg::{
    Container, MediaInfo, concat_list_line, escape_filter_value, ffmpeg, fmt_time, media_arg,
    probe, video_encoder_args,
};
use crate::jobs::JobContext;
use crate::process::run_checked;
use crate::types::EditDecision;

/// Transitions are only rendered for EDLs up to this many segments; longer
/// lists fall back to hard cuts (each xfade input is an open decoder).
pub const MAX_XFADE_SEGMENTS: usize = 64;

/// Shortest transition that is actually rendered, in seconds.
const MIN_TRANSITION_SECS: f64 = 0.04;

// ============================================================================
// Scene detection
// ============================================================================

/// Detect scene changes, returning their timestamps in seconds.
///
/// `threshold` is ffmpeg's scene score cut-off in (0, 1]. The video is
/// downscaled before scoring, which is much faster and barely affects the
/// detection.
pub async fn detect_scene_changes(video: &Path, threshold: f64) -> Result<Vec<f64>> {
    if !(threshold > 0.0 && threshold <= 1.0) {
        bail!("scene_threshold must be in (0, 1], got {threshold}");
    }
    info!("Detecting scene changes in {}", video.display());
    let filter = format!("scale=320:-2,select='gt(scene,{threshold:.3})',metadata=print:file=-");
    let output = run_checked(
        ffmpeg().arg("-i").arg(media_arg(video)).args([
            "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", &filter, "-f", "null", "-",
        ]),
        "ffmpeg scene detection",
    )
    .await?;
    let scenes = parse_scene_output(&String::from_utf8_lossy(&output.stdout));
    info!("Detected {} scene changes", scenes.len());
    Ok(scenes)
}

/// Parse `pts_time:` values from the metadata filter's output.
pub fn parse_scene_output(text: &str) -> Vec<f64> {
    let mut out: Vec<f64> = text
        .lines()
        .filter_map(|line| {
            let idx = line.find("pts_time:")?;
            line[idx + 9..]
                .split_whitespace()
                .next()?
                .parse::<f64>()
                .ok()
        })
        .filter(|t| t.is_finite() && *t >= 0.0)
        .map(|t| (t * 1000.0).round() / 1000.0)
        .collect();
    out.sort_by(f64::total_cmp);
    out.dedup();
    out
}

// ============================================================================
// Clip extraction
// ============================================================================

/// Extract `[start, end)` of `video` into `output`.
///
/// By default the clip is re-encoded (frame-accurate cut points). With
/// `stream_copy` the streams are copied, which is fast and lossless but cuts
/// land on the nearest preceding keyframe.
pub async fn extract_clip(
    video: &Path,
    start: f64,
    end: f64,
    output: &Path,
    stream_copy: bool,
) -> Result<()> {
    if !start.is_finite() || !end.is_finite() || end <= start {
        bail!("Invalid clip range {start}..{end}");
    }
    let container = Container::from_path(output).unwrap_or(Container::Mp4);
    let mut cmd = ffmpeg();
    cmd.arg("-y")
        .args(["-ss", &fmt_time(start)])
        .arg("-i")
        .arg(media_arg(video))
        .args(["-t", &fmt_time(end - start)])
        .args(["-map", "0:v:0?", "-map", "0:a:0?"]);
    if stream_copy {
        cmd.args(["-c", "copy", "-avoid_negative_ts", "make_zero"]);
    } else {
        cmd.args(quality_encoder_args(container))
            .args(container.audio_args());
    }
    cmd.args(container.mux_args()).arg(media_arg(output));
    run_checked(&mut cmd, "ffmpeg clip extraction").await?;
    Ok(())
}

/// Constant-quality encoder arguments for single-pass operations (clips,
/// captions) where no bitrate was requested.
pub fn quality_encoder_args(container: Container) -> Vec<String> {
    let v: &[&str] = match container {
        Container::Webm => &[
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "32",
            "-b:v",
            "0",
            "-row-mt",
            "1",
        ],
        _ => &["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"],
    };
    let mut args: Vec<String> = v.iter().map(|s| s.to_string()).collect();
    args.extend(["-pix_fmt".into(), "yuv420p".into()]);
    args
}

// ============================================================================
// Rendering
// ============================================================================

/// Resolved render parameters.
#[derive(Debug, Clone)]
pub struct RenderSpec {
    pub width: u32,
    pub height: u32,
    pub fps: u32,
    pub bitrate: String,
    pub codec: String,
    pub container: Container,
    /// Faster encoder presets (preview renders).
    pub fast: bool,
    /// Default transition length when a decision does not specify one.
    pub default_transition: f64,
    /// Punch-in factor for the `zoom_in` effect.
    pub zoom_factor: f64,
}

/// Result of a render.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenderResult {
    pub success: bool,
    pub output_path: String,
    pub duration: f64,
    pub fps: u32,
    pub resolution: String,
    pub file_size: u64,
    pub codec: String,
    pub segments: usize,
    pub transitions_rendered: usize,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub warnings: Vec<String>,
}

/// Validate an EDL before any encoding starts.
pub fn validate_edl(edl: &[EditDecision]) -> Result<()> {
    if edl.is_empty() {
        bail!("edit_decision_list is empty");
    }
    for (i, d) in edl.iter().enumerate() {
        if !(d.timestamp.is_finite() && d.timestamp >= 0.0) {
            bail!("Decision {i}: timestamp must be a non-negative number");
        }
        if !(d.duration.is_finite() && d.duration > 0.0) {
            bail!("Decision {i}: duration must be a positive number");
        }
        if let Some(t) = &d.transition_type {
            xfade_transition(t).map_err(|e| anyhow::anyhow!("Decision {i}: {e}"))?;
        }
        if let Some(td) = d.transition_duration
            && !(td.is_finite() && (0.0..=5.0).contains(&td))
        {
            bail!("Decision {i}: transition_duration must be between 0 and 5 seconds");
        }
        for e in &d.effects {
            if !SUPPORTED_EFFECTS.contains(&e.as_str()) {
                bail!(
                    "Decision {i}: unsupported effect '{e}' (supported: {})",
                    SUPPORTED_EFFECTS.join(", ")
                );
            }
        }
        if let Some(p) = d.pip_size
            && !(0.05..=0.9).contains(&p)
        {
            bail!("Decision {i}: pip_size must be between 0.05 and 0.9");
        }
    }
    Ok(())
}

/// Planned transition into segment `k` (index into the EDL), after clamping.
#[derive(Debug, Clone, PartialEq)]
pub struct PlannedTransition {
    pub xfade: &'static str,
    pub duration: f64,
}

/// Decide which transitions to render given the actual segment lengths.
///
/// A transition may use at most 45% of either neighbouring segment so
/// consecutive transitions never overlap; anything shorter than
/// [`MIN_TRANSITION_SECS`] becomes a hard cut.
pub fn plan_transitions(
    edl: &[EditDecision],
    lengths: &[f64],
    default_duration: f64,
) -> Vec<Option<PlannedTransition>> {
    let mut out = vec![None; edl.len()];
    for k in 1..edl.len().min(lengths.len()) {
        let Some(name) = edl[k].transition_type.as_deref() else {
            continue;
        };
        let Ok(Some(xfade)) = xfade_transition(name) else {
            continue;
        };
        let wanted = edl[k].transition_duration.unwrap_or(default_duration);
        let d = wanted.min(lengths[k - 1] * 0.45).min(lengths[k] * 0.45);
        if d >= MIN_TRANSITION_SECS {
            out[k] = Some(PlannedTransition {
                xfade,
                duration: (d * 1000.0).floor() / 1000.0,
            });
        }
    }
    out
}

/// Build the `-filter_complex` graph joining `lengths.len()` segment inputs
/// with the planned transitions. Output pads are `[vout]` and `[aout]`.
pub fn build_join_graph(lengths: &[f64], transitions: &[Option<PlannedTransition>]) -> String {
    let mut graph = String::new();
    let mut cur_v = "0:v".to_string();
    let mut cur_a = "0:a".to_string();
    let mut length = lengths.first().copied().unwrap_or(0.0);
    for k in 1..lengths.len() {
        let (vo, ao) = if k + 1 == lengths.len() {
            ("vout".to_string(), "aout".to_string())
        } else {
            (format!("v{k}"), format!("a{k}"))
        };
        match transitions.get(k).cloned().flatten() {
            Some(t) => {
                let offset = (length - t.duration).max(0.0);
                let _ = write!(
                    graph,
                    "[{cur_v}][{k}:v]xfade=transition={}:duration={}:offset={}[{vo}];\
                     [{cur_a}][{k}:a]acrossfade=d={}[{ao}];",
                    t.xfade,
                    fmt_time(t.duration),
                    fmt_time(offset),
                    fmt_time(t.duration)
                );
                length += lengths[k] - t.duration;
            },
            None => {
                let _ = write!(
                    graph,
                    "[{cur_v}][{cur_a}][{k}:v][{k}:a]concat=n=2:v=1:a=1[{vo}][{ao}];"
                );
                length += lengths[k];
            },
        }
        cur_v = vo;
        cur_a = ao;
    }
    graph.trim_end_matches(';').to_string()
}

/// Build the per-segment video filter graph (scale/letterbox, zoom, PiP).
/// Output pad is `[v]`.
pub fn build_segment_graph(spec: &RenderSpec, zoom: bool, pip: Option<(usize, f64)>) -> String {
    let (w, h) = (spec.width, spec.height);
    let zoom_filter = if zoom && spec.zoom_factor > 1.0 {
        format!(
            "crop=trunc(iw/{z}/2)*2:trunc(ih/{z}/2)*2,",
            z = format_args!("{:.3}", spec.zoom_factor)
        )
    } else {
        String::new()
    };
    let fit = format!(
        "scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    );
    let tail = format!("fps={},format=yuv420p", spec.fps);
    match pip {
        None => format!("[0:v]{zoom_filter}{fit},{tail}[v]"),
        Some((input, size)) => {
            let pw = (((w as f64) * size / 2.0).round() as u32).max(8) * 2;
            let margin = ((w as f64 * 0.02 / 2.0).round() as u32) * 2;
            format!(
                "[0:v]{zoom_filter}{fit}[base];[{input}:v]scale={pw}:-2,setsar=1[pip];\
                 [base][pip]overlay=W-w-{margin}:H-h-{margin}:eof_action=pass,{tail}[v]"
            )
        },
    }
}

/// Render an EDL to `output`.
pub async fn render_edl(
    edl: &[EditDecision],
    spec: &RenderSpec,
    output: &Path,
    temp_root: &Path,
    ctx: Option<&JobContext>,
) -> Result<RenderResult> {
    validate_edl(edl)?;
    std::fs::create_dir_all(temp_root)?;
    let work = tempfile::Builder::new()
        .prefix("render_")
        .tempdir_in(temp_root)
        .context("Failed to create render work directory")?;
    let mut warnings = Vec::new();

    // Probe every distinct source once.
    let mut infos: HashMap<String, MediaInfo> = HashMap::new();
    for d in edl {
        for src in std::iter::once(&d.source).chain(d.pip_source.as_ref()) {
            if !infos.contains_key(src) {
                let info = probe(Path::new(src)).await?;
                if !info.has_video {
                    bail!("Source {src} has no video stream");
                }
                infos.insert(src.clone(), info);
            }
        }
    }

    // 1. Encode segments.
    let total = edl.len();
    let mut seg_paths: Vec<PathBuf> = Vec::with_capacity(total);
    for (i, d) in edl.iter().enumerate() {
        if let Some(ctx) = ctx {
            let pct = 5 + (i as u32 * 80) / total as u32;
            ctx.progress(pct, &format!("encoding segment {}/{}", i + 1, total))
                .await;
        }
        let info = &infos[&d.source];
        let duration =
            clamp_to_source(d, info.duration).with_context(|| format!("Decision {i}"))?;
        if duration + 0.01 < d.duration {
            warnings.push(format!(
                "Decision {i}: shortened from {:.2}s to {:.2}s (source ends at {:.2}s)",
                d.duration, duration, info.duration
            ));
        }
        let seg = work.path().join(format!("seg_{i:04}.mkv"));
        encode_segment(d, duration, info, &infos, spec, &seg)
            .await
            .with_context(|| format!("Failed to encode decision {i} ({})", d.source))?;
        seg_paths.push(seg);
    }

    // Actual segment lengths (frame rounding makes them differ slightly).
    let mut lengths = Vec::with_capacity(total);
    for p in &seg_paths {
        lengths.push(probe(p).await?.duration);
    }

    // 2. Join.
    if let Some(ctx) = ctx {
        ctx.progress(88, "joining segments").await;
    }
    let mut transitions = plan_transitions(edl, &lengths, spec.default_transition);
    let wanted = transitions.iter().flatten().count();
    if wanted > 0 && total > MAX_XFADE_SEGMENTS {
        warnings.push(format!(
            "Transitions skipped: {total} segments exceeds the limit of {MAX_XFADE_SEGMENTS} for \
             cross-fades; hard cuts used instead"
        ));
        transitions = vec![None; total];
    }
    let rendered_transitions = transitions.iter().flatten().count();

    if total == 1 || rendered_transitions == 0 {
        let list = work.path().join("concat.txt");
        let content: String = seg_paths.iter().map(|p| concat_list_line(p)).collect();
        std::fs::write(&list, content)?;
        run_checked(
            ffmpeg()
                .arg("-y")
                .args(["-f", "concat", "-safe", "0", "-i"])
                .arg(media_arg(&list))
                .args(["-map", "0:v", "-map", "0:a", "-c", "copy"])
                .args(spec.container.mux_args())
                .arg(media_arg(output)),
            "ffmpeg concat",
        )
        .await?;
    } else {
        let graph = build_join_graph(&lengths, &transitions);
        let mut cmd = ffmpeg();
        cmd.arg("-y");
        for p in &seg_paths {
            cmd.arg("-i").arg(media_arg(p));
        }
        cmd.args([
            "-filter_complex",
            &graph,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
        ])
        .args(video_encoder_args(&spec.codec, &spec.bitrate, spec.fast))
        .args(["-r", &spec.fps.to_string()])
        .args(spec.container.audio_args())
        .args(spec.container.mux_args())
        .arg(media_arg(output));
        run_checked(&mut cmd, "ffmpeg transition render").await?;
    }

    let out_info = probe(output).await?;
    Ok(RenderResult {
        success: true,
        output_path: output.to_string_lossy().to_string(),
        duration: (out_info.duration * 1000.0).round() / 1000.0,
        fps: spec.fps,
        resolution: format!("{}x{}", out_info.width, out_info.height),
        file_size: out_info.file_size,
        codec: spec.codec.clone(),
        segments: total,
        transitions_rendered: rendered_transitions,
        warnings,
    })
}

/// Clamp a decision's duration to what the source actually contains.
fn clamp_to_source(d: &EditDecision, source_duration: f64) -> Result<f64> {
    if source_duration <= 0.0 {
        return Ok(d.duration); // unknown duration: trust the EDL
    }
    let available = source_duration - d.timestamp;
    if available < 0.05 {
        bail!(
            "starts at {:.2}s but {} is only {:.2}s long",
            d.timestamp,
            d.source,
            source_duration
        );
    }
    Ok(d.duration.min(available))
}

async fn encode_segment(
    d: &EditDecision,
    duration: f64,
    info: &MediaInfo,
    infos: &HashMap<String, MediaInfo>,
    spec: &RenderSpec,
    out: &Path,
) -> Result<()> {
    let mut cmd = ffmpeg();
    cmd.arg("-y")
        .args(["-ss", &fmt_time(d.timestamp), "-t", &fmt_time(duration)])
        .arg("-i")
        .arg(media_arg(Path::new(&d.source)));
    let mut next_input = 1;
    let pip = match &d.pip_source {
        Some(p) if infos.contains_key(p) => {
            cmd.args(["-ss", &fmt_time(d.timestamp), "-t", &fmt_time(duration)])
                .arg("-i")
                .arg(media_arg(Path::new(p)));
            next_input += 1;
            Some((1, d.pip_size.unwrap_or(0.25)))
        },
        _ => None,
    };
    let audio_map = if info.has_audio {
        "0:a:0".to_string()
    } else {
        cmd.args([
            "-f",
            "lavfi",
            "-t",
            &fmt_time(duration),
            "-i",
            "anullsrc=r=48000:cl=stereo",
        ]);
        format!("{next_input}:a:0")
    };
    let zoom = d.effects.iter().any(|e| e == "zoom_in");
    let graph = build_segment_graph(spec, zoom, pip);
    cmd.args(["-filter_complex", &graph, "-map", "[v]", "-map", &audio_map])
        .args(["-t", &fmt_time(duration)])
        .args(video_encoder_args(&spec.codec, &spec.bitrate, spec.fast))
        .args(spec.container.audio_args())
        .args(["-ar", "48000", "-ac", "2"])
        .arg(media_arg(out));
    run_checked(&mut cmd, "ffmpeg segment encode").await?;
    Ok(())
}

// ============================================================================
// Subtitles
// ============================================================================

/// Burn subtitles from `srt` into `video` using libass, with `force_style`.
pub async fn burn_subtitles(
    video: &Path,
    srt: &Path,
    force_style: &str,
    output: &Path,
) -> Result<()> {
    let container = Container::from_path(output).unwrap_or(Container::Mp4);
    let filter = format!(
        "subtitles=filename={}:force_style={}",
        escape_filter_value(&srt.to_string_lossy()),
        escape_filter_value(force_style)
    );
    run_checked(
        ffmpeg()
            .arg("-y")
            .arg("-i")
            .arg(media_arg(video))
            .args(["-map", "0:v:0", "-map", "0:a:0?", "-vf", &filter])
            .args(quality_encoder_args(container))
            .args(container.audio_args())
            .args(container.mux_args())
            .arg(media_arg(output)),
        "ffmpeg subtitle burn-in",
    )
    .await?;
    Ok(())
}

/// Mux `srt` into `video` as a soft (selectable) subtitle track, without
/// re-encoding audio or video.
pub async fn mux_subtitles(
    video: &Path,
    srt: &Path,
    output: &Path,
    language: Option<&str>,
) -> Result<()> {
    let container = Container::from_path(output).unwrap_or(Container::Mp4);
    let mut cmd = ffmpeg();
    cmd.arg("-y")
        .arg("-i")
        .arg(media_arg(video))
        .arg("-i")
        .arg(media_arg(srt))
        .args(["-map", "0:v?", "-map", "0:a?", "-map", "1:0", "-c", "copy"])
        .args(["-c:s", container.subtitle_codec()]);
    if let Some(lang) = language.and_then(iso639_2) {
        cmd.args(["-metadata:s:s:0", &format!("language={lang}")]);
    }
    cmd.args(container.mux_args()).arg(media_arg(output));
    run_checked(&mut cmd, "ffmpeg subtitle mux").await?;
    Ok(())
}

/// Map common ISO 639-1 codes to the 639-2 codes containers expect.
fn iso639_2(code: &str) -> Option<&'static str> {
    Some(match code.to_ascii_lowercase().as_str() {
        "en" => "eng",
        "es" => "spa",
        "fr" => "fra",
        "de" => "deu",
        "it" => "ita",
        "pt" => "por",
        "ja" => "jpn",
        "zh" => "zho",
        "ko" => "kor",
        "ru" => "rus",
        "nl" => "nld",
        "ar" => "ara",
        "hi" => "hin",
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spec() -> RenderSpec {
        RenderSpec {
            width: 1280,
            height: 720,
            fps: 30,
            bitrate: "4M".into(),
            codec: "libx264".into(),
            container: Container::Mp4,
            fast: true,
            default_transition: 0.5,
            zoom_factor: 1.3,
        }
    }

    fn decision(t: Option<&str>) -> EditDecision {
        EditDecision {
            transition_type: t.map(Into::into),
            ..EditDecision::shot("a.mp4", 0.0, 5.0)
        }
    }

    #[test]
    fn scene_output_parsing() {
        let text = "frame:0    pts:12800  pts_time:0.5\nlavfi.scene_score=0.9\n\
                    frame:1    pts:99     pts_time:4.25\nframe:2 pts_time:4.25\ngarbage";
        assert_eq!(parse_scene_output(text), vec![0.5, 4.25]);
        assert!(parse_scene_output("").is_empty());
    }

    #[test]
    fn edl_validation() {
        assert!(validate_edl(&[]).is_err());
        assert!(validate_edl(&[decision(None)]).is_ok());
        let mut d = decision(None);
        d.duration = 0.0;
        assert!(validate_edl(&[d]).is_err());
        let mut d = decision(None);
        d.timestamp = f64::NAN;
        assert!(validate_edl(&[d]).is_err());
        assert!(validate_edl(&[decision(Some("explode"))]).is_err());
        let mut d = decision(None);
        d.effects.push("sepia".into());
        assert!(validate_edl(&[d]).is_err());
    }

    #[test]
    fn transition_planning_clamps() {
        let edl = vec![
            decision(None),
            decision(Some("cross_dissolve")),
            decision(Some("cut")),
        ];
        let plan = plan_transitions(&edl, &[5.0, 1.0, 5.0], 0.5);
        assert_eq!(plan[0], None);
        assert_eq!(
            plan[1],
            Some(PlannedTransition {
                xfade: "fade",
                duration: 0.45
            })
        );
        assert_eq!(plan[2], None);
        let plan = plan_transitions(&edl, &[5.0, 0.05, 5.0], 0.5);
        assert_eq!(plan[1], None, "too short to cross-fade");
    }

    #[test]
    fn join_graph_mixes_xfade_and_concat() {
        let lengths = [5.0, 4.0, 3.0];
        let transitions = vec![
            None,
            Some(PlannedTransition {
                xfade: "fade",
                duration: 0.5,
            }),
            None,
        ];
        let g = build_join_graph(&lengths, &transitions);
        assert!(g.contains("[0:v][1:v]xfade=transition=fade:duration=0.500:offset=4.500[v1]"));
        assert!(g.contains("[0:a][1:a]acrossfade=d=0.500[a1]"));
        assert!(g.contains("[v1][a1][2:v][2:a]concat=n=2:v=1:a=1[vout][aout]"));
        assert!(!g.ends_with(';'));
    }

    #[test]
    fn join_graph_offsets_accumulate() {
        let lengths = [5.0, 5.0, 5.0];
        let t = Some(PlannedTransition {
            xfade: "fade",
            duration: 1.0,
        });
        let g = build_join_graph(&lengths, &[None, t.clone(), t]);
        assert!(g.contains("offset=4.000[v1]"));
        assert!(g.contains("offset=8.000[vout]"));
    }

    #[test]
    fn segment_graph_variants() {
        let s = spec();
        let plain = build_segment_graph(&s, false, None);
        assert!(plain.starts_with("[0:v]scale=1280:720:force_original_aspect_ratio=decrease"));
        assert!(plain.ends_with("fps=30,format=yuv420p[v]"));
        let zoom = build_segment_graph(&s, true, None);
        assert!(zoom.contains("crop=trunc(iw/1.300/2)*2"));
        let pip = build_segment_graph(&s, false, Some((1, 0.25)));
        assert!(pip.contains("[1:v]scale=320:-2"));
        assert!(pip.contains("overlay=W-w-26:H-h-26"));
    }

    #[test]
    fn clamping_to_source() {
        let d = EditDecision::shot("a.mp4", 8.0, 5.0);
        assert_eq!(clamp_to_source(&d, 10.0).unwrap(), 2.0);
        assert_eq!(clamp_to_source(&d, 0.0).unwrap(), 5.0);
        assert!(clamp_to_source(&d, 8.0).is_err());
    }

    #[test]
    fn language_codes() {
        assert_eq!(iso639_2("EN"), Some("eng"));
        assert_eq!(iso639_2("xx"), None);
    }
}

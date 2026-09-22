//! Edit decision list (EDL) generation, highlight extraction and edit
//! suggestions. Everything here is pure (no I/O) so it is fully unit-tested.
//!
//! # EDL model
//!
//! All inputs are assumed to share one timeline (e.g. several cameras that
//! recorded the same conversation, started in sync). A decision takes
//! `duration` seconds from `source` starting at `timestamp`; decisions play
//! back in order. Generation happens in stages:
//!
//! 1. **Shots**: split the timeline by speaker turns (multi-camera), scene
//!    changes, fixed intervals (multi-input without speakers) or keep the
//!    whole video (single input).
//! 2. **Silence removal**: cut out silences longer than the threshold (with a
//!    small pad so words are not clipped).
//! 3. **Emphasis**: split out short windows around highlights and mark them
//!    with the `zoom_in` effect.
//! 4. **Transitions**: a change of source gets the configured transition;
//!    jump cuts inside the same source are hard cuts.

use std::collections::HashMap;

use crate::config::ServerConfig;
use crate::types::{
    EditDecision, EditSuggestion, EditingRules, EditingRulesInput, Highlight, PipMode, SpeakerTurn,
    VideoAnalysis,
};

/// Silence kept on each side of a removed silence, in seconds.
const SILENCE_KEEP_PAD: f64 = 0.25;
/// Shots shorter than this are dropped after silence removal.
const MIN_PIECE_SECS: f64 = 0.3;
/// Minimum spacing between scene cuts used as shot boundaries.
const MIN_SCENE_SHOT_SECS: f64 = 1.0;
/// Shot length used when rotating between inputs without other cues.
const INTERVAL_SECS: f64 = 10.0;
/// Emphasis window around a highlight: `[t - BEFORE, t + AFTER]`.
const EMPHASIS_BEFORE: f64 = 0.5;
const EMPHASIS_AFTER: f64 = 2.5;
/// Sub-shots shorter than this are merged into a neighbour when splitting.
const MIN_SUBSHOT_SECS: f64 = 0.5;

/// Transition names accepted in EDLs, mapped to ffmpeg `xfade` transitions.
/// `None` means a hard cut.
pub fn xfade_transition(name: &str) -> Result<Option<&'static str>, String> {
    let n = name.trim().to_ascii_lowercase();
    Ok(Some(match n.as_str() {
        "" | "cut" | "none" | "hard_cut" => return Ok(None),
        "cross_dissolve" | "crossfade" | "fade" | "mix" => "fade",
        "dissolve" => "dissolve",
        "fadeblack" | "fade_black" | "dip_to_black" => "fadeblack",
        "fadewhite" | "fade_white" | "dip_to_white" => "fadewhite",
        "wipeleft" => "wipeleft",
        "wiperight" => "wiperight",
        "wipeup" => "wipeup",
        "wipedown" => "wipedown",
        "slideleft" => "slideleft",
        "slideright" => "slideright",
        "circleopen" => "circleopen",
        "circleclose" => "circleclose",
        _ => {
            return Err(format!(
                "Unsupported transition '{name}' (supported: cut, cross_dissolve, fade, dissolve, \
                 fadeblack, fadewhite, wipeleft, wiperight, wipeup, wipedown, slideleft, \
                 slideright, circleopen, circleclose)"
            ));
        },
    }))
}

/// Effects the renderer understands.
pub const SUPPORTED_EFFECTS: &[&str] = &["zoom_in"];

/// Merge caller-supplied rules with server defaults and validate them.
pub fn resolve_rules(
    input: Option<EditingRulesInput>,
    cfg: &ServerConfig,
) -> Result<EditingRules, String> {
    let i = input.unwrap_or_default();
    let finite_nonneg = |name: &str, v: f64| -> Result<f64, String> {
        if v.is_finite() && v >= 0.0 {
            Ok(v)
        } else {
            Err(format!(
                "editing_rules.{name} must be a non-negative number"
            ))
        }
    };
    let rules = EditingRules {
        switch_on_speaker: i.switch_on_speaker.unwrap_or(true),
        speaker_switch_delay: finite_nonneg(
            "speaker_switch_delay",
            i.speaker_switch_delay.unwrap_or(cfg.speaker_switch_delay),
        )?,
        picture_in_picture: PipMode::parse(i.picture_in_picture.as_deref().unwrap_or("auto"))?,
        zoom_on_emphasis: i.zoom_on_emphasis.unwrap_or(true),
        remove_silence: i.remove_silence.unwrap_or(true),
        silence_threshold: finite_nonneg(
            "silence_threshold",
            i.silence_threshold.unwrap_or(cfg.silence_threshold),
        )?
        .max(0.1),
        pip_size: finite_nonneg("pip_size", i.pip_size.unwrap_or(cfg.pip_size))?,
        transition_duration: finite_nonneg(
            "transition_duration",
            i.transition_duration.unwrap_or(cfg.transition_duration),
        )?,
        transition_type: i
            .transition_type
            .unwrap_or_else(|| "cross_dissolve".to_string()),
    };
    if !(0.05..=0.9).contains(&rules.pip_size) {
        return Err("editing_rules.pip_size must be between 0.05 and 0.9".into());
    }
    if rules.transition_duration > 5.0 {
        return Err("editing_rules.transition_duration must be at most 5 seconds".into());
    }
    xfade_transition(&rules.transition_type)?;
    Ok(rules)
}

/// Everything EDL generation needs to know about the inputs.
#[derive(Debug, Default)]
pub struct EdlInputs<'a> {
    /// Input videos (first is the primary).
    pub video_inputs: &'a [String],
    /// Length of the shared timeline in seconds.
    pub timeline_duration: f64,
    /// Speaker turns from multi-camera speaker detection.
    pub speaker_turns: &'a [SpeakerTurn],
    /// Scene-change times of the primary video.
    pub scene_changes: &'a [f64],
    /// Silent intervals of the (combined) audio.
    pub silence: &'a [(f64, f64)],
    /// Highlight times to emphasise.
    pub highlights: &'a [f64],
    /// Speaker ID -> source video overrides.
    pub speaker_mapping: Option<&'a HashMap<String, String>>,
}

/// Generated EDL plus a description of how it was produced.
#[derive(Debug, Clone)]
pub struct EdlPlan {
    pub decisions: Vec<EditDecision>,
    /// `speaker`, `scene`, `interval` or `full`.
    pub strategy: &'static str,
    /// Seconds removed as silence.
    pub silence_removed: f64,
}

#[derive(Debug, Clone, PartialEq)]
struct Piece {
    source: String,
    start: f64,
    end: f64,
    zoom: bool,
}

/// Generate an edit decision list.
pub fn generate_edl(inp: &EdlInputs<'_>, rules: &EditingRules) -> EdlPlan {
    let duration = inp.timeline_duration;
    let n = inp.video_inputs.len();
    if n == 0 || !duration.is_finite() || duration <= 0.0 {
        return EdlPlan {
            decisions: Vec::new(),
            strategy: "full",
            silence_removed: 0.0,
        };
    }

    // 1. Shots.
    let (mut pieces, strategy) = if rules.switch_on_speaker && !inp.speaker_turns.is_empty() {
        (speaker_shots(inp, duration), "speaker")
    } else if let Some(p) = scene_shots(inp, duration) {
        (p, "scene")
    } else if n > 1 {
        (interval_shots(inp.video_inputs, duration), "interval")
    } else {
        (
            vec![Piece {
                source: inp.video_inputs[0].clone(),
                start: 0.0,
                end: duration,
                zoom: false,
            }],
            "full",
        )
    };

    // 2. Silence removal.
    let before: f64 = pieces.iter().map(|p| p.end - p.start).sum();
    if rules.remove_silence {
        let cuts: Vec<(f64, f64)> = inp
            .silence
            .iter()
            .filter(|(s, e)| e - s >= rules.silence_threshold)
            .map(|(s, e)| (s + SILENCE_KEEP_PAD, e - SILENCE_KEEP_PAD))
            .filter(|(s, e)| e > s)
            .collect();
        pieces = subtract_intervals(pieces, &cuts);
    }
    let after: f64 = pieces.iter().map(|p| p.end - p.start).sum();

    // 3. Emphasis.
    if rules.zoom_on_emphasis && !inp.highlights.is_empty() {
        let windows = merge_intervals(
            inp.highlights
                .iter()
                .map(|h| {
                    (
                        (h - EMPHASIS_BEFORE).max(0.0),
                        (h + EMPHASIS_AFTER).min(duration),
                    )
                })
                .collect(),
        );
        pieces = pieces
            .into_iter()
            .flat_map(|p| split_for_zoom(p, &windows))
            .collect();
    }

    // 4. Decisions.
    let transition = xfade_transition(&rules.transition_type)
        .ok()
        .flatten()
        .map(|_| rules.transition_type.clone());
    let mut decisions: Vec<EditDecision> = Vec::with_capacity(pieces.len());
    let mut prev: Option<&Piece> = None;
    let mut last_other_source: Option<String> = None;
    for p in &pieces {
        let mut d = EditDecision::shot(&p.source, round3(p.start), round3(p.end - p.start));
        if let Some(prev) = prev {
            if prev.source != p.source {
                last_other_source = Some(prev.source.clone());
                if let Some(t) = &transition {
                    d.action = "transition".into();
                    d.transition_type = Some(t.clone());
                    d.transition_duration = Some(rules.transition_duration);
                } else {
                    d.action = "cut".into();
                }
            } else {
                d.action = "cut".into();
            }
        }
        if p.zoom {
            d.effects.push("zoom_in".into());
        }
        if rules.picture_in_picture == PipMode::Always && n > 1 {
            let pip = last_other_source
                .clone()
                .filter(|s| *s != p.source)
                .or_else(|| inp.video_inputs.iter().find(|s| **s != p.source).cloned());
            if let Some(pip) = pip {
                d.pip_source = Some(pip);
                d.pip_size = Some(rules.pip_size);
            }
        }
        decisions.push(d);
        prev = Some(p);
    }

    EdlPlan {
        decisions,
        strategy,
        silence_removed: round3((before - after).max(0.0)),
    }
}

fn speaker_shots(inp: &EdlInputs<'_>, duration: f64) -> Vec<Piece> {
    let default_source = |speaker: &str| -> String {
        speaker
            .strip_prefix("SPEAKER_")
            .and_then(|n| n.parse::<usize>().ok())
            .and_then(|i| inp.video_inputs.get(i))
            .unwrap_or(&inp.video_inputs[0])
            .clone()
    };
    inp.speaker_turns
        .iter()
        .filter_map(|t| {
            let start = t.start.max(0.0);
            let end = t.end.min(duration);
            (end > start).then(|| Piece {
                source: inp
                    .speaker_mapping
                    .and_then(|m| m.get(&t.speaker).cloned())
                    .unwrap_or_else(|| default_source(&t.speaker)),
                start,
                end,
                zoom: false,
            })
        })
        .collect()
}

fn scene_shots(inp: &EdlInputs<'_>, duration: f64) -> Option<Vec<Piece>> {
    let mut cuts: Vec<f64> = inp
        .scene_changes
        .iter()
        .copied()
        .filter(|t| t.is_finite() && *t > 0.0 && *t < duration)
        .collect();
    cuts.sort_by(f64::total_cmp);
    let mut bounds = vec![0.0];
    for c in cuts {
        let last = *bounds.last().unwrap_or(&0.0);
        if c - last >= MIN_SCENE_SHOT_SECS && duration - c >= MIN_SCENE_SHOT_SECS {
            bounds.push(c);
        }
    }
    if bounds.len() < 2 {
        return None;
    }
    bounds.push(duration);
    let n = inp.video_inputs.len();
    Some(
        bounds
            .windows(2)
            .enumerate()
            .map(|(i, w)| Piece {
                source: inp.video_inputs[i % n].clone(),
                start: w[0],
                end: w[1],
                zoom: false,
            })
            .collect(),
    )
}

fn interval_shots(inputs: &[String], duration: f64) -> Vec<Piece> {
    let mut out = Vec::new();
    let mut t = 0.0;
    let mut i = 0;
    while t < duration {
        let mut end = (t + INTERVAL_SECS).min(duration);
        // Fold a very short tail into the last shot.
        if duration - end < MIN_SCENE_SHOT_SECS {
            end = duration;
        }
        out.push(Piece {
            source: inputs[i % inputs.len()].clone(),
            start: t,
            end,
            zoom: false,
        });
        t = end;
        i += 1;
    }
    out
}

/// Sort and merge overlapping intervals.
pub fn merge_intervals(mut v: Vec<(f64, f64)>) -> Vec<(f64, f64)> {
    v.retain(|(s, e)| s.is_finite() && e.is_finite() && e > s);
    v.sort_by(|a, b| a.0.total_cmp(&b.0));
    let mut out: Vec<(f64, f64)> = Vec::with_capacity(v.len());
    for (s, e) in v {
        match out.last_mut() {
            Some(last) if s <= last.1 => last.1 = last.1.max(e),
            _ => out.push((s, e)),
        }
    }
    out
}

/// Remove `cuts` from every piece, dropping fragments shorter than
/// [`MIN_PIECE_SECS`].
fn subtract_intervals(pieces: Vec<Piece>, cuts: &[(f64, f64)]) -> Vec<Piece> {
    let cuts = merge_intervals(cuts.to_vec());
    let mut out = Vec::new();
    for p in pieces {
        let mut cursor = p.start;
        for &(cs, ce) in &cuts {
            if ce <= cursor || cs >= p.end {
                continue;
            }
            if cs > cursor {
                out.push(Piece {
                    start: cursor,
                    end: cs,
                    ..p.clone()
                });
            }
            cursor = cursor.max(ce);
        }
        if p.end > cursor {
            out.push(Piece {
                start: cursor,
                ..p.clone()
            });
        }
    }
    out.retain(|p| p.end - p.start >= MIN_PIECE_SECS);
    out
}

/// Split a piece at emphasis windows, marking the overlapping parts as zoomed.
fn split_for_zoom(p: Piece, windows: &[(f64, f64)]) -> Vec<Piece> {
    let mut parts: Vec<Piece> = Vec::new();
    let mut cursor = p.start;
    for &(ws, we) in windows {
        if we <= cursor || ws >= p.end {
            continue;
        }
        if ws > cursor {
            parts.push(Piece {
                start: cursor,
                end: ws,
                zoom: false,
                ..p.clone()
            });
        }
        let end = we.min(p.end);
        parts.push(Piece {
            start: ws.max(cursor),
            end,
            zoom: true,
            ..p.clone()
        });
        cursor = end;
    }
    if p.end > cursor {
        parts.push(Piece {
            start: cursor,
            zoom: false,
            ..p.clone()
        });
    }
    // Merge slivers into their predecessor (or successor for the first one).
    let mut merged: Vec<Piece> = Vec::new();
    for part in parts {
        match merged.last_mut() {
            Some(last) if part.end - part.start < MIN_SUBSHOT_SECS || last.zoom == part.zoom => {
                last.end = part.end;
            },
            _ => merged.push(part),
        }
    }
    if merged.len() > 1 && merged[0].end - merged[0].start < MIN_SUBSHOT_SECS {
        let first = merged.remove(0);
        merged[0].start = first.start;
    }
    merged
}

/// Extract highlight moments from an analysis: audio peaks and transcript
/// segments containing emphasis keywords.
pub fn extract_highlights(analysis: &VideoAnalysis) -> Vec<Highlight> {
    let mut highlights = Vec::new();
    if let Some(audio) = &analysis.audio_analysis {
        for &t in &audio.peak_moments {
            highlights.push(Highlight {
                time: t,
                highlight_type: "audio_peak".into(),
                confidence: 0.6,
                keyword: None,
                text: None,
            });
        }
    }
    if let Some(transcript) = &analysis.transcript {
        const KEYWORDS: [&str; 7] = [
            "important",
            "key point",
            "summary",
            "in conclusion",
            "remember",
            "the main thing",
            "crucial",
        ];
        for segment in &transcript.segments {
            let lower = segment.text.to_lowercase();
            if let Some(k) = KEYWORDS.iter().find(|k| lower.contains(*k)) {
                highlights.push(Highlight {
                    time: segment.start,
                    highlight_type: "keyword".into(),
                    confidence: 0.9,
                    keyword: Some((*k).to_string()),
                    text: Some(segment.text.clone()),
                });
            }
        }
    }
    highlights.sort_by(|a, b| a.time.total_cmp(&b.time));
    highlights
}

/// Suggest edits (silence removal, emphasis, scene cuts) from an analysis.
pub fn generate_edit_suggestions(
    analysis: &VideoAnalysis,
    silence_threshold: f64,
) -> Vec<EditSuggestion> {
    let mut suggestions = Vec::new();
    if let Some(audio) = &analysis.audio_analysis {
        for &(start, end) in &audio.silence_segments {
            let d = end - start;
            if d >= silence_threshold {
                suggestions.push(EditSuggestion {
                    suggestion_type: "remove_silence".into(),
                    start: Some(start),
                    end: Some(end),
                    time: None,
                    effect: None,
                    transition: None,
                    reason: format!("Silence of {d:.1} seconds"),
                });
            }
        }
    }
    if let Some(highlights) = &analysis.highlights {
        for h in highlights {
            suggestions.push(EditSuggestion {
                suggestion_type: "add_emphasis".into(),
                start: None,
                end: None,
                time: Some(h.time),
                effect: Some("zoom_in".into()),
                transition: None,
                reason: format!("Highlight detected: {}", h.highlight_type),
            });
        }
    }
    if let Some(scenes) = &analysis.scene_changes {
        for &t in scenes.iter().take(10) {
            suggestions.push(EditSuggestion {
                suggestion_type: "scene_cut".into(),
                start: None,
                end: None,
                time: Some(t),
                effect: None,
                transition: Some("cross_dissolve".into()),
                reason: "Scene change detected".into(),
            });
        }
    }
    suggestions
}

fn round3(v: f64) -> f64 {
    (v * 1000.0).round() / 1000.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{AudioAnalysis, Transcript, TranscriptSegment};

    fn rules() -> EditingRules {
        EditingRules {
            transition_type: "cross_dissolve".into(),
            ..EditingRules::default()
        }
    }

    fn inputs(names: &[&str]) -> Vec<String> {
        names.iter().map(|s| s.to_string()).collect()
    }

    fn total(plan: &EdlPlan) -> f64 {
        plan.decisions.iter().map(|d| d.duration).sum()
    }

    #[test]
    fn single_input_without_cues_is_one_shot() {
        let vids = inputs(&["a.mp4"]);
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 42.0,
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.strategy, "full");
        assert_eq!(plan.decisions.len(), 1);
        assert_eq!(plan.decisions[0].duration, 42.0);
        assert_eq!(plan.decisions[0].action, "show");
    }

    #[test]
    fn zero_duration_yields_empty_plan() {
        let vids = inputs(&["a.mp4"]);
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                ..Default::default()
            },
            &rules(),
        );
        assert!(plan.decisions.is_empty());
    }

    #[test]
    fn scene_shots_cover_whole_timeline_including_tail() {
        let vids = inputs(&["a.mp4"]);
        let scenes = [5.0, 10.0, 15.0, 20.0];
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 30.0,
                scene_changes: &scenes,
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.strategy, "scene");
        assert_eq!(plan.decisions.len(), 5);
        assert_eq!(plan.decisions[0].timestamp, 0.0);
        assert!(
            (total(&plan) - 30.0).abs() < 1e-9,
            "tail after last scene is kept"
        );
        // Same source throughout: jump cuts, not dissolves.
        assert!(
            plan.decisions[1..]
                .iter()
                .all(|d| d.action == "cut" && d.transition_type.is_none())
        );
    }

    #[test]
    fn scene_cuts_too_close_are_ignored() {
        let vids = inputs(&["a.mp4"]);
        let scenes = [0.2, 5.0, 5.3, 9.9];
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 10.0,
                scene_changes: &scenes,
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.decisions.len(), 2);
    }

    #[test]
    fn interval_rotation_for_multiple_inputs() {
        let vids = inputs(&["a.mp4", "b.mp4"]);
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 25.0,
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.strategy, "interval");
        assert_eq!(plan.decisions.len(), 3);
        assert_eq!(plan.decisions[1].source, "b.mp4");
        assert_eq!(plan.decisions[1].action, "transition");
        assert_eq!(
            plan.decisions[1].transition_type.as_deref(),
            Some("cross_dissolve")
        );
        assert!((total(&plan) - 25.0).abs() < 1e-9);
    }

    #[test]
    fn speaker_turns_drive_sources_and_mapping() {
        let vids = inputs(&["a.mp4", "b.mp4"]);
        let turns = vec![
            SpeakerTurn {
                speaker: "SPEAKER_00".into(),
                start: 0.0,
                end: 4.0,
            },
            SpeakerTurn {
                speaker: "SPEAKER_01".into(),
                start: 4.0,
                end: 9.0,
            },
        ];
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 9.0,
                speaker_turns: &turns,
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.strategy, "speaker");
        assert_eq!(plan.decisions[0].source, "a.mp4");
        assert_eq!(plan.decisions[1].source, "b.mp4");

        let mut mapping = HashMap::new();
        mapping.insert("SPEAKER_01".to_string(), "c.mp4".to_string());
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 9.0,
                speaker_turns: &turns,
                speaker_mapping: Some(&mapping),
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.decisions[1].source, "c.mp4");
    }

    #[test]
    fn silence_is_removed_with_padding() {
        let vids = inputs(&["a.mp4"]);
        let silence = [(10.0, 14.0), (20.0, 21.0)];
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 30.0,
                silence: &silence,
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.decisions.len(), 2);
        assert_eq!(plan.decisions[0].timestamp, 0.0);
        assert_eq!(plan.decisions[0].duration, 10.25);
        assert_eq!(plan.decisions[1].timestamp, 13.75);
        assert_eq!(plan.decisions[1].action, "cut");
        assert!((plan.silence_removed - 3.5).abs() < 1e-9);
    }

    #[test]
    fn silence_kept_when_disabled() {
        let vids = inputs(&["a.mp4"]);
        let silence = [(10.0, 14.0)];
        let r = EditingRules {
            remove_silence: false,
            ..rules()
        };
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 30.0,
                silence: &silence,
                ..Default::default()
            },
            &r,
        );
        assert_eq!(plan.decisions.len(), 1);
        assert_eq!(plan.silence_removed, 0.0);
    }

    #[test]
    fn highlights_become_zoomed_subshots() {
        let vids = inputs(&["a.mp4"]);
        let hl = [10.0];
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 30.0,
                highlights: &hl,
                ..Default::default()
            },
            &rules(),
        );
        assert_eq!(plan.decisions.len(), 3);
        assert!(plan.decisions[1].effects.contains(&"zoom_in".to_string()));
        assert_eq!(plan.decisions[1].timestamp, 9.5);
        assert_eq!(plan.decisions[1].duration, 3.0);
        assert!((total(&plan) - 30.0).abs() < 1e-9);
    }

    #[test]
    fn pip_always_uses_other_input() {
        let vids = inputs(&["a.mp4", "b.mp4"]);
        let r = EditingRules {
            picture_in_picture: PipMode::Always,
            ..rules()
        };
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 20.0,
                ..Default::default()
            },
            &r,
        );
        for d in &plan.decisions {
            assert!(d.pip_source.is_some());
            assert_ne!(d.pip_source.as_deref(), Some(d.source.as_str()));
        }
    }

    #[test]
    fn cut_transition_type_yields_hard_cuts() {
        let vids = inputs(&["a.mp4", "b.mp4"]);
        let r = EditingRules {
            transition_type: "cut".into(),
            ..rules()
        };
        let plan = generate_edl(
            &EdlInputs {
                video_inputs: &vids,
                timeline_duration: 20.0,
                ..Default::default()
            },
            &r,
        );
        assert!(plan.decisions.iter().all(|d| d.transition_type.is_none()));
    }

    #[test]
    fn transition_names() {
        assert_eq!(xfade_transition("cross_dissolve").unwrap(), Some("fade"));
        assert_eq!(xfade_transition("CUT").unwrap(), None);
        assert!(xfade_transition("explode").is_err());
    }

    #[test]
    fn rules_resolution_and_validation() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(tmp.path());
        let r = resolve_rules(None, &cfg).unwrap();
        assert_eq!(r.silence_threshold, cfg.silence_threshold);
        assert_eq!(r.transition_type, "cross_dissolve");
        let bad = EditingRulesInput {
            pip_size: Some(2.0),
            ..Default::default()
        };
        assert!(resolve_rules(Some(bad), &cfg).is_err());
        let bad = EditingRulesInput {
            speaker_switch_delay: Some(f64::NAN),
            ..Default::default()
        };
        assert!(resolve_rules(Some(bad), &cfg).is_err());
        let bad = EditingRulesInput {
            transition_type: Some("spin".into()),
            ..Default::default()
        };
        assert!(resolve_rules(Some(bad), &cfg).is_err());
    }

    #[test]
    fn merge_intervals_merges_and_drops_invalid() {
        let m = merge_intervals(vec![
            (5.0, 6.0),
            (1.0, 3.0),
            (2.0, 4.0),
            (7.0, 7.0),
            (f64::NAN, 1.0),
        ]);
        assert_eq!(m, vec![(1.0, 4.0), (5.0, 6.0)]);
    }

    #[test]
    fn highlights_and_suggestions() {
        let mut a = VideoAnalysis::new("a.mp4", 0);
        a.audio_analysis = Some(AudioAnalysis {
            duration: 60.0,
            sample_rate: 16000,
            silence_segments: vec![(1.0, 2.0), (10.0, 15.0)],
            volume_profile: vec![],
            peak_moments: vec![30.0],
            mean_db: -20.0,
            max_db: -3.0,
        });
        a.transcript = Some(Transcript {
            text: String::new(),
            language: "en".into(),
            segments: vec![TranscriptSegment {
                id: 0,
                start: 5.0,
                end: 7.0,
                text: "This is IMPORTANT".into(),
                words: vec![],
            }],
        });
        let h = extract_highlights(&a);
        assert_eq!(h.len(), 2);
        assert_eq!(h[0].time, 5.0);
        assert_eq!(h[0].keyword.as_deref(), Some("important"));
        a.highlights = Some(h);
        a.scene_changes = Some(vec![12.0]);
        let s = generate_edit_suggestions(&a, 2.0);
        assert_eq!(
            s.iter()
                .filter(|s| s.suggestion_type == "remove_silence")
                .count(),
            1
        );
        assert_eq!(
            s.iter()
                .filter(|s| s.suggestion_type == "add_emphasis")
                .count(),
            2
        );
        assert_eq!(
            s.iter()
                .filter(|s| s.suggestion_type == "scene_cut")
                .count(),
            1
        );
    }

    #[test]
    fn empty_analysis_has_no_highlights() {
        assert!(extract_highlights(&VideoAnalysis::new("a.mp4", 0)).is_empty());
    }
}

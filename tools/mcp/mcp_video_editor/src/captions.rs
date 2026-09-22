//! Caption generation: SRT cue building (with line wrapping) and translation
//! of [`CaptionStyle`] into a libass `force_style` string.

use std::fmt::Write as _;

use anyhow::{Result, bail};

use crate::types::{CaptionStyle, TranscriptSegmentWithSpeaker};

/// Maximum text lines shown at once in a caption.
const MAX_LINES_PER_CUE: usize = 2;

/// libass renders SRT with a script height of 288; font sizes are relative to it.
const ASS_PLAY_RES_Y: f64 = 288.0;

/// A single subtitle cue.
#[derive(Debug, Clone, PartialEq)]
pub struct Cue {
    pub start: f64,
    pub end: f64,
    /// One or more display lines.
    pub lines: Vec<String>,
}

/// Greedy word wrap into lines of at most `max_chars` characters. Words longer
/// than the limit are placed on their own line rather than split.
pub fn wrap_text(text: &str, max_chars: usize) -> Vec<String> {
    let max_chars = max_chars.max(1);
    let mut lines = Vec::new();
    let mut current = String::new();
    for word in text.split_whitespace() {
        let needed = if current.is_empty() {
            word.chars().count()
        } else {
            current.chars().count() + 1 + word.chars().count()
        };
        if needed > max_chars && !current.is_empty() {
            lines.push(std::mem::take(&mut current));
        }
        if !current.is_empty() {
            current.push(' ');
        }
        current.push_str(word);
    }
    if !current.is_empty() {
        lines.push(current);
    }
    lines
}

/// Build cues from transcript segments.
///
/// Each segment's text is wrapped to `max_chars` per line; segments needing
/// more than [`MAX_LINES_PER_CUE`] lines are split into consecutive cues whose
/// durations are proportional to their character counts. When
/// `speaker_names` is set and a segment carries a speaker label, the label is
/// prefixed (`SPEAKER_00: ...`).
pub fn build_cues(
    segments: &[TranscriptSegmentWithSpeaker],
    max_chars: usize,
    speaker_names: bool,
) -> Vec<Cue> {
    let mut cues = Vec::new();
    for seg in segments {
        let text = seg.text.trim();
        if text.is_empty() || seg.end.is_nan() || seg.end <= seg.start {
            continue;
        }
        let text = match (&seg.speaker, speaker_names) {
            (Some(spk), true) => format!("{spk}: {text}"),
            _ => text.to_string(),
        };
        let lines = wrap_text(&text, max_chars);
        let groups: Vec<&[String]> = lines.chunks(MAX_LINES_PER_CUE).collect();
        let total_chars: usize = lines
            .iter()
            .map(|l| l.chars().count())
            .sum::<usize>()
            .max(1);
        let span = seg.end - seg.start;
        let mut t = seg.start;
        for (i, group) in groups.iter().enumerate() {
            let chars: usize = group.iter().map(|l| l.chars().count()).sum();
            let end = if i + 1 == groups.len() {
                seg.end
            } else {
                t + span * chars as f64 / total_chars as f64
            };
            cues.push(Cue {
                start: t,
                end,
                lines: group.to_vec(),
            });
            t = end;
        }
    }
    cues
}

/// Format seconds as an SRT timestamp (`HH:MM:SS,mmm`).
pub fn format_srt_timestamp(seconds: f64) -> String {
    let total_ms = (seconds.max(0.0) * 1000.0).round() as u64;
    let ms = total_ms % 1000;
    let s = (total_ms / 1000) % 60;
    let m = (total_ms / 60_000) % 60;
    let h = total_ms / 3_600_000;
    format!("{h:02}:{m:02}:{s:02},{ms:03}")
}

/// Render cues as SRT text.
pub fn render_srt(cues: &[Cue]) -> String {
    let mut out = String::new();
    for (i, cue) in cues.iter().enumerate() {
        let _ = writeln!(out, "{}", i + 1);
        let _ = writeln!(
            out,
            "{} --> {}",
            format_srt_timestamp(cue.start),
            format_srt_timestamp(cue.end)
        );
        for line in &cue.lines {
            let _ = writeln!(out, "{line}");
        }
        out.push('\n');
    }
    out
}

/// Parse `#RRGGBB` / `#RRGGBBAA` into an ASS colour `&HAABBGGRR`
/// (ASS alpha is inverted: 00 = opaque).
pub fn css_to_ass_color(color: &str) -> Result<String> {
    let hex = color.trim().trim_start_matches('#');
    if !(hex.len() == 6 || hex.len() == 8) || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
        bail!("Invalid colour '{color}' (expected #RRGGBB or #RRGGBBAA)");
    }
    let byte = |i: usize| u8::from_str_radix(&hex[i..i + 2], 16).unwrap_or(0);
    let (r, g, b) = (byte(0), byte(2), byte(4));
    let alpha = if hex.len() == 8 { 255 - byte(6) } else { 0 };
    Ok(format!("&H{alpha:02X}{b:02X}{g:02X}{r:02X}"))
}

/// Build a libass `force_style` string for `style`, scaling the pixel font
/// size to the video's height.
pub fn force_style(style: &CaptionStyle, video_height: u32) -> Result<String> {
    let font = style.font.trim();
    if font.is_empty()
        || font.len() > 64
        || !font
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, ' ' | '-' | '_'))
    {
        bail!(
            "Invalid font name '{}' (letters, digits, space, '-' and '_' only)",
            style.font
        );
    }
    if !(8..=300).contains(&style.size) {
        bail!("Caption size {} out of range (8..=300 pixels)", style.size);
    }
    let alignment = match style.position.trim().to_ascii_lowercase().as_str() {
        "bottom" => 2,
        "middle" | "center" | "centre" => 5,
        "top" => 8,
        other => bail!("Invalid caption position '{other}' (bottom, middle or top)"),
    };
    let height = if video_height > 0 {
        video_height as f64
    } else {
        1080.0
    };
    let font_size = ((style.size as f64) * ASS_PLAY_RES_Y / height)
        .round()
        .max(1.0);
    let primary = css_to_ass_color(&style.color)?;

    let bg = style.background.trim().to_ascii_lowercase();
    let box_style = if bg.is_empty() || bg == "none" || bg == "transparent" {
        "BorderStyle=1,Outline=1.5,Shadow=0,OutlineColour=&H00000000".to_string()
    } else {
        let c = css_to_ass_color(&style.background)?;
        format!("BorderStyle=3,Outline=1,Shadow=0,OutlineColour={c},BackColour={c}")
    };
    Ok(format!(
        "FontName={font},FontSize={font_size},PrimaryColour={primary},{box_style},Alignment={alignment},MarginV=12"
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn seg(
        start: f64,
        end: f64,
        text: &str,
        speaker: Option<&str>,
    ) -> TranscriptSegmentWithSpeaker {
        TranscriptSegmentWithSpeaker {
            id: 0,
            start,
            end,
            text: text.into(),
            speaker: speaker.map(Into::into),
        }
    }

    #[test]
    fn srt_timestamps() {
        assert_eq!(format_srt_timestamp(0.0), "00:00:00,000");
        assert_eq!(format_srt_timestamp(3661.5), "01:01:01,500");
        assert_eq!(format_srt_timestamp(59.9999), "00:01:00,000");
        assert_eq!(format_srt_timestamp(-1.0), "00:00:00,000");
    }

    #[test]
    fn wrapping() {
        assert_eq!(
            wrap_text("the quick brown fox", 9),
            vec!["the quick", "brown fox"]
        );
        assert_eq!(
            wrap_text("supercalifragilistic word", 5),
            vec!["supercalifragilistic", "word"]
        );
        assert!(wrap_text("   ", 10).is_empty());
    }

    #[test]
    fn long_segments_split_into_multiple_cues() {
        let text = "one two three four five six seven eight nine ten";
        let cues = build_cues(&[seg(0.0, 10.0, text, None)], 10, false);
        assert!(cues.len() >= 2);
        assert!(cues.iter().all(|c| c.lines.len() <= MAX_LINES_PER_CUE));
        assert_eq!(cues.first().unwrap().start, 0.0);
        assert_eq!(cues.last().unwrap().end, 10.0);
        for w in cues.windows(2) {
            assert!((w[0].end - w[1].start).abs() < 1e-9);
        }
    }

    #[test]
    fn empty_and_invalid_segments_skipped() {
        let cues = build_cues(
            &[seg(0.0, 1.0, "  ", None), seg(2.0, 2.0, "x", None)],
            40,
            false,
        );
        assert!(cues.is_empty());
    }

    #[test]
    fn speaker_prefix() {
        let cues = build_cues(&[seg(0.0, 1.0, "hi", Some("SPEAKER_01"))], 40, true);
        assert_eq!(cues[0].lines[0], "SPEAKER_01: hi");
        let cues = build_cues(&[seg(0.0, 1.0, "hi", Some("SPEAKER_01"))], 40, false);
        assert_eq!(cues[0].lines[0], "hi");
    }

    #[test]
    fn srt_rendering() {
        let srt = render_srt(&[Cue {
            start: 0.0,
            end: 1.5,
            lines: vec!["a".into(), "b".into()],
        }]);
        assert_eq!(srt, "1\n00:00:00,000 --> 00:00:01,500\na\nb\n\n");
    }

    #[test]
    fn colour_conversion() {
        assert_eq!(css_to_ass_color("#FF8000").unwrap(), "&H000080FF");
        assert_eq!(css_to_ass_color("#00000080").unwrap(), "&H7F000000");
        assert!(css_to_ass_color("red").is_err());
    }

    #[test]
    fn force_style_building() {
        let style = CaptionStyle::default();
        let s = force_style(&style, 1080).unwrap();
        assert!(s.contains("FontName=Arial"));
        assert!(s.contains("FontSize=11")); // 42 * 288 / 1080 = 11.2
        assert!(s.contains("Alignment=2"));
        assert!(s.contains("BorderStyle=3"));
    }

    #[test]
    fn force_style_rejects_injection() {
        let style = CaptionStyle {
            font: "Arial,Outline=9".into(),
            ..CaptionStyle::default()
        };
        assert!(force_style(&style, 1080).is_err());
        let style = CaptionStyle {
            position: "left".into(),
            ..CaptionStyle::default()
        };
        assert!(force_style(&style, 1080).is_err());
    }

    #[test]
    fn force_style_no_background() {
        let style = CaptionStyle {
            background: "none".into(),
            position: "top".into(),
            ..CaptionStyle::default()
        };
        let s = force_style(&style, 720).unwrap();
        assert!(s.contains("BorderStyle=1"));
        assert!(s.contains("Alignment=8"));
    }
}

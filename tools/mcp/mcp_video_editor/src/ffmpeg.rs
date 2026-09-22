//! ffmpeg / ffprobe helpers: safe argument construction, filter escaping,
//! media probing and encoder selection.
//!
//! # Safety model
//!
//! * Every command is spawned directly (no shell), so there is no shell
//!   injection surface.
//! * File paths handed to ffmpeg are prefixed with the `file:` protocol
//!   ([`media_arg`]). That prevents a user-supplied "path" such as
//!   `http://...`, `concat:...` or `-` (stdin) from being interpreted as a
//!   network protocol or pseudo-input, and stops an output path that starts
//!   with `-` from being parsed as an option.
//! * Values embedded in filtergraph strings go through
//!   [`escape_filter_value`], which applies both of ffmpeg's escaping levels so
//!   characters like `'`, `:`, `,`, `;`, `[` and `]` cannot break out of the
//!   option value and inject additional filters.

use std::ffi::OsString;
use std::path::Path;

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use tokio::process::Command;
use tokio::sync::OnceCell;
use tracing::info;

use crate::process::{output_with_timeout, run_checked};

/// Build an `ffmpeg` command with quiet, non-interactive defaults.
pub fn ffmpeg() -> Command {
    let mut cmd = Command::new("ffmpeg");
    cmd.args(["-hide_banner", "-nostdin", "-nostats", "-loglevel", "error"]);
    cmd
}

/// Argument for a local media file: `file:` + path.
pub fn media_arg(path: &Path) -> OsString {
    let mut s = OsString::from("file:");
    s.push(path.as_os_str());
    s
}

/// Escape an arbitrary string for use as a filter option value inside a
/// filtergraph passed to `-vf` / `-filter_complex`.
///
/// Level 1 (option value): wrap in single quotes; an embedded `'` becomes
/// `'\''`. Level 2 (filtergraph): backslash-escape `\ ' [ ] , ;`.
pub fn escape_filter_value(value: &str) -> String {
    let level1 = format!("'{}'", value.replace('\'', r"'\''"));
    let mut level2 = String::with_capacity(level1.len() * 2);
    for ch in level1.chars() {
        if matches!(ch, '\\' | '\'' | '[' | ']' | ',' | ';') {
            level2.push('\\');
        }
        level2.push(ch);
    }
    level2
}

/// Escape a path for a line of an ffmpeg concat-demuxer list file.
pub fn concat_list_line(path: &Path) -> String {
    format!("file '{}'\n", path.to_string_lossy().replace('\'', r"'\''"))
}

/// Format a time value for ffmpeg (fixed precision, never exponent notation).
pub fn fmt_time(seconds: f64) -> String {
    format!("{:.3}", seconds.max(0.0))
}

/// Basic information about a media file.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MediaInfo {
    /// Container duration in seconds (0 if unknown).
    pub duration: f64,
    /// Video width in pixels (0 if no video stream).
    pub width: u32,
    /// Video height in pixels (0 if no video stream).
    pub height: u32,
    /// Average video frame rate.
    pub fps: f64,
    /// Video codec name.
    pub video_codec: Option<String>,
    /// Audio codec name, if an audio stream exists.
    pub audio_codec: Option<String>,
    /// Whether the file has a video stream.
    pub has_video: bool,
    /// Whether the file has an audio stream.
    pub has_audio: bool,
    /// Size of the file in bytes.
    pub file_size: u64,
    /// Overall bitrate in bits/s (0 if unknown).
    pub bitrate: u64,
    /// Container format name reported by ffprobe.
    pub format_name: Option<String>,
}

/// Parse an ffprobe rational such as `30000/1001`.
pub fn parse_rational(r: &str) -> Option<f64> {
    match r.split_once('/') {
        Some((n, d)) => {
            let n: f64 = n.trim().parse().ok()?;
            let d: f64 = d.trim().parse().ok()?;
            (d != 0.0).then_some(n / d)
        },
        None => r.trim().parse().ok(),
    }
}

/// Parse ffprobe JSON (`-show_format -show_streams`) into [`MediaInfo`].
pub fn parse_probe_json(json: &[u8], file_size: u64) -> Result<MediaInfo> {
    #[derive(Deserialize)]
    struct Probe {
        format: Option<Format>,
        #[serde(default)]
        streams: Vec<Stream>,
    }
    #[derive(Deserialize)]
    struct Format {
        duration: Option<String>,
        bit_rate: Option<String>,
        format_name: Option<String>,
    }
    #[derive(Deserialize)]
    struct Stream {
        codec_type: Option<String>,
        codec_name: Option<String>,
        width: Option<u32>,
        height: Option<u32>,
        avg_frame_rate: Option<String>,
        r_frame_rate: Option<String>,
        duration: Option<String>,
        disposition: Option<serde_json::Value>,
    }

    let probe: Probe = serde_json::from_slice(json).context("Failed to parse ffprobe output")?;
    // Skip cover-art "video" streams (attached pictures).
    let video = probe.streams.iter().find(|s| {
        s.codec_type.as_deref() == Some("video")
            && s.disposition
                .as_ref()
                .and_then(|d| d.get("attached_pic"))
                .and_then(|v| v.as_i64())
                .unwrap_or(0)
                == 0
    });
    let audio = probe
        .streams
        .iter()
        .find(|s| s.codec_type.as_deref() == Some("audio"));

    let fps = video
        .and_then(|v| {
            v.avg_frame_rate
                .as_deref()
                .and_then(parse_rational)
                .filter(|f| *f > 0.0)
                .or_else(|| v.r_frame_rate.as_deref().and_then(parse_rational))
        })
        .filter(|f| f.is_finite() && *f > 0.0)
        .unwrap_or(0.0);

    let format = probe.format.as_ref();
    let duration = format
        .and_then(|f| f.duration.as_deref())
        .and_then(|d| d.parse::<f64>().ok())
        .or_else(|| {
            probe
                .streams
                .iter()
                .filter_map(|s| s.duration.as_deref()?.parse::<f64>().ok())
                .reduce(f64::max)
        })
        .filter(|d| d.is_finite() && *d >= 0.0)
        .unwrap_or(0.0);

    Ok(MediaInfo {
        duration,
        width: video.and_then(|v| v.width).unwrap_or(0),
        height: video.and_then(|v| v.height).unwrap_or(0),
        fps,
        video_codec: video.and_then(|v| v.codec_name.clone()),
        audio_codec: audio.and_then(|a| a.codec_name.clone()),
        has_video: video.is_some(),
        has_audio: audio.is_some(),
        file_size,
        bitrate: format
            .and_then(|f| f.bit_rate.as_deref())
            .and_then(|b| b.parse().ok())
            .unwrap_or(0),
        format_name: format.and_then(|f| f.format_name.clone()),
    })
}

/// Probe a media file with ffprobe.
pub async fn probe(path: &Path) -> Result<MediaInfo> {
    let file_size = std::fs::metadata(path)
        .with_context(|| format!("Cannot read {}", path.display()))?
        .len();
    let output = run_checked(
        Command::new("ffprobe")
            .args([
                "-v",
                "error",
                "-show_entries",
                "format=duration,bit_rate,format_name:stream=codec_type,codec_name,width,height,\
                 avg_frame_rate,r_frame_rate,duration:stream_disposition=attached_pic",
                "-of",
                "json",
            ])
            .arg(media_arg(path)),
        "ffprobe",
    )
    .await
    .with_context(|| {
        format!(
            "Could not probe {} (is it a valid media file?)",
            path.display()
        )
    })?;
    parse_probe_json(&output.stdout, file_size)
}

/// Supported output container formats.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Container {
    Mp4,
    Mov,
    Mkv,
    Webm,
}

impl Container {
    /// Parse a format name (`mp4`, `mov`, `mkv`/`matroska`, `webm`).
    pub fn parse(s: &str) -> Result<Self> {
        match s
            .trim()
            .trim_start_matches('.')
            .to_ascii_lowercase()
            .as_str()
        {
            "mp4" | "m4v" => Ok(Self::Mp4),
            "mov" => Ok(Self::Mov),
            "mkv" | "matroska" => Ok(Self::Mkv),
            "webm" => Ok(Self::Webm),
            other => bail!("Unsupported output format '{other}' (supported: mp4, mov, mkv, webm)"),
        }
    }

    /// Infer the container from a file extension, if recognised.
    pub fn from_path(path: &Path) -> Option<Self> {
        path.extension()
            .and_then(|e| e.to_str())
            .and_then(|e| Self::parse(e).ok())
    }

    /// Canonical file extension.
    pub fn extension(self) -> &'static str {
        match self {
            Self::Mp4 => "mp4",
            Self::Mov => "mov",
            Self::Mkv => "mkv",
            Self::Webm => "webm",
        }
    }

    /// Audio encoder arguments suited to the container.
    pub fn audio_args(self) -> Vec<String> {
        match self {
            Self::Webm => vec![
                "-c:a".into(),
                "libopus".into(),
                "-b:a".into(),
                "128k".into(),
            ],
            _ => vec!["-c:a".into(), "aac".into(), "-b:a".into(), "192k".into()],
        }
    }

    /// Container-specific muxer flags.
    pub fn mux_args(self) -> Vec<String> {
        match self {
            Self::Mp4 | Self::Mov => vec!["-movflags".into(), "+faststart".into()],
            _ => Vec::new(),
        }
    }

    /// Subtitle codec for soft (non-burned) subtitles.
    pub fn subtitle_codec(self) -> &'static str {
        match self {
            Self::Mp4 | Self::Mov => "mov_text",
            Self::Mkv => "srt",
            Self::Webm => "webvtt",
        }
    }
}

/// Video encoders the server is willing to use.
pub const ALLOWED_VIDEO_CODECS: &[&str] = &[
    "libx264",
    "libx265",
    "h264_nvenc",
    "hevc_nvenc",
    "libvpx-vp9",
];

/// Validate a user-requested encoder name against the allowlist and container.
pub fn validate_codec(codec: &str, container: Container) -> Result<()> {
    if !ALLOWED_VIDEO_CODECS.contains(&codec) {
        bail!(
            "Unsupported codec '{codec}' (supported: {})",
            ALLOWED_VIDEO_CODECS.join(", ")
        );
    }
    let is_vp9 = codec == "libvpx-vp9";
    if (container == Container::Webm) != is_vp9 {
        bail!(
            "Codec '{codec}' is not compatible with the {} container (webm requires libvpx-vp9)",
            container.extension()
        );
    }
    Ok(())
}

/// Encoder arguments (codec + rate control) for a video encoder.
pub fn video_encoder_args(codec: &str, bitrate: &str, fast: bool) -> Vec<String> {
    let mut args = vec!["-c:v".to_string(), codec.to_string()];
    match codec {
        "libx264" | "libx265" => {
            args.extend([
                "-preset".into(),
                if fast { "veryfast" } else { "medium" }.into(),
            ]);
        },
        "h264_nvenc" | "hevc_nvenc" => {
            args.extend(["-preset".into(), if fast { "p2" } else { "p5" }.into()]);
        },
        "libvpx-vp9" => {
            args.extend([
                "-deadline".into(),
                "good".into(),
                "-cpu-used".into(),
                if fast { "5" } else { "2" }.into(),
                "-row-mt".into(),
                "1".into(),
            ]);
        },
        _ => {},
    }
    args.extend([
        "-b:v".into(),
        bitrate.to_string(),
        "-pix_fmt".into(),
        "yuv420p".into(),
    ]);
    args
}

/// Whether NVENC H.264 encoding actually works on this machine (encoder
/// compiled in *and* a usable GPU). Probed once with a tiny test encode.
pub async fn nvenc_available() -> bool {
    static NVENC: OnceCell<bool> = OnceCell::const_new();
    *NVENC
        .get_or_init(|| async {
            let result = output_with_timeout(
                ffmpeg().args([
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=256x256:d=0.1",
                    "-c:v",
                    "h264_nvenc",
                    "-f",
                    "null",
                    "-",
                ]),
                "ffmpeg NVENC probe",
            )
            .await;
            let ok = matches!(result, Ok(ref o) if o.status.success());
            info!("NVENC hardware encoding available: {}", ok);
            ok
        })
        .await
}

/// Pick the video encoder for a render.
///
/// An explicit `requested` codec wins (after validation). Otherwise VP9 for
/// webm, NVENC H.264 when hardware acceleration is allowed and works, else
/// libx264.
pub async fn select_codec(
    requested: Option<&str>,
    container: Container,
    allow_hw: bool,
) -> Result<String> {
    if let Some(codec) = requested.map(str::trim).filter(|c| !c.is_empty()) {
        validate_codec(codec, container)?;
        return Ok(codec.to_string());
    }
    if container == Container::Webm {
        return Ok("libvpx-vp9".to_string());
    }
    if allow_hw && nvenc_available().await {
        return Ok("h264_nvenc".to_string());
    }
    Ok("libx264".to_string())
}

/// Validate a bitrate string such as `8M`, `2500k` or `1500000`.
pub fn validate_bitrate(bitrate: &str) -> Result<()> {
    let b = bitrate.trim();
    let digits_end = b
        .find(|c: char| !(c.is_ascii_digit() || c == '.'))
        .unwrap_or(b.len());
    let (num, suffix) = b.split_at(digits_end);
    let valid_num = num
        .parse::<f64>()
        .map(|n| n > 0.0 && n.is_finite())
        .unwrap_or(false);
    let valid_suffix = matches!(suffix, "" | "k" | "K" | "m" | "M" | "g" | "G");
    if !(valid_num && valid_suffix) {
        bail!("Invalid bitrate '{bitrate}' (expected e.g. '8M', '2500k')");
    }
    Ok(())
}

/// Parse and validate a `WIDTHxHEIGHT` resolution. Dimensions must be even
/// (required by yuv420p encoders) and between 16 and 7680.
pub fn parse_resolution(resolution: &str) -> Result<(u32, u32)> {
    let (w, h) = resolution.trim().split_once(['x', 'X']).ok_or_else(|| {
        anyhow::anyhow!("Invalid resolution '{resolution}' (expected WIDTHxHEIGHT)")
    })?;
    let w: u32 = w
        .trim()
        .parse()
        .with_context(|| format!("Invalid width in '{resolution}'"))?;
    let h: u32 = h
        .trim()
        .parse()
        .with_context(|| format!("Invalid height in '{resolution}'"))?;
    for d in [w, h] {
        if !(16..=7680).contains(&d) {
            bail!("Resolution '{resolution}' out of range (each side 16..=7680)");
        }
        if d % 2 != 0 {
            bail!("Resolution '{resolution}' must use even dimensions");
        }
    }
    Ok((w, h))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn escape_plain_path() {
        assert_eq!(escape_filter_value("/tmp/a.srt"), r"\'/tmp/a.srt\'");
    }

    #[test]
    fn escape_special_characters() {
        let e = escape_filter_value("a'b,c;d[e]f:g\\h");
        // Every graph-level special char is backslash-escaped.
        assert!(e.contains(r"\,"));
        assert!(e.contains(r"\;"));
        assert!(e.contains(r"\["));
        assert!(e.contains(r"\]"));
        // Colon is protected by the level-1 quotes and left as-is.
        assert!(e.contains(":g"));
        // Backslash doubled.
        assert!(e.contains(r"\\h"));
        // No unescaped comma/semicolon remains.
        let bytes: Vec<char> = e.chars().collect();
        for (i, c) in bytes.iter().enumerate() {
            if matches!(c, ',' | ';' | '[' | ']') {
                assert_eq!(bytes[i - 1], '\\', "unescaped {c} at {i} in {e}");
            }
        }
    }

    #[test]
    fn concat_line_escapes_quotes() {
        assert_eq!(
            concat_list_line(Path::new("/a/it's.mkv")),
            "file '/a/it'\\''s.mkv'\n"
        );
    }

    #[test]
    fn media_arg_prefixes_file_protocol() {
        assert_eq!(media_arg(Path::new("-y")), OsString::from("file:-y"));
    }

    #[test]
    fn rational_parsing() {
        assert!((parse_rational("30000/1001").unwrap() - 29.97).abs() < 0.01);
        assert_eq!(parse_rational("25"), Some(25.0));
        assert_eq!(parse_rational("0/0"), None);
        assert_eq!(parse_rational("abc"), None);
    }

    #[test]
    fn probe_json_parsing() {
        let json = br#"{
            "streams": [
                {"codec_type": "video", "codec_name": "mjpeg", "width": 300, "height": 300,
                 "avg_frame_rate": "0/0", "disposition": {"attached_pic": 1}},
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                 "avg_frame_rate": "30/1", "disposition": {"attached_pic": 0}},
                {"codec_type": "audio", "codec_name": "aac"}
            ],
            "format": {"duration": "12.5", "bit_rate": "800000", "format_name": "mov,mp4"}
        }"#;
        let info = parse_probe_json(json, 1234).unwrap();
        assert_eq!(info.width, 1920);
        assert_eq!(info.video_codec.as_deref(), Some("h264"));
        assert!(info.has_audio);
        assert_eq!(info.fps, 30.0);
        assert_eq!(info.duration, 12.5);
        assert_eq!(info.file_size, 1234);
    }

    #[test]
    fn probe_json_audio_only() {
        let json =
            br#"{"streams":[{"codec_type":"audio","codec_name":"pcm_s16le","duration":"3.0"}],
                        "format":{}}"#;
        let info = parse_probe_json(json, 0).unwrap();
        assert!(!info.has_video);
        assert_eq!(info.duration, 3.0);
    }

    #[test]
    fn container_parsing() {
        assert_eq!(Container::parse("MP4").unwrap(), Container::Mp4);
        assert_eq!(Container::parse(".mkv").unwrap(), Container::Mkv);
        assert!(Container::parse("avi").is_err());
        assert_eq!(
            Container::from_path(Path::new("x.webm")),
            Some(Container::Webm)
        );
    }

    #[test]
    fn codec_validation() {
        assert!(validate_codec("libx264", Container::Mp4).is_ok());
        assert!(validate_codec("libvpx-vp9", Container::Webm).is_ok());
        assert!(validate_codec("libx264", Container::Webm).is_err());
        assert!(validate_codec("rm -rf", Container::Mp4).is_err());
    }

    #[test]
    fn bitrate_validation() {
        for ok in ["8M", "2500k", "1500000", "1.5M"] {
            assert!(validate_bitrate(ok).is_ok(), "{ok}");
        }
        for bad in ["", "M", "-1M", "8MB", "8M -y", "0"] {
            assert!(validate_bitrate(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn resolution_validation() {
        assert_eq!(parse_resolution("1920x1080").unwrap(), (1920, 1080));
        assert_eq!(parse_resolution("640X360").unwrap(), (640, 360));
        assert!(parse_resolution("1921x1080").is_err());
        assert!(parse_resolution("abc").is_err());
        assert!(parse_resolution("8x8").is_err());
    }

    #[test]
    fn encoder_args_include_bitrate() {
        let args = video_encoder_args("libx264", "4M", true);
        assert!(args.windows(2).any(|w| w[0] == "-b:v" && w[1] == "4M"));
        assert!(args.contains(&"veryfast".to_string()));
    }

    #[test]
    fn time_formatting() {
        assert_eq!(fmt_time(1.23456), "1.235");
        assert_eq!(fmt_time(-3.0), "0.000");
        assert_eq!(fmt_time(1e-9), "0.000");
    }
}

//! Audio pipeline for the Virtual Character MCP server.
//!
//! Responsibilities:
//! - Resolve `play_audio` input (file path, http(s) URL, data URL, raw base64)
//!   into bytes, with size limits, timeouts and path allow-listing.
//! - Detect/validate the audio container from magic bytes and estimate its
//!   duration (WAV header, CBR MP3 frame header).
//! - Play audio on the local machine through an external player (VLC,
//!   ffplay, PowerShell `SoundPlayer`, paplay/aplay) without blocking the
//!   caller: playback runs in a background task that enforces a maximum
//!   runtime and removes the temporary file afterwards.

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use base64::Engine;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use tokio::sync::oneshot;
use tracing::{debug, info, warn};

/// Minimum size for a valid audio payload (bytes).
pub const MIN_AUDIO_SIZE: usize = 100;

/// Maximum accepted audio payload (bytes) from any source.
pub const MAX_AUDIO_SIZE: usize = 50 * 1024 * 1024;

/// Total timeout for downloading audio from a URL.
pub const DOWNLOAD_TIMEOUT: Duration = Duration::from_secs(30);

/// Playback is killed after this long if no duration hint is available.
pub const DEFAULT_MAX_PLAYBACK: Duration = Duration::from_secs(600);

/// How long to wait after spawning a player to see whether it failed
/// immediately (bad device, unsupported format, ...).
const PLAYER_STARTUP_GRACE: Duration = Duration::from_millis(400);

/// Environment variable with extra directories (OS path-list syntax) from
/// which `play_audio` may read files.
pub const AUDIO_DIRS_ENV: &str = "VIRTUAL_CHARACTER_AUDIO_DIRS";

/// Default base directories file reads are allowed from (in addition to the
/// OS temp directory and [`AUDIO_DIRS_ENV`]).
pub static ALLOWED_AUDIO_PATHS: &[&str] = &["outputs", "/tmp"];

/// Container-path to host-path rewrites (the ElevenLabs container writes to
/// `/tmp/elevenlabs_audio`, which is bind-mounted to `outputs/elevenlabs_speech`).
const PATH_MAPPINGS: &[(&str, &str)] = &[
    ("/tmp/elevenlabs_audio/", "outputs/elevenlabs_speech/"),
    ("/tmp/audio_storage/", "outputs/audio_storage/"),
];

/// Audio container format.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AudioFormat {
    Mp3,
    Wav,
    Ogg,
    Flac,
    /// Headerless 16-bit little-endian PCM (wrapped into WAV before playback).
    Pcm,
    Unknown,
}

impl AudioFormat {
    /// Get file extension for this format.
    pub fn extension(&self) -> &'static str {
        match self {
            AudioFormat::Mp3 => "mp3",
            AudioFormat::Wav | AudioFormat::Pcm => "wav",
            AudioFormat::Ogg => "ogg",
            AudioFormat::Flac => "flac",
            AudioFormat::Unknown => "bin",
        }
    }

    /// Parse a user-supplied format name (`mp3`, `wav`, `opus`, `ogg`,
    /// `flac`, `pcm`). Returns `None` for unknown names.
    pub fn from_name(name: &str) -> Option<Self> {
        match name.trim().to_lowercase().as_str() {
            "mp3" | "mpeg" => Some(AudioFormat::Mp3),
            "wav" | "wave" => Some(AudioFormat::Wav),
            "ogg" | "opus" | "vorbis" => Some(AudioFormat::Ogg),
            "flac" => Some(AudioFormat::Flac),
            "pcm" | "raw" => Some(AudioFormat::Pcm),
            _ => None,
        }
    }
}

impl std::fmt::Display for AudioFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            AudioFormat::Mp3 => "mp3",
            AudioFormat::Wav => "wav",
            AudioFormat::Ogg => "ogg",
            AudioFormat::Flac => "flac",
            AudioFormat::Pcm => "pcm",
            AudioFormat::Unknown => "unknown",
        };
        f.write_str(s)
    }
}

/// Audio validation, format detection and duration estimation.
pub struct AudioValidator;

impl AudioValidator {
    /// Detect audio format from magic bytes (never returns `Pcm`: raw PCM has
    /// no signature).
    pub fn detect_format(data: &[u8]) -> AudioFormat {
        if data.len() < 4 {
            return AudioFormat::Unknown;
        }
        if data.starts_with(b"ID3") {
            return AudioFormat::Mp3; // ID3v2 tag
        }
        if data[0] == 0xff && (data[1] & 0xe0) == 0xe0 {
            return AudioFormat::Mp3; // MPEG frame sync
        }
        if data.starts_with(b"RIFF") && data.len() >= 12 && &data[8..12] == b"WAVE" {
            return AudioFormat::Wav;
        }
        if data.starts_with(b"OggS") {
            return AudioFormat::Ogg; // Ogg container (Opus, Vorbis)
        }
        if data.starts_with(b"fLaC") {
            return AudioFormat::Flac;
        }
        AudioFormat::Unknown
    }

    /// Validate an audio payload: size bounds and "not an HTML error page".
    ///
    /// Unknown formats are accepted when the payload is reasonably large,
    /// since raw PCM (and some exotic containers) have no magic bytes.
    pub fn validate(data: &[u8]) -> Result<AudioFormat, String> {
        if data.len() < MIN_AUDIO_SIZE {
            return Err(format!(
                "Audio too small ({} bytes, minimum {})",
                data.len(),
                MIN_AUDIO_SIZE
            ));
        }
        if data.len() > MAX_AUDIO_SIZE {
            return Err(format!(
                "Audio too large ({} bytes, maximum {})",
                data.len(),
                MAX_AUDIO_SIZE
            ));
        }

        let head: Vec<u8> = data[..data.len().min(256)]
            .iter()
            .map(|b| b.to_ascii_lowercase())
            .collect();
        let trimmed: &[u8] = {
            let start = head
                .iter()
                .position(|b| !b.is_ascii_whitespace())
                .unwrap_or(0);
            &head[start..]
        };
        if trimmed.starts_with(b"<!doctype") || head.windows(5).any(|w| w == b"<html") {
            return Err("Data appears to be HTML, not audio".to_string());
        }

        let format = Self::detect_format(data);
        if format != AudioFormat::Unknown || data.len() > MIN_AUDIO_SIZE * 10 {
            Ok(format)
        } else {
            Err("Unknown audio format".to_string())
        }
    }

    /// Estimate the duration of an audio payload in seconds.
    ///
    /// Supports WAV (exact, from the header) and MP3 (assumes constant
    /// bitrate from the first frame header, which matches ElevenLabs output).
    /// Returns `None` if the duration cannot be determined.
    pub fn estimate_duration(data: &[u8], format: AudioFormat) -> Option<f64> {
        match format {
            AudioFormat::Wav => wav_duration(data),
            AudioFormat::Mp3 => mp3_cbr_duration(data),
            _ => None,
        }
    }
}

/// Duration of a RIFF/WAVE payload from its `fmt ` byte rate and `data` size.
fn wav_duration(data: &[u8]) -> Option<f64> {
    if data.len() < 12 || &data[0..4] != b"RIFF" || &data[8..12] != b"WAVE" {
        return None;
    }
    let mut pos = 12usize;
    let mut byte_rate: Option<u32> = None;
    while pos + 8 <= data.len() {
        let id = &data[pos..pos + 4];
        let size = u32::from_le_bytes(data[pos + 4..pos + 8].try_into().ok()?) as usize;
        let body = pos + 8;
        if id == b"fmt " && body + 12 <= data.len() {
            byte_rate = Some(u32::from_le_bytes(
                data[body + 8..body + 12].try_into().ok()?,
            ));
        } else if id == b"data" {
            let rate = byte_rate.filter(|r| *r > 0)?;
            // Streaming writers may put 0 or 0xFFFFFFFF here; clamp to what we have.
            let available = data.len().saturating_sub(body);
            let len = if size == 0 || size > available {
                available
            } else {
                size
            };
            return Some(len as f64 / rate as f64);
        }
        // Chunks are word aligned.
        pos = body.checked_add(size)?.checked_add(size & 1)?;
    }
    None
}

/// Duration of an MP3 payload assuming a constant bitrate.
fn mp3_cbr_duration(data: &[u8]) -> Option<f64> {
    let mut offset = 0usize;
    if data.len() >= 10 && data.starts_with(b"ID3") {
        // Syncsafe 28-bit size, excluding the 10-byte header.
        let size = ((data[6] as usize & 0x7f) << 21)
            | ((data[7] as usize & 0x7f) << 14)
            | ((data[8] as usize & 0x7f) << 7)
            | (data[9] as usize & 0x7f);
        offset = 10 + size;
    }
    // Find the first frame sync within a bounded window.
    let search_end = data.len().min(offset.saturating_add(64 * 1024));
    let mut i = offset;
    while i + 4 <= search_end {
        if data[i] == 0xff && (data[i + 1] & 0xe0) == 0xe0 {
            let version_bits = (data[i + 1] >> 3) & 0x03; // 3=MPEG1, 2=MPEG2, 0=MPEG2.5
            let layer_bits = (data[i + 1] >> 1) & 0x03; // 1=Layer III
            let bitrate_index = (data[i + 2] >> 4) as usize;
            if layer_bits == 1 && version_bits != 1 && (1..15).contains(&bitrate_index) {
                const V1_L3: [u32; 15] = [
                    0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320,
                ];
                const V2_L3: [u32; 15] =
                    [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160];
                let kbps = if version_bits == 3 {
                    V1_L3[bitrate_index]
                } else {
                    V2_L3[bitrate_index]
                };
                let audio_bytes = data.len() - i;
                return Some(audio_bytes as f64 * 8.0 / (kbps as f64 * 1000.0));
            }
        }
        i += 1;
    }
    None
}

/// Wrap headerless 16-bit little-endian PCM into a WAV container.
pub fn pcm_to_wav(pcm: &[u8], sample_rate: u32, channels: u16) -> Vec<u8> {
    let bits_per_sample: u16 = 16;
    let block_align = channels * bits_per_sample / 8;
    let byte_rate = sample_rate * block_align as u32;
    let data_len = pcm.len() as u32;

    let mut out = Vec::with_capacity(44 + pcm.len());
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes()); // PCM
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&sample_rate.to_le_bytes());
    out.extend_from_slice(&byte_rate.to_le_bytes());
    out.extend_from_slice(&block_align.to_le_bytes());
    out.extend_from_slice(&bits_per_sample.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    out.extend_from_slice(pcm);
    out
}

/// How a `play_audio` input string should be interpreted.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AudioInputKind {
    /// `data:audio/...;base64,...`
    DataUrl,
    /// `http://` or `https://`
    Url,
    /// A filesystem path.
    FilePath,
    /// Raw base64.
    Base64,
}

/// Classify a `play_audio` input string.
///
/// Base64 may legitimately start with `/` (an MPEG frame sync `0xFFFx`
/// encodes to `//...`), so a string is only treated as a path when it is
/// short and looks like one: it has an audio file extension, contains a
/// backslash / drive prefix, or exists on disk.
pub fn classify_audio_input(input: &str) -> AudioInputKind {
    let s = input.trim();
    if s.starts_with("data:") {
        return AudioInputKind::DataUrl;
    }
    let lower = s.to_ascii_lowercase();
    if lower.starts_with("http://") || lower.starts_with("https://") {
        return AudioInputKind::Url;
    }
    if s.len() <= 4096 && !s.contains('\n') {
        let has_audio_ext = Path::new(&lower)
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| matches!(e, "mp3" | "wav" | "ogg" | "opus" | "flac" | "pcm" | "m4a"))
            .unwrap_or(false);
        let windows_like = s.contains('\\')
            || (s.len() > 2 && s.as_bytes()[1] == b':' && s.as_bytes()[0].is_ascii_alphabetic());
        if has_audio_ext || windows_like || s.starts_with("./") || Path::new(s).is_file() {
            return AudioInputKind::FilePath;
        }
    }
    AudioInputKind::Base64
}

/// Decode base64 (standard alphabet, whitespace tolerated).
pub fn decode_base64(data: &str) -> Result<Vec<u8>, String> {
    // Reject obviously oversized input before allocating the decoded buffer.
    if data.len() / 4 * 3 > MAX_AUDIO_SIZE + 3 {
        return Err(format!(
            "Base64 audio too large (maximum {} decoded bytes)",
            MAX_AUDIO_SIZE
        ));
    }
    let compact: String = data.chars().filter(|c| !c.is_whitespace()).collect();
    base64::engine::general_purpose::STANDARD
        .decode(compact.as_bytes())
        .map_err(|e| format!("Invalid base64 audio data: {}", e))
}

/// Path validation for audio files (allow-list of base directories).
pub struct AudioPathValidator {
    allowed_paths: Vec<PathBuf>,
}

impl Default for AudioPathValidator {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioPathValidator {
    /// Default allow-list: `outputs/`, `/tmp`, the OS temp dir and any
    /// directories listed in [`AUDIO_DIRS_ENV`].
    pub fn new() -> Self {
        let mut allowed_paths: Vec<PathBuf> =
            ALLOWED_AUDIO_PATHS.iter().map(PathBuf::from).collect();
        allowed_paths.push(std::env::temp_dir());
        if let Some(extra) = std::env::var_os(AUDIO_DIRS_ENV) {
            allowed_paths
                .extend(std::env::split_paths(&extra).filter(|p| !p.as_os_str().is_empty()));
        }
        Self { allowed_paths }
    }

    /// Validator with an explicit allow-list (used by tests).
    pub fn with_paths(paths: Vec<PathBuf>) -> Self {
        Self {
            allowed_paths: paths,
        }
    }

    /// The configured allow-list.
    pub fn allowed_paths(&self) -> &[PathBuf] {
        &self.allowed_paths
    }

    /// Check if an existing file is inside one of the allowed directories.
    ///
    /// Both sides are canonicalized, so `..` segments and symlinks cannot be
    /// used to escape the allow-list. Non-existent files are rejected.
    pub fn is_path_allowed(&self, file_path: &Path) -> bool {
        let Ok(resolved) = file_path.canonicalize() else {
            return false;
        };
        self.allowed_paths
            .iter()
            .filter_map(|allowed| allowed.canonicalize().ok())
            .any(|root| resolved.starts_with(root))
    }

    /// Resolve an audio path (applying container path mappings) to an
    /// existing, allowed file.
    pub fn resolve_audio_path(&self, audio_path: &str) -> Result<PathBuf, String> {
        let audio_path = audio_path.trim();
        let normalized = audio_path.replace('\\', "/");
        for (container_path, host_path) in PATH_MAPPINGS {
            if let Some(idx) = normalized.find(container_path) {
                let rest = &normalized[idx + container_path.len()..];
                let candidate = PathBuf::from(host_path).join(rest);
                if candidate.is_file() && self.is_path_allowed(&candidate) {
                    return Ok(candidate);
                }
            }
        }

        let file_path = PathBuf::from(audio_path);
        if !file_path.exists() {
            return Err(format!("Audio file not found: {}", audio_path));
        }
        if !file_path.is_file() {
            return Err(format!("Not a regular file: {}", audio_path));
        }
        if !self.is_path_allowed(&file_path) {
            return Err(format!(
                "Path not in allowed directories: {} (allowed: {}; extend with {})",
                audio_path,
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect::<Vec<_>>()
                    .join(", "),
                AUDIO_DIRS_ENV
            ));
        }
        Ok(file_path)
    }
}

/// Download audio from URLs with validation, timeouts and a size cap.
pub struct AudioDownloader {
    client: reqwest::Client,
}

impl Default for AudioDownloader {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioDownloader {
    /// Create a new audio downloader (30 s total timeout, 10 s connect).
    pub fn new() -> Self {
        let client = mcp_core::http::build_client_or_default(DOWNLOAD_TIMEOUT);
        Self { client }
    }

    /// Download audio from URL with validation.
    pub async fn download(&self, url: &str) -> Result<Vec<u8>, String> {
        let mut response = self
            .client
            .get(url)
            .send()
            .await
            .map_err(|e| format!("Download error: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("HTTP {} downloading audio", response.status()));
        }

        if let Some(ct) = response
            .headers()
            .get(reqwest::header::CONTENT_TYPE)
            .and_then(|v| v.to_str().ok())
        {
            if ct.contains("text/html") {
                return Err("Server returned HTML instead of audio".to_string());
            }
        }

        if let Some(len) = response.content_length() {
            if len as usize > MAX_AUDIO_SIZE {
                return Err(format!(
                    "Audio too large ({} bytes, maximum {})",
                    len, MAX_AUDIO_SIZE
                ));
            }
        }

        let mut data = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|e| format!("Failed to read response: {}", e))?
        {
            if data.len() + chunk.len() > MAX_AUDIO_SIZE {
                return Err(format!(
                    "Audio too large (exceeds {} bytes)",
                    MAX_AUDIO_SIZE
                ));
            }
            data.extend_from_slice(&chunk);
        }

        AudioValidator::validate(&data)?;
        Ok(data)
    }
}

/// A command line for one external audio player.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlayerCommand {
    /// Human-readable method name reported to the caller.
    pub name: &'static str,
    /// Program to execute.
    pub program: String,
    /// Arguments.
    pub args: Vec<String>,
}

/// Escape a string for use inside a PowerShell single-quoted literal.
fn ps_single_quote(s: &str) -> String {
    s.replace('\'', "''")
}

/// Candidate player commands, in preference order, for a file on the given
/// platform. Pure function so the selection logic is testable.
pub fn player_candidates(
    path: &Path,
    format: AudioFormat,
    device: Option<&str>,
    windows: bool,
) -> Vec<PlayerCommand> {
    let p = path.to_string_lossy().to_string();
    let mut out = Vec::new();

    if windows {
        let mut vlc_args = vec![
            "--intf".to_string(),
            "dummy".to_string(),
            "--play-and-exit".to_string(),
            "--no-loop".to_string(),
            "--no-repeat".to_string(),
        ];
        if let Some(dev) = device.filter(|d| !d.is_empty()) {
            vlc_args.extend([
                "--aout".to_string(),
                "waveout".to_string(),
                "--waveout-audio-device".to_string(),
                dev.to_string(),
            ]);
        }
        vlc_args.push(p.clone());
        out.push(PlayerCommand {
            name: "vlc",
            program: "vlc".to_string(),
            args: vlc_args.clone(),
        });
        let program_files_vlc = r"C:\Program Files\VideoLAN\VLC\vlc.exe";
        out.push(PlayerCommand {
            name: "vlc",
            program: program_files_vlc.to_string(),
            args: vlc_args,
        });
        out.push(PlayerCommand {
            name: "ffplay",
            program: "ffplay".to_string(),
            args: vec![
                "-nodisp".into(),
                "-autoexit".into(),
                "-loglevel".into(),
                "error".into(),
                p.clone(),
            ],
        });
        if format == AudioFormat::Wav || format == AudioFormat::Pcm {
            out.push(PlayerCommand {
                name: "powershell-soundplayer",
                program: "powershell".to_string(),
                args: vec![
                    "-NoProfile".into(),
                    "-NonInteractive".into(),
                    "-Command".into(),
                    format!(
                        "(New-Object System.Media.SoundPlayer '{}').PlaySync()",
                        ps_single_quote(&p)
                    ),
                ],
            });
        }
    } else {
        out.push(PlayerCommand {
            name: "ffplay",
            program: "ffplay".to_string(),
            args: vec![
                "-nodisp".into(),
                "-autoexit".into(),
                "-loglevel".into(),
                "error".into(),
                p.clone(),
            ],
        });
        if matches!(
            format,
            AudioFormat::Wav | AudioFormat::Pcm | AudioFormat::Ogg | AudioFormat::Flac
        ) {
            let mut args = Vec::new();
            if let Some(dev) = device.filter(|d| !d.is_empty()) {
                args.push(format!("--device={}", dev));
            }
            args.push(p.clone());
            out.push(PlayerCommand {
                name: "paplay",
                program: "paplay".to_string(),
                args,
            });
        }
        if format == AudioFormat::Wav || format == AudioFormat::Pcm {
            out.push(PlayerCommand {
                name: "aplay",
                program: "aplay".to_string(),
                args: vec!["-q".into(), p],
            });
        }
    }
    out
}

/// Handle to a playback started by [`AudioPlayer::play`].
#[derive(Debug)]
pub struct Playback {
    /// Which player is used (e.g. `"vlc"`, `"ffplay"`).
    pub method: String,
    /// Resolves when playback has finished (or was killed / failed).
    pub done: oneshot::Receiver<()>,
}

/// Plays audio on the machine running this server via external players.
pub struct AudioPlayer {
    default_device: Option<String>,
}

impl Default for AudioPlayer {
    fn default() -> Self {
        Self::new(None)
    }
}

impl AudioPlayer {
    /// Create a new audio player. `default_device` is used when `play` is
    /// called without an explicit device.
    pub fn new(default_device: Option<String>) -> Self {
        Self { default_device }
    }

    /// Start playing `audio_bytes`. Returns once a player has started (or all
    /// failed); playback continues in the background and is killed after
    /// `max_duration`. The temporary file is removed when playback ends.
    pub async fn play(
        &self,
        audio_bytes: &[u8],
        format: AudioFormat,
        device: Option<&str>,
        max_duration: Duration,
    ) -> Result<Playback, String> {
        let device = device.or(self.default_device.as_deref());
        let tmp_path = write_temp_file(audio_bytes, format)
            .await
            .map_err(|e| format!("Failed to create temp audio file: {}", e))?;

        let candidates = player_candidates(&tmp_path, format, device, cfg!(windows));
        play_candidates(tmp_path, candidates, max_duration).await
    }
}

/// Try each candidate player in order; the first one that starts (and does
/// not fail within [`PLAYER_STARTUP_GRACE`]) wins. Owns `tmp_path` and
/// removes it once playback ends or every candidate failed.
async fn play_candidates(
    tmp_path: PathBuf,
    candidates: Vec<PlayerCommand>,
    max_duration: Duration,
) -> Result<Playback, String> {
    let mut failures = Vec::new();

    for cand in candidates {
        let mut cmd = Command::new(&cand.program);
        cmd.args(&cand.args)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .kill_on_drop(true);
        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                debug!("Player {} unavailable: {}", cand.program, e);
                failures.push(format!("{}: {}", cand.name, e));
                continue;
            },
        };

        // Detect immediate failures (bad device, unsupported file).
        match tokio::time::timeout(PLAYER_STARTUP_GRACE, child.wait()).await {
            Ok(Ok(status)) if !status.success() => {
                failures.push(format!("{}: exited with {}", cand.name, status));
                continue;
            },
            Ok(Err(e)) => {
                failures.push(format!("{}: {}", cand.name, e));
                continue;
            },
            // Finished successfully already (very short clip) or still running.
            _ => {},
        }

        let (tx, rx) = oneshot::channel();
        let path = tmp_path.clone();
        let name = cand.name;
        tokio::spawn(async move {
            match tokio::time::timeout(max_duration, child.wait()).await {
                Ok(_) => debug!("Audio playback via {} finished", name),
                Err(_) => {
                    warn!(
                        "Audio playback via {} exceeded {:?}; killing player",
                        name, max_duration
                    );
                    let _ = child.kill().await;
                },
            }
            remove_temp_file(&path).await;
            let _ = tx.send(());
        });

        info!("Playing audio via {}", cand.name);
        return Ok(Playback {
            method: cand.name.to_string(),
            done: rx,
        });
    }

    remove_temp_file(&tmp_path).await;
    Err(format!(
        "No audio player could play the file. Install VLC or ffmpeg (ffplay). Attempts: {}",
        failures.join("; ")
    ))
}

async fn write_temp_file(data: &[u8], format: AudioFormat) -> std::io::Result<PathBuf> {
    let filename = format!("vc_audio_{}.{}", uuid::Uuid::new_v4(), format.extension());
    let tmp_path = std::env::temp_dir().join(filename);
    let mut file = tokio::fs::File::create(&tmp_path).await?;
    file.write_all(data).await?;
    file.flush().await?;
    Ok(tmp_path)
}

async fn remove_temp_file(path: &Path) {
    // Windows players may hold the file briefly after exit; retry a few times.
    for _ in 0..5 {
        match tokio::fs::remove_file(path).await {
            Ok(()) => return,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return,
            Err(_) => tokio::time::sleep(Duration::from_millis(200)).await,
        }
    }
    warn!("Could not remove temporary audio file {}", path.display());
}

/// Audio input resolution (path / URL / data URL / base64 -> bytes).
pub struct AudioHandler {
    pub path_validator: AudioPathValidator,
    pub downloader: AudioDownloader,
}

impl Default for AudioHandler {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioHandler {
    /// Create a handler with the default path allow-list.
    pub fn new() -> Self {
        Self {
            path_validator: AudioPathValidator::new(),
            downloader: AudioDownloader::new(),
        }
    }

    /// Resolve any supported input into validated audio bytes.
    pub async fn load(&self, audio_data: &str) -> Result<Vec<u8>, String> {
        let input = audio_data.trim();
        if input.is_empty() {
            return Err("audio_data is empty".to_string());
        }
        let bytes = match classify_audio_input(input) {
            AudioInputKind::DataUrl => {
                let (_, payload) = input
                    .split_once(',')
                    .ok_or_else(|| "Invalid data URL (missing ',')".to_string())?;
                decode_base64(payload)?
            },
            AudioInputKind::Url => return self.downloader.download(input).await,
            AudioInputKind::FilePath => {
                let path = self.path_validator.resolve_audio_path(input)?;
                let meta = tokio::fs::metadata(&path)
                    .await
                    .map_err(|e| format!("Error reading file: {}", e))?;
                if meta.len() as usize > MAX_AUDIO_SIZE {
                    return Err(format!(
                        "Audio file too large ({} bytes, maximum {})",
                        meta.len(),
                        MAX_AUDIO_SIZE
                    ));
                }
                tokio::fs::read(&path)
                    .await
                    .map_err(|e| format!("Error reading file: {}", e))?
            },
            AudioInputKind::Base64 => decode_base64(input)?,
        };
        AudioValidator::validate(&bytes)?;
        Ok(bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn silent_wav(seconds: f64) -> Vec<u8> {
        let samples = (44100.0 * seconds) as usize;
        pcm_to_wav(&vec![0u8; samples * 2], 44100, 1)
    }

    #[test]
    fn test_detect_format_mp3_id3() {
        let data = b"ID3\x04\x00\x00\x00\x00\x00\x00";
        assert_eq!(AudioValidator::detect_format(data), AudioFormat::Mp3);
    }

    #[test]
    fn test_detect_format_mp3_mpeg() {
        let data = &[0xff, 0xfb, 0x90, 0x00];
        assert_eq!(AudioValidator::detect_format(data), AudioFormat::Mp3);
    }

    #[test]
    fn test_detect_format_wav_ogg_flac() {
        assert_eq!(
            AudioValidator::detect_format(b"RIFF\x00\x00\x00\x00WAVE"),
            AudioFormat::Wav
        );
        assert_eq!(
            AudioValidator::detect_format(b"OggS\x00\x02\x00\x00"),
            AudioFormat::Ogg
        );
        assert_eq!(
            AudioValidator::detect_format(b"fLaC\x00\x00\x00\x22"),
            AudioFormat::Flac
        );
        assert_eq!(AudioValidator::detect_format(b"ab"), AudioFormat::Unknown);
    }

    #[test]
    fn test_validate_rejects_small_html_and_large() {
        assert!(AudioValidator::validate(&[0xff, 0xfb])
            .unwrap_err()
            .contains("too small"));

        let mut html = b"  <!DOCTYPE html><html>".to_vec();
        html.extend(vec![0u8; 200]);
        assert!(AudioValidator::validate(&html)
            .unwrap_err()
            .contains("HTML"));

        let mut mp3 = b"ID3\x04\x00\x00\x00\x00".to_vec();
        mp3.extend(vec![0u8; 200]);
        assert_eq!(AudioValidator::validate(&mp3).unwrap(), AudioFormat::Mp3);

        // Small unknown payload is rejected, large unknown accepted (raw PCM).
        assert!(AudioValidator::validate(&[1u8; 500]).is_err());
        assert_eq!(
            AudioValidator::validate(&[1u8; 5000]).unwrap(),
            AudioFormat::Unknown
        );
    }

    #[test]
    fn test_pcm_to_wav_and_duration() {
        let wav = silent_wav(1.5);
        assert_eq!(AudioValidator::detect_format(&wav), AudioFormat::Wav);
        let d = AudioValidator::estimate_duration(&wav, AudioFormat::Wav).unwrap();
        assert!((d - 1.5).abs() < 0.01, "got {d}");
    }

    #[test]
    fn test_mp3_cbr_duration() {
        // MPEG1 Layer III, 128 kbps (index 9), 44.1 kHz frame header.
        let mut mp3 = vec![0xff, 0xfb, 0x90, 0x64];
        mp3.extend(vec![0u8; 16_000 - 4]);
        let d = AudioValidator::estimate_duration(&mp3, AudioFormat::Mp3).unwrap();
        assert!((d - 1.0).abs() < 0.01, "got {d}");

        // Same with an ID3v2 tag in front (10-byte header + 20-byte body).
        let mut tagged = b"ID3\x04\x00\x00\x00\x00\x00\x14".to_vec();
        tagged.extend(vec![0u8; 20]);
        tagged.extend(&mp3);
        let d2 = AudioValidator::estimate_duration(&tagged, AudioFormat::Mp3).unwrap();
        assert!((d2 - 1.0).abs() < 0.01, "got {d2}");

        assert!(AudioValidator::estimate_duration(&[0u8; 100], AudioFormat::Mp3).is_none());
        assert!(AudioValidator::estimate_duration(b"OggS1234", AudioFormat::Ogg).is_none());
    }

    #[test]
    fn test_classify_audio_input() {
        assert_eq!(
            classify_audio_input("data:audio/mp3;base64,AAAA"),
            AudioInputKind::DataUrl
        );
        assert_eq!(
            classify_audio_input("https://example.com/a.mp3"),
            AudioInputKind::Url
        );
        assert_eq!(
            classify_audio_input("/tmp/elevenlabs_audio/speech.mp3"),
            AudioInputKind::FilePath
        );
        assert_eq!(
            classify_audio_input(r"C:\audio\speech.wav"),
            AudioInputKind::FilePath
        );
        assert_eq!(
            classify_audio_input("outputs/elevenlabs_speech/x.mp3"),
            AudioInputKind::FilePath
        );
        // Base64 of an MPEG frame starts with "//" and must NOT be a path.
        let b64 =
            base64::engine::general_purpose::STANDARD.encode([0xffu8, 0xfb, 0x90, 0x64, 1, 2, 3]);
        assert!(b64.starts_with("//"));
        assert_eq!(classify_audio_input(&b64), AudioInputKind::Base64);
    }

    #[test]
    fn test_decode_base64_tolerates_whitespace() {
        let enc = base64::engine::general_purpose::STANDARD.encode(b"hello world audio");
        let wrapped = format!("{}\n{}", &enc[..8], &enc[8..]);
        assert_eq!(decode_base64(&wrapped).unwrap(), b"hello world audio");
        assert!(decode_base64("!!!notbase64").is_err());
    }

    #[test]
    fn test_path_validator_blocks_traversal() {
        let root = std::env::temp_dir().join(format!("vc_test_{}", uuid::Uuid::new_v4()));
        let allowed = root.join("allowed");
        let outside = root.join("outside");
        std::fs::create_dir_all(&allowed).unwrap();
        std::fs::create_dir_all(&outside).unwrap();
        let good = allowed.join("a.wav");
        let bad = outside.join("b.wav");
        std::fs::write(&good, silent_wav(0.1)).unwrap();
        std::fs::write(&bad, silent_wav(0.1)).unwrap();

        let v = AudioPathValidator::with_paths(vec![allowed.clone()]);
        assert!(v.is_path_allowed(&good));
        assert!(!v.is_path_allowed(&bad));
        // `..` traversal out of the allowed dir is rejected after canonicalization.
        let sneaky = allowed.join("..").join("outside").join("b.wav");
        assert!(!v.is_path_allowed(&sneaky));
        assert!(v
            .resolve_audio_path(&sneaky.to_string_lossy())
            .unwrap_err()
            .contains("not in allowed"));
        assert!(v
            .resolve_audio_path(&allowed.join("missing.wav").to_string_lossy())
            .unwrap_err()
            .contains("not found"));
        assert_eq!(v.resolve_audio_path(&good.to_string_lossy()).unwrap(), good);

        std::fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn test_handler_load_sources() {
        let handler = AudioHandler {
            path_validator: AudioPathValidator::with_paths(vec![]),
            downloader: AudioDownloader::new(),
        };
        let wav = silent_wav(0.2);
        let b64 = base64::engine::general_purpose::STANDARD.encode(&wav);
        assert_eq!(handler.load(&b64).await.unwrap(), wav);
        let data_url = format!("data:audio/wav;base64,{}", b64);
        assert_eq!(handler.load(&data_url).await.unwrap(), wav);
        assert!(handler.load("   ").await.is_err());
        assert!(handler.load("data:audio/wav;base64").await.is_err());
    }

    #[test]
    fn test_player_candidates() {
        let path = Path::new("/tmp/it's.mp3");
        let win = player_candidates(path, AudioFormat::Mp3, Some("VoiceMeeter Input"), true);
        assert_eq!(win[0].name, "vlc");
        assert!(win[0].args.contains(&"VoiceMeeter Input".to_string()));
        // SoundPlayer only handles WAV.
        assert!(!win.iter().any(|c| c.name == "powershell-soundplayer"));
        let win_wav = player_candidates(path, AudioFormat::Wav, None, true);
        let ps = win_wav
            .iter()
            .find(|c| c.name == "powershell-soundplayer")
            .unwrap();
        // Single quote in the path is escaped for PowerShell.
        assert!(ps.args.last().unwrap().contains("it''s.mp3"));
        assert!(!win_wav[0].args.contains(&"--aout".to_string()));

        let unix = player_candidates(path, AudioFormat::Mp3, None, false);
        assert_eq!(unix.len(), 1);
        assert_eq!(unix[0].name, "ffplay");
        let unix_wav = player_candidates(path, AudioFormat::Wav, None, false);
        let names: Vec<_> = unix_wav.iter().map(|c| c.name).collect();
        assert_eq!(names, vec!["ffplay", "paplay", "aplay"]);
    }

    #[test]
    fn test_format_names() {
        assert_eq!(AudioFormat::from_name("MP3"), Some(AudioFormat::Mp3));
        assert_eq!(AudioFormat::from_name("opus"), Some(AudioFormat::Ogg));
        assert_eq!(AudioFormat::from_name("pcm"), Some(AudioFormat::Pcm));
        assert_eq!(AudioFormat::from_name("aac"), None);
        assert_eq!(AudioFormat::Pcm.extension(), "wav");
    }

    /// Portable stand-ins for audio players.
    fn shell(name: &'static str, script: &str) -> PlayerCommand {
        if cfg!(windows) {
            PlayerCommand {
                name,
                program: "cmd".into(),
                args: vec!["/C".into(), script.into()],
            }
        } else {
            PlayerCommand {
                name,
                program: "sh".into(),
                args: vec!["-c".into(), script.into()],
            }
        }
    }

    async fn temp_audio() -> PathBuf {
        write_temp_file(&silent_wav(0.05), AudioFormat::Wav)
            .await
            .unwrap()
    }

    #[tokio::test]
    async fn test_player_fallback_and_cleanup() {
        let path = temp_audio().await;
        let candidates = vec![
            PlayerCommand {
                name: "missing",
                program: "definitely-not-a-real-player-xyz".into(),
                args: vec![],
            },
            shell("fails", "exit 3"),
            shell("works", "exit 0"),
        ];
        let playback = play_candidates(path.clone(), candidates, Duration::from_secs(10))
            .await
            .unwrap();
        assert_eq!(playback.method, "works");
        tokio::time::timeout(Duration::from_secs(5), playback.done)
            .await
            .unwrap()
            .unwrap();
        assert!(!path.exists(), "temp file not cleaned up");
    }

    #[tokio::test]
    async fn test_player_all_fail_reports_attempts() {
        let path = temp_audio().await;
        let err = play_candidates(
            path.clone(),
            vec![shell("fails", "exit 2")],
            Duration::from_secs(5),
        )
        .await
        .unwrap_err();
        assert!(err.contains("fails"), "{err}");
        assert!(!path.exists());
    }

    #[tokio::test]
    async fn test_player_killed_after_max_duration() {
        let path = temp_audio().await;
        let long = if cfg!(windows) {
            shell("slow", "ping -n 30 127.0.0.1 >NUL")
        } else {
            shell("slow", "sleep 30")
        };
        let playback = play_candidates(path.clone(), vec![long], Duration::from_millis(800))
            .await
            .unwrap();
        tokio::time::timeout(Duration::from_secs(10), playback.done)
            .await
            .expect("player was not killed")
            .unwrap();
        assert!(!path.exists());
    }
}

//! Audio handling module for Virtual Character MCP Server.
//!
//! This module handles:
//! - Audio playback through various methods (ffplay, VLC, PowerShell)
//! - Audio file validation and format detection
//! - Path resolution for audio files
//! - Storage service integration for seamless audio transfer
//! - URL download with validation

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use base64::Engine;
use tokio::fs;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
#[cfg(windows)]
use tracing::info;

/// Minimum size for valid audio file (bytes).
pub const MIN_AUDIO_SIZE: usize = 100;

/// Default cleanup delay for temporary files (seconds).
pub const DEFAULT_CLEANUP_DELAY: u64 = 10;

/// Allowed base paths for file reads (security).
pub static ALLOWED_AUDIO_PATHS: &[&str] = &[
    "outputs",
    "/tmp",
    "/tmp/elevenlabs_audio",
    "/tmp/audio_storage",
];

/// Audio format detection result.
#[derive(Debug, Clone, PartialEq)]
pub enum AudioFormat {
    Mp3,
    Wav,
    Ogg,
    Flac,
    Unknown,
}

impl AudioFormat {
    /// Get file extension for this format.
    pub fn extension(&self) -> &'static str {
        match self {
            AudioFormat::Mp3 => "mp3",
            AudioFormat::Wav => "wav",
            AudioFormat::Ogg => "ogg",
            AudioFormat::Flac => "flac",
            AudioFormat::Unknown => "bin",
        }
    }
}

impl std::fmt::Display for AudioFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AudioFormat::Mp3 => write!(f, "mp3"),
            AudioFormat::Wav => write!(f, "wav"),
            AudioFormat::Ogg => write!(f, "ogg"),
            AudioFormat::Flac => write!(f, "flac"),
            AudioFormat::Unknown => write!(f, "unknown"),
        }
    }
}

/// Audio validation and format detection.
pub struct AudioValidator;

impl AudioValidator {
    /// Detect audio format from magic bytes.
    pub fn detect_format(data: &[u8]) -> AudioFormat {
        if data.len() < 4 {
            return AudioFormat::Unknown;
        }

        // Check for various audio signatures
        if data.starts_with(b"ID3") {
            return AudioFormat::Mp3; // ID3v2 tag
        }
        if data.len() >= 2 && data[0] == 0xff && (data[1] & 0xe0) == 0xe0 {
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

    /// Validate audio data.
    ///
    /// Returns (is_valid, message).
    pub fn is_valid_audio(data: &[u8]) -> (bool, String) {
        if data.len() < MIN_AUDIO_SIZE {
            return (false, format!("Audio too small ({} bytes)", data.len()));
        }

        // Check for HTML error pages
        let start = &data[..std::cmp::min(100, data.len())];
        let start_lower: Vec<u8> = start.iter().map(|b| b.to_ascii_lowercase()).collect();
        if start.starts_with(b"<!DOCTYPE")
            || start.starts_with(b"<html")
            || start_lower.windows(5).any(|w| w == b"<html")
        {
            return (false, "Data appears to be HTML, not audio".to_string());
        }

        // Check for known audio format
        let format = Self::detect_format(data);
        if format != AudioFormat::Unknown {
            return (true, format!("Valid {} audio", format));
        }

        // Allow through if it's large enough (might be valid format we don't detect)
        if data.len() > MIN_AUDIO_SIZE * 10 {
            return (true, "Unknown format but sufficient size".to_string());
        }

        (false, "Unknown audio format".to_string())
    }
}

/// Path validation for audio files with security checks.
pub struct AudioPathValidator {
    allowed_paths: Vec<PathBuf>,
}

impl Default for AudioPathValidator {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioPathValidator {
    /// Create a new path validator with default allowed paths.
    pub fn new() -> Self {
        let allowed_paths = ALLOWED_AUDIO_PATHS.iter().map(PathBuf::from).collect();
        Self { allowed_paths }
    }

    /// Add additional allowed paths.
    pub fn with_additional_paths(mut self, paths: Vec<PathBuf>) -> Self {
        self.allowed_paths.extend(paths);
        self
    }

    /// Check if a path is within allowed directories.
    pub fn is_path_allowed(&self, file_path: &Path) -> bool {
        let resolved = match file_path.canonicalize() {
            Ok(p) => p,
            Err(_) => {
                // If we can't canonicalize, check if parent exists
                if let Some(parent) = file_path.parent() {
                    if let Ok(p) = parent.canonicalize() {
                        p.join(file_path.file_name().unwrap_or_default())
                    } else {
                        return false;
                    }
                } else {
                    return false;
                }
            },
        };

        for allowed in &self.allowed_paths {
            let allowed_resolved = match allowed.canonicalize() {
                Ok(p) => p,
                Err(_) => {
                    // If allowed path doesn't exist, try as-is for relative paths
                    if resolved.starts_with(allowed) {
                        return true;
                    }
                    continue;
                },
            };

            if resolved.starts_with(&allowed_resolved) {
                return true;
            }
        }

        false
    }

    /// Resolve an audio path, checking container path mappings.
    ///
    /// Returns (resolved_path, error_message).
    pub async fn resolve_audio_path(&self, audio_path: &str) -> (Option<PathBuf>, Option<String>) {
        // Container path mappings
        let path_mappings = [
            ("/tmp/elevenlabs_audio/", "outputs/elevenlabs_speech/"),
            ("/tmp/audio_storage/", "outputs/audio_storage/"),
        ];

        // Check for container path mappings
        for (container_path, host_path) in &path_mappings {
            if audio_path.contains(container_path) {
                let filename = Path::new(audio_path)
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("");

                // Try various paths
                let possible_paths = [
                    PathBuf::from(host_path).join(filename),
                    PathBuf::from(format!("{}{}", host_path, filename)),
                ];

                for path in &possible_paths {
                    if path.exists() && self.is_path_allowed(path) {
                        return (Some(path.clone()), None);
                    }
                }
            }
        }

        // Direct path resolution
        let file_path = PathBuf::from(audio_path);

        if file_path.exists() {
            if self.is_path_allowed(&file_path) {
                return (Some(file_path), None);
            }
            return (
                None,
                Some(format!("Path not in allowed directories: {}", audio_path)),
            );
        }

        (None, Some(format!("File not found: {}", audio_path)))
    }
}

/// Download audio from URLs with validation.
pub struct AudioDownloader {
    client: reqwest::Client,
}

impl Default for AudioDownloader {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioDownloader {
    /// Create a new audio downloader.
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .unwrap_or_default();
        Self { client }
    }

    /// Download audio from URL with validation.
    ///
    /// Returns (audio_bytes, error_message).
    pub async fn download(&self, url: &str) -> (Option<Vec<u8>>, Option<String>) {
        let response = match self.client.get(url).send().await {
            Ok(r) => r,
            Err(e) => return (None, Some(format!("Download error: {}", e))),
        };

        if !response.status().is_success() {
            return (
                None,
                Some(format!("HTTP {} downloading audio", response.status())),
            );
        }

        // Check content type
        if let Some(content_type) = response.headers().get("content-type") {
            if let Ok(ct) = content_type.to_str() {
                if ct.contains("text/html") {
                    return (
                        None,
                        Some("Server returned HTML instead of audio".to_string()),
                    );
                }
            }
        }

        // Check content length
        if let Some(content_length) = response.headers().get("content-length") {
            if let Ok(len_str) = content_length.to_str() {
                if let Ok(len) = len_str.parse::<usize>() {
                    if len < MIN_AUDIO_SIZE {
                        return (None, Some(format!("File too small ({} bytes)", len)));
                    }
                }
            }
        }

        // Download content
        let data = match response.bytes().await {
            Ok(b) => b.to_vec(),
            Err(e) => return (None, Some(format!("Failed to read response: {}", e))),
        };

        // Validate audio
        let (is_valid, msg) = AudioValidator::is_valid_audio(&data);
        if !is_valid {
            return (None, Some(msg));
        }

        (Some(data), None)
    }
}

/// Audio playback on different platforms.
pub struct AudioPlayer {
    default_device: String,
    cleanup_delay: Duration,
}

impl Default for AudioPlayer {
    fn default() -> Self {
        Self::new("VoiceMeeter Input".to_string(), DEFAULT_CLEANUP_DELAY)
    }
}

impl AudioPlayer {
    /// Create a new audio player.
    pub fn new(default_device: String, cleanup_delay_secs: u64) -> Self {
        Self {
            default_device,
            cleanup_delay: Duration::from_secs(cleanup_delay_secs),
        }
    }

    /// Play audio bytes through the system.
    ///
    /// Returns (success, message).
    pub async fn play(
        &self,
        audio_bytes: &[u8],
        audio_format: &AudioFormat,
        device_name: Option<&str>,
    ) -> (bool, String) {
        let device = device_name.unwrap_or(&self.default_device);

        // Save to temp file
        let tmp_path = match self.write_temp_file(audio_bytes, audio_format).await {
            Ok(p) => p,
            Err(e) => return (false, format!("Failed to create temp file: {}", e)),
        };

        let result = if cfg!(windows) {
            self.play_windows(&tmp_path, audio_format, device).await
        } else {
            self.play_unix(&tmp_path).await
        };

        // Schedule cleanup
        let cleanup_path = tmp_path.clone();
        let cleanup_delay = self.cleanup_delay;
        tokio::spawn(async move {
            tokio::time::sleep(cleanup_delay).await;
            let _ = fs::remove_file(&cleanup_path).await;
        });

        result
    }

    async fn write_temp_file(
        &self,
        data: &[u8],
        format: &AudioFormat,
    ) -> Result<PathBuf, std::io::Error> {
        let tmp_dir = std::env::temp_dir();
        let filename = format!("vc_audio_{}.{}", uuid::Uuid::new_v4(), format.extension());
        let tmp_path = tmp_dir.join(filename);

        let mut file = fs::File::create(&tmp_path).await?;
        file.write_all(data).await?;
        file.flush().await?;

        Ok(tmp_path)
    }

    #[cfg(windows)]
    async fn play_windows(
        &self,
        audio_path: &Path,
        audio_format: &AudioFormat,
        device: &str,
    ) -> (bool, String) {
        // Method 1: Convert to WAV and play via PowerShell
        let wav_path = audio_path.with_extension("wav");

        let convert_result = Command::new("ffmpeg")
            .args([
                "-i",
                audio_path.to_str().unwrap_or(""),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-y",
                wav_path.to_str().unwrap_or(""),
            ])
            .output()
            .await;

        if let Ok(output) = convert_result {
            if output.status.success() && wav_path.exists() {
                info!("Converted to WAV: {:?}", wav_path);

                let play_cmd = format!(
                    "(New-Object Media.SoundPlayer '{}').PlaySync()",
                    wav_path.to_str().unwrap_or("")
                );

                let play_result = Command::new("powershell")
                    .args(["-Command", &play_cmd])
                    .output()
                    .await;

                let _ = fs::remove_file(&wav_path).await;

                if play_result.is_ok() {
                    return (
                        true,
                        format!("Playing through default device (should be {})", device),
                    );
                }
            }
        }

        // Method 2: Try VLC
        let vlc_result = Command::new("vlc")
            .args([
                "--intf",
                "dummy",
                "--play-and-exit",
                "--no-loop",
                "--no-repeat",
                "--aout",
                "waveout",
                "--waveout-audio-device",
                device,
                audio_path.to_str().unwrap_or(""),
            ])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();

        if vlc_result.is_ok() {
            return (true, format!("Playing via VLC through {}", device));
        }

        // Method 3: PowerShell fallback
        let ps_cmd = format!(
            r#"
            try {{
                $player = New-Object System.Media.SoundPlayer
                $player.SoundLocation = '{}'
                $player.PlaySync()
                Write-Host "Audio played successfully"
            }} catch {{
                $wmp = New-Object -ComObject WMPlayer.OCX
                $wmp.URL = '{}'
                $wmp.controls.play()
                Start-Sleep -Seconds 5
                Write-Host "Audio played via WMP"
            }}
            "#,
            audio_path.to_str().unwrap_or(""),
            audio_path.to_str().unwrap_or("")
        );

        let ps_result = Command::new("powershell")
            .args(["-Command", &ps_cmd])
            .output()
            .await;

        match ps_result {
            Ok(output) => {
                let stdout = String::from_utf8_lossy(&output.stdout);
                (true, format!("Playing via PowerShell: {}", stdout.trim()))
            },
            Err(e) => (false, format!("All playback methods failed: {}", e)),
        }
    }

    #[cfg(not(windows))]
    async fn play_windows(
        &self,
        _audio_path: &Path,
        _audio_format: &AudioFormat,
        _device: &str,
    ) -> (bool, String) {
        (
            false,
            "Windows playback not available on this platform".to_string(),
        )
    }

    async fn play_unix(&self, audio_path: &Path) -> (bool, String) {
        // Try ffplay
        let result = Command::new("ffplay")
            .args(["-nodisp", "-autoexit", audio_path.to_str().unwrap_or("")])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();

        match result {
            Ok(_) => (true, format!("Playing via ffplay: {:?}", audio_path)),
            Err(_) => {
                // Try aplay as fallback
                let aplay_result = Command::new("aplay")
                    .arg(audio_path)
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .spawn();

                match aplay_result {
                    Ok(_) => (true, format!("Playing via aplay: {:?}", audio_path)),
                    Err(e) => (false, format!("Playback failed: {}", e)),
                }
            },
        }
    }
}

/// Main audio handler combining all audio functionality.
pub struct AudioHandler {
    pub storage_base_url: String,
    pub path_validator: AudioPathValidator,
    pub downloader: AudioDownloader,
    pub player: AudioPlayer,
}

impl Default for AudioHandler {
    fn default() -> Self {
        Self::new(None, None, None)
    }
}

impl AudioHandler {
    /// Create a new audio handler.
    pub fn new(
        storage_base_url: Option<String>,
        default_device: Option<String>,
        cleanup_delay: Option<u64>,
    ) -> Self {
        let storage_url = storage_base_url
            .or_else(|| std::env::var("STORAGE_BASE_URL").ok())
            .unwrap_or_else(|| "http://localhost:8021".to_string());

        let device = default_device.unwrap_or_else(|| "VoiceMeeter Input".to_string());
        let delay = cleanup_delay.unwrap_or(DEFAULT_CLEANUP_DELAY);

        Self {
            storage_base_url: storage_url,
            path_validator: AudioPathValidator::new(),
            downloader: AudioDownloader::new(),
            player: AudioPlayer::new(device, delay),
        }
    }

    /// Process various audio input formats and return audio bytes.
    ///
    /// Can handle: file path, URL, base64, or data URL.
    ///
    /// Returns (audio_bytes, error_message).
    pub async fn process_audio_input(&self, audio_data: &str) -> (Option<Vec<u8>>, Option<String>) {
        // Check for storage service URL
        let storage_download_prefix = format!("{}/download/", self.storage_base_url);
        if audio_data.starts_with(&storage_download_prefix) {
            return self.download_from_storage(audio_data).await;
        }

        // Data URL format
        if audio_data.starts_with("data:") {
            return self.decode_data_url(audio_data);
        }

        // HTTP/HTTPS URL
        if audio_data.starts_with("http://") || audio_data.starts_with("https://") {
            return self.downloader.download(audio_data).await;
        }

        // File path
        if audio_data.starts_with('/')
            || audio_data.starts_with("./")
            || audio_data.starts_with("outputs/")
        {
            return self.read_from_file(audio_data).await;
        }

        // Assume base64
        self.decode_base64(audio_data)
    }

    async fn download_from_storage(&self, url: &str) -> (Option<Vec<u8>>, Option<String>) {
        // For now, use the regular downloader
        // In a full implementation, this would use authenticated requests
        self.downloader.download(url).await
    }

    fn decode_data_url(&self, data_url: &str) -> (Option<Vec<u8>>, Option<String>) {
        // Format: data:audio/mp3;base64,<data>
        let parts: Vec<&str> = data_url.splitn(2, ',').collect();
        if parts.len() != 2 {
            return (None, Some("Invalid data URL format".to_string()));
        }

        self.decode_base64(parts[1])
    }

    async fn read_from_file(&self, file_path: &str) -> (Option<Vec<u8>>, Option<String>) {
        let (resolved, error) = self.path_validator.resolve_audio_path(file_path).await;

        let resolved = match resolved {
            Some(p) => p,
            None => return (None, error),
        };

        match fs::read(&resolved).await {
            Ok(data) => {
                let (is_valid, msg) = AudioValidator::is_valid_audio(&data);
                if !is_valid {
                    return (None, Some(msg));
                }
                (Some(data), None)
            },
            Err(e) => (None, Some(format!("Error reading file: {}", e))),
        }
    }

    fn decode_base64(&self, data: &str) -> (Option<Vec<u8>>, Option<String>) {
        match base64::engine::general_purpose::STANDARD.decode(data) {
            Ok(audio_bytes) => {
                let (is_valid, msg) = AudioValidator::is_valid_audio(&audio_bytes);
                if !is_valid {
                    return (None, Some(msg));
                }
                (Some(audio_bytes), None)
            },
            Err(e) => (None, Some(format!("Invalid base64: {}", e))),
        }
    }

    /// Process and play audio from various input formats.
    pub async fn play_audio(
        &self,
        audio_data: &str,
        audio_format: Option<&str>,
        device_name: Option<&str>,
    ) -> Result<String, String> {
        // Process input to get bytes
        let (audio_bytes, error) = self.process_audio_input(audio_data).await;
        let audio_bytes = match audio_bytes {
            Some(b) => b,
            None => return Err(error.unwrap_or_else(|| "Failed to process audio".to_string())),
        };

        // Detect or use provided format
        let format = audio_format
            .map(|f| match f.to_lowercase().as_str() {
                "mp3" => AudioFormat::Mp3,
                "wav" => AudioFormat::Wav,
                "ogg" | "opus" => AudioFormat::Ogg,
                "flac" => AudioFormat::Flac,
                _ => AudioValidator::detect_format(&audio_bytes),
            })
            .unwrap_or_else(|| AudioValidator::detect_format(&audio_bytes));

        // Play audio
        let (success, message) = self.player.play(&audio_bytes, &format, device_name).await;

        if success {
            Ok(message)
        } else {
            Err(message)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
    fn test_detect_format_wav() {
        let data = b"RIFF\x00\x00\x00\x00WAVE";
        assert_eq!(AudioValidator::detect_format(data), AudioFormat::Wav);
    }

    #[test]
    fn test_detect_format_ogg() {
        let data = b"OggS\x00\x02\x00\x00";
        assert_eq!(AudioValidator::detect_format(data), AudioFormat::Ogg);
    }

    #[test]
    fn test_detect_format_flac() {
        let data = b"fLaC\x00\x00\x00\x22";
        assert_eq!(AudioValidator::detect_format(data), AudioFormat::Flac);
    }

    #[test]
    fn test_is_valid_audio_too_small() {
        let data = vec![0xff, 0xfb];
        let (is_valid, msg) = AudioValidator::is_valid_audio(&data);
        assert!(!is_valid);
        assert!(msg.contains("too small"));
    }

    #[test]
    fn test_is_valid_audio_html() {
        // Need to make it larger than MIN_AUDIO_SIZE so it checks for HTML
        let mut data = b"<!DOCTYPE html><html>".to_vec();
        data.extend(vec![0u8; 200]);
        let (is_valid, msg) = AudioValidator::is_valid_audio(&data);
        assert!(!is_valid);
        assert!(msg.contains("HTML"));
    }

    #[test]
    fn test_is_valid_audio_valid_mp3() {
        let mut data = b"ID3\x04\x00\x00\x00\x00".to_vec();
        data.extend(vec![0u8; 200]);
        let (is_valid, msg) = AudioValidator::is_valid_audio(&data);
        assert!(is_valid);
        assert!(msg.contains("mp3"));
    }

    #[test]
    fn test_path_validator_tmp() {
        let validator = AudioPathValidator::new();
        let path = Path::new("/tmp/test.mp3");
        // This test may fail if /tmp doesn't exist, which is fine
        if path.parent().map(|p| p.exists()).unwrap_or(false) {
            // Just test that the method doesn't panic
            let _ = validator.is_path_allowed(path);
        }
    }
}

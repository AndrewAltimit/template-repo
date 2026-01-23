//! YouTube URL extraction using yt-dlp.
//!
//! This module is only available with the `youtube` feature flag.
//!
//! # Requirements
//!
//! - `yt-dlp` must be installed and available in PATH
//! - Works best with a recent version of yt-dlp
//!
//! # Example
//!
//! ```ignore
//! use itk_video::youtube;
//!
//! let direct_url = youtube::extract_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ").await?;
//! // Now use direct_url with VideoDecoder
//! ```

use crate::error::{VideoError, VideoResult};
use tokio::process::Command;
use tracing::{debug, info, warn};

/// Maximum resolution to request (720p).
const MAX_HEIGHT: u32 = 720;

/// Extract a direct video URL from a YouTube link using yt-dlp.
///
/// This function shells out to yt-dlp to get the actual video URL that
/// can be fed to ffmpeg. It requests the best quality up to 720p.
///
/// # Arguments
///
/// * `youtube_url` - A YouTube URL (youtube.com or youtu.be)
///
/// # Returns
///
/// The direct video URL that can be used with ffmpeg.
pub async fn extract_url(youtube_url: &str) -> VideoResult<String> {
    info!(url = %youtube_url, "extracting direct URL via yt-dlp");

    // Build the yt-dlp command
    let output = Command::new("yt-dlp")
        .args([
            // Format selection: best video+audio up to 720p
            "-f",
            &format!("bestvideo[height<={}]+bestaudio/best[height<={}]", MAX_HEIGHT, MAX_HEIGHT),
            // Get URL only, don't download
            "-g",
            // No warnings (cleaner output)
            "--no-warnings",
            // No playlist (single video only)
            "--no-playlist",
            // The URL
            youtube_url,
        ])
        .output()
        .await
        .map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                VideoError::YoutubeExtraction(
                    "yt-dlp not found in PATH. Install it: pip install yt-dlp".to_string(),
                )
            } else {
                VideoError::YoutubeExtraction(format!("failed to run yt-dlp: {}", e))
            }
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(VideoError::YoutubeExtraction(format!(
            "yt-dlp failed: {}",
            stderr.trim()
        )));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let lines: Vec<&str> = stdout.trim().lines().collect();

    // yt-dlp returns one URL per stream (video, audio)
    // We need to return the video URL for ffmpeg
    // If there are two lines, the first is video, second is audio
    // ffmpeg can handle both via concat protocol
    let url = if lines.is_empty() {
        return Err(VideoError::YoutubeExtraction("yt-dlp returned no URLs".to_string()));
    } else if lines.len() == 1 {
        // Single combined stream
        lines[0].to_string()
    } else {
        // Multiple streams - use the first (video) for now
        // TODO: Support merging video+audio streams
        warn!(
            "yt-dlp returned {} URLs, using first (video only)",
            lines.len()
        );
        lines[0].to_string()
    };

    debug!(extracted_url = %url, "extracted direct URL");
    Ok(url)
}

/// Check if yt-dlp is available in PATH.
pub async fn is_available() -> bool {
    Command::new("yt-dlp")
        .arg("--version")
        .output()
        .await
        .is_ok_and(|o| o.status.success())
}

/// Get the version of yt-dlp if available.
pub async fn version() -> Option<String> {
    let output = Command::new("yt-dlp")
        .arg("--version")
        .output()
        .await
        .ok()?;

    if output.status.success() {
        Some(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_is_available() {
        // This test just checks the function runs without panic
        // Actual availability depends on the system
        let _ = is_available().await;
    }
}

//! Video stream source types.

use std::path::PathBuf;

/// Represents a video source that can be decoded.
#[derive(Debug, Clone)]
pub enum StreamSource {
    /// Local file path.
    File(PathBuf),

    /// Remote URL (HTTP/HTTPS, including HLS/DASH manifests).
    Url(String),

    /// Separate video and audio URLs (e.g., YouTube DASH streams).
    UrlWithAudio { video: String, audio: String },
}

impl StreamSource {
    /// Create a stream source from a string, auto-detecting the type.
    ///
    /// - Strings starting with `http://` or `https://` are treated as URLs.
    /// - Strings starting with `file://` have the prefix stripped and are treated as files.
    /// - Everything else is treated as a local file path.
    pub fn from_string(s: &str) -> Self {
        let trimmed = s.trim();

        if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
            StreamSource::Url(trimmed.to_string())
        } else if let Some(path) = trimmed.strip_prefix("file://") {
            StreamSource::File(PathBuf::from(path))
        } else {
            StreamSource::File(PathBuf::from(trimmed))
        }
    }

    /// Check if this source is a YouTube URL.
    pub fn is_youtube(&self) -> bool {
        match self {
            StreamSource::Url(url) | StreamSource::UrlWithAudio { video: url, .. } => {
                url.contains("youtube.com") || url.contains("youtu.be")
            }
            StreamSource::File(_) => false,
        }
    }

    /// Get the path/URL as a string for ffmpeg (video stream).
    pub fn as_ffmpeg_input(&self) -> &str {
        match self {
            StreamSource::File(path) => path.to_str().unwrap_or(""),
            StreamSource::Url(url) | StreamSource::UrlWithAudio { video: url, .. } => url.as_str(),
        }
    }

    /// Get the audio URL if this is a split video+audio source.
    pub fn audio_url(&self) -> Option<&str> {
        match self {
            StreamSource::UrlWithAudio { audio, .. } => Some(audio.as_str()),
            _ => None,
        }
    }
}

impl From<PathBuf> for StreamSource {
    fn from(path: PathBuf) -> Self {
        StreamSource::File(path)
    }
}

impl From<String> for StreamSource {
    fn from(s: String) -> Self {
        StreamSource::from_string(&s)
    }
}

impl From<&str> for StreamSource {
    fn from(s: &str) -> Self {
        StreamSource::from_string(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_auto_detect_file() {
        let source = StreamSource::from_string("/path/to/video.mp4");
        assert!(matches!(source, StreamSource::File(_)));
    }

    #[test]
    fn test_auto_detect_url() {
        let source = StreamSource::from_string("https://example.com/stream.m3u8");
        assert!(matches!(source, StreamSource::Url(_)));
    }

    #[test]
    fn test_auto_detect_file_uri() {
        let source = StreamSource::from_string("file:///path/to/video.mp4");
        match source {
            StreamSource::File(path) => assert_eq!(path.to_str().unwrap(), "/path/to/video.mp4"),
            _ => panic!("expected File variant"),
        }
    }

    #[test]
    fn test_is_youtube() {
        assert!(StreamSource::from_string("https://www.youtube.com/watch?v=abc").is_youtube());
        assert!(StreamSource::from_string("https://youtu.be/abc").is_youtube());
        assert!(!StreamSource::from_string("https://example.com/video.mp4").is_youtube());
        assert!(!StreamSource::from_string("/path/to/video.mp4").is_youtube());
    }
}

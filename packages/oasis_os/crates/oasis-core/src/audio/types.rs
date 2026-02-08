//! Audio type definitions.
//!
//! Platform-agnostic types for track metadata, playback state, and
//! repeat/shuffle modes used by the audio manager.

use serde::{Deserialize, Serialize};

/// Metadata about an audio track.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrackInfo {
    /// Display title (filename if no ID3 tag).
    pub title: String,
    /// Artist name (empty if unknown).
    pub artist: String,
    /// Track duration in milliseconds (0 if unknown).
    pub duration_ms: u64,
    /// VFS path to the audio file.
    pub path: String,
}

impl TrackInfo {
    /// Create a new `TrackInfo` with just a path.
    /// Title defaults to the filename portion of the path.
    pub fn from_path(path: &str) -> Self {
        let title = path.rsplit('/').next().unwrap_or(path).to_string();
        Self {
            title,
            artist: String::new(),
            duration_ms: 0,
            path: path.to_string(),
        }
    }

    /// Builder: set the title.
    pub fn with_title(mut self, title: &str) -> Self {
        self.title = title.to_string();
        self
    }

    /// Builder: set the artist.
    pub fn with_artist(mut self, artist: &str) -> Self {
        self.artist = artist.to_string();
        self
    }

    /// Builder: set the duration.
    pub fn with_duration_ms(mut self, ms: u64) -> Self {
        self.duration_ms = ms;
        self
    }
}

/// Current playback state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PlaybackState {
    /// No track loaded or playback stopped.
    Stopped,
    /// A track is actively playing.
    Playing,
    /// Playback is paused.
    Paused,
}

impl std::fmt::Display for PlaybackState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Stopped => write!(f, "stopped"),
            Self::Playing => write!(f, "playing"),
            Self::Paused => write!(f, "paused"),
        }
    }
}

/// Repeat mode for the playlist.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RepeatMode {
    /// No repeat -- stop after last track.
    Off,
    /// Repeat the entire playlist.
    All,
    /// Repeat the current track.
    One,
}

impl std::fmt::Display for RepeatMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Off => write!(f, "off"),
            Self::All => write!(f, "all"),
            Self::One => write!(f, "one"),
        }
    }
}

impl RepeatMode {
    /// Parse from a string (case-insensitive).
    pub fn parse(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "off" | "none" => Some(Self::Off),
            "all" | "playlist" => Some(Self::All),
            "one" | "track" | "single" => Some(Self::One),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn track_info_from_path() {
        let info = TrackInfo::from_path("/music/album/song.mp3");
        assert_eq!(info.title, "song.mp3");
        assert_eq!(info.path, "/music/album/song.mp3");
        assert!(info.artist.is_empty());
        assert_eq!(info.duration_ms, 0);
    }

    #[test]
    fn track_info_builder() {
        let info = TrackInfo::from_path("/music/test.mp3")
            .with_title("Test Song")
            .with_artist("Test Artist")
            .with_duration_ms(180_000);
        assert_eq!(info.title, "Test Song");
        assert_eq!(info.artist, "Test Artist");
        assert_eq!(info.duration_ms, 180_000);
    }

    #[test]
    fn playback_state_display() {
        assert_eq!(PlaybackState::Stopped.to_string(), "stopped");
        assert_eq!(PlaybackState::Playing.to_string(), "playing");
        assert_eq!(PlaybackState::Paused.to_string(), "paused");
    }

    #[test]
    fn repeat_mode_parse() {
        assert_eq!(RepeatMode::parse("off"), Some(RepeatMode::Off));
        assert_eq!(RepeatMode::parse("ALL"), Some(RepeatMode::All));
        assert_eq!(RepeatMode::parse("one"), Some(RepeatMode::One));
        assert_eq!(RepeatMode::parse("track"), Some(RepeatMode::One));
        assert_eq!(RepeatMode::parse("invalid"), None);
    }

    #[test]
    fn repeat_mode_display() {
        assert_eq!(RepeatMode::Off.to_string(), "off");
        assert_eq!(RepeatMode::All.to_string(), "all");
        assert_eq!(RepeatMode::One.to_string(), "one");
    }
}

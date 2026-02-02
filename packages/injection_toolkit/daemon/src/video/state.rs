//! Video player state and commands.

use std::time::Instant;

/// Commands that can be sent to the video player.
#[derive(Debug, Clone)]
pub enum PlayerCommand {
    /// Load a video from a URL or file path.
    Load {
        source: String,
        start_position_ms: u64,
        autoplay: bool,
    },
    /// Start or resume playback.
    Play,
    /// Pause playback.
    Pause,
    /// Seek to a position in milliseconds.
    Seek { position_ms: u64 },
    /// Set the playback rate (1.0 = normal).
    SetRate { rate: f64 },
    /// Set volume (0.0 - 1.0).
    SetVolume { volume: f32 },
    /// Stop playback and unload the video.
    Stop,
}

/// Video player state.
#[derive(Debug, Clone)]
pub enum PlayerState {
    /// No video loaded.
    Idle,
    /// Loading a video.
    Loading { source: String },
    /// Video is playing.
    Playing {
        info: VideoInfo,
        position_ms: u64,
        started_at: Instant,
    },
    /// Video is paused.
    Paused { info: VideoInfo, position_ms: u64 },
    /// Buffering (waiting for data).
    Buffering {
        info: VideoInfo,
        target_position_ms: u64,
    },
    /// Playback error.
    Error { message: String },
}

impl PlayerState {
    /// Check if the player is currently playing.
    pub fn is_playing(&self) -> bool {
        matches!(self, PlayerState::Playing { .. })
    }

    /// Check if the player is paused.
    pub fn is_paused(&self) -> bool {
        matches!(self, PlayerState::Paused { .. })
    }

    /// Check if a video is loaded (playing, paused, or buffering).
    pub fn has_video(&self) -> bool {
        matches!(
            self,
            PlayerState::Playing { .. }
                | PlayerState::Paused { .. }
                | PlayerState::Buffering { .. }
        )
    }

    /// Get the current video info, if available.
    pub fn video_info(&self) -> Option<&VideoInfo> {
        match self {
            PlayerState::Playing { info, .. }
            | PlayerState::Paused { info, .. }
            | PlayerState::Buffering { info, .. } => Some(info),
            _ => None,
        }
    }

    /// Get the current position in milliseconds.
    pub fn position_ms(&self) -> u64 {
        match self {
            PlayerState::Playing {
                position_ms,
                started_at,
                ..
            } => {
                // Calculate current position based on elapsed time
                let elapsed_ms = started_at.elapsed().as_millis() as u64;
                position_ms.saturating_add(elapsed_ms)
            },
            PlayerState::Paused { position_ms, .. } => *position_ms,
            PlayerState::Buffering {
                target_position_ms, ..
            } => *target_position_ms,
            _ => 0,
        }
    }
}

/// Information about the currently loaded video.
#[derive(Debug, Clone)]
pub struct VideoInfo {
    /// Content identifier (URL or file path hash).
    pub content_id: String,
    /// Video width in pixels.
    pub width: u32,
    /// Video height in pixels.
    pub height: u32,
    /// Duration in milliseconds (0 if unknown/live).
    pub duration_ms: u64,
    /// Frames per second.
    pub fps: f32,
    /// Codec name.
    pub codec: String,
    /// Whether this is a live stream.
    pub is_live: bool,
    /// Title from metadata.
    pub title: Option<String>,
    /// Playback rate (1.0 = normal).
    pub playback_rate: f64,
    /// Volume (0.0 - 1.0).
    pub volume: f32,
}

impl Default for VideoInfo {
    fn default() -> Self {
        Self {
            content_id: String::new(),
            width: 1280,
            height: 720,
            duration_ms: 0,
            fps: 30.0,
            codec: String::new(),
            is_live: false,
            title: None,
            playback_rate: 1.0,
            volume: 1.0,
        }
    }
}

//! Video player implementation.

use super::state::{PlayerCommand, PlayerState, VideoInfo};
use itk_protocol::{VideoMetadata, VideoState};
use itk_shmem::FrameBuffer;
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};
use tracing::{debug, error, info, warn};

/// Default output width for video frames.
const DEFAULT_WIDTH: u32 = 1280;
/// Default output height for video frames.
const DEFAULT_HEIGHT: u32 = 720;
/// Shared memory name for video frames.
const SHMEM_NAME: &str = "itk_video_frames";

/// Video player that decodes video and writes frames to shared memory.
pub struct VideoPlayer {
    /// Current player state.
    state: Arc<Mutex<PlayerState>>,
    /// Command sender for the decode thread.
    command_tx: Sender<PlayerCommand>,
    /// Handle to the decode thread.
    decode_thread: Option<JoinHandle<()>>,
    /// Shared memory frame buffer (used when ffmpeg decoding is enabled).
    #[allow(dead_code)]
    frame_buffer: Option<FrameBuffer>,
}

impl VideoPlayer {
    /// Create a new video player.
    pub fn new() -> Self {
        let (command_tx, command_rx) = mpsc::channel();
        let state = Arc::new(Mutex::new(PlayerState::Idle));

        // Try to create the shared memory frame buffer
        let frame_buffer = match FrameBuffer::create(SHMEM_NAME, DEFAULT_WIDTH, DEFAULT_HEIGHT) {
            Ok(fb) => {
                info!(
                    width = DEFAULT_WIDTH,
                    height = DEFAULT_HEIGHT,
                    "Created video frame buffer"
                );
                Some(fb)
            }
            Err(e) => {
                warn!(?e, "Failed to create frame buffer, video output disabled");
                None
            }
        };

        // Start the decode thread
        let state_clone = Arc::clone(&state);
        let decode_thread = thread::spawn(move || {
            decode_loop(state_clone, command_rx);
        });

        Self {
            state,
            command_tx,
            decode_thread: Some(decode_thread),
            frame_buffer,
        }
    }

    /// Send a command to the video player.
    pub fn send_command(&self, cmd: PlayerCommand) {
        if let Err(e) = self.command_tx.send(cmd) {
            error!(?e, "Failed to send command to video player");
        }
    }

    /// Load a video from a source.
    pub fn load(&self, source: &str, start_position_ms: u64, autoplay: bool) {
        self.send_command(PlayerCommand::Load {
            source: source.to_string(),
            start_position_ms,
            autoplay,
        });
    }

    /// Start or resume playback.
    pub fn play(&self) {
        self.send_command(PlayerCommand::Play);
    }

    /// Pause playback.
    pub fn pause(&self) {
        self.send_command(PlayerCommand::Pause);
    }

    /// Seek to a position.
    pub fn seek(&self, position_ms: u64) {
        self.send_command(PlayerCommand::Seek { position_ms });
    }

    /// Stop playback and unload.
    pub fn stop(&self) {
        self.send_command(PlayerCommand::Stop);
    }

    /// Get the current player state.
    pub fn state(&self) -> PlayerState {
        self.state.lock().unwrap().clone()
    }

    /// Get the current video state for protocol messages.
    pub fn get_video_state(&self) -> Option<VideoState> {
        let state = self.state.lock().unwrap();
        match &*state {
            PlayerState::Playing { info, .. }
            | PlayerState::Paused { info, .. }
            | PlayerState::Buffering { info, .. } => Some(VideoState {
                content_id: info.content_id.clone(),
                position_ms: state.position_ms(),
                duration_ms: info.duration_ms,
                is_playing: state.is_playing(),
                is_buffering: matches!(*state, PlayerState::Buffering { .. }),
                playback_rate: info.playback_rate,
                volume: info.volume,
            }),
            _ => None,
        }
    }

    /// Get video metadata for protocol messages.
    pub fn get_metadata(&self) -> Option<VideoMetadata> {
        let state = self.state.lock().unwrap();
        state.video_info().map(|info| VideoMetadata {
            content_id: info.content_id.clone(),
            width: info.width,
            height: info.height,
            duration_ms: info.duration_ms,
            fps: info.fps,
            codec: info.codec.clone(),
            is_live: info.is_live,
            title: info.title.clone(),
        })
    }
}

impl Default for VideoPlayer {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for VideoPlayer {
    fn drop(&mut self) {
        // Signal the decode thread to stop
        let _ = self.command_tx.send(PlayerCommand::Stop);

        // Wait for the thread to finish
        if let Some(handle) = self.decode_thread.take() {
            let _ = handle.join();
        }
    }
}

/// Main decode loop that runs in a separate thread.
fn decode_loop(state: Arc<Mutex<PlayerState>>, command_rx: Receiver<PlayerCommand>) {
    info!("Video decode thread started");

    loop {
        // Wait for a command with timeout to allow periodic state checks
        match command_rx.recv_timeout(Duration::from_millis(16)) {
            Ok(cmd) => {
                debug!(?cmd, "Received video command");
                match cmd {
                    PlayerCommand::Load {
                        source,
                        start_position_ms,
                        autoplay,
                    } => {
                        handle_load(&state, &source, start_position_ms, autoplay);
                    }
                    PlayerCommand::Play => {
                        handle_play(&state);
                    }
                    PlayerCommand::Pause => {
                        handle_pause(&state);
                    }
                    PlayerCommand::Seek { position_ms } => {
                        handle_seek(&state, position_ms);
                    }
                    PlayerCommand::SetRate { rate } => {
                        handle_set_rate(&state, rate);
                    }
                    PlayerCommand::SetVolume { volume } => {
                        handle_set_volume(&state, volume);
                    }
                    PlayerCommand::Stop => {
                        info!("Video decode thread stopping");
                        *state.lock().unwrap() = PlayerState::Idle;
                        break;
                    }
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                // Check if we need to decode more frames
                let current_state = state.lock().unwrap().clone();
                if let PlayerState::Playing { .. } = current_state {
                    // In a real implementation, this would decode and output frames
                    // For now, just update the position based on elapsed time
                }
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                info!("Command channel disconnected, stopping decode thread");
                break;
            }
        }
    }
}

/// Handle a load command.
fn handle_load(
    state: &Arc<Mutex<PlayerState>>,
    source: &str,
    start_position_ms: u64,
    autoplay: bool,
) {
    info!(source = %source, start_ms = start_position_ms, autoplay, "Loading video");

    // Set loading state
    *state.lock().unwrap() = PlayerState::Loading {
        source: source.to_string(),
    };

    // In a real implementation, this would:
    // 1. Initialize ffmpeg decoder for the source
    // 2. Extract metadata (duration, codec, fps)
    // 3. Seek to start_position_ms
    // 4. Start decoding if autoplay is true

    // For now, create a mock video info
    let content_id = format!("{:016x}", hash_string(source));
    let info = VideoInfo {
        content_id,
        width: DEFAULT_WIDTH,
        height: DEFAULT_HEIGHT,
        duration_ms: 0, // Unknown duration for mock
        fps: 30.0,
        codec: "mock".to_string(),
        is_live: source.contains(".m3u8") || source.contains("/live/"),
        title: None,
        playback_rate: 1.0,
        volume: 1.0,
    };

    if autoplay {
        *state.lock().unwrap() = PlayerState::Playing {
            info,
            position_ms: start_position_ms,
            started_at: Instant::now(),
        };
    } else {
        *state.lock().unwrap() = PlayerState::Paused {
            info,
            position_ms: start_position_ms,
        };
    }
}

/// Handle a play command.
fn handle_play(state: &Arc<Mutex<PlayerState>>) {
    let mut state = state.lock().unwrap();
    if let PlayerState::Paused { info, position_ms } = state.clone() {
        info!(position_ms, "Resuming playback");
        *state = PlayerState::Playing {
            info,
            position_ms,
            started_at: Instant::now(),
        };
    }
}

/// Handle a pause command.
fn handle_pause(state: &Arc<Mutex<PlayerState>>) {
    let mut state = state.lock().unwrap();
    if let PlayerState::Playing {
        info,
        position_ms,
        started_at,
    } = state.clone()
    {
        let current_pos = position_ms.saturating_add(started_at.elapsed().as_millis() as u64);
        info!(position_ms = current_pos, "Pausing playback");
        *state = PlayerState::Paused {
            info,
            position_ms: current_pos,
        };
    }
}

/// Handle a seek command.
fn handle_seek(state: &Arc<Mutex<PlayerState>>, position_ms: u64) {
    let mut state = state.lock().unwrap();
    match state.clone() {
        PlayerState::Playing { info, .. } => {
            info!(position_ms, "Seeking (playing)");
            *state = PlayerState::Playing {
                info,
                position_ms,
                started_at: Instant::now(),
            };
        }
        PlayerState::Paused { info, .. } => {
            info!(position_ms, "Seeking (paused)");
            *state = PlayerState::Paused { info, position_ms };
        }
        _ => {
            warn!("Seek ignored - no video loaded");
        }
    }
}

/// Handle a set rate command.
fn handle_set_rate(state: &Arc<Mutex<PlayerState>>, rate: f64) {
    let mut state = state.lock().unwrap();
    if let Some(info) = state.video_info().cloned() {
        let mut new_info = info;
        new_info.playback_rate = rate.clamp(0.25, 4.0);
        debug!(rate = new_info.playback_rate, "Set playback rate");

        // Update the info in the current state
        match &mut *state {
            PlayerState::Playing { info, .. }
            | PlayerState::Paused { info, .. }
            | PlayerState::Buffering { info, .. } => {
                *info = new_info;
            }
            _ => {}
        }
    }
}

/// Handle a set volume command.
fn handle_set_volume(state: &Arc<Mutex<PlayerState>>, volume: f32) {
    let mut state = state.lock().unwrap();
    if let Some(info) = state.video_info().cloned() {
        let mut new_info = info;
        new_info.volume = volume.clamp(0.0, 1.0);
        debug!(volume = new_info.volume, "Set volume");

        // Update the info in the current state
        match &mut *state {
            PlayerState::Playing { info, .. }
            | PlayerState::Paused { info, .. }
            | PlayerState::Buffering { info, .. } => {
                *info = new_info;
            }
            _ => {}
        }
    }
}

/// Simple hash function for content IDs.
fn hash_string(s: &str) -> u64 {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut hasher = DefaultHasher::new();
    s.hash(&mut hasher);
    hasher.finish()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_player_creation() {
        // This test verifies the player can be created
        // Frame buffer creation may fail without proper permissions
        let player = VideoPlayer::new();
        assert!(matches!(player.state(), PlayerState::Idle));
    }

    #[test]
    fn test_hash_string() {
        let hash1 = hash_string("test");
        let hash2 = hash_string("test");
        let hash3 = hash_string("other");
        assert_eq!(hash1, hash2);
        assert_ne!(hash1, hash3);
    }
}

//! Video player implementation with real ffmpeg decoding.

use super::audio::AudioPlayer;
use super::state::{PlayerCommand, PlayerState, VideoInfo};
use itk_protocol::{VideoMetadata, VideoState};
use itk_video::{DecodedFrame, FrameWriter, StreamSource, VideoDecoder};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};
use tracing::{debug, error, info, warn};

/// Lock the player state mutex, recovering from poisoning.
///
/// A poisoned mutex means a thread panicked while holding the lock.
/// We recover by taking the inner data since partial state is better
/// than crashing the daemon.
fn lock_state(mutex: &Mutex<PlayerState>) -> std::sync::MutexGuard<'_, PlayerState> {
    mutex.lock().unwrap_or_else(|poisoned| {
        warn!("Player state mutex was poisoned, recovering");
        poisoned.into_inner()
    })
}

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
}

impl VideoPlayer {
    /// Create a new video player.
    pub fn new() -> Self {
        let (command_tx, command_rx) = mpsc::channel();
        let state = Arc::new(Mutex::new(PlayerState::Idle));

        // Start the decode thread
        let state_clone = Arc::clone(&state);
        let decode_thread = thread::spawn(move || {
            decode_loop(state_clone, command_rx);
        });

        Self {
            state,
            command_tx,
            decode_thread: Some(decode_thread),
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
    #[allow(dead_code)]
    pub fn stop(&self) {
        self.send_command(PlayerCommand::Stop);
    }

    /// Get the current player state.
    #[allow(dead_code)]
    pub fn state(&self) -> PlayerState {
        lock_state(&self.state).clone()
    }

    /// Get the current video state for protocol messages.
    pub fn get_video_state(&self) -> Option<VideoState> {
        let state = lock_state(&self.state);
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
    #[allow(dead_code)]
    pub fn get_metadata(&self) -> Option<VideoMetadata> {
        let state = lock_state(&self.state);
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

/// Resolve a source string to a StreamSource, handling YouTube URLs.
fn resolve_source(source: &str) -> Result<StreamSource, String> {
    let stream_source = StreamSource::from_string(source);

    if stream_source.is_youtube() {
        #[cfg(feature = "youtube")]
        {
            info!(url = %source, "Extracting YouTube direct URL via yt-dlp");
            let output = std::process::Command::new("yt-dlp")
                .args([
                    "-f",
                    // Progressive formats (muxed audio+video) first, then DASH with audio.
                    // Format 22 = 720p progressive MP4 (h264+aac)
                    // Format 18 = 360p progressive MP4 (h264+aac)
                    // DASH fallback requests bestaudio paired, so audio player gets a URL.
                    "22/18/bestvideo[height<=720][vcodec^=avc1]+bestaudio/bestvideo[height<=720]+bestaudio",
                    "-g",
                    "--no-warnings",
                    "--no-playlist",
                    source,
                ])
                .output()
                .map_err(|e| {
                    if e.kind() == std::io::ErrorKind::NotFound {
                        "yt-dlp not found in PATH. Install: pip install yt-dlp".to_string()
                    } else {
                        format!("Failed to run yt-dlp: {e}")
                    }
                })?;

            if !output.status.success() {
                let stderr = String::from_utf8_lossy(&output.stderr);
                return Err(format!("yt-dlp failed: {}", stderr.trim()));
            }

            let stdout = String::from_utf8_lossy(&output.stdout);
            let lines: Vec<&str> = stdout.trim().lines().collect();

            if lines.is_empty() {
                return Err("yt-dlp returned no URLs".to_string());
            }

            let video_url = lines[0].to_string();

            if lines.len() >= 2 {
                // DASH format selected: separate video + audio URLs.
                // Return as AudioUrl variant so the audio player uses the correct stream.
                info!("YouTube DASH streams: video + audio URLs extracted");
                return Ok(StreamSource::UrlWithAudio {
                    video: video_url,
                    audio: lines[1].to_string(),
                });
            }

            info!("YouTube progressive stream extracted (muxed audio+video)");
            return Ok(StreamSource::Url(video_url));
        }
        #[cfg(not(feature = "youtube"))]
        {
            return Err(
                "YouTube support not enabled (compile with --features youtube)".to_string(),
            );
        }
    }

    Ok(stream_source)
}

/// Decode thread state holding the active decoder and frame writer.
struct DecodeContext {
    decoder: VideoDecoder,
    writer: FrameWriter,
    info: VideoInfo,
    /// The PTS (ms) at which current playback segment started.
    base_pts_ms: u64,
    /// Wall-clock time when current playback segment started.
    playback_start: Instant,
    /// Audio player (None if source has no audio or output unavailable).
    audio: Option<AudioPlayer>,
    /// Frame decoded too early (>100ms ahead), held until its scheduled time.
    pending_frame: Option<DecodedFrame>,
}

/// Main decode loop that runs in a separate thread.
fn decode_loop(state: Arc<Mutex<PlayerState>>, command_rx: Receiver<PlayerCommand>) {
    info!("Video decode thread started");

    let mut ctx: Option<DecodeContext> = None;

    loop {
        let is_playing = lock_state(&state).is_playing();
        let timeout = if is_playing {
            Duration::from_millis(1) // Fast polling during playback
        } else {
            Duration::from_millis(100) // Slower when idle/paused
        };

        match command_rx.recv_timeout(timeout) {
            Ok(cmd) => {
                debug!(?cmd, "Received video command");
                match cmd {
                    PlayerCommand::Load {
                        source,
                        start_position_ms,
                        autoplay,
                    } => {
                        ctx = handle_load(&state, &source, start_position_ms, autoplay);
                    },
                    PlayerCommand::Play => {
                        handle_play(&state, &mut ctx);
                    },
                    PlayerCommand::Pause => {
                        handle_pause(&state, &ctx);
                    },
                    PlayerCommand::Seek { position_ms } => {
                        handle_seek(&state, &mut ctx, position_ms);
                    },
                    PlayerCommand::SetRate { rate } => {
                        handle_set_rate(&state, rate);
                    },
                    PlayerCommand::SetVolume { volume } => {
                        handle_set_volume(&state, &ctx, volume);
                    },
                    PlayerCommand::Stop => {
                        info!("Video decode thread stopping");
                        drop(ctx.take());
                        *lock_state(&state) = PlayerState::Idle;
                        break;
                    },
                }
            },
            Err(mpsc::RecvTimeoutError::Timeout) => {
                // Decode next frame if playing
                if is_playing {
                    if let Some(decode_ctx) = &mut ctx {
                        decode_next_frame(decode_ctx, &state);
                    }
                }
            },
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                info!("Command channel disconnected, stopping decode thread");
                break;
            },
        }
    }
}

/// Decode and output the next frame with PTS-based pacing.
///
/// If a previously-decoded frame was too early (>100ms ahead), it is held in
/// `pending_frame` and retried on the next call instead of being dropped.
fn decode_next_frame(ctx: &mut DecodeContext, state: &Arc<Mutex<PlayerState>>) {
    // Use pending frame if available, otherwise decode a new one
    let frame_result = if ctx.pending_frame.is_some() {
        Ok(ctx.pending_frame.take())
    } else {
        ctx.decoder.next_frame()
    };

    match frame_result {
        Ok(Some(frame)) => {
            // PTS-based frame pacing: sleep until the correct wall-clock time
            let target_elapsed_ms = frame.pts_ms.saturating_sub(ctx.base_pts_ms);
            let wall_elapsed = ctx.playback_start.elapsed();
            let target_wall = Duration::from_millis(target_elapsed_ms);

            if target_wall > wall_elapsed {
                let sleep_dur = target_wall - wall_elapsed;
                // Cap sleep to 100ms to stay responsive to commands
                if sleep_dur < Duration::from_millis(100) {
                    thread::sleep(sleep_dur);
                } else {
                    // Frame is too early - hold it for the next iteration
                    thread::sleep(Duration::from_millis(100));
                    ctx.pending_frame = Some(frame);
                    return;
                }
            }

            // Write frame to shared memory
            match ctx.writer.write_frame(&frame) {
                Ok(_written) => {
                    // Update position in state
                    let mut s = lock_state(state);
                    if let PlayerState::Playing { position_ms, .. } = &mut *s {
                        *position_ms = frame.pts_ms;
                    }
                },
                Err(e) => {
                    warn!(?e, "Failed to write frame to shared memory");
                },
            }
        },
        Ok(None) => {
            // End of stream
            info!("Video playback complete (end of stream)");
            let mut s = lock_state(state);
            if let PlayerState::Playing { info, .. } = s.clone() {
                *s = PlayerState::Paused {
                    info,
                    position_ms: ctx.info.duration_ms,
                };
            }
        },
        Err(e) => {
            error!(?e, "Decode error");
            *lock_state(state) = PlayerState::Error {
                message: format!("Decode error: {e}"),
            };
        },
    }
}

/// Handle a load command - creates decoder and frame writer.
fn handle_load(
    state: &Arc<Mutex<PlayerState>>,
    source: &str,
    start_position_ms: u64,
    autoplay: bool,
) -> Option<DecodeContext> {
    info!(source = %source, start_ms = start_position_ms, autoplay, "Loading video");

    // Set loading state
    *lock_state(state) = PlayerState::Loading {
        source: source.to_string(),
    };

    // Resolve source (handles YouTube extraction)
    let stream_source = match resolve_source(source) {
        Ok(s) => s,
        Err(e) => {
            error!(error = %e, "Failed to resolve video source");
            *lock_state(state) = PlayerState::Error {
                message: format!("Source resolution failed: {e}"),
            };
            return None;
        },
    };

    // Get the audio source path: use separate audio URL for DASH streams,
    // or the same video URL for progressive (muxed) streams.
    let audio_source_path = stream_source
        .audio_url()
        .unwrap_or_else(|| stream_source.as_ffmpeg_input())
        .to_string();

    // Create the decoder
    let mut decoder = match VideoDecoder::with_size(stream_source, DEFAULT_WIDTH, DEFAULT_HEIGHT) {
        Ok(d) => d,
        Err(e) => {
            error!(?e, "Failed to create video decoder");
            *lock_state(state) = PlayerState::Error {
                message: format!("Decoder init failed: {e}"),
            };
            return None;
        },
    };

    // Create the frame writer (shared memory)
    let mut writer = match FrameWriter::create(SHMEM_NAME, DEFAULT_WIDTH, DEFAULT_HEIGHT) {
        Ok(w) => w,
        Err(e) => {
            error!(?e, "Failed to create frame writer");
            *lock_state(state) = PlayerState::Error {
                message: format!("Frame writer failed: {e}"),
            };
            return None;
        },
    };

    // Build video info from decoder metadata
    let content_id = format!("{:016x}", hash_string(source));
    let info = VideoInfo {
        content_id: content_id.clone(),
        width: decoder.output_width(),
        height: decoder.output_height(),
        duration_ms: decoder.duration_ms().unwrap_or(0),
        fps: decoder.fps().unwrap_or(30.0) as f32,
        codec: "h264".to_string(), // ffmpeg-next doesn't easily expose codec name string
        is_live: source.contains(".m3u8") || source.contains("/live/"),
        title: None,
        playback_rate: 1.0,
        volume: 1.0,
    };

    writer.set_content_id(&content_id);
    writer.set_duration_ms(info.duration_ms);

    // Create audio player (opens the same source independently)
    let audio = AudioPlayer::new(&audio_source_path, info.volume, autoplay);
    if audio.is_some() {
        info!("Audio player initialized");
    } else {
        info!("No audio available for this source");
    }

    // Seek to start position if needed
    if start_position_ms > 0 {
        if let Err(e) = decoder.seek(start_position_ms) {
            warn!(
                ?e,
                "Failed to seek to start position, starting from beginning"
            );
        }
        if let Some(audio_player) = &audio {
            audio_player.seek(start_position_ms);
        }
    }

    info!(
        width = info.width,
        height = info.height,
        duration_ms = info.duration_ms,
        fps = info.fps,
        "Video loaded successfully"
    );

    let ctx = DecodeContext {
        decoder,
        writer,
        info: info.clone(),
        base_pts_ms: start_position_ms,
        playback_start: Instant::now(),
        audio,
        pending_frame: None,
    };

    if autoplay {
        *lock_state(state) = PlayerState::Playing {
            info,
            position_ms: start_position_ms,
            started_at: Instant::now(),
        };
    } else {
        *lock_state(state) = PlayerState::Paused {
            info,
            position_ms: start_position_ms,
        };
    }

    Some(ctx)
}

/// Handle a play command.
fn handle_play(state: &Arc<Mutex<PlayerState>>, ctx: &mut Option<DecodeContext>) {
    let mut s = lock_state(state);
    if let PlayerState::Paused { info, position_ms } = s.clone() {
        info!(position_ms, "Resuming playback");

        // Update decode context timing
        if let Some(decode_ctx) = ctx {
            decode_ctx.base_pts_ms = position_ms;
            decode_ctx.playback_start = Instant::now();

            // Resume audio
            if let Some(audio) = &decode_ctx.audio {
                audio.play();
            }
        }

        *s = PlayerState::Playing {
            info,
            position_ms,
            started_at: Instant::now(),
        };
    }
}

/// Handle a pause command.
fn handle_pause(state: &Arc<Mutex<PlayerState>>, ctx: &Option<DecodeContext>) {
    let mut s = lock_state(state);
    if let PlayerState::Playing { info, .. } = s.clone() {
        // Use the frame writer's last PTS as the accurate position
        let current_pos = ctx.as_ref().map(|c| c.writer.last_pts_ms()).unwrap_or(0);
        info!(position_ms = current_pos, "Pausing playback");

        // Pause audio
        if let Some(ctx) = ctx {
            if let Some(audio) = &ctx.audio {
                audio.pause();
            }
        }

        *s = PlayerState::Paused {
            info,
            position_ms: current_pos,
        };
    }
}

/// Handle a seek command.
fn handle_seek(state: &Arc<Mutex<PlayerState>>, ctx: &mut Option<DecodeContext>, position_ms: u64) {
    // Seek the decoder
    if let Some(decode_ctx) = ctx {
        if let Err(e) = decode_ctx.decoder.seek(position_ms) {
            warn!(?e, position_ms, "Seek failed");
            return;
        }
        // Reset timing for the new position
        decode_ctx.base_pts_ms = position_ms;
        decode_ctx.playback_start = Instant::now();
        decode_ctx.pending_frame = None; // Discard stale buffered frame

        // Seek audio
        if let Some(audio) = &decode_ctx.audio {
            audio.seek(position_ms);
        }
    }

    let mut s = lock_state(state);
    match s.clone() {
        PlayerState::Playing { info, .. } => {
            info!(position_ms, "Seeking (playing)");
            *s = PlayerState::Playing {
                info,
                position_ms,
                started_at: Instant::now(),
            };
        },
        PlayerState::Paused { info, .. } => {
            info!(position_ms, "Seeking (paused)");
            *s = PlayerState::Paused { info, position_ms };
        },
        _ => {
            warn!("Seek ignored - no video loaded");
        },
    }
}

/// Handle a set rate command.
fn handle_set_rate(state: &Arc<Mutex<PlayerState>>, rate: f64) {
    let mut state = lock_state(state);
    if let Some(info) = state.video_info().cloned() {
        let mut new_info = info;
        new_info.playback_rate = rate.clamp(0.25, 4.0);
        debug!(rate = new_info.playback_rate, "Set playback rate");

        match &mut *state {
            PlayerState::Playing { info, .. }
            | PlayerState::Paused { info, .. }
            | PlayerState::Buffering { info, .. } => {
                *info = new_info;
            },
            _ => {},
        }
    }
}

/// Handle a set volume command.
fn handle_set_volume(state: &Arc<Mutex<PlayerState>>, ctx: &Option<DecodeContext>, volume: f32) {
    let clamped = volume.clamp(0.0, 1.0);

    // Update audio player volume
    if let Some(decode_ctx) = ctx {
        if let Some(audio) = &decode_ctx.audio {
            audio.set_volume(clamped);
        }
    }

    let mut state = lock_state(state);
    if let Some(info) = state.video_info().cloned() {
        let mut new_info = info;
        new_info.volume = clamped;
        debug!(volume = new_info.volume, "Set volume");

        match &mut *state {
            PlayerState::Playing { info, .. }
            | PlayerState::Paused { info, .. }
            | PlayerState::Buffering { info, .. } => {
                *info = new_info;
            },
            _ => {},
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

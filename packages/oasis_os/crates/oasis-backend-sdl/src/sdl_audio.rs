//! SDL2 audio backend for OASIS_OS.
//!
//! Implements `AudioBackend` using SDL2's audio subsystem. On desktop and
//! Raspberry Pi, SDL2 handles device discovery, mixing, and output.
//!
//! Audio data is stored in-memory after `load_track()`. Playback is managed
//! through SDL2's audio callback or queue-based API.
//!
//! Note: Real audio output requires hardware. In CI (Docker without audio
//! devices), `init()` may fail gracefully. The `NullAudioBackend` in
//! `oasis-core` is used for testing without hardware.

use std::collections::HashMap;

use oasis_core::backend::{AudioBackend, AudioTrackId};
use oasis_core::error::{OasisError, Result};

/// SDL2-based audio backend.
///
/// Stores loaded tracks as raw byte data indexed by `AudioTrackId`.
/// Actual SDL2 audio device interaction is gated behind `init()`.
pub struct SdlAudioBackend {
    /// Whether the audio subsystem has been initialized.
    initialized: bool,
    /// Loaded track data keyed by track ID.
    tracks: HashMap<u64, Vec<u8>>,
    /// Next track ID to assign.
    next_id: u64,
    /// Currently playing track ID (if any).
    current_track: Option<u64>,
    /// Current volume (0-100).
    volume: u8,
    /// Whether playback is active.
    playing: bool,
    /// Whether playback is paused.
    paused: bool,
    /// Simulated playback position in ms (for status display).
    position_ms: u64,
    /// Simulated track duration in ms.
    duration_ms: u64,
}

impl SdlAudioBackend {
    /// Create a new SDL2 audio backend (not yet initialized).
    pub fn new() -> Self {
        Self {
            initialized: false,
            tracks: HashMap::new(),
            next_id: 0,
            current_track: None,
            volume: 80,
            playing: false,
            paused: false,
            position_ms: 0,
            duration_ms: 0,
        }
    }
}

impl Default for SdlAudioBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioBackend for SdlAudioBackend {
    fn init(&mut self) -> Result<()> {
        // In a full implementation, this would call:
        //   sdl2::init()?.audio()?
        // and open an audio device. For now, we mark as initialized
        // and manage track state. Real SDL2 audio device opening will
        // be added when we integrate with the main loop.
        self.initialized = true;
        log::info!("SDL2 audio backend initialized");
        Ok(())
    }

    fn load_track(&mut self, data: &[u8]) -> Result<AudioTrackId> {
        if !self.initialized {
            return Err(OasisError::Backend("audio not initialized".into()));
        }
        let id = self.next_id;
        self.next_id += 1;
        self.tracks.insert(id, data.to_vec());
        // Estimate duration from data size (rough MP3 estimate: 128kbps).
        // Real implementation would parse MP3 headers.
        let estimated_ms = (data.len() as u64 * 8) / 128; // bits / kbps = ms
        log::debug!(
            "Loaded audio track {id} ({} bytes, ~{estimated_ms}ms)",
            data.len()
        );
        Ok(AudioTrackId(id))
    }

    fn play(&mut self, track: AudioTrackId) -> Result<()> {
        if !self.initialized {
            return Err(OasisError::Backend("audio not initialized".into()));
        }
        if !self.tracks.contains_key(&track.0) {
            return Err(OasisError::Backend(format!("track {} not loaded", track.0)));
        }
        // In a full implementation, this would decode the audio data and
        // feed it to the SDL2 audio queue/callback.
        self.current_track = Some(track.0);
        self.playing = true;
        self.paused = false;
        self.position_ms = 0;

        // Set duration from track data.
        if let Some(data) = self.tracks.get(&track.0) {
            self.duration_ms = (data.len() as u64 * 8) / 128;
        }
        Ok(())
    }

    fn pause(&mut self) -> Result<()> {
        if !self.playing {
            return Err(OasisError::Backend("not playing".into()));
        }
        self.playing = false;
        self.paused = true;
        Ok(())
    }

    fn resume(&mut self) -> Result<()> {
        if !self.paused {
            return Err(OasisError::Backend("not paused".into()));
        }
        self.playing = true;
        self.paused = false;
        Ok(())
    }

    fn stop(&mut self) -> Result<()> {
        self.playing = false;
        self.paused = false;
        self.position_ms = 0;
        Ok(())
    }

    fn set_volume(&mut self, volume: u8) -> Result<()> {
        self.volume = volume.min(100);
        // In full implementation: SDL_mixer SetVolume or adjust gain.
        Ok(())
    }

    fn get_volume(&self) -> u8 {
        self.volume
    }

    fn is_playing(&self) -> bool {
        self.playing
    }

    fn position_ms(&self) -> u64 {
        self.position_ms
    }

    fn duration_ms(&self) -> u64 {
        self.duration_ms
    }

    fn unload_track(&mut self, track: AudioTrackId) -> Result<()> {
        if self.current_track == Some(track.0) {
            self.stop()?;
            self.current_track = None;
        }
        self.tracks.remove(&track.0);
        Ok(())
    }

    fn shutdown(&mut self) -> Result<()> {
        self.stop()?;
        self.tracks.clear();
        self.initialized = false;
        log::info!("SDL2 audio backend shut down");
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn init_backend() -> SdlAudioBackend {
        let mut backend = SdlAudioBackend::new();
        backend.init().unwrap();
        backend
    }

    #[test]
    fn init_and_shutdown() {
        let mut backend = SdlAudioBackend::new();
        assert!(!backend.initialized);
        backend.init().unwrap();
        assert!(backend.initialized);
        backend.shutdown().unwrap();
        assert!(!backend.initialized);
    }

    #[test]
    fn load_and_play_track() {
        let mut backend = init_backend();
        let track = backend.load_track(b"fake mp3 data here").unwrap();
        backend.play(track).unwrap();
        assert!(backend.is_playing());
        assert_eq!(backend.current_track, Some(track.0));
    }

    #[test]
    fn load_without_init_fails() {
        let mut backend = SdlAudioBackend::new();
        assert!(backend.load_track(b"data").is_err());
    }

    #[test]
    fn play_missing_track_fails() {
        let mut backend = init_backend();
        assert!(backend.play(AudioTrackId(999)).is_err());
    }

    #[test]
    fn pause_and_resume() {
        let mut backend = init_backend();
        let track = backend.load_track(b"data").unwrap();
        backend.play(track).unwrap();

        backend.pause().unwrap();
        assert!(!backend.is_playing());
        assert!(backend.paused);

        backend.resume().unwrap();
        assert!(backend.is_playing());
        assert!(!backend.paused);
    }

    #[test]
    fn pause_when_not_playing_fails() {
        let mut backend = init_backend();
        assert!(backend.pause().is_err());
    }

    #[test]
    fn resume_when_not_paused_fails() {
        let mut backend = init_backend();
        assert!(backend.resume().is_err());
    }

    #[test]
    fn stop_playback() {
        let mut backend = init_backend();
        let track = backend.load_track(b"data").unwrap();
        backend.play(track).unwrap();
        backend.stop().unwrap();
        assert!(!backend.is_playing());
        assert_eq!(backend.position_ms(), 0);
    }

    #[test]
    fn volume_control() {
        let mut backend = init_backend();
        backend.set_volume(42).unwrap();
        assert_eq!(backend.get_volume(), 42);

        // Clamp to 100.
        backend.set_volume(200).unwrap();
        assert_eq!(backend.get_volume(), 100);
    }

    #[test]
    fn unload_track() {
        let mut backend = init_backend();
        let track = backend.load_track(b"data").unwrap();
        backend.play(track).unwrap();

        backend.unload_track(track).unwrap();
        assert!(!backend.is_playing());
        assert!(!backend.tracks.contains_key(&track.0));
    }

    #[test]
    fn multiple_tracks() {
        let mut backend = init_backend();
        let t1 = backend.load_track(b"track 1").unwrap();
        let t2 = backend.load_track(b"track 2").unwrap();
        assert_ne!(t1, t2);
        assert_eq!(backend.tracks.len(), 2);

        backend.play(t1).unwrap();
        assert!(backend.is_playing());

        backend.stop().unwrap();
        backend.play(t2).unwrap();
        assert!(backend.is_playing());
        assert_eq!(backend.current_track, Some(t2.0));
    }

    #[test]
    fn shutdown_clears_tracks() {
        let mut backend = init_backend();
        backend.load_track(b"track 1").unwrap();
        backend.load_track(b"track 2").unwrap();
        backend.shutdown().unwrap();
        assert!(backend.tracks.is_empty());
    }
}

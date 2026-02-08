//! Null audio backend for testing and headless operation.
//!
//! Implements `AudioBackend` as a no-op. Used in unit tests,
//! CI environments without audio hardware, and the UE5 backend
//! (which handles audio through the game engine).

use crate::backend::{AudioBackend, AudioTrackId};
use crate::error::{OasisError, Result};

/// No-op audio backend.
///
/// All operations succeed but produce no actual audio output.
/// Track loading assigns sequential IDs and tracks play/pause state.
pub struct NullAudioBackend {
    next_id: u64,
    volume: u8,
    playing: bool,
    paused: bool,
    current_track: Option<u64>,
    loaded_count: usize,
}

impl NullAudioBackend {
    pub fn new() -> Self {
        Self {
            next_id: 0,
            volume: 80,
            playing: false,
            paused: false,
            current_track: None,
            loaded_count: 0,
        }
    }

    /// Return how many tracks have been loaded.
    pub fn loaded_count(&self) -> usize {
        self.loaded_count
    }
}

impl Default for NullAudioBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioBackend for NullAudioBackend {
    fn init(&mut self) -> Result<()> {
        Ok(())
    }

    fn load_track(&mut self, _data: &[u8]) -> Result<AudioTrackId> {
        let id = self.next_id;
        self.next_id += 1;
        self.loaded_count += 1;
        Ok(AudioTrackId(id))
    }

    fn play(&mut self, track: AudioTrackId) -> Result<()> {
        if track.0 >= self.next_id {
            return Err(OasisError::Backend(format!("track {} not loaded", track.0)));
        }
        self.current_track = Some(track.0);
        self.playing = true;
        self.paused = false;
        Ok(())
    }

    fn pause(&mut self) -> Result<()> {
        self.playing = false;
        self.paused = true;
        Ok(())
    }

    fn resume(&mut self) -> Result<()> {
        self.paused = false;
        self.playing = true;
        Ok(())
    }

    fn stop(&mut self) -> Result<()> {
        self.playing = false;
        self.paused = false;
        Ok(())
    }

    fn set_volume(&mut self, volume: u8) -> Result<()> {
        self.volume = volume.min(100);
        Ok(())
    }

    fn get_volume(&self) -> u8 {
        self.volume
    }

    fn is_playing(&self) -> bool {
        self.playing
    }

    fn position_ms(&self) -> u64 {
        0
    }

    fn duration_ms(&self) -> u64 {
        0
    }

    fn unload_track(&mut self, _track: AudioTrackId) -> Result<()> {
        self.loaded_count = self.loaded_count.saturating_sub(1);
        Ok(())
    }

    fn shutdown(&mut self) -> Result<()> {
        self.playing = false;
        self.paused = false;
        self.loaded_count = 0;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn null_backend_lifecycle() {
        let mut backend = NullAudioBackend::new();
        backend.init().unwrap();

        let track = backend.load_track(b"data").unwrap();
        assert_eq!(backend.loaded_count(), 1);

        backend.play(track).unwrap();
        assert!(backend.is_playing());

        backend.pause().unwrap();
        assert!(!backend.is_playing());

        backend.resume().unwrap();
        assert!(backend.is_playing());

        backend.stop().unwrap();
        assert!(!backend.is_playing());

        backend.unload_track(track).unwrap();
        assert_eq!(backend.loaded_count(), 0);

        backend.shutdown().unwrap();
    }

    #[test]
    fn null_backend_volume() {
        let mut backend = NullAudioBackend::new();
        backend.set_volume(50).unwrap();
        assert_eq!(backend.get_volume(), 50);

        backend.set_volume(255).unwrap();
        assert_eq!(backend.get_volume(), 100); // Clamped.
    }

    #[test]
    fn null_backend_play_missing_track() {
        let mut backend = NullAudioBackend::new();
        assert!(backend.play(AudioTrackId(999)).is_err());
    }

    #[test]
    fn null_backend_position_and_duration() {
        let backend = NullAudioBackend::new();
        assert_eq!(backend.position_ms(), 0);
        assert_eq!(backend.duration_ms(), 0);
    }
}

//! High-level audio manager.
//!
//! Wraps an `AudioBackend` with playlist management, volume control,
//! and VFS-based status publishing for the terminal to read.

use crate::backend::AudioBackend;
use crate::error::{OasisError, Result};
use crate::vfs::Vfs;

use super::playlist::{Playlist, format_duration};
use super::types::{PlaybackState, RepeatMode, TrackInfo};

/// VFS path where the audio manager publishes its status.
pub const AUDIO_STATUS_PATH: &str = "/var/audio/status";
/// VFS path where the terminal writes audio requests.
pub const AUDIO_REQUEST_PATH: &str = "/var/audio/request";

/// High-level audio manager that coordinates backend + playlist.
pub struct AudioManager {
    /// Current playback state.
    state: PlaybackState,
    /// The playlist.
    pub playlist: Playlist,
    /// Current volume (0-100).
    volume: u8,
}

impl AudioManager {
    /// Create a new audio manager.
    pub fn new() -> Self {
        Self {
            state: PlaybackState::Stopped,
            playlist: Playlist::new(),
            volume: 80,
        }
    }

    /// Get the current playback state.
    pub fn state(&self) -> PlaybackState {
        self.state
    }

    /// Get the current volume.
    pub fn volume(&self) -> u8 {
        self.volume
    }

    /// Set the volume (clamped to 0-100).
    pub fn set_volume(&mut self, vol: u8, backend: &mut dyn AudioBackend) -> Result<()> {
        self.volume = vol.min(100);
        backend.set_volume(self.volume)
    }

    /// Add a track from a VFS path. Reads the file and creates a TrackInfo.
    pub fn add_track_from_vfs(
        &mut self,
        path: &str,
        vfs: &mut dyn Vfs,
        backend: &mut dyn AudioBackend,
    ) -> Result<()> {
        if !vfs.exists(path) {
            return Err(OasisError::Vfs(format!("file not found: {path}")));
        }
        let data = vfs.read(path)?;
        let _track_id = backend.load_track(&data)?;

        let info = TrackInfo::from_path(path);
        self.playlist.add(info);
        Ok(())
    }

    /// Play the current track (or start from the first track if none selected).
    pub fn play(&mut self, backend: &mut dyn AudioBackend) -> Result<()> {
        if self.playlist.is_empty() {
            return Err(OasisError::Command("playlist is empty".to_string()));
        }
        if self.playlist.current_track().is_none() {
            self.playlist.set_current(0);
        }
        // In a full implementation, we'd load the track data via VFS here.
        // For now, we update state and let the backend handle playback.
        let idx = self.playlist.current_index().unwrap_or(0);
        let track_id = crate::backend::AudioTrackId(idx as u64);
        backend.play(track_id)?;
        self.state = PlaybackState::Playing;
        Ok(())
    }

    /// Pause playback.
    pub fn pause(&mut self, backend: &mut dyn AudioBackend) -> Result<()> {
        if self.state != PlaybackState::Playing {
            return Err(OasisError::Command("not playing".to_string()));
        }
        backend.pause()?;
        self.state = PlaybackState::Paused;
        Ok(())
    }

    /// Resume paused playback.
    pub fn resume(&mut self, backend: &mut dyn AudioBackend) -> Result<()> {
        if self.state != PlaybackState::Paused {
            return Err(OasisError::Command("not paused".to_string()));
        }
        backend.resume()?;
        self.state = PlaybackState::Playing;
        Ok(())
    }

    /// Stop playback.
    pub fn stop(&mut self, backend: &mut dyn AudioBackend) -> Result<()> {
        backend.stop()?;
        self.state = PlaybackState::Stopped;
        Ok(())
    }

    /// Skip to the next track. Returns `false` if at end of playlist.
    pub fn next(&mut self, backend: &mut dyn AudioBackend) -> Result<bool> {
        let was_playing = self.state == PlaybackState::Playing;
        if was_playing {
            backend.stop()?;
        }
        let has_next = self.playlist.advance();
        if has_next && was_playing {
            self.play(backend)?;
        } else if !has_next {
            self.state = PlaybackState::Stopped;
        }
        Ok(has_next)
    }

    /// Go to the previous track. Returns `false` if at start.
    pub fn prev(&mut self, backend: &mut dyn AudioBackend) -> Result<bool> {
        let was_playing = self.state == PlaybackState::Playing;
        if was_playing {
            backend.stop()?;
        }
        let has_prev = self.playlist.go_back();
        if has_prev && was_playing {
            self.play(backend)?;
        } else if !has_prev {
            self.state = PlaybackState::Stopped;
        }
        Ok(has_prev)
    }

    /// Set the repeat mode.
    pub fn set_repeat(&mut self, mode: RepeatMode) {
        self.playlist.repeat = mode;
    }

    /// Toggle shuffle on/off.
    pub fn toggle_shuffle(&mut self) {
        self.playlist.shuffle = !self.playlist.shuffle;
    }

    /// Format the current status as a human-readable string.
    pub fn format_status(&self, backend: &dyn AudioBackend) -> String {
        let mut lines = Vec::new();
        lines.push(format!("State: {}", self.state));
        lines.push(format!("Volume: {}%", self.volume));

        if let Some(track) = self.playlist.current_track() {
            lines.push(format!("Track: {}", track.title));
            if !track.artist.is_empty() {
                lines.push(format!("Artist: {}", track.artist));
            }
            let pos = format_duration(backend.position_ms());
            let dur = format_duration(backend.duration_ms());
            lines.push(format!("Position: {pos} / {dur}"));
        }

        lines.push(format!("Repeat: {}", self.playlist.repeat));
        lines.push(format!(
            "Shuffle: {}",
            if self.playlist.shuffle { "on" } else { "off" }
        ));
        lines.push(format!("Playlist: {} tracks", self.playlist.len()));

        lines.join("\n")
    }

    /// Publish the current status to the VFS for terminal commands to read.
    pub fn publish_status(&self, backend: &dyn AudioBackend, vfs: &mut dyn Vfs) -> Result<()> {
        let status = self.format_status(backend);
        vfs.write(AUDIO_STATUS_PATH, status.as_bytes())?;
        Ok(())
    }

    /// Process a request string from the terminal.
    /// Returns a response string.
    pub fn process_request(
        &mut self,
        request: &str,
        backend: &mut dyn AudioBackend,
    ) -> Result<String> {
        let parts: Vec<&str> = request.trim().splitn(2, ' ').collect();
        let cmd = parts[0];

        match cmd {
            "play" => {
                self.play(backend)?;
                Ok("playing".to_string())
            },
            "pause" => {
                self.pause(backend)?;
                Ok("paused".to_string())
            },
            "resume" => {
                self.resume(backend)?;
                Ok("resumed".to_string())
            },
            "stop" => {
                self.stop(backend)?;
                Ok("stopped".to_string())
            },
            "next" => {
                let ok = self.next(backend)?;
                if ok {
                    let title = self
                        .playlist
                        .current_track()
                        .map(|t| t.title.as_str())
                        .unwrap_or("unknown");
                    Ok(format!("next: {title}"))
                } else {
                    Ok("end of playlist".to_string())
                }
            },
            "prev" => {
                let ok = self.prev(backend)?;
                if ok {
                    let title = self
                        .playlist
                        .current_track()
                        .map(|t| t.title.as_str())
                        .unwrap_or("unknown");
                    Ok(format!("prev: {title}"))
                } else {
                    Ok("start of playlist".to_string())
                }
            },
            "vol" => {
                let vol_str = parts.get(1).unwrap_or(&"");
                let vol: u8 = vol_str
                    .parse()
                    .map_err(|_| OasisError::Command(format!("invalid volume: {vol_str}")))?;
                self.set_volume(vol, backend)?;
                Ok(format!("volume: {}%", self.volume))
            },
            "repeat" => {
                let mode_str = parts.get(1).unwrap_or(&"");
                let mode = RepeatMode::parse(mode_str).ok_or_else(|| {
                    OasisError::Command(format!(
                        "invalid repeat mode: {mode_str} (use off/all/one)"
                    ))
                })?;
                self.set_repeat(mode);
                Ok(format!("repeat: {mode}"))
            },
            "shuffle" => {
                self.toggle_shuffle();
                let state = if self.playlist.shuffle { "on" } else { "off" };
                Ok(format!("shuffle: {state}"))
            },
            _ => Err(OasisError::Command(format!("unknown audio command: {cmd}"))),
        }
    }
}

impl Default for AudioManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::AudioTrackId;
    use crate::error::Result;
    use crate::vfs::MemoryVfs;

    /// Stub audio backend for testing.
    struct StubAudioBackend {
        volume: u8,
        playing: bool,
        paused: bool,
        loaded_count: u64,
    }

    impl StubAudioBackend {
        fn new() -> Self {
            Self {
                volume: 80,
                playing: false,
                paused: false,
                loaded_count: 0,
            }
        }
    }

    impl AudioBackend for StubAudioBackend {
        fn init(&mut self) -> Result<()> {
            Ok(())
        }
        fn load_track(&mut self, _data: &[u8]) -> Result<AudioTrackId> {
            let id = self.loaded_count;
            self.loaded_count += 1;
            Ok(AudioTrackId(id))
        }
        fn play(&mut self, _track: AudioTrackId) -> Result<()> {
            self.playing = true;
            self.paused = false;
            Ok(())
        }
        fn pause(&mut self) -> Result<()> {
            self.paused = true;
            self.playing = false;
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
        fn set_volume(&mut self, vol: u8) -> Result<()> {
            self.volume = vol;
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
            180_000
        }
        fn unload_track(&mut self, _track: AudioTrackId) -> Result<()> {
            Ok(())
        }
        fn shutdown(&mut self) -> Result<()> {
            Ok(())
        }
    }

    fn setup() -> (AudioManager, StubAudioBackend) {
        let mut mgr = AudioManager::new();
        mgr.playlist
            .add(TrackInfo::from_path("/music/a.mp3").with_title("Song A"));
        mgr.playlist
            .add(TrackInfo::from_path("/music/b.mp3").with_title("Song B"));
        mgr.playlist
            .add(TrackInfo::from_path("/music/c.mp3").with_title("Song C"));
        (mgr, StubAudioBackend::new())
    }

    #[test]
    fn play_starts_first_track() {
        let (mut mgr, mut backend) = setup();
        mgr.play(&mut backend).unwrap();
        assert_eq!(mgr.state(), PlaybackState::Playing);
        assert_eq!(mgr.playlist.current_index(), Some(0));
    }

    #[test]
    fn play_empty_playlist_fails() {
        let mut mgr = AudioManager::new();
        let mut backend = StubAudioBackend::new();
        assert!(mgr.play(&mut backend).is_err());
    }

    #[test]
    fn pause_and_resume() {
        let (mut mgr, mut backend) = setup();
        mgr.play(&mut backend).unwrap();

        mgr.pause(&mut backend).unwrap();
        assert_eq!(mgr.state(), PlaybackState::Paused);

        mgr.resume(&mut backend).unwrap();
        assert_eq!(mgr.state(), PlaybackState::Playing);
    }

    #[test]
    fn pause_when_not_playing_fails() {
        let (mut mgr, mut backend) = setup();
        assert!(mgr.pause(&mut backend).is_err());
    }

    #[test]
    fn resume_when_not_paused_fails() {
        let (mut mgr, mut backend) = setup();
        assert!(mgr.resume(&mut backend).is_err());
    }

    #[test]
    fn stop_playback() {
        let (mut mgr, mut backend) = setup();
        mgr.play(&mut backend).unwrap();
        mgr.stop(&mut backend).unwrap();
        assert_eq!(mgr.state(), PlaybackState::Stopped);
    }

    #[test]
    fn next_track() {
        let (mut mgr, mut backend) = setup();
        mgr.play(&mut backend).unwrap();

        let ok = mgr.next(&mut backend).unwrap();
        assert!(ok);
        assert_eq!(mgr.playlist.current_index(), Some(1));
        assert_eq!(mgr.state(), PlaybackState::Playing);
    }

    #[test]
    fn prev_track() {
        let (mut mgr, mut backend) = setup();
        mgr.playlist.set_current(2);
        mgr.play(&mut backend).unwrap();

        let ok = mgr.prev(&mut backend).unwrap();
        assert!(ok);
        assert_eq!(mgr.playlist.current_index(), Some(1));
    }

    #[test]
    fn volume_control() {
        let (mut mgr, mut backend) = setup();
        mgr.set_volume(50, &mut backend).unwrap();
        assert_eq!(mgr.volume(), 50);
        assert_eq!(backend.volume, 50);

        // Clamp to 100.
        mgr.set_volume(200, &mut backend).unwrap();
        assert_eq!(mgr.volume(), 100);
    }

    #[test]
    fn repeat_mode() {
        let (mut mgr, _) = setup();
        mgr.set_repeat(RepeatMode::All);
        assert_eq!(mgr.playlist.repeat, RepeatMode::All);
    }

    #[test]
    fn toggle_shuffle() {
        let (mut mgr, _) = setup();
        assert!(!mgr.playlist.shuffle);
        mgr.toggle_shuffle();
        assert!(mgr.playlist.shuffle);
        mgr.toggle_shuffle();
        assert!(!mgr.playlist.shuffle);
    }

    #[test]
    fn process_request_play() {
        let (mut mgr, mut backend) = setup();
        let resp = mgr.process_request("play", &mut backend).unwrap();
        assert_eq!(resp, "playing");
        assert_eq!(mgr.state(), PlaybackState::Playing);
    }

    #[test]
    fn process_request_vol() {
        let (mut mgr, mut backend) = setup();
        let resp = mgr.process_request("vol 42", &mut backend).unwrap();
        assert!(resp.contains("42%"));
        assert_eq!(mgr.volume(), 42);
    }

    #[test]
    fn process_request_repeat() {
        let (mut mgr, mut backend) = setup();
        let resp = mgr.process_request("repeat all", &mut backend).unwrap();
        assert!(resp.contains("all"));
        assert_eq!(mgr.playlist.repeat, RepeatMode::All);
    }

    #[test]
    fn process_request_shuffle() {
        let (mut mgr, mut backend) = setup();
        let resp = mgr.process_request("shuffle", &mut backend).unwrap();
        assert!(resp.contains("on"));
        assert!(mgr.playlist.shuffle);
    }

    #[test]
    fn process_request_unknown() {
        let (mut mgr, mut backend) = setup();
        assert!(mgr.process_request("invalid", &mut backend).is_err());
    }

    #[test]
    fn format_status_output() {
        let (mut mgr, mut backend) = setup();
        mgr.play(&mut backend).unwrap();
        let status = mgr.format_status(&backend);
        assert!(status.contains("playing"));
        assert!(status.contains("Song A"));
        assert!(status.contains("Volume: 80%"));
        assert!(status.contains("3 tracks"));
    }

    #[test]
    fn publish_status_to_vfs() {
        let (mut mgr, mut backend) = setup();
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/audio").unwrap();

        mgr.play(&mut backend).unwrap();
        mgr.publish_status(&backend, &mut vfs).unwrap();

        let data = vfs.read(AUDIO_STATUS_PATH).unwrap();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains("playing"));
    }

    #[test]
    fn add_track_from_vfs() {
        let mut mgr = AudioManager::new();
        let mut backend = StubAudioBackend::new();
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/music").unwrap();
        vfs.write("/music/test.mp3", b"fake mp3 data").unwrap();

        mgr.add_track_from_vfs("/music/test.mp3", &mut vfs, &mut backend)
            .unwrap();
        assert_eq!(mgr.playlist.len(), 1);
        assert_eq!(mgr.playlist.tracks()[0].title, "test.mp3");
    }

    #[test]
    fn add_track_from_vfs_missing_file() {
        let mut mgr = AudioManager::new();
        let mut backend = StubAudioBackend::new();
        let mut vfs = MemoryVfs::new();

        assert!(
            mgr.add_track_from_vfs("/music/missing.mp3", &mut vfs, &mut backend)
                .is_err()
        );
    }
}

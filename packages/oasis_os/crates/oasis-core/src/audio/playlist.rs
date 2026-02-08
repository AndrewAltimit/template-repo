//! Playlist management.
//!
//! An ordered list of tracks with current-index tracking, repeat mode,
//! and shuffle support. The playlist is backend-agnostic -- it manages
//! only metadata and ordering.

use super::types::{RepeatMode, TrackInfo};

/// An ordered playlist of audio tracks.
#[derive(Debug)]
pub struct Playlist {
    /// Tracks in play order.
    tracks: Vec<TrackInfo>,
    /// Index of the current track (None if empty/not started).
    current: Option<usize>,
    /// Repeat mode.
    pub repeat: RepeatMode,
    /// Whether shuffle is enabled.
    pub shuffle: bool,
    /// Shuffle order indices (populated when shuffle is toggled on).
    shuffle_order: Vec<usize>,
    /// Current position in the shuffle order.
    shuffle_pos: usize,
}

impl Playlist {
    /// Create an empty playlist.
    pub fn new() -> Self {
        Self {
            tracks: Vec::new(),
            current: None,
            repeat: RepeatMode::Off,
            shuffle: false,
            shuffle_order: Vec::new(),
            shuffle_pos: 0,
        }
    }

    /// Add a track to the end of the playlist.
    pub fn add(&mut self, info: TrackInfo) {
        self.tracks.push(info);
        if self.shuffle {
            self.rebuild_shuffle();
        }
    }

    /// Remove a track by index. Adjusts current index if needed.
    pub fn remove(&mut self, index: usize) -> Option<TrackInfo> {
        if index >= self.tracks.len() {
            return None;
        }
        let removed = self.tracks.remove(index);

        // Adjust current index.
        if let Some(cur) = self.current {
            if index < cur {
                self.current = Some(cur - 1);
            } else if index == cur {
                // Current track was removed.
                if self.tracks.is_empty() {
                    self.current = None;
                } else if cur >= self.tracks.len() {
                    self.current = Some(self.tracks.len() - 1);
                }
            }
        }

        if self.shuffle {
            self.rebuild_shuffle();
        }
        Some(removed)
    }

    /// Clear all tracks.
    pub fn clear(&mut self) {
        self.tracks.clear();
        self.current = None;
        self.shuffle_order.clear();
        self.shuffle_pos = 0;
    }

    /// Get the number of tracks.
    pub fn len(&self) -> usize {
        self.tracks.len()
    }

    /// Check if the playlist is empty.
    pub fn is_empty(&self) -> bool {
        self.tracks.is_empty()
    }

    /// Get the current track info.
    pub fn current_track(&self) -> Option<&TrackInfo> {
        self.current.and_then(|i| self.tracks.get(i))
    }

    /// Get the current track index.
    pub fn current_index(&self) -> Option<usize> {
        self.current
    }

    /// Set the current track by index.
    pub fn set_current(&mut self, index: usize) -> bool {
        if index < self.tracks.len() {
            self.current = Some(index);
            true
        } else {
            false
        }
    }

    /// Advance to the next track in the playlist.
    /// Returns `true` if there is a next track. Respects repeat mode and shuffle.
    pub fn advance(&mut self) -> bool {
        if self.tracks.is_empty() {
            return false;
        }

        if self.repeat == RepeatMode::One {
            // Stay on the same track.
            return self.current.is_some();
        }

        if self.shuffle {
            return self.next_shuffle();
        }

        match self.current {
            None => {
                self.current = Some(0);
                true
            },
            Some(i) => {
                if i + 1 < self.tracks.len() {
                    self.current = Some(i + 1);
                    true
                } else if self.repeat == RepeatMode::All {
                    self.current = Some(0);
                    true
                } else {
                    false
                }
            },
        }
    }

    /// Go back to the previous track in the playlist.
    /// Returns `true` if there is a previous track.
    pub fn go_back(&mut self) -> bool {
        if self.tracks.is_empty() {
            return false;
        }

        if self.repeat == RepeatMode::One {
            return self.current.is_some();
        }

        if self.shuffle {
            return self.prev_shuffle();
        }

        match self.current {
            None => {
                self.current = Some(0);
                true
            },
            Some(i) => {
                if i > 0 {
                    self.current = Some(i - 1);
                    true
                } else if self.repeat == RepeatMode::All {
                    self.current = Some(self.tracks.len() - 1);
                    true
                } else {
                    false
                }
            },
        }
    }

    /// Get an immutable reference to all tracks.
    pub fn tracks(&self) -> &[TrackInfo] {
        &self.tracks
    }

    /// Build a deterministic "shuffle" order.
    /// Uses a simple Fisher-Yates-like reorder seeded by track count.
    /// For a real implementation this would use a proper RNG.
    fn rebuild_shuffle(&mut self) {
        let n = self.tracks.len();
        self.shuffle_order = (0..n).collect();
        // Simple deterministic shuffle: reverse halves and interleave.
        // Not cryptographically random, but sufficient for playlist shuffling.
        if n > 1 {
            let mid = n / 2;
            let mut new_order = Vec::with_capacity(n);
            let (first, second) = self.shuffle_order.split_at(mid);
            let mut a = first.iter();
            let mut b = second.iter().rev();
            loop {
                match (a.next(), b.next()) {
                    (Some(&x), Some(&y)) => {
                        new_order.push(y);
                        new_order.push(x);
                    },
                    (Some(&x), None) => new_order.push(x),
                    (None, Some(&y)) => new_order.push(y),
                    (None, None) => break,
                }
            }
            self.shuffle_order = new_order;
        }
        self.shuffle_pos = 0;
    }

    fn next_shuffle(&mut self) -> bool {
        if self.shuffle_order.is_empty() {
            self.rebuild_shuffle();
        }
        if self.shuffle_order.is_empty() {
            return false;
        }

        self.shuffle_pos += 1;
        if self.shuffle_pos >= self.shuffle_order.len() {
            if self.repeat == RepeatMode::All {
                self.shuffle_pos = 0;
            } else {
                self.shuffle_pos = self.shuffle_order.len() - 1;
                return false;
            }
        }
        self.current = Some(self.shuffle_order[self.shuffle_pos]);
        true
    }

    fn prev_shuffle(&mut self) -> bool {
        if self.shuffle_order.is_empty() {
            return false;
        }
        if self.shuffle_pos > 0 {
            self.shuffle_pos -= 1;
            self.current = Some(self.shuffle_order[self.shuffle_pos]);
            true
        } else if self.repeat == RepeatMode::All {
            self.shuffle_pos = self.shuffle_order.len() - 1;
            self.current = Some(self.shuffle_order[self.shuffle_pos]);
            true
        } else {
            false
        }
    }
}

impl Default for Playlist {
    fn default() -> Self {
        Self::new()
    }
}

/// Format the playlist as a displayable string for terminal output.
pub fn format_playlist(playlist: &Playlist) -> String {
    if playlist.is_empty() {
        return "(empty playlist)".to_string();
    }

    let mut lines = Vec::new();
    lines.push(format!(
        "Playlist ({} tracks, repeat: {}, shuffle: {})",
        playlist.len(),
        playlist.repeat,
        if playlist.shuffle { "on" } else { "off" }
    ));

    for (i, track) in playlist.tracks().iter().enumerate() {
        let marker = if Some(i) == playlist.current_index() {
            ">"
        } else {
            " "
        };
        let artist_part = if track.artist.is_empty() {
            String::new()
        } else {
            format!(" - {}", track.artist)
        };
        let dur = format_duration(track.duration_ms);
        lines.push(format!(
            " {marker} {i}. {}{artist_part} [{dur}]",
            track.title
        ));
    }
    lines.join("\n")
}

/// Format milliseconds as M:SS or H:MM:SS.
pub fn format_duration(ms: u64) -> String {
    let total_secs = ms / 1000;
    let hours = total_secs / 3600;
    let minutes = (total_secs % 3600) / 60;
    let seconds = total_secs % 60;
    if hours > 0 {
        format!("{hours}:{minutes:02}:{seconds:02}")
    } else {
        format!("{minutes}:{seconds:02}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audio::types::TrackInfo;

    fn make_tracks(n: usize) -> Vec<TrackInfo> {
        (0..n)
            .map(|i| {
                TrackInfo::from_path(&format!("/music/track{i}.mp3"))
                    .with_title(&format!("Track {i}"))
                    .with_duration_ms((i as u64 + 1) * 60_000)
            })
            .collect()
    }

    #[test]
    fn empty_playlist() {
        let pl = Playlist::new();
        assert!(pl.is_empty());
        assert_eq!(pl.len(), 0);
        assert!(pl.current_track().is_none());
    }

    #[test]
    fn add_and_get_tracks() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        assert_eq!(pl.len(), 3);
        assert!(pl.current_track().is_none()); // Not started yet.
    }

    #[test]
    fn sequential_next() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }

        assert!(pl.advance()); // -> Track 0
        assert_eq!(pl.current_index(), Some(0));
        assert!(pl.advance()); // -> Track 1
        assert_eq!(pl.current_index(), Some(1));
        assert!(pl.advance()); // -> Track 2
        assert_eq!(pl.current_index(), Some(2));
        assert!(!pl.advance()); // End of playlist (repeat off).
    }

    #[test]
    fn sequential_prev() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        pl.set_current(2);

        assert!(pl.go_back()); // -> Track 1
        assert_eq!(pl.current_index(), Some(1));
        assert!(pl.go_back()); // -> Track 0
        assert_eq!(pl.current_index(), Some(0));
        assert!(!pl.go_back()); // Beginning of playlist.
    }

    #[test]
    fn repeat_all() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        pl.repeat = RepeatMode::All;
        pl.set_current(2);

        assert!(pl.advance()); // Wraps to Track 0.
        assert_eq!(pl.current_index(), Some(0));
    }

    #[test]
    fn repeat_all_prev_wraps() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        pl.repeat = RepeatMode::All;
        pl.set_current(0);

        assert!(pl.go_back()); // Wraps to Track 2.
        assert_eq!(pl.current_index(), Some(2));
    }

    #[test]
    fn repeat_one() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        pl.repeat = RepeatMode::One;
        pl.set_current(1);

        assert!(pl.advance()); // Stays on Track 1.
        assert_eq!(pl.current_index(), Some(1));
        assert!(pl.go_back()); // Still Track 1.
        assert_eq!(pl.current_index(), Some(1));
    }

    #[test]
    fn set_current() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        assert!(pl.set_current(1));
        assert_eq!(pl.current_track().unwrap().title, "Track 1");
        assert!(!pl.set_current(10)); // Out of bounds.
    }

    #[test]
    fn remove_track() {
        let mut pl = Playlist::new();
        for t in make_tracks(4) {
            pl.add(t);
        }
        pl.set_current(2);

        // Remove track before current.
        let removed = pl.remove(0).unwrap();
        assert_eq!(removed.title, "Track 0");
        assert_eq!(pl.current_index(), Some(1)); // Adjusted down.
        assert_eq!(pl.len(), 3);
    }

    #[test]
    fn remove_current_track() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        pl.set_current(1);

        pl.remove(1);
        // Current stays at 1 (now "Track 2").
        assert_eq!(pl.current_index(), Some(1));
        assert_eq!(pl.current_track().unwrap().title, "Track 2");
    }

    #[test]
    fn clear_playlist() {
        let mut pl = Playlist::new();
        for t in make_tracks(3) {
            pl.add(t);
        }
        pl.set_current(1);
        pl.clear();
        assert!(pl.is_empty());
        assert!(pl.current_track().is_none());
    }

    #[test]
    fn shuffle_next() {
        let mut pl = Playlist::new();
        for t in make_tracks(4) {
            pl.add(t);
        }
        pl.shuffle = true;
        pl.set_current(0);

        // Should advance through shuffle order.
        assert!(pl.advance());
        let first = pl.current_index().unwrap();
        assert!(pl.advance());
        let second = pl.current_index().unwrap();
        // In shuffle mode, the order differs from sequential.
        // We can't assert exact values but can check they're valid indices.
        assert!(first < 4);
        assert!(second < 4);
    }

    #[test]
    fn format_duration_minutes() {
        assert_eq!(format_duration(0), "0:00");
        assert_eq!(format_duration(1_000), "0:01");
        assert_eq!(format_duration(61_000), "1:01");
        assert_eq!(format_duration(3_600_000), "1:00:00");
        assert_eq!(format_duration(3_661_000), "1:01:01");
    }

    #[test]
    fn format_playlist_display() {
        let mut pl = Playlist::new();
        for t in make_tracks(2) {
            pl.add(t);
        }
        pl.set_current(0);

        let text = format_playlist(&pl);
        assert!(text.contains("2 tracks"));
        assert!(text.contains("> 0. Track 0"));
        assert!(text.contains("  1. Track 1"));
    }

    #[test]
    fn format_empty_playlist() {
        let pl = Playlist::new();
        assert_eq!(format_playlist(&pl), "(empty playlist)");
    }

    #[test]
    fn next_on_empty_playlist() {
        let mut pl = Playlist::new();
        assert!(!pl.advance());
        assert!(!pl.go_back());
    }
}

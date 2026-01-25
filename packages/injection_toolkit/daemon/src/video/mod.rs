//! Video playback subsystem for the daemon.
//!
//! This module handles video decoding, frame output to shared memory,
//! and playback state management.

mod player;
mod state;

pub use player::VideoPlayer;

// Re-export state types for external use
#[allow(unused_imports)]
pub use state::{PlayerCommand, PlayerState, VideoInfo};

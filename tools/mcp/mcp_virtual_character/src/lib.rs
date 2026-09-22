//! Virtual Character MCP server library.
//!
//! Controls virtual characters (VRChat avatars over OSC, or an in-memory mock)
//! through the Model Context Protocol: emotions, gestures, movement, audio
//! playback with expression tags, and timed event sequences.
//!
//! Module map:
//! - [`server`]: MCP tool definitions and shared state
//! - [`backends`]: backend trait, VRChat OSC backend, mock backend
//! - [`sequence_handler`]: sequence building and background playback
//! - [`spec`]: typed/validated tool argument structs
//! - [`audio`]: audio loading, validation, duration estimation, local playback
//! - [`audio_emotion_mappings`]: ElevenLabs audio tag -> emotion mapping
//! - [`constants`], [`types`]: VRCEmote mappings, defaults, canonical models

pub mod audio;
pub mod audio_emotion_mappings;
pub mod backends;
pub mod constants;
pub mod sequence_handler;
pub mod server;
pub mod spec;
pub mod types;

pub use backends::{
    AudioOutcome, BackendAdapter, BackendError, BackendResult, MockBackend, VRChatConfig,
    VRChatRemoteBackend,
};
pub use server::VirtualCharacterServer;
pub use types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EmotionType, EmotionVector,
    EnvironmentState, EventSequence, EventType, GestureType, SequenceEvent,
};

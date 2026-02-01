//! Virtual Character MCP Server library.
//!
#![allow(dead_code)]

//! This library provides functionality for controlling virtual characters
//! via VRChat OSC or other backends through the Model Context Protocol.

pub mod backends;
pub mod constants;
pub mod server;
pub mod types;

pub use backends::{BackendAdapter, BackendError, BackendResult, MockBackend, VRChatRemoteBackend};
pub use constants::{
    emotion_to_vrcemote, gesture_to_vrcemote, get_emotion_from_tag, get_vrcemote_name,
    get_vrcemote_value, VRCEmoteValue, DEFAULT_MCP_SERVER_PORT, DEFAULT_OSC_IN_PORT,
    DEFAULT_OSC_OUT_PORT, DEFAULT_VRCHAT_HOST, VRCEMOTE_DESCRIPTION,
};
pub use server::VirtualCharacterServer;
pub use types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EmotionType, EmotionVector,
    EnvironmentState, EventSequence, EventType, GestureType, SequenceEvent, VideoFrame, VisemeType,
};

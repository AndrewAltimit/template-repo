//! Virtual Character MCP Server library.
//!
#![allow(dead_code)]

//! This library provides functionality for controlling virtual characters
//! via VRChat OSC or other backends through the Model Context Protocol.

pub mod audio;
pub mod audio_emotion_mappings;
pub mod backends;
pub mod constants;
pub mod sequence_handler;
pub mod server;
pub mod storage;
pub mod storage_server;
pub mod types;

pub use audio::{
    AudioDownloader, AudioFormat, AudioHandler, AudioPathValidator, AudioPlayer, AudioValidator,
    ALLOWED_AUDIO_PATHS, DEFAULT_CLEANUP_DELAY, MIN_AUDIO_SIZE,
};
pub use audio_emotion_mappings::{
    extract_emotions_from_text, get_audio_tags_for_emotion, get_dominant_emotion,
    get_emotion_from_tag as get_emotion_from_audio_tag, AudioTagMapping, AUDIO_TAG_TO_EMOTION,
    EMOTION_TO_AUDIO_TAGS,
};
pub use backends::{BackendAdapter, BackendError, BackendResult, MockBackend, VRChatRemoteBackend};
pub use constants::{
    emotion_to_vrcemote, gesture_to_vrcemote, get_emotion_from_tag, get_vrcemote_name,
    get_vrcemote_value, VRCEmoteValue, DEFAULT_MCP_SERVER_PORT, DEFAULT_OSC_IN_PORT,
    DEFAULT_OSC_OUT_PORT, DEFAULT_VRCHAT_HOST, VRCEMOTE_DESCRIPTION,
};
pub use sequence_handler::{
    create_event_from_params, SequenceError, SequenceHandler, SequenceResponse, SequenceResult,
    SequenceStatus,
};
pub use server::VirtualCharacterServer;
pub use storage::{StorageError, StorageResult, StorageService, UploadResponse};
pub use types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EmotionType, EmotionVector,
    EnvironmentState, EventSequence, EventType, GestureType, SequenceEvent, VideoFrame, VisemeType,
};

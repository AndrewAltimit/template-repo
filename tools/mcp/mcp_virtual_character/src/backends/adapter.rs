//! Backend adapter interface for virtual character control.
//!
//! Every backend (VRChat over OSC, the in-memory mock, future platforms)
//! implements [`BackendAdapter`]. The MCP tools only ever talk to this trait,
//! so backend-specific behavior (toggle semantics, OSC addresses, audio
//! routing) stays inside the backend implementation.

use async_trait::async_trait;
use serde::Serialize;
use serde_json::Value;
use std::collections::HashMap;
use thiserror::Error;

use crate::types::{AudioData, BackendCapabilities, CanonicalAnimationData, EnvironmentState};

/// Backend error types.
#[derive(Error, Debug)]
pub enum BackendError {
    #[error("Not connected to backend")]
    NotConnected,

    #[error("Connection failed: {0}")]
    ConnectionFailed(String),

    #[error("OSC error: {0}")]
    OscError(String),

    #[error("Network error: {0}")]
    NetworkError(String),

    #[error("Invalid parameter: {0}")]
    InvalidParameter(String),

    #[error("Unsupported operation: {0}")]
    UnsupportedOperation(String),

    #[error("Timeout: {0}")]
    Timeout(String),

    #[error("Audio error: {0}")]
    Audio(String),
}

/// Result alias for backend operations.
pub type BackendResult<T> = Result<T, BackendError>;

/// What a backend actually did with a `send_audio_data` call.
///
/// Returned to the caller so `play_audio` reports honestly whether audio was
/// audible, instead of claiming success when only metadata was sent.
#[derive(Debug, Clone, Default, Serialize, PartialEq)]
pub struct AudioOutcome {
    /// True if the audio is being played on an output device.
    pub played: bool,
    /// Player used for playback (e.g. `"vlc"`, `"ffplay"`), if any.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub method: Option<String>,
    /// Emotion applied from expression tags, if any.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub emotion: Option<String>,
    /// Human-readable notes (e.g. why audio was not played).
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub notes: Vec<String>,
}

/// Result of a VRCEmote state change.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EmoteAction {
    /// The emote was started.
    Activated,
    /// The same emote was already active and has been toggled off.
    ToggledOff,
    /// An active emote was cleared (value 0 requested).
    Cleared,
    /// Nothing to do (clear requested with no active emote).
    Unchanged,
}

/// Base interface for all backend plugins.
#[async_trait]
pub trait BackendAdapter: Send + Sync {
    /// Get the name of this backend (matches the `set_backend` identifier).
    fn backend_name(&self) -> &'static str;

    /// Check if backend is currently connected.
    fn is_connected(&self) -> bool;

    /// Get backend capabilities.
    fn capabilities(&self) -> &BackendCapabilities;

    /// Establish connection to the backend system.
    ///
    /// Calling `connect` on an already connected backend must first release
    /// the previous connection (sockets, background tasks).
    async fn connect(&mut self, config: HashMap<String, Value>) -> BackendResult<()>;

    /// Clean up and close connections. Must be idempotent.
    async fn disconnect(&mut self) -> BackendResult<()>;

    /// Send animation data in canonical format to backend.
    async fn send_animation_data(&mut self, data: CanonicalAnimationData) -> BackendResult<()>;

    /// Send audio data with sync metadata.
    async fn send_audio_data(&mut self, audio: AudioData) -> BackendResult<AudioOutcome>;

    /// Receive current state from virtual environment.
    async fn receive_state(&self) -> BackendResult<Option<EnvironmentState>>;

    /// Reset all states - clear emotes, stop movement, reset to neutral.
    async fn reset_all(&mut self) -> BackendResult<()>;

    /// Execute a high-level behavior (see
    /// [`SUPPORTED_BEHAVIORS`](crate::constants::SUPPORTED_BEHAVIORS)).
    async fn execute_behavior(
        &mut self,
        behavior: &str,
        parameters: HashMap<String, Value>,
    ) -> BackendResult<()>;

    /// Send a raw VRCEmote value (0-8). Only meaningful for VRChat-like
    /// backends; the default rejects the operation.
    async fn send_vrcemote(&mut self, _value: i32) -> BackendResult<EmoteAction> {
        Err(BackendError::UnsupportedOperation(format!(
            "VRCEmote is not supported by the {} backend (use vrchat_remote)",
            self.backend_name()
        )))
    }

    /// Avatar parameters most recently reported by the platform (for VRChat:
    /// values received over OSC from `/avatar/parameters/*`).
    async fn avatar_parameters(&self) -> BackendResult<HashMap<String, Value>> {
        Ok(HashMap::new())
    }

    /// Perform health check on backend connection.
    async fn health_check(&self) -> BackendResult<HashMap<String, Value>> {
        let mut result = HashMap::new();
        result.insert(
            "backend".to_string(),
            Value::String(self.backend_name().to_string()),
        );
        result.insert("connected".to_string(), Value::Bool(self.is_connected()));
        result.insert(
            "capabilities".to_string(),
            serde_json::to_value(self.capabilities()).unwrap_or(Value::Null),
        );
        Ok(result)
    }

    /// Get backend statistics and metrics.
    async fn get_statistics(&self) -> BackendResult<HashMap<String, Value>> {
        let mut stats = HashMap::new();
        stats.insert(
            "backend".to_string(),
            Value::String(self.backend_name().to_string()),
        );
        stats.insert("connected".to_string(), Value::Bool(self.is_connected()));
        Ok(stats)
    }
}

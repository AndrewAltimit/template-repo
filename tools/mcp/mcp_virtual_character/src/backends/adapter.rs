//! Base backend adapter interface for virtual character control.
//!
//! All backend plugins must implement this interface to ensure
//! compatibility with the middleware.

use async_trait::async_trait;
use serde_json::Value;
use std::collections::HashMap;
use thiserror::Error;

use crate::types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EnvironmentState, VideoFrame,
};

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

    #[error("Internal error: {0}")]
    Internal(String),
}

pub type BackendResult<T> = Result<T, BackendError>;

/// Base interface for all backend plugins.
///
/// This trait defines the contract that all backend implementations
/// must follow to integrate with the middleware.
#[async_trait]
pub trait BackendAdapter: Send + Sync {
    /// Get the name of this backend.
    fn backend_name(&self) -> &'static str;

    /// Check if backend is currently connected.
    fn is_connected(&self) -> bool;

    /// Get backend capabilities.
    fn capabilities(&self) -> &BackendCapabilities;

    /// Establish connection to the backend system.
    async fn connect(&mut self, config: HashMap<String, Value>) -> BackendResult<()>;

    /// Clean up and close connections.
    async fn disconnect(&mut self) -> BackendResult<()>;

    /// Send animation data in canonical format to backend.
    async fn send_animation_data(&mut self, data: CanonicalAnimationData) -> BackendResult<()>;

    /// Send audio data with sync metadata.
    async fn send_audio_data(&mut self, audio: AudioData) -> BackendResult<()>;

    /// Receive current state from virtual environment.
    async fn receive_state(&self) -> BackendResult<Option<EnvironmentState>>;

    /// Capture current view from agent's perspective.
    async fn capture_video_frame(&self) -> BackendResult<Option<VideoFrame>>;

    /// Reset all states - clear emotes, stop movement, reset to neutral.
    async fn reset_all(&mut self) -> BackendResult<()>;

    /// Execute a high-level behavior.
    async fn execute_behavior(
        &mut self,
        _behavior: &str,
        _parameters: HashMap<String, Value>,
    ) -> BackendResult<()> {
        // Default implementation does nothing
        Ok(())
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

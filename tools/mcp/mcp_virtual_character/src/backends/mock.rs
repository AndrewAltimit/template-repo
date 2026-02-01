//! Mock backend for testing virtual character control.
//!
//! This backend simulates virtual character operations without
//! requiring an actual VRChat or other platform connection.

use async_trait::async_trait;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info};

use crate::types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EmotionType, EnvironmentState,
    GestureType, VideoFrame,
};

use super::adapter::{BackendAdapter, BackendError, BackendResult};

/// Mock backend for testing.
pub struct MockBackend {
    connected: AtomicBool,
    capabilities: BackendCapabilities,
    config: Arc<RwLock<HashMap<String, Value>>>,

    // State tracking
    current_emotion: Arc<RwLock<EmotionType>>,
    current_gesture: Arc<RwLock<GestureType>>,
    animation_history: Arc<RwLock<Vec<CanonicalAnimationData>>>,
    audio_history: Arc<RwLock<Vec<AudioData>>>,

    // Statistics
    frames_sent: AtomicU64,
    audio_sent: AtomicU64,
    errors: AtomicU64,
}

impl Default for MockBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl MockBackend {
    /// Create a new mock backend.
    pub fn new() -> Self {
        let capabilities = BackendCapabilities {
            audio: true,
            animation: true,
            video_capture: true,
            bidirectional: true,
            ..Default::default()
        };

        Self {
            connected: AtomicBool::new(false),
            capabilities,
            config: Arc::new(RwLock::new(HashMap::new())),
            current_emotion: Arc::new(RwLock::new(EmotionType::Neutral)),
            current_gesture: Arc::new(RwLock::new(GestureType::None)),
            animation_history: Arc::new(RwLock::new(Vec::new())),
            audio_history: Arc::new(RwLock::new(Vec::new())),
            frames_sent: AtomicU64::new(0),
            audio_sent: AtomicU64::new(0),
            errors: AtomicU64::new(0),
        }
    }

    /// Get animation history for testing.
    pub async fn get_animation_history(&self) -> Vec<CanonicalAnimationData> {
        self.animation_history.read().await.clone()
    }

    /// Get audio history for testing.
    pub async fn get_audio_history(&self) -> Vec<AudioData> {
        self.audio_history.read().await.clone()
    }

    /// Clear history.
    pub async fn clear_history(&self) {
        self.animation_history.write().await.clear();
        self.audio_history.write().await.clear();
    }
}

#[async_trait]
impl BackendAdapter for MockBackend {
    fn backend_name(&self) -> &'static str {
        "mock"
    }

    fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }

    fn capabilities(&self) -> &BackendCapabilities {
        &self.capabilities
    }

    async fn connect(&mut self, config: HashMap<String, Value>) -> BackendResult<()> {
        info!("Mock backend connecting with config: {:?}", config);

        *self.config.write().await = config;
        self.connected.store(true, Ordering::SeqCst);

        info!("Mock backend connected");
        Ok(())
    }

    async fn disconnect(&mut self) -> BackendResult<()> {
        info!("Mock backend disconnecting");

        self.connected.store(false, Ordering::SeqCst);
        self.config.write().await.clear();

        Ok(())
    }

    async fn send_animation_data(&mut self, data: CanonicalAnimationData) -> BackendResult<()> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        debug!(
            "Mock backend received animation data: emotion={:?}, gesture={:?}",
            data.emotion, data.gesture
        );

        // Update state
        if let Some(emotion) = data.emotion {
            *self.current_emotion.write().await = emotion;
        }
        if let Some(gesture) = data.gesture {
            *self.current_gesture.write().await = gesture;
        }

        // Track history
        self.animation_history.write().await.push(data);
        self.frames_sent.fetch_add(1, Ordering::SeqCst);

        Ok(())
    }

    async fn send_audio_data(&mut self, audio: AudioData) -> BackendResult<()> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        debug!(
            "Mock backend received audio data: {} bytes, format={}",
            audio.data.len(),
            audio.format
        );

        self.audio_history.write().await.push(audio);
        self.audio_sent.fetch_add(1, Ordering::SeqCst);

        Ok(())
    }

    async fn receive_state(&self) -> BackendResult<Option<EnvironmentState>> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        // Return mock environment state
        let state = EnvironmentState {
            world_name: Some("MockWorld".to_string()),
            instance_id: Some("mock-instance-001".to_string()),
            ..Default::default()
        };

        Ok(Some(state))
    }

    async fn capture_video_frame(&self) -> BackendResult<Option<VideoFrame>> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        // Generate a simple mock frame (1x1 gray pixel JPEG)
        let mock_jpeg = vec![
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00,
            0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43, 0x00, 0x08, 0x06, 0x06,
            0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D,
            0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12, 0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
            0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28,
            0x37, 0x29, 0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01,
            0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02,
            0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10,
            0x00, 0x02, 0x01, 0x03, 0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00,
            0x01, 0x7D, 0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08, 0x23, 0x42,
            0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16,
            0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35, 0x36, 0x37,
            0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55,
            0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73,
            0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5,
            0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA,
            0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6,
            0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA,
            0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08,
            0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xBA, 0xA3, 0xFF, 0xD9,
        ];

        let frame = VideoFrame {
            data: mock_jpeg,
            width: 1,
            height: 1,
            format: "jpeg".to_string(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs_f64(),
            frame_number: 0,
        };

        Ok(Some(frame))
    }

    async fn reset_all(&mut self) -> BackendResult<()> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        info!("Mock backend resetting all states");

        *self.current_emotion.write().await = EmotionType::Neutral;
        *self.current_gesture.write().await = GestureType::None;

        Ok(())
    }

    async fn execute_behavior(
        &mut self,
        behavior: &str,
        parameters: HashMap<String, Value>,
    ) -> BackendResult<()> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        info!(
            "Mock backend executing behavior: {} with params: {:?}",
            behavior, parameters
        );

        Ok(())
    }

    async fn get_statistics(&self) -> BackendResult<HashMap<String, Value>> {
        let mut stats = HashMap::new();
        stats.insert(
            "backend".to_string(),
            Value::String(self.backend_name().to_string()),
        );
        stats.insert("connected".to_string(), Value::Bool(self.is_connected()));
        stats.insert(
            "frames_sent".to_string(),
            Value::Number(self.frames_sent.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "audio_sent".to_string(),
            Value::Number(self.audio_sent.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "errors".to_string(),
            Value::Number(self.errors.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "current_emotion".to_string(),
            serde_json::to_value(*self.current_emotion.read().await).unwrap_or(Value::Null),
        );
        stats.insert(
            "current_gesture".to_string(),
            serde_json::to_value(*self.current_gesture.read().await).unwrap_or(Value::Null),
        );

        Ok(stats)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_mock_backend_connect_disconnect() {
        let mut backend = MockBackend::new();

        assert!(!backend.is_connected());

        backend.connect(HashMap::new()).await.unwrap();
        assert!(backend.is_connected());

        backend.disconnect().await.unwrap();
        assert!(!backend.is_connected());
    }

    #[tokio::test]
    async fn test_mock_backend_animation() {
        let mut backend = MockBackend::new();
        backend.connect(HashMap::new()).await.unwrap();

        let animation = CanonicalAnimationData::new(0.0).with_emotion(EmotionType::Happy, 1.0);

        backend.send_animation_data(animation).await.unwrap();

        let history = backend.get_animation_history().await;
        assert_eq!(history.len(), 1);
        assert_eq!(history[0].emotion, Some(EmotionType::Happy));
    }
}

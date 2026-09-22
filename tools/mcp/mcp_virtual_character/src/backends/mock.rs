//! In-memory mock backend.
//!
//! Simulates a character without any external platform: it validates input
//! the same way the VRChat backend does, tracks the current emotion/gesture,
//! and records a bounded history of animation frames and audio clips so the
//! full tool flow (including sequences) can be exercised offline.

use async_trait::async_trait;
use serde_json::{json, Value};
use std::collections::{HashMap, VecDeque};

use super::adapter::{AudioOutcome, BackendAdapter, BackendError, BackendResult};
use super::movement::{parse_avatar_params, parse_movement};
use crate::audio_emotion_mappings::{extract_tags_from_text, get_dominant_emotion_from_tags};
use crate::constants::SUPPORTED_BEHAVIORS;
use crate::types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EmotionType, EnvironmentState,
    GestureType,
};

/// Maximum number of history entries kept per kind.
pub const MOCK_HISTORY_LIMIT: usize = 1000;

/// Mock backend for testing and development.
pub struct MockBackend {
    connected: bool,
    capabilities: BackendCapabilities,
    config: HashMap<String, Value>,

    current_emotion: EmotionType,
    current_gesture: GestureType,
    animation_history: VecDeque<CanonicalAnimationData>,
    audio_history: VecDeque<AudioData>,
    behavior_history: VecDeque<String>,

    frames_sent: u64,
    audio_sent: u64,
    resets: u64,
}

impl Default for MockBackend {
    fn default() -> Self {
        Self::new()
    }
}

fn push_bounded<T>(q: &mut VecDeque<T>, item: T) {
    if q.len() >= MOCK_HISTORY_LIMIT {
        q.pop_front();
    }
    q.push_back(item);
}

impl MockBackend {
    /// Create a new (disconnected) mock backend.
    pub fn new() -> Self {
        Self {
            connected: false,
            capabilities: BackendCapabilities {
                audio: true,
                animation: true,
                bidirectional: true,
                ..Default::default()
            },
            config: HashMap::new(),
            current_emotion: EmotionType::Neutral,
            current_gesture: GestureType::None,
            animation_history: VecDeque::new(),
            audio_history: VecDeque::new(),
            behavior_history: VecDeque::new(),
            frames_sent: 0,
            audio_sent: 0,
            resets: 0,
        }
    }

    /// Recorded animation frames (oldest first).
    pub fn animation_history(&self) -> Vec<CanonicalAnimationData> {
        self.animation_history.iter().cloned().collect()
    }

    /// Recorded audio clips (oldest first).
    pub fn audio_history(&self) -> Vec<AudioData> {
        self.audio_history.iter().cloned().collect()
    }

    /// Clear recorded history.
    pub fn clear_history(&mut self) {
        self.animation_history.clear();
        self.audio_history.clear();
        self.behavior_history.clear();
    }

    fn ensure_connected(&self) -> BackendResult<()> {
        if self.connected {
            Ok(())
        } else {
            Err(BackendError::NotConnected)
        }
    }
}

#[async_trait]
impl BackendAdapter for MockBackend {
    fn backend_name(&self) -> &'static str {
        "mock"
    }

    fn is_connected(&self) -> bool {
        self.connected
    }

    fn capabilities(&self) -> &BackendCapabilities {
        &self.capabilities
    }

    async fn connect(&mut self, config: HashMap<String, Value>) -> BackendResult<()> {
        self.config = config;
        self.connected = true;
        Ok(())
    }

    async fn disconnect(&mut self) -> BackendResult<()> {
        self.connected = false;
        self.config.clear();
        Ok(())
    }

    async fn send_animation_data(&mut self, data: CanonicalAnimationData) -> BackendResult<()> {
        self.ensure_connected()?;
        // Same validation as real backends.
        parse_movement(&data.parameters)?;
        parse_avatar_params(&data.parameters)?;

        if let Some(emotion) = data.emotion {
            self.current_emotion = emotion;
        }
        if let Some(gesture) = data.gesture {
            self.current_gesture = gesture;
        }
        push_bounded(&mut self.animation_history, data);
        self.frames_sent += 1;
        Ok(())
    }

    async fn send_audio_data(&mut self, audio: AudioData) -> BackendResult<AudioOutcome> {
        self.ensure_connected()?;
        let tags: Vec<String> = match (&audio.expression_tags, &audio.text) {
            (Some(t), _) if !t.is_empty() => t.clone(),
            (_, Some(text)) => extract_tags_from_text(text),
            _ => Vec::new(),
        };
        let emotion = get_dominant_emotion_from_tags(&tags).map(|(e, _)| e);
        if let Some(e) = emotion {
            self.current_emotion = e;
        }
        push_bounded(&mut self.audio_history, audio);
        self.audio_sent += 1;
        Ok(AudioOutcome {
            played: false,
            method: None,
            emotion: emotion.map(|e| e.as_str().to_string()),
            notes: vec!["mock backend records audio without playing it".to_string()],
        })
    }

    async fn receive_state(&self) -> BackendResult<Option<EnvironmentState>> {
        self.ensure_connected()?;
        Ok(Some(EnvironmentState {
            world_name: Some("MockWorld".to_string()),
            instance_id: Some("mock-instance-001".to_string()),
            ..Default::default()
        }))
    }

    async fn reset_all(&mut self) -> BackendResult<()> {
        self.ensure_connected()?;
        self.current_emotion = EmotionType::Neutral;
        self.current_gesture = GestureType::None;
        self.resets += 1;
        Ok(())
    }

    async fn execute_behavior(
        &mut self,
        behavior: &str,
        _parameters: HashMap<String, Value>,
    ) -> BackendResult<()> {
        self.ensure_connected()?;
        if !SUPPORTED_BEHAVIORS.contains(&behavior) {
            return Err(BackendError::InvalidParameter(format!(
                "unknown behavior '{behavior}'"
            )));
        }
        push_bounded(&mut self.behavior_history, behavior.to_string());
        Ok(())
    }

    async fn avatar_parameters(&self) -> BackendResult<HashMap<String, Value>> {
        self.ensure_connected()?;
        let mut params = HashMap::new();
        params.insert("emotion".to_string(), json!(self.current_emotion.as_str()));
        params.insert("gesture".to_string(), json!(self.current_gesture.as_str()));
        Ok(params)
    }

    async fn get_statistics(&self) -> BackendResult<HashMap<String, Value>> {
        let mut stats = HashMap::new();
        stats.insert("backend".to_string(), json!(self.backend_name()));
        stats.insert("connected".to_string(), json!(self.connected));
        stats.insert("frames_sent".to_string(), json!(self.frames_sent));
        stats.insert("audio_sent".to_string(), json!(self.audio_sent));
        stats.insert("resets".to_string(), json!(self.resets));
        stats.insert(
            "current_emotion".to_string(),
            json!(self.current_emotion.as_str()),
        );
        stats.insert(
            "current_gesture".to_string(),
            json!(self.current_gesture.as_str()),
        );
        stats.insert(
            "recent_behaviors".to_string(),
            json!(self
                .behavior_history
                .iter()
                .rev()
                .take(10)
                .collect::<Vec<_>>()),
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
        assert!(matches!(
            backend.reset_all().await,
            Err(BackendError::NotConnected)
        ));
    }

    #[tokio::test]
    async fn test_mock_backend_animation() {
        let mut backend = MockBackend::new();
        backend.connect(HashMap::new()).await.unwrap();
        let animation = CanonicalAnimationData::new(0.0).with_emotion(EmotionType::Happy, 1.0);
        backend.send_animation_data(animation).await.unwrap();
        let history = backend.animation_history();
        assert_eq!(history.len(), 1);
        assert_eq!(history[0].emotion, Some(EmotionType::Happy));
    }

    #[tokio::test]
    async fn test_mock_history_is_bounded() {
        let mut backend = MockBackend::new();
        backend.connect(HashMap::new()).await.unwrap();
        for i in 0..(MOCK_HISTORY_LIMIT + 5) {
            backend
                .send_animation_data(CanonicalAnimationData::new(i as f64))
                .await
                .unwrap();
        }
        let h = backend.animation_history();
        assert_eq!(h.len(), MOCK_HISTORY_LIMIT);
        assert_eq!(h[0].timestamp, 5.0);
    }

    #[tokio::test]
    async fn test_mock_audio_emotion_and_behaviors() {
        let mut backend = MockBackend::new();
        backend.connect(HashMap::new()).await.unwrap();
        let outcome = backend
            .send_audio_data(AudioData {
                text: Some("[sighs] oh well".into()),
                ..Default::default()
            })
            .await
            .unwrap();
        assert_eq!(outcome.emotion.as_deref(), Some("sad"));
        assert!(!outcome.played);
        assert!(backend
            .execute_behavior("greet", HashMap::new())
            .await
            .is_ok());
        assert!(backend
            .execute_behavior("fly", HashMap::new())
            .await
            .is_err());
    }
}

//! Sequence handling module for Virtual Character MCP Server.
//!
//! This module handles:
//! - Event sequence creation and management
//! - Sequence playback with proper timing
//! - Event type processing (animation, audio, expression, movement, parallel)
//! - Sequence state management (play, pause, resume, stop)

use base64::Engine;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{oneshot, RwLock};
use tokio::time::{sleep, Duration, Instant};
use tracing::{error, info, warn};

use crate::backends::BackendAdapter;
use crate::types::{
    AudioData, CanonicalAnimationData, EmotionType, EventSequence, EventType, GestureType,
    SequenceEvent,
};

/// Result type for sequence operations.
pub type SequenceResult<T> = Result<T, SequenceError>;

/// Errors that can occur during sequence operations.
#[derive(Debug, thiserror::Error)]
pub enum SequenceError {
    #[error("No sequence created")]
    NoSequence,
    #[error("No sequence is playing")]
    NotPlaying,
    #[error("Sequence is already playing")]
    AlreadyPlaying,
    #[error("Backend not connected")]
    BackendNotConnected,
    #[error("Invalid event type: {0}")]
    InvalidEventType(String),
    #[error("Invalid parameter: {0}")]
    InvalidParameter(String),
    #[error("Sequence cancelled")]
    Cancelled,
    #[error("Backend error: {0}")]
    BackendError(String),
}

/// Response from sequence operations.
#[derive(Debug, Clone)]
pub struct SequenceResponse {
    pub success: bool,
    pub message: String,
}

impl SequenceResponse {
    pub fn ok(message: impl Into<String>) -> Self {
        Self {
            success: true,
            message: message.into(),
        }
    }

    pub fn err(message: impl Into<String>) -> Self {
        Self {
            success: false,
            message: message.into(),
        }
    }
}

/// Status of current sequence playback.
#[derive(Debug, Clone, Default)]
pub struct SequenceStatus {
    pub has_sequence: bool,
    pub is_playing: bool,
    pub is_paused: bool,
    pub current_time: f64,
    pub sequence_name: Option<String>,
    pub total_duration: Option<f64>,
    pub event_count: usize,
    pub loop_enabled: bool,
}

/// Handles event sequence creation, management, and playback.
pub struct SequenceHandler {
    /// Current sequence being built or played
    current_sequence: Arc<RwLock<Option<EventSequence>>>,
    /// Handle to the running sequence task
    sequence_task: Arc<RwLock<Option<tokio::task::JoinHandle<()>>>>,
    /// Channel to cancel the sequence
    cancel_tx: Arc<RwLock<Option<oneshot::Sender<()>>>>,
    /// Whether sequence is paused
    is_paused: Arc<RwLock<bool>>,
    /// Current playback time
    current_time: Arc<RwLock<f64>>,
    /// Pause event for synchronization
    pause_event: Arc<tokio::sync::Notify>,
}

impl Default for SequenceHandler {
    fn default() -> Self {
        Self::new()
    }
}

impl SequenceHandler {
    /// Create a new sequence handler.
    pub fn new() -> Self {
        Self {
            current_sequence: Arc::new(RwLock::new(None)),
            sequence_task: Arc::new(RwLock::new(None)),
            cancel_tx: Arc::new(RwLock::new(None)),
            is_paused: Arc::new(RwLock::new(false)),
            current_time: Arc::new(RwLock::new(0.0)),
            pause_event: Arc::new(tokio::sync::Notify::new()),
        }
    }

    /// Create a new event sequence.
    pub async fn create_sequence(
        &self,
        name: String,
        description: Option<String>,
        loop_sequence: bool,
        interrupt_current: bool,
    ) -> SequenceResult<SequenceResponse> {
        // Stop current sequence if needed
        if interrupt_current {
            self.stop_sequence().await.ok();
        }

        let sequence = EventSequence {
            name: name.clone(),
            description,
            loop_sequence,
            created_timestamp: Some(
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs_f64(),
            ),
            ..Default::default()
        };

        *self.current_sequence.write().await = Some(sequence);

        Ok(SequenceResponse::ok(format!("Created sequence: {}", name)))
    }

    /// Add an event to the current sequence.
    pub async fn add_event(&self, event: SequenceEvent) -> SequenceResult<SequenceResponse> {
        let mut seq_guard = self.current_sequence.write().await;
        let seq = seq_guard.as_mut().ok_or(SequenceError::NoSequence)?;

        let event_type = format!("{:?}", event.event_type);
        let timestamp = event.timestamp;
        seq.add_event(event);

        Ok(SequenceResponse::ok(format!(
            "Added {} event at {}s",
            event_type, timestamp
        )))
    }

    /// Play the current sequence.
    pub async fn play_sequence<B: BackendAdapter + Send + Sync + 'static>(
        &self,
        backend: Arc<RwLock<Option<Box<B>>>>,
        start_time: f64,
    ) -> SequenceResult<SequenceResponse> {
        let seq_guard = self.current_sequence.read().await;
        let seq = seq_guard.as_ref().ok_or(SequenceError::NoSequence)?;
        let seq_name = seq.name.clone();
        drop(seq_guard);

        // Cancel any existing sequence
        self.cancel_running_sequence().await;

        // Reset state
        *self.current_time.write().await = start_time;
        *self.is_paused.write().await = false;

        // Create cancel channel
        let (cancel_tx, cancel_rx) = oneshot::channel();
        *self.cancel_tx.write().await = Some(cancel_tx);

        // Clone references for the task
        let sequence = self.current_sequence.clone();
        let is_paused = self.is_paused.clone();
        let current_time = self.current_time.clone();
        let pause_event = self.pause_event.clone();

        // Spawn the sequence execution task
        let task = tokio::spawn(async move {
            if let Err(e) = Self::execute_sequence_internal(
                sequence,
                backend,
                is_paused,
                current_time,
                pause_event,
                cancel_rx,
                start_time,
            )
            .await
            {
                match e {
                    SequenceError::Cancelled => info!("Sequence cancelled"),
                    _ => error!("Sequence error: {}", e),
                }
            }
        });

        *self.sequence_task.write().await = Some(task);

        Ok(SequenceResponse::ok(format!(
            "Started playing sequence: {}",
            seq_name
        )))
    }

    /// Pause the currently playing sequence.
    pub async fn pause_sequence(&self) -> SequenceResult<SequenceResponse> {
        let task_guard = self.sequence_task.read().await;
        if task_guard.is_none() || task_guard.as_ref().unwrap().is_finished() {
            return Err(SequenceError::NotPlaying);
        }

        *self.is_paused.write().await = true;
        Ok(SequenceResponse::ok("Sequence paused"))
    }

    /// Resume the paused sequence.
    pub async fn resume_sequence(&self) -> SequenceResult<SequenceResponse> {
        let task_guard = self.sequence_task.read().await;
        if task_guard.is_none() || task_guard.as_ref().unwrap().is_finished() {
            return Err(SequenceError::NotPlaying);
        }

        *self.is_paused.write().await = false;
        self.pause_event.notify_one();
        Ok(SequenceResponse::ok("Sequence resumed"))
    }

    /// Stop the currently playing sequence.
    pub async fn stop_sequence(&self) -> SequenceResult<SequenceResponse> {
        self.cancel_running_sequence().await;
        *self.current_time.write().await = 0.0;
        Ok(SequenceResponse::ok("Sequence stopped"))
    }

    /// Get status of current sequence playback.
    pub async fn get_status(&self) -> SequenceStatus {
        let seq_guard = self.current_sequence.read().await;
        let task_guard = self.sequence_task.read().await;
        let is_paused = *self.is_paused.read().await;
        let current_time = *self.current_time.read().await;

        let is_playing = task_guard
            .as_ref()
            .map(|t| !t.is_finished())
            .unwrap_or(false);

        SequenceStatus {
            has_sequence: seq_guard.is_some(),
            is_playing,
            is_paused,
            current_time,
            sequence_name: seq_guard.as_ref().map(|s| s.name.clone()),
            total_duration: seq_guard.as_ref().and_then(|s| s.total_duration),
            event_count: seq_guard.as_ref().map(|s| s.events.len()).unwrap_or(0),
            loop_enabled: seq_guard.as_ref().map(|s| s.loop_sequence).unwrap_or(false),
        }
    }

    /// Emergency reset - stops all sequences and resets avatar.
    pub async fn panic_reset<B: BackendAdapter + Send + Sync + 'static>(
        &self,
        backend: Arc<RwLock<Option<Box<B>>>>,
    ) -> SequenceResult<SequenceResponse> {
        // Cancel running sequence
        self.cancel_running_sequence().await;

        // Clear state
        *self.current_sequence.write().await = None;
        *self.is_paused.write().await = false;
        *self.current_time.write().await = 0.0;

        // Reset avatar if backend available
        let mut backend_guard = backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            Self::reset_avatar_state(backend.as_mut()).await.ok();
        }

        Ok(SequenceResponse::ok("Emergency reset completed"))
    }

    /// Cancel any running sequence task.
    async fn cancel_running_sequence(&self) {
        // Send cancel signal
        if let Some(tx) = self.cancel_tx.write().await.take() {
            let _ = tx.send(());
        }

        // Wait for task to complete
        if let Some(task) = self.sequence_task.write().await.take() {
            task.abort();
            let _ = task.await;
        }
    }

    /// Internal sequence execution with proper async handling.
    async fn execute_sequence_internal<B: BackendAdapter + Send + Sync + 'static>(
        sequence: Arc<RwLock<Option<EventSequence>>>,
        backend: Arc<RwLock<Option<Box<B>>>>,
        is_paused: Arc<RwLock<bool>>,
        current_time: Arc<RwLock<f64>>,
        pause_event: Arc<tokio::sync::Notify>,
        mut cancel_rx: oneshot::Receiver<()>,
        start_time: f64,
    ) -> SequenceResult<()> {
        loop {
            // Get sequence data
            let seq_guard = sequence.read().await;
            let seq = seq_guard.as_ref().ok_or(SequenceError::NoSequence)?;
            let loop_sequence = seq.loop_sequence;
            let total_duration = seq.total_duration;

            // Sort events by timestamp
            let mut sorted_events: Vec<_> = seq.events.to_vec();
            sorted_events.sort_by(|a, b| {
                a.timestamp
                    .partial_cmp(&b.timestamp)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });
            drop(seq_guard);

            // Reset avatar state before starting
            {
                let mut backend_guard = backend.write().await;
                if let Some(ref mut b) = *backend_guard {
                    Self::reset_avatar_state(b.as_mut()).await.ok();
                }
            }

            let start_instant = Instant::now();
            let mut pause_offset = Duration::ZERO;

            // Execute events at scheduled times
            for event in sorted_events {
                // Check for cancellation
                if cancel_rx.try_recv().is_ok() {
                    return Err(SequenceError::Cancelled);
                }

                // Handle pause
                while *is_paused.read().await {
                    let pause_start = Instant::now();

                    tokio::select! {
                        _ = pause_event.notified() => {}
                        _ = &mut cancel_rx => {
                            return Err(SequenceError::Cancelled);
                        }
                    }

                    pause_offset += pause_start.elapsed();
                }

                // Calculate wait time
                let elapsed = (start_instant.elapsed() - pause_offset).as_secs_f64() + start_time;
                let time_to_wait = event.timestamp - elapsed;

                if time_to_wait > 0.0 {
                    tokio::select! {
                        _ = sleep(Duration::from_secs_f64(time_to_wait)) => {}
                        _ = &mut cancel_rx => {
                            return Err(SequenceError::Cancelled);
                        }
                    }
                }

                // Update current time
                *current_time.write().await = event.timestamp;

                // Execute event
                {
                    let mut backend_guard = backend.write().await;
                    if let Some(ref mut b) = *backend_guard {
                        if let Err(e) = Self::execute_event(&event, b.as_mut()).await {
                            warn!("Error executing event at {}s: {}", event.timestamp, e);
                        }
                    }
                }
            }

            // Wait for remaining duration
            if let Some(total) = total_duration {
                let elapsed = (start_instant.elapsed() - pause_offset).as_secs_f64() + start_time;
                let final_wait = total - elapsed;
                if final_wait > 0.0 {
                    tokio::select! {
                        _ = sleep(Duration::from_secs_f64(final_wait)) => {}
                        _ = &mut cancel_rx => {
                            return Err(SequenceError::Cancelled);
                        }
                    }
                }
            }

            // Reset avatar state after completion
            {
                let mut backend_guard = backend.write().await;
                if let Some(ref mut b) = *backend_guard {
                    Self::reset_avatar_state(b.as_mut()).await.ok();
                }
            }

            // Handle looping
            if !loop_sequence {
                break;
            }

            *current_time.write().await = 0.0;
        }

        Ok(())
    }

    /// Execute a single event.
    async fn execute_event<B: BackendAdapter>(
        event: &SequenceEvent,
        backend: &mut B,
    ) -> SequenceResult<()> {
        match event.event_type {
            EventType::Animation => {
                if let Some(ref animation) = event.animation_data {
                    backend
                        .send_animation_data(animation.clone())
                        .await
                        .map_err(|e| SequenceError::BackendError(e.to_string()))?;
                }
            },
            EventType::Audio => {
                if let Some(ref audio) = event.audio_data {
                    backend
                        .send_audio_data(audio.clone())
                        .await
                        .map_err(|e| SequenceError::BackendError(e.to_string()))?;
                }
            },
            EventType::Wait => {
                // Wait is handled by timing logic
                if let Some(wait_dur) = event.wait_duration {
                    sleep(Duration::from_secs_f64(wait_dur)).await;
                }
            },
            EventType::Expression => {
                if let Some(emotion) = event.expression {
                    let animation = CanonicalAnimationData {
                        timestamp: event.timestamp,
                        emotion: Some(emotion),
                        emotion_intensity: event.expression_intensity.unwrap_or(1.0),
                        ..Default::default()
                    };
                    backend
                        .send_animation_data(animation)
                        .await
                        .map_err(|e| SequenceError::BackendError(e.to_string()))?;
                }
            },
            EventType::Movement => {
                if let Some(ref params) = event.movement_params {
                    let animation = CanonicalAnimationData {
                        timestamp: event.timestamp,
                        parameters: params.clone(),
                        ..Default::default()
                    };
                    backend
                        .send_animation_data(animation)
                        .await
                        .map_err(|e| SequenceError::BackendError(e.to_string()))?;
                }
            },
            EventType::Parallel => {
                if let Some(ref parallel_events) = event.parallel_events {
                    // Execute parallel events sequentially
                    // Note: True parallel execution would require cloning backend
                    for p_event in parallel_events {
                        Box::pin(Self::execute_event(p_event, backend)).await?;
                    }
                }
            },
            EventType::LoopStart | EventType::LoopEnd => {
                // Loop markers are handled by the sequence execution logic
                // They don't execute any backend commands
            },
        }
        Ok(())
    }

    /// Reset avatar to neutral state.
    async fn reset_avatar_state<B: BackendAdapter>(backend: &mut B) -> SequenceResult<()> {
        let neutral_animation = CanonicalAnimationData {
            timestamp: 0.0,
            emotion: Some(EmotionType::Neutral),
            emotion_intensity: 0.0,
            gesture: Some(GestureType::None),
            gesture_intensity: 0.0,
            parameters: {
                let mut params = HashMap::new();
                params.insert("move_forward".to_string(), Value::Number(0.into()));
                params.insert("move_right".to_string(), Value::Number(0.into()));
                params.insert("look_horizontal".to_string(), Value::Number(0.into()));
                params.insert("look_vertical".to_string(), Value::Number(0.into()));
                params.insert("jump".to_string(), Value::Bool(false));
                params.insert("crouch".to_string(), Value::Bool(false));
                params.insert("run".to_string(), Value::Bool(false));
                params
            },
            ..Default::default()
        };

        backend
            .send_animation_data(neutral_animation)
            .await
            .map_err(|e| SequenceError::BackendError(e.to_string()))?;

        sleep(Duration::from_millis(100)).await;
        Ok(())
    }
}

/// Helper to create events from dictionary parameters.
pub fn create_event_from_params(params: &HashMap<String, Value>) -> Result<SequenceEvent, String> {
    let event_type_str = params
        .get("event_type")
        .and_then(|v| v.as_str())
        .ok_or("Missing event_type")?;

    let event_type = event_type_str
        .parse::<EventType>()
        .map_err(|e| format!("Invalid event_type: {}", e))?;

    let timestamp = params
        .get("timestamp")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);

    let mut event = SequenceEvent::new(event_type, timestamp);
    event.duration = params.get("duration").and_then(|v| v.as_f64());
    event.wait_duration = params.get("wait_duration").and_then(|v| v.as_f64());

    // Parse expression
    if let Some(expr_str) = params.get("expression").and_then(|v| v.as_str()) {
        if let Ok(emotion) = expr_str.parse::<EmotionType>() {
            event.expression = Some(emotion);
            event.expression_intensity = params
                .get("expression_intensity")
                .and_then(|v| v.as_f64())
                .map(|v| v as f32);
        }
    }

    // Parse movement params
    if let Some(move_params) = params.get("movement_params") {
        if let Ok(parsed) = serde_json::from_value(move_params.clone()) {
            event.movement_params = Some(parsed);
        }
    }

    // Parse audio data
    if let Some(audio_data_str) = params.get("audio_data").and_then(|v| v.as_str()) {
        let audio_format = params
            .get("audio_format")
            .and_then(|v| v.as_str())
            .unwrap_or("mp3")
            .to_string();

        // Handle data URL or base64
        let audio_str = if audio_data_str.starts_with("data:") {
            audio_data_str.split(',').nth(1).unwrap_or(audio_data_str)
        } else {
            audio_data_str
        };

        if let Ok(audio_bytes) = base64::engine::general_purpose::STANDARD.decode(audio_str) {
            event.audio_data = Some(AudioData {
                data: audio_bytes,
                format: audio_format,
                duration: event.duration.unwrap_or(0.0) as f32,
                ..Default::default()
            });
        }
    }

    // Parse animation params
    if let Some(anim_params) = params.get("animation_params") {
        let mut animation = CanonicalAnimationData::new(timestamp);

        if let Some(emotion_str) = anim_params.get("emotion").and_then(|v| v.as_str()) {
            if let Ok(emotion) = emotion_str.parse::<EmotionType>() {
                animation.emotion = Some(emotion);
                animation.emotion_intensity = anim_params
                    .get("emotion_intensity")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(1.0) as f32;
            }
        }

        if let Some(gesture_str) = anim_params.get("gesture").and_then(|v| v.as_str()) {
            if let Ok(gesture) = gesture_str.parse::<GestureType>() {
                animation.gesture = Some(gesture);
                animation.gesture_intensity = anim_params
                    .get("gesture_intensity")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(1.0) as f32;
            }
        }

        if let Some(params) = anim_params.get("parameters") {
            if let Ok(parsed) = serde_json::from_value(params.clone()) {
                animation.parameters = parsed;
            }
        }

        event.animation_data = Some(animation);
    }

    Ok(event)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_sequence_handler_creation() {
        let handler = SequenceHandler::new();
        let status = handler.get_status().await;
        assert!(!status.has_sequence);
        assert!(!status.is_playing);
    }

    #[tokio::test]
    async fn test_create_sequence() {
        let handler = SequenceHandler::new();
        let result = handler
            .create_sequence("test".to_string(), None, false, false)
            .await;
        assert!(result.is_ok());

        let status = handler.get_status().await;
        assert!(status.has_sequence);
        assert_eq!(status.sequence_name, Some("test".to_string()));
    }

    #[tokio::test]
    async fn test_add_event() {
        let handler = SequenceHandler::new();
        handler
            .create_sequence("test".to_string(), None, false, false)
            .await
            .unwrap();

        let event = SequenceEvent::new(EventType::Expression, 1.0);
        let result = handler.add_event(event).await;
        assert!(result.is_ok());

        let status = handler.get_status().await;
        assert_eq!(status.event_count, 1);
    }

    #[tokio::test]
    async fn test_create_event_from_params() {
        let mut params = HashMap::new();
        params.insert(
            "event_type".to_string(),
            Value::String("expression".to_string()),
        );
        params.insert("timestamp".to_string(), Value::Number(1.into()));
        params.insert("expression".to_string(), Value::String("happy".to_string()));

        let event = create_event_from_params(&params);
        assert!(event.is_ok());

        let event = event.unwrap();
        assert_eq!(event.event_type, EventType::Expression);
        assert_eq!(event.timestamp, 1.0);
        assert_eq!(event.expression, Some(EmotionType::Happy));
    }

    #[tokio::test]
    async fn test_stop_without_playing() {
        let handler = SequenceHandler::new();
        let result = handler.stop_sequence().await;
        // Should succeed even if nothing is playing
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_add_event_without_sequence() {
        let handler = SequenceHandler::new();
        let event = SequenceEvent::new(EventType::Expression, 1.0);
        let result = handler.add_event(event).await;
        assert!(result.is_err());
        matches!(result.unwrap_err(), SequenceError::NoSequence);
    }

    #[tokio::test]
    async fn test_create_sequence_with_description() {
        let handler = SequenceHandler::new();
        let result = handler
            .create_sequence(
                "greeting".to_string(),
                Some("A friendly greeting sequence".to_string()),
                true,
                false,
            )
            .await;
        assert!(result.is_ok());

        let status = handler.get_status().await;
        assert_eq!(status.sequence_name, Some("greeting".to_string()));
        assert!(status.loop_enabled);
    }

    #[tokio::test]
    async fn test_multiple_events() {
        let handler = SequenceHandler::new();
        handler
            .create_sequence("multi".to_string(), None, false, false)
            .await
            .unwrap();

        // Add multiple events
        for i in 0..5 {
            let event = SequenceEvent::new(EventType::Wait, i as f64);
            handler.add_event(event).await.unwrap();
        }

        let status = handler.get_status().await;
        assert_eq!(status.event_count, 5);
    }

    #[tokio::test]
    async fn test_create_event_with_animation_params() {
        let mut params = HashMap::new();
        params.insert(
            "event_type".to_string(),
            Value::String("animation".to_string()),
        );
        params.insert("timestamp".to_string(), Value::Number(2.into()));

        let mut anim_params = serde_json::Map::new();
        anim_params.insert("emotion".to_string(), Value::String("happy".to_string()));
        anim_params.insert(
            "emotion_intensity".to_string(),
            serde_json::Number::from_f64(0.8).unwrap().into(),
        );
        anim_params.insert("gesture".to_string(), Value::String("wave".to_string()));

        params.insert("animation_params".to_string(), Value::Object(anim_params));

        let event = create_event_from_params(&params).unwrap();
        assert_eq!(event.event_type, EventType::Animation);
        assert!(event.animation_data.is_some());
        let anim = event.animation_data.unwrap();
        assert_eq!(anim.emotion, Some(EmotionType::Happy));
        assert_eq!(anim.gesture, Some(GestureType::Wave));
    }

    #[tokio::test]
    async fn test_create_event_with_movement_params() {
        let mut params = HashMap::new();
        params.insert(
            "event_type".to_string(),
            Value::String("movement".to_string()),
        );
        params.insert("timestamp".to_string(), Value::Number(0.into()));

        let mut move_params = serde_json::Map::new();
        move_params.insert(
            "move_forward".to_string(),
            serde_json::Number::from_f64(0.5).unwrap().into(),
        );
        move_params.insert(
            "move_right".to_string(),
            serde_json::Number::from_f64(-0.3).unwrap().into(),
        );

        params.insert("movement_params".to_string(), Value::Object(move_params));

        let event = create_event_from_params(&params).unwrap();
        assert_eq!(event.event_type, EventType::Movement);
        assert!(event.movement_params.is_some());
    }

    #[tokio::test]
    async fn test_create_event_invalid_type() {
        let mut params = HashMap::new();
        params.insert(
            "event_type".to_string(),
            Value::String("invalid_type".to_string()),
        );

        let result = create_event_from_params(&params);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Invalid event_type"));
    }

    #[tokio::test]
    async fn test_create_event_missing_type() {
        let params = HashMap::new();

        let result = create_event_from_params(&params);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Missing event_type"));
    }

    #[tokio::test]
    async fn test_pause_without_playing() {
        let handler = SequenceHandler::new();
        let result = handler.pause_sequence().await;
        assert!(result.is_err());
        matches!(result.unwrap_err(), SequenceError::NotPlaying);
    }

    #[tokio::test]
    async fn test_resume_without_playing() {
        let handler = SequenceHandler::new();
        let result = handler.resume_sequence().await;
        assert!(result.is_err());
        matches!(result.unwrap_err(), SequenceError::NotPlaying);
    }

    #[tokio::test]
    async fn test_sequence_status_initial() {
        let handler = SequenceHandler::new();
        let status = handler.get_status().await;

        assert!(!status.has_sequence);
        assert!(!status.is_playing);
        assert!(!status.is_paused);
        assert_eq!(status.current_time, 0.0);
        assert!(status.sequence_name.is_none());
        assert!(status.total_duration.is_none());
        assert_eq!(status.event_count, 0);
        assert!(!status.loop_enabled);
    }

    #[tokio::test]
    async fn test_sequence_response() {
        let ok = SequenceResponse::ok("Success");
        assert!(ok.success);
        assert_eq!(ok.message, "Success");

        let err = SequenceResponse::err("Failed");
        assert!(!err.success);
        assert_eq!(err.message, "Failed");
    }

    #[test]
    fn test_sequence_error_display() {
        let errors = [
            SequenceError::NoSequence,
            SequenceError::NotPlaying,
            SequenceError::AlreadyPlaying,
            SequenceError::BackendNotConnected,
            SequenceError::InvalidEventType("test".to_string()),
            SequenceError::InvalidParameter("param".to_string()),
            SequenceError::Cancelled,
            SequenceError::BackendError("error".to_string()),
        ];

        for err in errors {
            // Ensure Display trait works
            let msg = format!("{}", err);
            assert!(!msg.is_empty());
        }
    }

    #[tokio::test]
    async fn test_create_sequence_interrupt_current() {
        let handler = SequenceHandler::new();

        // Create first sequence
        handler
            .create_sequence("first".to_string(), None, false, false)
            .await
            .unwrap();

        // Create second sequence with interrupt
        handler
            .create_sequence("second".to_string(), None, false, true)
            .await
            .unwrap();

        let status = handler.get_status().await;
        assert_eq!(status.sequence_name, Some("second".to_string()));
    }

    #[tokio::test]
    async fn test_event_with_wait_duration() {
        let mut params = HashMap::new();
        params.insert("event_type".to_string(), Value::String("wait".to_string()));
        params.insert("timestamp".to_string(), Value::Number(0.into()));
        params.insert(
            "wait_duration".to_string(),
            serde_json::Number::from_f64(2.5).unwrap().into(),
        );

        let event = create_event_from_params(&params).unwrap();
        assert_eq!(event.event_type, EventType::Wait);
        assert_eq!(event.wait_duration, Some(2.5));
    }
}

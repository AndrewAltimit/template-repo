//! Virtual Character MCP Server implementation.
//!
//! This module implements all MCP tools for controlling virtual characters.

use async_trait::async_trait;
use mcp_core::error::Result;
use mcp_core::tool::{BoxedTool, Tool, ToolResult};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info};

use crate::audio::AudioHandler;
use crate::backends::{BackendAdapter, MockBackend, VRChatRemoteBackend};
use crate::constants::{get_vrcemote_name, VRCEmoteValue, VRCEMOTE_DESCRIPTION};
use crate::types::{
    AudioData, CanonicalAnimationData, EmotionType, EventSequence, EventType, GestureType,
    SequenceEvent,
};

/// Server state shared across all tools.
#[derive(Clone)]
pub struct ServerRefs {
    pub backend: Arc<RwLock<Option<Box<dyn BackendAdapter>>>>,
    pub backend_name: Arc<RwLock<Option<String>>>,
    pub current_sequence: Arc<RwLock<Option<EventSequence>>>,
    pub sequence_playing: Arc<RwLock<bool>>,
}

impl ServerRefs {
    pub fn new() -> Self {
        Self {
            backend: Arc::new(RwLock::new(None)),
            backend_name: Arc::new(RwLock::new(None)),
            current_sequence: Arc::new(RwLock::new(None)),
            sequence_playing: Arc::new(RwLock::new(false)),
        }
    }

    /// Check if backend is connected and return an error message if not.
    async fn check_connected(&self) -> Option<String> {
        let backend = self.backend.read().await;
        if backend.is_none() {
            return Some("No backend connected. Use set_backend first.".to_string());
        }
        if !backend.as_ref().unwrap().is_connected() {
            return Some("Backend is not connected.".to_string());
        }
        None
    }
}

impl Default for ServerRefs {
    fn default() -> Self {
        Self::new()
    }
}

/// Virtual Character MCP Server.
pub struct VirtualCharacterServer {
    refs: ServerRefs,
}

impl VirtualCharacterServer {
    pub fn new() -> Self {
        Self {
            refs: ServerRefs::new(),
        }
    }

    pub fn refs(&self) -> ServerRefs {
        self.refs.clone()
    }

    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(SetBackendTool {
                server: self.refs.clone(),
            }),
            Arc::new(SendAnimationTool {
                server: self.refs.clone(),
            }),
            Arc::new(ExecuteBehaviorTool {
                server: self.refs.clone(),
            }),
            Arc::new(ResetTool {
                server: self.refs.clone(),
            }),
            Arc::new(GetBackendStatusTool {
                server: self.refs.clone(),
            }),
            Arc::new(ListBackendsTool {
                server: self.refs.clone(),
            }),
            Arc::new(PlayAudioTool {
                server: self.refs.clone(),
            }),
            Arc::new(CreateSequenceTool {
                server: self.refs.clone(),
            }),
            Arc::new(AddSequenceEventTool {
                server: self.refs.clone(),
            }),
            Arc::new(PlaySequenceTool {
                server: self.refs.clone(),
            }),
            Arc::new(PauseSequenceTool {
                server: self.refs.clone(),
            }),
            Arc::new(ResumeSequenceTool {
                server: self.refs.clone(),
            }),
            Arc::new(StopSequenceTool {
                server: self.refs.clone(),
            }),
            Arc::new(GetSequenceStatusTool {
                server: self.refs.clone(),
            }),
            Arc::new(PanicResetTool {
                server: self.refs.clone(),
            }),
            Arc::new(SendVRCEmoteTool {
                server: self.refs.clone(),
            }),
        ]
    }
}

impl Default for VirtualCharacterServer {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// Tool Implementations
// =============================================================================

/// Set backend tool.
struct SetBackendTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SetBackendTool {
    fn name(&self) -> &str {
        "set_backend"
    }

    fn description(&self) -> &str {
        "Connect to a virtual character backend (mock, vrchat_remote)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "backend": {
                    "type": "string",
                    "enum": ["mock", "vrchat_remote"],
                    "description": "Backend to connect to"
                },
                "config": {
                    "type": "object",
                    "description": "Backend configuration",
                    "properties": {
                        "remote_host": {"type": "string", "description": "Remote host IP (for vrchat_remote)"},
                        "use_vrcemote": {"type": "boolean", "description": "Use VRCEmote system for gestures"},
                        "osc_in_port": {"type": "integer", "default": 9000},
                        "osc_out_port": {"type": "integer", "default": 9001}
                    }
                }
            },
            "required": ["backend"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let backend_name = args
            .get("backend")
            .and_then(|v| v.as_str())
            .unwrap_or("mock");

        let config: HashMap<String, Value> = args
            .get("config")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .unwrap_or_default();

        info!("Setting backend to: {}", backend_name);

        // Disconnect current backend if any
        let mut backend_guard = self.server.backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            if let Err(e) = backend.disconnect().await {
                error!("Error disconnecting old backend: {}", e);
            }
        }

        // Create new backend
        let mut new_backend: Box<dyn BackendAdapter> = match backend_name {
            "mock" => Box::new(MockBackend::new()),
            "vrchat_remote" => Box::new(VRChatRemoteBackend::new()),
            _ => {
                return Ok(ToolResult::error(format!(
                    "Unknown backend: {}",
                    backend_name
                )));
            }
        };

        // Connect
        match new_backend.connect(config).await {
            Ok(()) => {
                *backend_guard = Some(new_backend);
                *self.server.backend_name.write().await = Some(backend_name.to_string());

                ToolResult::json(&json!({
                    "success": true,
                    "backend": backend_name,
                    "message": format!("Connected to {}", backend_name)
                }))
            }
            Err(e) => Ok(ToolResult::error(format!("Failed to connect: {}", e))),
        }
    }
}

/// Send animation tool.
struct SendAnimationTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SendAnimationTool {
    fn name(&self) -> &str {
        "send_animation"
    }

    fn description(&self) -> &str {
        "Send animation data to the current backend"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "emotion": {
                    "type": "string",
                    "enum": ["neutral", "happy", "sad", "angry", "surprised", "fearful", "disgusted"],
                    "description": "Emotion to display"
                },
                "emotion_intensity": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 1.0
                },
                "gesture": {
                    "type": "string",
                    "enum": ["none", "wave", "point", "thumbs_up", "nod", "shake_head", "clap", "dance", "backflip", "cheer", "sadness", "die"],
                    "description": "Gesture to perform"
                },
                "gesture_intensity": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 1.0
                },
                "parameters": {
                    "type": "object",
                    "description": "Movement parameters",
                    "properties": {
                        "move_forward": {"type": "number", "minimum": -1, "maximum": 1},
                        "move_right": {"type": "number", "minimum": -1, "maximum": 1},
                        "look_horizontal": {"type": "number", "minimum": -1, "maximum": 1},
                        "look_vertical": {"type": "number", "minimum": -1, "maximum": 1},
                        "jump": {"type": "boolean"},
                        "crouch": {"type": "boolean"},
                        "run": {"type": "boolean"},
                        "duration": {"type": "number", "default": 2.0}
                    }
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        if let Some(e) = self.server.check_connected().await {
            return Ok(ToolResult::error(e));
        }

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        let mut animation = CanonicalAnimationData::new(timestamp);

        // Parse emotion
        if let Some(emotion_str) = args.get("emotion").and_then(|v| v.as_str()) {
            match emotion_str.parse::<EmotionType>() {
                Ok(emotion) => {
                    animation.emotion = Some(emotion);
                    animation.emotion_intensity = args
                        .get("emotion_intensity")
                        .and_then(|v| v.as_f64())
                        .unwrap_or(1.0) as f32;
                }
                Err(e) => return Ok(ToolResult::error(format!("Invalid emotion: {}", e))),
            }
        }

        // Parse gesture
        if let Some(gesture_str) = args.get("gesture").and_then(|v| v.as_str()) {
            match gesture_str.parse::<GestureType>() {
                Ok(gesture) => {
                    animation.gesture = Some(gesture);
                    animation.gesture_intensity = args
                        .get("gesture_intensity")
                        .and_then(|v| v.as_f64())
                        .unwrap_or(1.0) as f32;
                }
                Err(e) => return Ok(ToolResult::error(format!("Invalid gesture: {}", e))),
            }
        }

        // Parse parameters
        if let Some(params) = args.get("parameters") {
            if let Ok(params_map) = serde_json::from_value::<HashMap<String, Value>>(params.clone())
            {
                animation.parameters = params_map;
            }
        }

        // Send animation
        let mut backend_guard = self.server.backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            match backend.send_animation_data(animation).await {
                Ok(()) => ToolResult::json(&json!({"success": true})),
                Err(e) => Ok(ToolResult::error(format!(
                    "Failed to send animation: {}",
                    e
                ))),
            }
        } else {
            Ok(ToolResult::error("No backend connected"))
        }
    }
}

/// Execute behavior tool.
struct ExecuteBehaviorTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ExecuteBehaviorTool {
    fn name(&self) -> &str {
        "execute_behavior"
    }

    fn description(&self) -> &str {
        "Execute a high-level behavior"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "behavior": {"type": "string", "description": "Behavior to execute (greet, dance, sit, stand, etc.)"},
                "parameters": {"type": "object", "description": "Behavior parameters"}
            },
            "required": ["behavior"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        if let Some(e) = self.server.check_connected().await {
            return Ok(ToolResult::error(e));
        }

        let behavior = args.get("behavior").and_then(|v| v.as_str()).unwrap_or("");

        let params: HashMap<String, Value> = args
            .get("parameters")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .unwrap_or_default();

        let mut backend_guard = self.server.backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            match backend.execute_behavior(behavior, params).await {
                Ok(()) => ToolResult::json(&json!({"success": true})),
                Err(e) => Ok(ToolResult::error(format!(
                    "Failed to execute behavior: {}",
                    e
                ))),
            }
        } else {
            Ok(ToolResult::error("No backend connected"))
        }
    }
}

/// Reset tool.
struct ResetTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ResetTool {
    fn name(&self) -> &str {
        "reset"
    }

    fn description(&self) -> &str {
        "Reset all states - clear emotes and stop all movement"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        if let Some(e) = self.server.check_connected().await {
            return Ok(ToolResult::error(e));
        }

        let mut backend_guard = self.server.backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            match backend.reset_all().await {
                Ok(()) => ToolResult::json(&json!({
                    "success": true,
                    "message": "All states reset"
                })),
                Err(e) => Ok(ToolResult::error(format!("Failed to reset: {}", e))),
            }
        } else {
            Ok(ToolResult::error("No backend connected"))
        }
    }
}

/// Get backend status tool.
struct GetBackendStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetBackendStatusTool {
    fn name(&self) -> &str {
        "get_backend_status"
    }

    fn description(&self) -> &str {
        "Get current backend status and statistics"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let backend_guard = self.server.backend.read().await;
        let backend_name = self.server.backend_name.read().await;

        if let Some(ref backend) = *backend_guard {
            let health = backend.health_check().await.unwrap_or_default();
            let stats = backend.get_statistics().await.unwrap_or_default();

            ToolResult::json(&json!({
                "success": true,
                "backend": *backend_name,
                "connected": backend.is_connected(),
                "health": health,
                "statistics": stats
            }))
        } else {
            ToolResult::json(&json!({
                "success": true,
                "backend": null,
                "connected": false,
                "message": "No backend connected"
            }))
        }
    }
}

/// List backends tool.
struct ListBackendsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListBackendsTool {
    fn name(&self) -> &str {
        "list_backends"
    }

    fn description(&self) -> &str {
        "List available backends"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let current_backend = self.server.backend_name.read().await;

        ToolResult::json(&json!({
            "success": true,
            "backends": [
                {"name": "mock", "class": "MockBackend", "active": *current_backend == Some("mock".to_string())},
                {"name": "vrchat_remote", "class": "VRChatRemoteBackend", "active": *current_backend == Some("vrchat_remote".to_string())}
            ]
        }))
    }
}

/// Play audio tool.
struct PlayAudioTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for PlayAudioTool {
    fn name(&self) -> &str {
        "play_audio"
    }

    fn description(&self) -> &str {
        "Play audio through the virtual character with optional lip-sync metadata"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "audio_data": {
                    "type": "string",
                    "description": "File path, URL, or base64-encoded audio data"
                },
                "audio_format": {
                    "type": "string",
                    "enum": ["mp3", "wav", "opus", "pcm"],
                    "default": "mp3"
                },
                "text": {"type": "string", "description": "Optional text transcript"},
                "expression_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ElevenLabs audio tags like [laughs], [whisper]"
                },
                "duration": {"type": "number", "description": "Audio duration in seconds"}
            },
            "required": ["audio_data"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        if let Some(e) = self.server.check_connected().await {
            return Ok(ToolResult::error(e));
        }

        let audio_data_str = args
            .get("audio_data")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        // Use the AudioHandler to process various input formats
        let audio_handler = AudioHandler::default();
        let (audio_bytes, error): (Option<Vec<u8>>, Option<String>) =
            audio_handler.process_audio_input(audio_data_str).await;

        let audio_bytes = match audio_bytes {
            Some(bytes) => bytes,
            None => {
                return Ok(ToolResult::error(
                    error.unwrap_or_else(|| "Failed to process audio data".to_string()),
                ));
            }
        };

        // Detect format from data or use provided format
        let format_str = args
            .get("audio_format")
            .and_then(|v| v.as_str())
            .unwrap_or("mp3");

        let audio = AudioData {
            data: audio_bytes,
            format: format_str.to_string(),
            duration: args.get("duration").and_then(|v| v.as_f64()).unwrap_or(0.0) as f32,
            text: args.get("text").and_then(|v| v.as_str()).map(String::from),
            expression_tags: args.get("expression_tags").and_then(|v| {
                v.as_array().map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
            }),
            ..Default::default()
        };

        let mut backend_guard = self.server.backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            match backend.send_audio_data(audio).await {
                Ok(()) => ToolResult::json(&json!({"success": true, "message": "Audio sent to backend"})),
                Err(e) => Ok(ToolResult::error(format!("Failed to play audio: {}", e))),
            }
        } else {
            Ok(ToolResult::error("No backend connected"))
        }
    }
}

/// Create sequence tool.
struct CreateSequenceTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateSequenceTool {
    fn name(&self) -> &str {
        "create_sequence"
    }

    fn description(&self) -> &str {
        "Create a new event sequence for coordinated animations and audio"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Sequence name"},
                "description": {"type": "string"},
                "loop": {"type": "boolean", "default": false}
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("unnamed");

        let sequence = EventSequence {
            name: name.to_string(),
            description: args
                .get("description")
                .and_then(|v| v.as_str())
                .map(String::from),
            loop_sequence: args.get("loop").and_then(|v| v.as_bool()).unwrap_or(false),
            created_timestamp: Some(
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs_f64(),
            ),
            ..Default::default()
        };

        *self.server.current_sequence.write().await = Some(sequence);

        ToolResult::json(&json!({
            "success": true,
            "message": format!("Created sequence: {}", name)
        }))
    }
}

/// Add sequence event tool.
struct AddSequenceEventTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddSequenceEventTool {
    fn name(&self) -> &str {
        "add_sequence_event"
    }

    fn description(&self) -> &str {
        "Add an event to the current sequence"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "enum": ["animation", "audio", "wait", "expression", "movement", "parallel"]
                },
                "timestamp": {"type": "number"},
                "duration": {"type": "number"},
                "animation_params": {"type": "object"},
                "wait_duration": {"type": "number"},
                "expression": {"type": "string"},
                "expression_intensity": {"type": "number", "default": 1.0},
                "movement_params": {"type": "object"}
            },
            "required": ["event_type", "timestamp"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let mut sequence_guard = self.server.current_sequence.write().await;

        if sequence_guard.is_none() {
            return Ok(ToolResult::error(
                "No sequence created. Use create_sequence first.",
            ));
        }

        let event_type_str = args
            .get("event_type")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        let event_type = match event_type_str.parse::<EventType>() {
            Ok(t) => t,
            Err(e) => return Ok(ToolResult::error(format!("Invalid event type: {}", e))),
        };

        let timestamp = args
            .get("timestamp")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        let mut event = SequenceEvent::new(event_type, timestamp);
        event.duration = args.get("duration").and_then(|v| v.as_f64());
        event.wait_duration = args.get("wait_duration").and_then(|v| v.as_f64());

        if let Some(expr_str) = args.get("expression").and_then(|v| v.as_str()) {
            if let Ok(emotion) = expr_str.parse::<EmotionType>() {
                event.expression = Some(emotion);
                event.expression_intensity = Some(
                    args.get("expression_intensity")
                        .and_then(|v| v.as_f64())
                        .unwrap_or(1.0) as f32,
                );
            }
        }

        if let Some(move_params) = args.get("movement_params") {
            if let Ok(params) = serde_json::from_value(move_params.clone()) {
                event.movement_params = Some(params);
            }
        }

        if let Some(ref mut seq) = *sequence_guard {
            seq.add_event(event);
        }

        ToolResult::json(&json!({
            "success": true,
            "message": format!("Added {} event at {}s", event_type_str, timestamp)
        }))
    }
}

/// Play sequence tool.
struct PlaySequenceTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for PlaySequenceTool {
    fn name(&self) -> &str {
        "play_sequence"
    }

    fn description(&self) -> &str {
        "Play the current or specified event sequence"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "start_time": {"type": "number", "default": 0}
            }
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        if let Some(e) = self.server.check_connected().await {
            return Ok(ToolResult::error(e));
        }

        let sequence_guard = self.server.current_sequence.read().await;
        if sequence_guard.is_none() {
            return Ok(ToolResult::error("No sequence to play."));
        }

        let seq_name = sequence_guard.as_ref().unwrap().name.clone();
        *self.server.sequence_playing.write().await = true;

        // Note: Actual sequence execution would be implemented here
        // For now, just mark as playing

        ToolResult::json(&json!({
            "success": true,
            "message": format!("Started playing sequence: {}", seq_name)
        }))
    }
}

/// Pause sequence tool.
struct PauseSequenceTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for PauseSequenceTool {
    fn name(&self) -> &str {
        "pause_sequence"
    }

    fn description(&self) -> &str {
        "Pause the currently playing sequence"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let playing = *self.server.sequence_playing.read().await;
        if !playing {
            return Ok(ToolResult::error("No sequence is playing"));
        }

        *self.server.sequence_playing.write().await = false;

        ToolResult::json(&json!({
            "success": true,
            "message": "Sequence paused"
        }))
    }
}

/// Resume sequence tool.
struct ResumeSequenceTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ResumeSequenceTool {
    fn name(&self) -> &str {
        "resume_sequence"
    }

    fn description(&self) -> &str {
        "Resume the paused sequence"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        *self.server.sequence_playing.write().await = true;

        ToolResult::json(&json!({
            "success": true,
            "message": "Sequence resumed"
        }))
    }
}

/// Stop sequence tool.
struct StopSequenceTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for StopSequenceTool {
    fn name(&self) -> &str {
        "stop_sequence"
    }

    fn description(&self) -> &str {
        "Stop the currently playing sequence"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        *self.server.sequence_playing.write().await = false;

        ToolResult::json(&json!({
            "success": true,
            "message": "Sequence stopped"
        }))
    }
}

/// Get sequence status tool.
struct GetSequenceStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetSequenceStatusTool {
    fn name(&self) -> &str {
        "get_sequence_status"
    }

    fn description(&self) -> &str {
        "Get status of current sequence playback"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let sequence_guard = self.server.current_sequence.read().await;
        let playing = *self.server.sequence_playing.read().await;

        let mut status = json!({
            "has_sequence": sequence_guard.is_some(),
            "is_playing": playing
        });

        if let Some(ref seq) = *sequence_guard {
            status["sequence_name"] = json!(seq.name);
            status["total_duration"] = json!(seq.total_duration);
            status["event_count"] = json!(seq.events.len());
            status["loop"] = json!(seq.loop_sequence);
        }

        ToolResult::json(&json!({
            "success": true,
            "status": status
        }))
    }
}

/// Panic reset tool.
struct PanicResetTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for PanicResetTool {
    fn name(&self) -> &str {
        "panic_reset"
    }

    fn description(&self) -> &str {
        "Emergency reset - stops all sequences and resets avatar to neutral state"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        // Stop sequences
        *self.server.sequence_playing.write().await = false;
        *self.server.current_sequence.write().await = None;

        // Reset backend if connected
        let mut backend_guard = self.server.backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            if let Err(e) = backend.reset_all().await {
                error!("Error during panic reset: {}", e);
            }
        }

        ToolResult::json(&json!({
            "success": true,
            "message": "Emergency reset completed"
        }))
    }
}

/// Send VRCEmote tool.
struct SendVRCEmoteTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SendVRCEmoteTool {
    fn name(&self) -> &str {
        "send_vrcemote"
    }

    fn description(&self) -> &str {
        "Send a direct VRCEmote value (0-8) to VRChat backend for precise gesture control"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "emote_value": {
                    "type": "integer",
                    "minimum": VRCEmoteValue::MIN,
                    "maximum": VRCEmoteValue::MAX,
                    "description": VRCEMOTE_DESCRIPTION
                }
            },
            "required": ["emote_value"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        if let Some(e) = self.server.check_connected().await {
            return Ok(ToolResult::error(e));
        }

        let backend_name = self.server.backend_name.read().await;
        if *backend_name != Some("vrchat_remote".to_string()) {
            return Ok(ToolResult::error(
                "VRCEmote is only supported on vrchat_remote backend",
            ));
        }

        let emote_value = args
            .get("emote_value")
            .and_then(|v| v.as_i64())
            .unwrap_or(0) as i32;

        if !(VRCEmoteValue::MIN..=VRCEmoteValue::MAX).contains(&emote_value) {
            return Ok(ToolResult::error(format!(
                "VRCEmote value must be between {} and {}",
                VRCEmoteValue::MIN,
                VRCEmoteValue::MAX
            )));
        }

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        let mut params = HashMap::new();
        let mut avatar_params = serde_json::Map::new();
        avatar_params.insert("VRCEmote".to_string(), json!(emote_value));
        params.insert("avatar_params".to_string(), json!(avatar_params));

        let animation = CanonicalAnimationData::new(timestamp).with_parameters(params);

        let mut backend_guard = self.server.backend.write().await;
        if let Some(ref mut backend) = *backend_guard {
            match backend.send_animation_data(animation).await {
                Ok(()) => {
                    let gesture_name = get_vrcemote_name(emote_value);
                    ToolResult::json(&json!({
                        "success": true,
                        "emote_value": emote_value,
                        "gesture": gesture_name,
                        "message": format!("Sent VRCEmote {} ({})", emote_value, gesture_name)
                    }))
                }
                Err(e) => Ok(ToolResult::error(format!("Failed to send VRCEmote: {}", e))),
            }
        } else {
            Ok(ToolResult::error("No backend connected"))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mcp_core::tool::Content;

    #[tokio::test]
    async fn test_server_creation() {
        let server = VirtualCharacterServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 16);
    }

    #[tokio::test]
    async fn test_set_backend_mock() {
        let server = VirtualCharacterServer::new();
        let tools = server.tools();

        let set_backend = tools.iter().find(|t| t.name() == "set_backend").unwrap();

        let result = set_backend
            .execute(json!({"backend": "mock"}))
            .await
            .unwrap();

        if let Content::Text { text } = &result.content[0] {
            let response: Value = serde_json::from_str(text).unwrap();
            assert!(response["success"].as_bool().unwrap());
        } else {
            panic!("Expected text content");
        }
    }
}

//! MCP tool definitions for the Virtual Character server.
//!
//! All tools share one [`ServerState`]: the active backend slot, the sequence
//! player and the audio loader. Arguments are deserialized into typed structs
//! (see [`crate::spec`]) so wrong types and unknown enum values produce clear
//! errors; every tool returns a JSON object with `"success": true` or an
//! `isError` result with a human-readable message.

use async_trait::async_trait;
use mcp_core::error::Result;
use mcp_core::tool::{BoxedTool, Tool, ToolResult};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, warn};

use crate::audio::AudioHandler;
use crate::backends::{create_backend, BackendAdapter, SharedBackend, BACKEND_NAMES};
use crate::constants::{
    get_vrcemote_name, VRCEmoteValue, SUPPORTED_BEHAVIORS, VRCEMOTE_DESCRIPTION,
};
use crate::sequence_handler::SequenceHandler;
use crate::spec::{build_event, parse_args, prepare_audio, AnimationSpec, EventSpec};
use crate::types::{EmotionType, EventType, GestureType};

/// Seconds since the Unix epoch as `f64` (0.0 if the clock is before 1970).
fn unix_secs_f64() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

/// Longest `duration` accepted by `play_audio` (seconds).
const MAX_AUDIO_DURATION: f64 = 3600.0;

/// State shared by all tools.
pub struct ServerState {
    /// Active backend (None until `set_backend`).
    pub backend: SharedBackend,
    /// Name of the active backend.
    pub backend_name: RwLock<Option<String>>,
    /// Sequence builder / player.
    pub sequences: SequenceHandler,
    /// Audio input resolver (shared HTTP client).
    pub audio: AudioHandler,
}

impl ServerState {
    /// Fresh state with no backend.
    pub fn new() -> Self {
        Self {
            backend: Arc::new(RwLock::new(None)),
            backend_name: RwLock::new(None),
            sequences: SequenceHandler::new(),
            audio: AudioHandler::new(),
        }
    }
}

impl Default for ServerState {
    fn default() -> Self {
        Self::new()
    }
}

/// Return the connected backend or a helpful error.
fn connected_mut(
    slot: &mut Option<Box<dyn BackendAdapter>>,
) -> std::result::Result<&mut Box<dyn BackendAdapter>, String> {
    match slot {
        None => Err("No backend connected. Use set_backend first.".to_string()),
        Some(b) if !b.is_connected() => {
            Err("Backend is not connected. Call set_backend to reconnect.".to_string())
        },
        Some(b) => Ok(b),
    }
}

/// Virtual Character MCP server: owns the shared state and builds the tools.
pub struct VirtualCharacterServer {
    state: Arc<ServerState>,
}

impl VirtualCharacterServer {
    /// Create a server with no backend connected.
    pub fn new() -> Self {
        Self {
            state: Arc::new(ServerState::new()),
        }
    }

    /// Shared state (for embedding / tests).
    pub fn state(&self) -> Arc<ServerState> {
        self.state.clone()
    }

    /// All MCP tools.
    pub fn tools(&self) -> Vec<BoxedTool> {
        ToolKind::ALL
            .iter()
            .map(|kind| {
                Arc::new(VcTool {
                    kind: *kind,
                    state: self.state.clone(),
                }) as BoxedTool
            })
            .collect()
    }

    /// Connect a backend at startup (used by `--backend`).
    pub async fn connect_backend(
        &self,
        backend: &str,
        config: Value,
    ) -> std::result::Result<Value, String> {
        set_backend(
            &self.state,
            SetBackendArgs {
                backend: backend.to_string(),
                config: Some(config),
            },
        )
        .await
    }
}

impl Default for VirtualCharacterServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Every tool exposed by the server.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ToolKind {
    SetBackend,
    DisconnectBackend,
    SendAnimation,
    ExecuteBehavior,
    Reset,
    GetBackendStatus,
    ListBackends,
    GetAvatarState,
    PlayAudio,
    CreateSequence,
    AddSequenceEvent,
    PlaySequence,
    PauseSequence,
    ResumeSequence,
    StopSequence,
    GetSequenceStatus,
    PanicReset,
    SendVRCEmote,
}

impl ToolKind {
    const ALL: [ToolKind; 18] = [
        ToolKind::SetBackend,
        ToolKind::DisconnectBackend,
        ToolKind::SendAnimation,
        ToolKind::ExecuteBehavior,
        ToolKind::Reset,
        ToolKind::GetBackendStatus,
        ToolKind::ListBackends,
        ToolKind::GetAvatarState,
        ToolKind::PlayAudio,
        ToolKind::CreateSequence,
        ToolKind::AddSequenceEvent,
        ToolKind::PlaySequence,
        ToolKind::PauseSequence,
        ToolKind::ResumeSequence,
        ToolKind::StopSequence,
        ToolKind::GetSequenceStatus,
        ToolKind::PanicReset,
        ToolKind::SendVRCEmote,
    ];

    fn name(self) -> &'static str {
        match self {
            ToolKind::SetBackend => "set_backend",
            ToolKind::DisconnectBackend => "disconnect_backend",
            ToolKind::SendAnimation => "send_animation",
            ToolKind::ExecuteBehavior => "execute_behavior",
            ToolKind::Reset => "reset",
            ToolKind::GetBackendStatus => "get_backend_status",
            ToolKind::ListBackends => "list_backends",
            ToolKind::GetAvatarState => "get_avatar_state",
            ToolKind::PlayAudio => "play_audio",
            ToolKind::CreateSequence => "create_sequence",
            ToolKind::AddSequenceEvent => "add_sequence_event",
            ToolKind::PlaySequence => "play_sequence",
            ToolKind::PauseSequence => "pause_sequence",
            ToolKind::ResumeSequence => "resume_sequence",
            ToolKind::StopSequence => "stop_sequence",
            ToolKind::GetSequenceStatus => "get_sequence_status",
            ToolKind::PanicReset => "panic_reset",
            ToolKind::SendVRCEmote => "send_vrcemote",
        }
    }

    fn description(self) -> &'static str {
        match self {
            ToolKind::SetBackend => "Connect to a virtual character backend (mock, vrchat_remote). Replaces and disconnects any current backend and stops sequence playback. For vrchat_remote, unspecified config values come from VIRTUAL_CHARACTER_* environment variables.",
            ToolKind::DisconnectBackend => "Disconnect the current backend, stop sequence playback and release its network ports",
            ToolKind::SendAnimation => "Send emotion, gesture, movement, blend shapes and/or custom avatar parameters to the current backend. On VRChat, emotions and gestures map to VRCEmote wheel slots (toggle semantics: repeating the active one turns it off); a gesture takes priority over an emotion in the same call.",
            ToolKind::ExecuteBehavior => "Execute a high-level behavior: greet, dance, sit, stand, jump, crouch",
            ToolKind::Reset => "Reset all states - clear emotes and stop all movement",
            ToolKind::GetBackendStatus => "Get current backend status, health and statistics (including whether VRChat is sending OSC back)",
            ToolKind::ListBackends => "List available backends",
            ToolKind::GetAvatarState => "Get avatar/world state reported by the backend (for VRChat: avatar id and avatar parameters received over OSC)",
            ToolKind::PlayAudio => "Play audio through the virtual character. Accepts a file path, http(s) URL, data URL or base64. Expression tags (explicit or [tags] in text) drive the avatar's emotion. Reports whether the audio was actually played and how.",
            ToolKind::CreateSequence => "Create a new event sequence for coordinated animations and audio (replaces the sequence being built)",
            ToolKind::AddSequenceEvent => "Add an event to the current sequence. Events fire at 'timestamp' seconds from the start of playback.",
            ToolKind::PlaySequence => "Play the current event sequence on the connected backend (runs in the background)",
            ToolKind::PauseSequence => "Pause the currently playing sequence",
            ToolKind::ResumeSequence => "Resume the paused sequence",
            ToolKind::StopSequence => "Stop the currently playing sequence",
            ToolKind::GetSequenceStatus => "Get status of the current sequence and its playback (position, events executed/failed, last error)",
            ToolKind::PanicReset => "Emergency reset - stops and discards sequences and resets the avatar to a neutral state",
            ToolKind::SendVRCEmote => "Send a VRCEmote value (0-8) to the VRChat backend for precise gesture control (0 clears; repeating the active value toggles it off)",
        }
    }

    fn schema(self) -> Value {
        let emotions: Vec<&str> = EmotionType::ALL.iter().map(|e| e.as_str()).collect();
        let gestures: Vec<&str> = GestureType::ALL.iter().map(|g| g.as_str()).collect();
        let movement = json!({
            "type": "object",
            "description": "Movement and avatar parameters. Continuous axes auto-stop after 'duration' seconds.",
            "properties": {
                "move_forward": {"type": "number", "minimum": -1, "maximum": 1},
                "move_right": {"type": "number", "minimum": -1, "maximum": 1},
                "look_horizontal": {"type": "number", "minimum": -1, "maximum": 1, "description": "Turn rate"},
                "look_vertical": {"type": "number", "minimum": -1, "maximum": 1},
                "jump": {"type": "boolean"},
                "crouch": {"type": "boolean"},
                "run": {"type": "boolean"},
                "duration": {"type": "number", "default": 2.0, "description": "Seconds before axes reset to 0 (max 60)"},
                "avatar_params": {"type": "object", "description": "Custom avatar parameters: name -> number/boolean (VRCEmote is routed through the emote state machine)"}
            }
        });
        let animation_props = json!({
            "emotion": {"type": "string", "enum": emotions, "description": "Emotion to display"},
            "emotion_intensity": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0},
            "gesture": {"type": "string", "enum": gestures, "description": "Gesture to perform"},
            "gesture_intensity": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0},
            "parameters": movement,
            "blend_shapes": {"type": "object", "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}, "description": "Blend shape weights, sent as /avatar/parameters/BlendShape_<name>"}
        });
        let empty = json!({"type": "object", "properties": {}});

        match self {
            ToolKind::SetBackend => json!({
                "type": "object",
                "properties": {
                    "backend": {"type": "string", "enum": BACKEND_NAMES, "description": "Backend to connect to"},
                    "config": {
                        "type": "object",
                        "description": "Backend configuration (vrchat_remote only; mock ignores it)",
                        "properties": {
                            "remote_host": {"type": "string", "description": "Host running VRChat (default 127.0.0.1 or VIRTUAL_CHARACTER_HOST)"},
                            "osc_in_port": {"type": "integer", "default": 9000, "description": "VRChat's OSC input port (we send here)"},
                            "osc_out_port": {"type": "integer", "default": 9001, "description": "VRChat's OSC output port (we listen here)"},
                            "use_vrcemote": {"type": "boolean", "default": true, "description": "Express emotions/gestures via VRCEmote"},
                            "emote_timeout": {"type": "number", "default": 10, "description": "Seconds before an active emote is toggled off automatically (0 disables)"},
                            "listen": {"type": "boolean", "default": true, "description": "Listen for VRChat OSC output"},
                            "audio_playback": {"type": "string", "enum": ["auto", "local", "none"], "default": "auto", "description": "auto = play locally when remote_host is loopback"},
                            "audio_device": {"type": "string", "description": "Output device for local playback (default 'VoiceMeeter Input')"},
                            "chatbox_transcripts": {"type": "boolean", "default": false, "description": "Show play_audio text in the VRChat chatbox"}
                        }
                    }
                },
                "required": ["backend"]
            }),
            ToolKind::SendAnimation => json!({"type": "object", "properties": animation_props}),
            ToolKind::ExecuteBehavior => json!({
                "type": "object",
                "properties": {
                    "behavior": {"type": "string", "enum": SUPPORTED_BEHAVIORS, "description": "Behavior to execute"},
                    "parameters": {"type": "object", "description": "Behavior parameters (currently unused)"}
                },
                "required": ["behavior"]
            }),
            ToolKind::PlayAudio => json!({
                "type": "object",
                "properties": {
                    "audio_data": {"type": "string", "description": "File path, http(s) URL, data URL, or base64-encoded audio"},
                    "audio_format": {"type": "string", "enum": ["mp3", "wav", "opus", "ogg", "flac", "pcm"], "default": "mp3", "description": "Declared format (magic bytes take precedence; pcm = 16-bit mono little-endian)"},
                    "sample_rate": {"type": "integer", "default": 44100, "description": "Sample rate for pcm input"},
                    "text": {"type": "string", "description": "Transcript; [tags] inside it drive expression when expression_tags is omitted"},
                    "expression_tags": {"type": "array", "items": {"type": "string"}, "description": "ElevenLabs audio tags like [laughs], [whisper]"},
                    "duration": {"type": "number", "description": "Audio duration in seconds (estimated from WAV/MP3 headers if omitted)"}
                },
                "required": ["audio_data"]
            }),
            ToolKind::CreateSequence => json!({
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Sequence name"},
                    "description": {"type": "string"},
                    "loop": {"type": "boolean", "default": false},
                    "interrupt_current": {"type": "boolean", "default": true, "description": "Stop any sequence that is currently playing"}
                },
                "required": ["name"]
            }),
            ToolKind::AddSequenceEvent => {
                let event_types = [
                    "animation",
                    "audio",
                    "wait",
                    "expression",
                    "movement",
                    "parallel",
                ];
                json!({
                    "type": "object",
                    "properties": {
                        "event_type": {"type": "string", "enum": event_types},
                        "timestamp": {"type": "number", "minimum": 0, "description": "Seconds from sequence start"},
                        "duration": {"type": "number", "minimum": 0, "description": "Event length (audio defaults to the clip length)"},
                        "animation_params": {"type": "object", "properties": animation_props, "description": "animation: emotion/gesture/parameters/blend_shapes"},
                        "audio_data": {"type": "string", "description": "audio: file path, URL, data URL or base64"},
                        "audio_format": {"type": "string", "enum": ["mp3", "wav", "opus", "ogg", "flac", "pcm"]},
                        "text": {"type": "string", "description": "audio: transcript ([tags] drive expression)"},
                        "expression_tags": {"type": "array", "items": {"type": "string"}},
                        "wait_duration": {"type": "number", "minimum": 0, "description": "wait: seconds (extends the sequence length)"},
                        "expression": {"type": "string", "enum": emotions, "description": "expression: emotion to show"},
                        "expression_intensity": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0},
                        "movement_params": movement,
                        "parallel_events": {"type": "array", "items": {"type": "object"}, "description": "parallel: child events (same fields; they inherit this timestamp)"}
                    },
                    "required": ["event_type", "timestamp"]
                })
            },
            ToolKind::PlaySequence => json!({
                "type": "object",
                "properties": {
                    "start_time": {"type": "number", "minimum": 0, "default": 0, "description": "Start offset in seconds (earlier events are skipped)"}
                }
            }),
            ToolKind::SendVRCEmote => json!({
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
            }),
            ToolKind::DisconnectBackend
            | ToolKind::Reset
            | ToolKind::GetBackendStatus
            | ToolKind::ListBackends
            | ToolKind::GetAvatarState
            | ToolKind::PauseSequence
            | ToolKind::ResumeSequence
            | ToolKind::StopSequence
            | ToolKind::GetSequenceStatus
            | ToolKind::PanicReset => empty,
        }
    }
}

/// A tool bound to the shared state.
struct VcTool {
    kind: ToolKind,
    state: Arc<ServerState>,
}

#[async_trait]
impl Tool for VcTool {
    fn name(&self) -> &str {
        self.kind.name()
    }

    fn description(&self) -> &str {
        self.kind.description()
    }

    fn schema(&self) -> Value {
        self.kind.schema()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let s = &self.state;
        let result = match self.kind {
            ToolKind::SetBackend => match parse_args(args) {
                Ok(a) => set_backend(s, a).await,
                Err(e) => Err(e),
            },
            ToolKind::DisconnectBackend => disconnect_backend(s).await,
            ToolKind::SendAnimation => match parse_args(args) {
                Ok(a) => send_animation(s, a).await,
                Err(e) => Err(e),
            },
            ToolKind::ExecuteBehavior => match parse_args(args) {
                Ok(a) => execute_behavior(s, a).await,
                Err(e) => Err(e),
            },
            ToolKind::Reset => reset(s).await,
            ToolKind::GetBackendStatus => get_backend_status(s).await,
            ToolKind::ListBackends => list_backends(s).await,
            ToolKind::GetAvatarState => get_avatar_state(s).await,
            ToolKind::PlayAudio => match parse_args(args) {
                Ok(a) => play_audio(s, a).await,
                Err(e) => Err(e),
            },
            ToolKind::CreateSequence => match parse_args(args) {
                Ok(a) => create_sequence(s, a).await,
                Err(e) => Err(e),
            },
            ToolKind::AddSequenceEvent => match parse_args::<EventSpec>(args) {
                Ok(a) => add_sequence_event(s, a).await,
                Err(e) => Err(e),
            },
            ToolKind::PlaySequence => match parse_args(args) {
                Ok(a) => play_sequence(s, a).await,
                Err(e) => Err(e),
            },
            ToolKind::PauseSequence => s
                .sequences
                .pause()
                .await
                .map(|()| json!({"success": true, "message": "Sequence paused"}))
                .map_err(|e| e.to_string()),
            ToolKind::ResumeSequence => s
                .sequences
                .resume()
                .await
                .map(|()| json!({"success": true, "message": "Sequence resumed"}))
                .map_err(|e| e.to_string()),
            ToolKind::StopSequence => {
                let was_playing = s.sequences.stop().await;
                Ok(json!({
                    "success": true,
                    "was_playing": was_playing,
                    "message": if was_playing { "Sequence stopped" } else { "No sequence was playing" }
                }))
            },
            ToolKind::GetSequenceStatus => Ok(json!({
                "success": true,
                "status": s.sequences.status().await
            })),
            ToolKind::PanicReset => panic_reset(s).await,
            ToolKind::SendVRCEmote => match parse_args(args) {
                Ok(a) => send_vrcemote(s, a).await,
                Err(e) => Err(e),
            },
        };
        match result {
            Ok(v) => ToolResult::json(&v),
            Err(e) => Ok(ToolResult::error(e)),
        }
    }
}

type ToolOutcome = std::result::Result<Value, String>;

// =============================================================================
// Backend management
// =============================================================================

#[derive(Debug, Deserialize)]
struct SetBackendArgs {
    backend: String,
    config: Option<Value>,
}

async fn set_backend(s: &ServerState, a: SetBackendArgs) -> ToolOutcome {
    let name = a.backend.trim().to_string();
    let Some(mut new_backend) = create_backend(&name) else {
        return Err(format!(
            "Unknown backend '{}'. Available: {}",
            name,
            BACKEND_NAMES.join(", ")
        ));
    };
    let config: HashMap<String, Value> = match a.config {
        None | Some(Value::Null) => HashMap::new(),
        Some(Value::Object(m)) => m.into_iter().collect(),
        Some(other) => return Err(format!("config must be an object, got {other}")),
    };

    info!("Setting backend to: {}", name);
    // Playback references the backend slot; stop it before swapping.
    s.sequences.stop().await;

    let mut slot = s.backend.write().await;
    if let Some(mut old) = slot.take() {
        if let Err(e) = old.disconnect().await {
            warn!("Error disconnecting previous backend: {}", e);
        }
    }
    *s.backend_name.write().await = None;

    new_backend
        .connect(config)
        .await
        .map_err(|e| format!("Failed to connect to {}: {}", name, e))?;
    let stats = new_backend.get_statistics().await.unwrap_or_default();
    *slot = Some(new_backend);
    *s.backend_name.write().await = Some(name.clone());

    Ok(json!({
        "success": true,
        "backend": name,
        "message": format!("Connected to {}", name),
        "statistics": stats
    }))
}

async fn disconnect_backend(s: &ServerState) -> ToolOutcome {
    s.sequences.stop().await;
    let old = s.backend.write().await.take();
    let name = s.backend_name.write().await.take();
    match old {
        Some(mut b) => {
            b.disconnect()
                .await
                .map_err(|e| format!("Error while disconnecting: {e}"))?;
            Ok(
                json!({"success": true, "message": format!("Disconnected from {}", name.unwrap_or_default())}),
            )
        },
        None => Ok(json!({"success": true, "message": "No backend was connected"})),
    }
}

async fn get_backend_status(s: &ServerState) -> ToolOutcome {
    let guard = s.backend.read().await;
    let name = s.backend_name.read().await.clone();
    match guard.as_ref() {
        Some(b) => {
            let health = b.health_check().await.unwrap_or_default();
            let stats = b.get_statistics().await.unwrap_or_default();
            Ok(json!({
                "success": true,
                "backend": name,
                "connected": b.is_connected(),
                "health": health,
                "statistics": stats
            }))
        },
        None => Ok(json!({
            "success": true,
            "backend": null,
            "connected": false,
            "message": "No backend connected"
        })),
    }
}

async fn list_backends(s: &ServerState) -> ToolOutcome {
    let current = s.backend_name.read().await.clone();
    let describe = |n: &str| match n {
        "mock" => "In-memory backend for testing; records animation/audio without playing it",
        "vrchat_remote" => "VRChat avatar control over OSC (UDP)",
        _ => "",
    };
    let backends: Vec<Value> = BACKEND_NAMES
        .iter()
        .map(|n| {
            json!({
                "name": n,
                "description": describe(n),
                "active": current.as_deref() == Some(*n)
            })
        })
        .collect();
    Ok(json!({"success": true, "backends": backends}))
}

async fn get_avatar_state(s: &ServerState) -> ToolOutcome {
    let guard = s.backend.read().await;
    let b = match guard.as_ref() {
        Some(b) if b.is_connected() => b,
        _ => return Err("No backend connected. Use set_backend first.".to_string()),
    };
    let env = b.receive_state().await.map_err(|e| e.to_string())?;
    let params = b.avatar_parameters().await.map_err(|e| e.to_string())?;
    let stats = b.get_statistics().await.unwrap_or_default();
    let mut sorted: Vec<(&String, &Value)> = params.iter().collect();
    sorted.sort_by(|a, b| a.0.cmp(b.0));
    let params_obj: serde_json::Map<String, Value> = sorted
        .into_iter()
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    Ok(json!({
        "success": true,
        "backend": b.backend_name(),
        "environment": env,
        "avatar_id": stats.get("avatar_id").cloned().unwrap_or(Value::Null),
        "current_emotion": stats.get("current_emotion").cloned().unwrap_or(Value::Null),
        "current_gesture": stats.get("current_gesture").cloned().unwrap_or(Value::Null),
        "avatar_parameters": params_obj,
        "vrchat_responding": stats.get("vrchat_responding").cloned().unwrap_or(Value::Null)
    }))
}

// =============================================================================
// Animation / behavior / emotes
// =============================================================================

async fn send_animation(s: &ServerState, a: AnimationSpec) -> ToolOutcome {
    if a.is_empty() {
        return Err(
            "Nothing to send: provide emotion, gesture, parameters or blend_shapes".to_string(),
        );
    }
    let anim = a.to_canonical(unix_secs_f64())?;
    let mut guard = s.backend.write().await;
    let backend = connected_mut(&mut guard)?;
    backend
        .send_animation_data(anim)
        .await
        .map_err(|e| format!("Failed to send animation: {e}"))?;
    Ok(json!({
        "success": true,
        "emotion": a.emotion,
        "gesture": a.gesture,
        "message": "Animation sent"
    }))
}

#[derive(Debug, Deserialize)]
struct BehaviorArgs {
    behavior: String,
    parameters: Option<HashMap<String, Value>>,
}

async fn execute_behavior(s: &ServerState, a: BehaviorArgs) -> ToolOutcome {
    let behavior = a.behavior.trim().to_lowercase();
    if !SUPPORTED_BEHAVIORS.contains(&behavior.as_str()) {
        return Err(format!(
            "Unknown behavior '{}'. Supported: {}",
            a.behavior,
            SUPPORTED_BEHAVIORS.join(", ")
        ));
    }
    let mut guard = s.backend.write().await;
    let backend = connected_mut(&mut guard)?;
    backend
        .execute_behavior(&behavior, a.parameters.unwrap_or_default())
        .await
        .map_err(|e| format!("Failed to execute behavior: {e}"))?;
    Ok(json!({"success": true, "behavior": behavior}))
}

async fn reset(s: &ServerState) -> ToolOutcome {
    let mut guard = s.backend.write().await;
    let backend = connected_mut(&mut guard)?;
    backend
        .reset_all()
        .await
        .map_err(|e| format!("Failed to reset: {e}"))?;
    Ok(json!({"success": true, "message": "All states reset"}))
}

#[derive(Debug, Deserialize)]
struct VrcEmoteArgs {
    emote_value: i64,
}

async fn send_vrcemote(s: &ServerState, a: VrcEmoteArgs) -> ToolOutcome {
    let value = a.emote_value;
    if !(VRCEmoteValue::MIN as i64..=VRCEmoteValue::MAX as i64).contains(&value) {
        return Err(format!(
            "VRCEmote value must be between {} and {}",
            VRCEmoteValue::MIN,
            VRCEmoteValue::MAX
        ));
    }
    let value = value as i32;
    let mut guard = s.backend.write().await;
    let backend = connected_mut(&mut guard)?;
    let action = backend
        .send_vrcemote(value)
        .await
        .map_err(|e| format!("Failed to send VRCEmote: {e}"))?;
    let gesture_name = get_vrcemote_name(value);
    Ok(json!({
        "success": true,
        "emote_value": value,
        "gesture": gesture_name,
        "action": action,
        "message": format!("VRCEmote {} ({}): {:?}", value, gesture_name, action)
    }))
}

async fn panic_reset(s: &ServerState) -> ToolOutcome {
    s.sequences.clear().await;
    let mut guard = s.backend.write().await;
    let mut warnings = Vec::new();
    let mut backend_reset = false;
    if let Some(b) = guard.as_mut() {
        if b.is_connected() {
            match b.reset_all().await {
                Ok(()) => backend_reset = true,
                Err(e) => warnings.push(format!("backend reset failed: {e}")),
            }
        }
    }
    Ok(json!({
        "success": warnings.is_empty(),
        "backend_reset": backend_reset,
        "warnings": warnings,
        "message": "Emergency reset completed: sequences stopped and cleared"
    }))
}

// =============================================================================
// Audio
// =============================================================================

#[derive(Debug, Deserialize)]
struct PlayAudioArgs {
    audio_data: String,
    audio_format: Option<String>,
    sample_rate: Option<u32>,
    text: Option<String>,
    expression_tags: Option<Vec<String>>,
    duration: Option<f64>,
}

async fn play_audio(s: &ServerState, a: PlayAudioArgs) -> ToolOutcome {
    // Fail fast before loading/downloading audio.
    {
        let mut guard = s.backend.write().await;
        connected_mut(&mut guard)?;
    }
    if let Some(d) = a.duration {
        if !d.is_finite() || d <= 0.0 || d > MAX_AUDIO_DURATION {
            return Err(format!(
                "duration must be between 0 and {MAX_AUDIO_DURATION} seconds"
            ));
        }
    }

    let mut clip = prepare_audio(
        &s.audio,
        &a.audio_data,
        a.audio_format.as_deref(),
        a.sample_rate,
    )
    .await?;
    if let Some(d) = a.duration {
        clip.duration = d as f32;
    }
    clip.text = a.text;
    clip.expression_tags = a.expression_tags;
    let bytes = clip.data.len();
    let format = clip.format.clone();
    let duration = clip.duration;

    let mut guard = s.backend.write().await;
    let backend = connected_mut(&mut guard)?;
    let outcome = backend
        .send_audio_data(clip)
        .await
        .map_err(|e| format!("Failed to play audio: {e}"))?;

    let message = if outcome.played {
        format!(
            "Playing {} audio via {}",
            format,
            outcome.method.as_deref().unwrap_or("player")
        )
    } else {
        "Audio metadata sent to backend (audio not played)".to_string()
    };
    Ok(json!({
        "success": true,
        "played": outcome.played,
        "method": outcome.method,
        "format": format,
        "bytes": bytes,
        "duration": if duration > 0.0 { json!((duration as f64 * 100.0).round() / 100.0) } else { Value::Null },
        "emotion": outcome.emotion,
        "notes": outcome.notes,
        "message": message
    }))
}

// =============================================================================
// Sequences
// =============================================================================

#[derive(Debug, Deserialize)]
struct CreateSequenceArgs {
    name: String,
    description: Option<String>,
    #[serde(rename = "loop", default)]
    loop_sequence: bool,
    #[serde(default = "default_true")]
    interrupt_current: bool,
}

fn default_true() -> bool {
    true
}

async fn create_sequence(s: &ServerState, a: CreateSequenceArgs) -> ToolOutcome {
    s.sequences
        .create_sequence(
            a.name.clone(),
            a.description,
            a.loop_sequence,
            a.interrupt_current,
            unix_secs_f64(),
        )
        .await
        .map_err(|e| e.to_string())?;
    Ok(json!({
        "success": true,
        "message": format!("Created sequence: {}", a.name.trim())
    }))
}

async fn add_sequence_event(s: &ServerState, spec: EventSpec) -> ToolOutcome {
    if spec.timestamp.is_none() {
        return Err("timestamp is required (seconds from sequence start)".to_string());
    }
    // Fail before loading audio if there is no sequence.
    if !s.sequences.status().await.has_sequence {
        return Err("No sequence created. Use create_sequence first.".to_string());
    }
    let event = build_event(&spec, &s.audio, None, 0).await?;
    let event_type = event.event_type;
    let timestamp = event.timestamp;
    let duration = event.duration;
    let count = s
        .sequences
        .add_event(event)
        .await
        .map_err(|e| e.to_string())?;
    let status = s.sequences.status().await;
    Ok(json!({
        "success": true,
        "event_count": count,
        "total_duration": status.total_duration,
        "event_duration": duration,
        "message": format!("Added {} event at {}s", event_type_name(event_type), timestamp)
    }))
}

fn event_type_name(t: EventType) -> &'static str {
    match t {
        EventType::Animation => "animation",
        EventType::Audio => "audio",
        EventType::Wait => "wait",
        EventType::LoopStart => "loop_start",
        EventType::LoopEnd => "loop_end",
        EventType::Parallel => "parallel",
        EventType::Expression => "expression",
        EventType::Movement => "movement",
    }
}

#[derive(Debug, Deserialize)]
struct PlaySequenceArgs {
    #[serde(default)]
    start_time: f64,
}

async fn play_sequence(s: &ServerState, a: PlaySequenceArgs) -> ToolOutcome {
    {
        let mut guard = s.backend.write().await;
        connected_mut(&mut guard)?;
    }
    let name = s
        .sequences
        .play(s.backend.clone(), a.start_time)
        .await
        .map_err(|e| e.to_string())?;
    let status = s.sequences.status().await;
    Ok(json!({
        "success": true,
        "message": format!("Started playing sequence: {}", name),
        "total_duration": status.total_duration,
        "loop": status.loop_enabled
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audio::pcm_to_wav;
    use base64::Engine;
    use mcp_core::tool::Content;
    use std::time::Duration;

    fn response_json(result: &ToolResult) -> Value {
        match &result.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap_or(json!(text)),
            _ => panic!("Expected text content"),
        }
    }

    fn error_text(result: &ToolResult) -> String {
        assert!(result.is_error, "expected error, got {:?}", result);
        match &result.content[0] {
            Content::Text { text } => text.clone(),
            _ => panic!("Expected text content"),
        }
    }

    struct Harness {
        tools: Vec<BoxedTool>,
    }

    impl Harness {
        fn new() -> Self {
            Self {
                tools: VirtualCharacterServer::new().tools(),
            }
        }

        async fn call(&self, name: &str, args: Value) -> ToolResult {
            let tool = self
                .tools
                .iter()
                .find(|t| t.name() == name)
                .unwrap_or_else(|| panic!("no tool {name}"));
            tool.execute(args).await.unwrap()
        }

        async fn ok(&self, name: &str, args: Value) -> Value {
            let r = self.call(name, args).await;
            assert!(!r.is_error, "{name} failed: {:?}", r.content);
            response_json(&r)
        }

        async fn mock(self) -> Self {
            self.ok("set_backend", json!({"backend": "mock"})).await;
            self
        }
    }

    fn wav_b64(seconds: f64) -> String {
        let wav = pcm_to_wav(&vec![0u8; (44_100.0 * seconds) as usize * 2], 44_100, 1);
        base64::engine::general_purpose::STANDARD.encode(wav)
    }

    #[tokio::test]
    async fn test_tool_names_and_schemas() {
        let h = Harness::new();
        assert_eq!(h.tools.len(), 18);
        let expected = [
            "set_backend",
            "disconnect_backend",
            "send_animation",
            "execute_behavior",
            "reset",
            "get_backend_status",
            "list_backends",
            "get_avatar_state",
            "play_audio",
            "create_sequence",
            "add_sequence_event",
            "play_sequence",
            "pause_sequence",
            "resume_sequence",
            "stop_sequence",
            "get_sequence_status",
            "panic_reset",
            "send_vrcemote",
        ];
        for name in expected {
            let tool = h.tools.iter().find(|t| t.name() == name);
            assert!(tool.is_some(), "Missing tool: {name}");
            let schema = tool.unwrap().schema();
            assert_eq!(schema["type"], "object", "{name}");
            assert!(schema["properties"].is_object(), "{name}");
            assert!(!tool.unwrap().description().is_empty());
        }
    }

    #[tokio::test]
    async fn test_set_backend_mock_and_unknown() {
        let h = Harness::new();
        let r = h.ok("set_backend", json!({"backend": "mock"})).await;
        assert_eq!(r["backend"], "mock");
        let err = error_text(&h.call("set_backend", json!({"backend": "unity"})).await);
        assert!(err.contains("Available: mock, vrchat_remote"));
        // An unknown backend must not disconnect the current one.
        let status = h.ok("get_backend_status", json!({})).await;
        assert_eq!(status["connected"], true);
        // Missing required argument is a clean error.
        assert!(h.call("set_backend", json!({})).await.is_error);
        assert!(
            h.call("set_backend", json!({"backend": "mock", "config": 5}))
                .await
                .is_error
        );
    }

    #[tokio::test]
    async fn test_vrchat_config_errors_leave_no_backend() {
        let h = Harness::new().mock().await;
        let err = error_text(
            &h.call(
                "set_backend",
                json!({"backend": "vrchat_remote", "config": {"osc_in_port": 70000}}),
            )
            .await,
        );
        assert!(err.contains("osc_in_port"), "{err}");
        let status = h.ok("get_backend_status", json!({})).await;
        assert_eq!(status["connected"], false);
        assert!(h.call("reset", json!({})).await.is_error);
    }

    #[tokio::test]
    async fn test_list_backends_marks_active() {
        let h = Harness::new().mock().await;
        let r = h.ok("list_backends", json!({})).await;
        let backends = r["backends"].as_array().unwrap();
        assert_eq!(backends.len(), 2);
        assert_eq!(backends[0]["name"], "mock");
        assert_eq!(backends[0]["active"], true);
        assert_eq!(backends[1]["active"], false);
    }

    #[tokio::test]
    async fn test_not_connected_errors() {
        let h = Harness::new();
        for (tool, args) in [
            ("send_animation", json!({"emotion": "happy"})),
            ("reset", json!({})),
            ("execute_behavior", json!({"behavior": "greet"})),
            ("send_vrcemote", json!({"emote_value": 1})),
            ("get_avatar_state", json!({})),
            ("play_audio", json!({"audio_data": wav_b64(0.1)})),
        ] {
            let err = error_text(&h.call(tool, args).await);
            assert!(err.contains("set_backend"), "{tool}: {err}");
        }
        let status = h.ok("get_backend_status", json!({})).await;
        assert_eq!(status["connected"], false);
    }

    #[tokio::test]
    async fn test_send_animation_validation() {
        let h = Harness::new().mock().await;
        let r = h
            .ok(
                "send_animation",
                json!({"emotion": "happy", "emotion_intensity": 0.8, "gesture": "wave"}),
            )
            .await;
        assert_eq!(r["success"], true);
        assert!(error_text(
            &h.call("send_animation", json!({"emotion": "gleeful"}))
                .await
        )
        .contains("Valid emotions"));
        assert!(
            h.call(
                "send_animation",
                json!({"emotion": "happy", "emotion_intensity": "high"})
            )
            .await
            .is_error
        );
        assert!(h.call("send_animation", json!({})).await.is_error);
        assert!(
            h.call(
                "send_animation",
                json!({"parameters": {"move_forward": "fast"}})
            )
            .await
            .is_error
        );
        h.ok(
            "send_animation",
            json!({"parameters": {"move_forward": 0.5, "duration": 1}}),
        )
        .await;
        let status = h.ok("get_backend_status", json!({})).await;
        assert_eq!(status["statistics"]["frames_sent"], 2);
    }

    #[tokio::test]
    async fn test_behaviors_and_vrcemote() {
        let h = Harness::new().mock().await;
        h.ok("execute_behavior", json!({"behavior": "greet"})).await;
        let err = error_text(
            &h.call("execute_behavior", json!({"behavior": "moonwalk"}))
                .await,
        );
        assert!(err.contains("Supported"));
        // Mock does not support VRCEmote.
        let err = error_text(&h.call("send_vrcemote", json!({"emote_value": 5})).await);
        assert!(err.contains("vrchat_remote"));
        assert!(
            h.call("send_vrcemote", json!({"emote_value": 12}))
                .await
                .is_error
        );
        assert!(
            h.call("send_vrcemote", json!({"emote_value": "x"}))
                .await
                .is_error
        );
    }

    #[tokio::test]
    async fn test_play_audio_on_mock() {
        let h = Harness::new().mock().await;
        let r = h
            .ok(
                "play_audio",
                json!({"audio_data": wav_b64(0.5), "audio_format": "mp3", "text": "[laughs] hello"}),
            )
            .await;
        assert_eq!(r["format"], "wav"); // detected from magic bytes
        assert_eq!(r["played"], false);
        assert_eq!(r["emotion"], "happy");
        assert_eq!(r["duration"], 0.5);

        let err = error_text(
            &h.call("play_audio", json!({"audio_data": "not audio at all"}))
                .await,
        );
        assert!(err.contains("base64") || err.contains("small"), "{err}");
        assert!(
            h.call(
                "play_audio",
                json!({"audio_data": wav_b64(0.1), "duration": -1})
            )
            .await
            .is_error
        );
        assert!(h.call("play_audio", json!({})).await.is_error);
    }

    #[tokio::test]
    async fn test_sequence_workflow_plays_on_backend() {
        let h = Harness::new().mock().await;
        assert!(
            h.call(
                "add_sequence_event",
                json!({"event_type": "expression", "timestamp": 0.0, "expression": "happy"})
            )
            .await
            .is_error
        );
        h.ok(
            "create_sequence",
            json!({"name": "greeting", "description": "hi"}),
        )
        .await;
        h.ok(
            "add_sequence_event",
            json!({"event_type": "expression", "timestamp": 0.0, "expression": "happy"}),
        )
        .await;
        h.ok(
            "add_sequence_event",
            json!({"event_type": "animation", "timestamp": 0.05, "animation_params": {"gesture": "wave"}}),
        )
        .await;
        let r = h
            .ok(
                "add_sequence_event",
                json!({"event_type": "audio", "timestamp": 0.1, "audio_data": wav_b64(0.1)}),
            )
            .await;
        assert_eq!(r["event_count"], 3);
        assert!((r["total_duration"].as_f64().unwrap() - 0.2).abs() < 0.01);
        assert!(
            h.call(
                "add_sequence_event",
                json!({"event_type": "expression", "expression": "happy"})
            )
            .await
            .is_error
        ); // missing timestamp

        h.ok("play_sequence", json!({})).await;
        tokio::time::sleep(Duration::from_millis(500)).await;
        let status = h.ok("get_sequence_status", json!({})).await;
        assert_eq!(status["status"]["events_executed"], 3, "{status}");
        assert_eq!(status["status"]["is_playing"], false);
        let backend = h.ok("get_backend_status", json!({})).await;
        assert_eq!(backend["statistics"]["frames_sent"], 2);
        assert_eq!(backend["statistics"]["audio_sent"], 1);
    }

    #[tokio::test]
    async fn test_sequence_controls() {
        let h = Harness::new().mock().await;
        assert!(h.call("pause_sequence", json!({})).await.is_error);
        assert!(h.call("resume_sequence", json!({})).await.is_error);
        let r = h.ok("stop_sequence", json!({})).await;
        assert_eq!(r["was_playing"], false);

        h.ok("create_sequence", json!({"name": "long"})).await;
        h.ok(
            "add_sequence_event",
            json!({"event_type": "wait", "timestamp": 0, "wait_duration": 5}),
        )
        .await;
        h.ok("play_sequence", json!({})).await;
        h.ok("pause_sequence", json!({})).await;
        let st = h.ok("get_sequence_status", json!({})).await;
        assert_eq!(st["status"]["is_paused"], true);
        h.ok("resume_sequence", json!({})).await;
        let r = h.ok("stop_sequence", json!({})).await;
        assert_eq!(r["was_playing"], true);
        assert!(
            h.call("play_sequence", json!({"start_time": 99}))
                .await
                .is_error
        );
    }

    #[tokio::test]
    async fn test_panic_reset_clears_everything() {
        let h = Harness::new().mock().await;
        h.ok("create_sequence", json!({"name": "test"})).await;
        h.ok(
            "add_sequence_event",
            json!({"event_type": "wait", "timestamp": 0, "wait_duration": 5}),
        )
        .await;
        h.ok("play_sequence", json!({})).await;
        let r = h.ok("panic_reset", json!({})).await;
        assert_eq!(r["success"], true);
        assert_eq!(r["backend_reset"], true);
        let st = h.ok("get_sequence_status", json!({})).await;
        assert_eq!(st["status"]["has_sequence"], false);
        assert_eq!(st["status"]["is_playing"], false);
        // Works without a backend too.
        let h2 = Harness::new();
        let r = h2.ok("panic_reset", json!({})).await;
        assert_eq!(r["backend_reset"], false);
    }

    #[tokio::test]
    async fn test_disconnect_and_avatar_state() {
        let h = Harness::new().mock().await;
        let st = h.ok("get_avatar_state", json!({})).await;
        assert_eq!(st["environment"]["world_name"], "MockWorld");
        assert_eq!(st["avatar_parameters"]["emotion"], "neutral");
        h.ok("disconnect_backend", json!({})).await;
        assert!(h.call("get_avatar_state", json!({})).await.is_error);
        let r = h.ok("disconnect_backend", json!({})).await;
        assert_eq!(r["message"], "No backend was connected");
        let list = h.ok("list_backends", json!({})).await;
        assert_eq!(list["backends"][0]["active"], false);
    }
}

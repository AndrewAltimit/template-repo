//! Canonical data models for virtual character animation.
//!
//! These models provide a universal representation that all backend
//! adapters can translate to their specific formats.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Standard emotion types.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum EmotionType {
    #[default]
    Neutral,
    Happy,
    Sad,
    Angry,
    Surprised,
    Fearful,
    Disgusted,
    Contemptuous,
    Excited,
    Calm,
}

impl EmotionType {
    /// Get PAD vector for this emotion.
    pub fn to_pad_vector(self) -> EmotionVector {
        match self {
            EmotionType::Neutral => EmotionVector::new(0.0, 0.0, 0.0),
            EmotionType::Happy => EmotionVector::new(0.8, 0.5, 0.2),
            EmotionType::Sad => EmotionVector::new(-0.7, -0.3, -0.4),
            EmotionType::Angry => EmotionVector::new(-0.6, 0.8, 0.6),
            EmotionType::Surprised => EmotionVector::new(0.2, 0.8, -0.1),
            EmotionType::Fearful => EmotionVector::new(-0.7, 0.7, -0.6),
            EmotionType::Disgusted => EmotionVector::new(-0.6, 0.2, 0.3),
            EmotionType::Contemptuous => EmotionVector::new(-0.3, 0.1, 0.7),
            EmotionType::Excited => EmotionVector::new(0.8, 0.9, 0.3),
            EmotionType::Calm => EmotionVector::new(0.3, -0.6, 0.1),
        }
    }
}

impl std::str::FromStr for EmotionType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "neutral" => Ok(EmotionType::Neutral),
            "happy" => Ok(EmotionType::Happy),
            "sad" => Ok(EmotionType::Sad),
            "angry" => Ok(EmotionType::Angry),
            "surprised" => Ok(EmotionType::Surprised),
            "fearful" => Ok(EmotionType::Fearful),
            "disgusted" => Ok(EmotionType::Disgusted),
            "contemptuous" => Ok(EmotionType::Contemptuous),
            "excited" => Ok(EmotionType::Excited),
            "calm" => Ok(EmotionType::Calm),
            _ => Err(format!("Unknown emotion type: {}", s)),
        }
    }
}

/// PAD (Pleasure, Arousal, Dominance) model for smooth emotion interpolation.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct EmotionVector {
    /// -1 (unhappy/unpleasant) to +1 (happy/pleasant)
    pub pleasure: f32,
    /// -1 (calm/sleepy) to +1 (excited/energized)
    pub arousal: f32,
    /// -1 (submissive/controlled) to +1 (dominant/controlling)
    pub dominance: f32,
}

impl EmotionVector {
    /// Create a new emotion vector with clamped values.
    pub fn new(pleasure: f32, arousal: f32, dominance: f32) -> Self {
        Self {
            pleasure: pleasure.clamp(-1.0, 1.0),
            arousal: arousal.clamp(-1.0, 1.0),
            dominance: dominance.clamp(-1.0, 1.0),
        }
    }

    /// Create a neutral emotion vector.
    pub fn neutral() -> Self {
        Self::new(0.0, 0.0, 0.0)
    }

    /// Linear interpolation for smooth transitions.
    pub fn lerp(&self, target: &EmotionVector, t: f32) -> EmotionVector {
        let t = t.clamp(0.0, 1.0);
        EmotionVector::new(
            self.pleasure + (target.pleasure - self.pleasure) * t,
            self.arousal + (target.arousal - self.arousal) * t,
            self.dominance + (target.dominance - self.dominance) * t,
        )
    }

    /// Euclidean distance to another emotion vector.
    pub fn distance(&self, other: &EmotionVector) -> f32 {
        ((self.pleasure - other.pleasure).powi(2)
            + (self.arousal - other.arousal).powi(2)
            + (self.dominance - other.dominance).powi(2))
        .sqrt()
    }

    /// Scale emotion vector by intensity.
    pub fn scale(&self, intensity: f32) -> EmotionVector {
        let intensity = intensity.clamp(0.0, 1.0);
        EmotionVector::new(
            self.pleasure * intensity,
            self.arousal * intensity,
            self.dominance * intensity,
        )
    }

    /// Calculate magnitude (intensity) of this emotion vector.
    pub fn magnitude(&self) -> f32 {
        (self.pleasure.powi(2) + self.arousal.powi(2) + self.dominance.powi(2)).sqrt()
    }
}

impl Default for EmotionVector {
    fn default() -> Self {
        Self::neutral()
    }
}

/// Standard gesture types.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum GestureType {
    #[default]
    None,
    Wave,
    Point,
    ThumbsUp,
    ThumbsDown,
    Clap,
    Nod,
    ShakeHead,
    Shrug,
    CrossedArms,
    Thinking,
    Dance,
    Backflip,
    Cheer,
    Die,
    Sadness,
}

impl std::str::FromStr for GestureType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "none" => Ok(GestureType::None),
            "wave" => Ok(GestureType::Wave),
            "point" => Ok(GestureType::Point),
            "thumbs_up" => Ok(GestureType::ThumbsUp),
            "thumbs_down" => Ok(GestureType::ThumbsDown),
            "clap" => Ok(GestureType::Clap),
            "nod" => Ok(GestureType::Nod),
            "shake_head" => Ok(GestureType::ShakeHead),
            "shrug" => Ok(GestureType::Shrug),
            "crossed_arms" => Ok(GestureType::CrossedArms),
            "thinking" => Ok(GestureType::Thinking),
            "dance" => Ok(GestureType::Dance),
            "backflip" => Ok(GestureType::Backflip),
            "cheer" => Ok(GestureType::Cheer),
            "die" => Ok(GestureType::Die),
            "sadness" => Ok(GestureType::Sadness),
            _ => Err(format!("Unknown gesture type: {}", s)),
        }
    }
}

/// Standard viseme set for lip-sync.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum VisemeType {
    Neutral,
    Aa,
    Ee,
    Ih,
    Oh,
    Uh,
    Mm,
    Fv,
    Th,
    L,
    R,
    Sz,
    Sh,
    Ng,
}

/// 3D vector for position, velocity, etc.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct Vector3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

impl Vector3 {
    pub fn new(x: f32, y: f32, z: f32) -> Self {
        Self { x, y, z }
    }

    pub fn to_array(self) -> [f32; 3] {
        [self.x, self.y, self.z]
    }
}

/// Quaternion for rotations.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Quaternion {
    pub w: f32,
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

impl Default for Quaternion {
    fn default() -> Self {
        Self {
            w: 1.0,
            x: 0.0,
            y: 0.0,
            z: 0.0,
        }
    }
}

impl Quaternion {
    pub fn identity() -> Self {
        Self::default()
    }

    pub fn to_array(self) -> [f32; 4] {
        [self.w, self.x, self.y, self.z]
    }
}

/// Complete 3D transform.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Transform {
    pub position: Vector3,
    pub rotation: Quaternion,
    pub scale: Vector3,
}

impl Transform {
    pub fn new() -> Self {
        Self {
            position: Vector3::default(),
            rotation: Quaternion::identity(),
            scale: Vector3::new(1.0, 1.0, 1.0),
        }
    }
}

/// Character locomotion state.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LocomotionState {
    pub velocity: Vector3,
    pub is_grounded: bool,
    pub movement_mode: String,
    pub direction: Vector3,
    pub speed: f32,
}

/// Universal animation data format.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CanonicalAnimationData {
    pub timestamp: f64,

    /// Skeletal animation
    #[serde(default)]
    pub bone_transforms: HashMap<String, Transform>,

    /// Facial animation
    #[serde(default)]
    pub blend_shapes: HashMap<String, f32>,

    /// Visemes for lip-sync
    #[serde(default)]
    pub visemes: HashMap<VisemeType, f32>,

    /// High-level states
    pub emotion: Option<EmotionType>,
    #[serde(default = "default_intensity")]
    pub emotion_intensity: f32,
    pub gesture: Option<GestureType>,
    #[serde(default = "default_intensity")]
    pub gesture_intensity: f32,

    /// Procedural parameters (backend-specific)
    #[serde(default)]
    pub parameters: HashMap<String, serde_json::Value>,

    /// Locomotion
    pub locomotion: Option<LocomotionState>,

    /// Audio sync
    pub audio_timestamp: Option<f64>,
}

fn default_intensity() -> f32 {
    1.0
}

impl CanonicalAnimationData {
    pub fn new(timestamp: f64) -> Self {
        Self {
            timestamp,
            emotion_intensity: 1.0,
            gesture_intensity: 1.0,
            ..Default::default()
        }
    }

    pub fn with_emotion(mut self, emotion: EmotionType, intensity: f32) -> Self {
        self.emotion = Some(emotion);
        self.emotion_intensity = intensity;
        self
    }

    pub fn with_gesture(mut self, gesture: GestureType, intensity: f32) -> Self {
        self.gesture = Some(gesture);
        self.gesture_intensity = intensity;
        self
    }

    pub fn with_parameters(mut self, params: HashMap<String, serde_json::Value>) -> Self {
        self.parameters = params;
        self
    }
}

/// Audio data with metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioData {
    #[serde(with = "base64_serde")]
    pub data: Vec<u8>,
    #[serde(default = "default_sample_rate")]
    pub sample_rate: u32,
    #[serde(default = "default_channels")]
    pub channels: u8,
    #[serde(default = "default_format")]
    pub format: String,
    #[serde(default)]
    pub duration: f32,

    /// Optional metadata
    pub text: Option<String>,
    pub language: Option<String>,
    pub voice: Option<String>,

    /// Lip sync and expression data
    pub viseme_timestamps: Option<Vec<(f32, String, f32)>>,
    pub expression_tags: Option<Vec<String>>,

    /// For streaming
    pub chunk_index: Option<u32>,
    pub total_chunks: Option<u32>,
    #[serde(default = "default_true")]
    pub is_final_chunk: bool,
}

fn default_sample_rate() -> u32 {
    44100
}
fn default_channels() -> u8 {
    1
}
fn default_format() -> String {
    "mp3".to_string()
}
fn default_true() -> bool {
    true
}

impl Default for AudioData {
    fn default() -> Self {
        Self {
            data: Vec::new(),
            sample_rate: 44100,
            channels: 1,
            format: "mp3".to_string(),
            duration: 0.0,
            text: None,
            language: None,
            voice: None,
            viseme_timestamps: None,
            expression_tags: None,
            chunk_index: None,
            total_chunks: None,
            is_final_chunk: true,
        }
    }
}

/// Base64 serialization helper module.
mod base64_serde {
    use base64::{engine::general_purpose::STANDARD, Engine};
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(bytes: &[u8], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&STANDARD.encode(bytes))
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Vec<u8>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        STANDARD.decode(&s).map_err(serde::de::Error::custom)
    }
}

/// Single video frame data.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoFrame {
    #[serde(with = "base64_serde")]
    pub data: Vec<u8>,
    pub width: u32,
    pub height: u32,
    #[serde(default = "default_video_format")]
    pub format: String,
    #[serde(default)]
    pub timestamp: f64,
    #[serde(default)]
    pub frame_number: u32,
}

fn default_video_format() -> String {
    "jpeg".to_string()
}

/// Virtual environment state information.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EnvironmentState {
    pub world_name: Option<String>,
    pub instance_id: Option<String>,

    /// Agent information
    pub agent_position: Option<Vector3>,
    pub agent_rotation: Option<Quaternion>,

    /// Nearby entities
    #[serde(default)]
    pub nearby_agents: Vec<HashMap<String, serde_json::Value>>,
    #[serde(default)]
    pub nearby_objects: Vec<HashMap<String, serde_json::Value>>,

    /// Interaction zones
    #[serde(default)]
    pub active_zones: Vec<String>,

    /// Environmental conditions
    pub time_of_day: Option<f32>,
    pub weather: Option<String>,
    pub ambient_audio: Option<String>,
}

/// Types of events in a sequence.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum EventType {
    Animation,
    Audio,
    Wait,
    LoopStart,
    LoopEnd,
    Parallel,
    Expression,
    Movement,
}

impl std::str::FromStr for EventType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "animation" => Ok(EventType::Animation),
            "audio" => Ok(EventType::Audio),
            "wait" => Ok(EventType::Wait),
            "loop_start" => Ok(EventType::LoopStart),
            "loop_end" => Ok(EventType::LoopEnd),
            "parallel" => Ok(EventType::Parallel),
            "expression" => Ok(EventType::Expression),
            "movement" => Ok(EventType::Movement),
            _ => Err(format!("Unknown event type: {}", s)),
        }
    }
}

/// Individual event in an event sequence.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SequenceEvent {
    pub event_type: EventType,
    pub timestamp: f64,
    pub duration: Option<f64>,

    /// Event-specific data
    pub animation_data: Option<CanonicalAnimationData>,
    pub audio_data: Option<AudioData>,
    pub wait_duration: Option<f64>,
    pub loop_count: Option<u32>,
    pub parallel_events: Option<Vec<SequenceEvent>>,

    /// For high-level events
    pub expression: Option<EmotionType>,
    pub expression_intensity: Option<f32>,
    pub movement_params: Option<HashMap<String, serde_json::Value>>,

    /// Sync settings
    #[serde(default)]
    pub sync_with_audio: bool,
    #[serde(default)]
    pub fade_in: f32,
    #[serde(default)]
    pub fade_out: f32,
}

impl SequenceEvent {
    pub fn new(event_type: EventType, timestamp: f64) -> Self {
        Self {
            event_type,
            timestamp,
            duration: None,
            animation_data: None,
            audio_data: None,
            wait_duration: None,
            loop_count: None,
            parallel_events: None,
            expression: None,
            expression_intensity: None,
            movement_params: None,
            sync_with_audio: false,
            fade_in: 0.0,
            fade_out: 0.0,
        }
    }
}

/// Complete sequence of synchronized events.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EventSequence {
    pub name: String,
    pub description: Option<String>,
    #[serde(default)]
    pub events: Vec<SequenceEvent>,
    pub total_duration: Option<f64>,

    /// Playback settings
    #[serde(default)]
    pub loop_sequence: bool,
    #[serde(default = "default_true")]
    pub interrupt_current: bool,
    #[serde(default)]
    pub priority: i32,

    /// Metadata
    pub created_timestamp: Option<f64>,
    #[serde(default)]
    pub tags: Vec<String>,
}

impl EventSequence {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            description: None,
            events: Vec::new(),
            total_duration: None,
            loop_sequence: false,
            interrupt_current: true,
            priority: 0,
            created_timestamp: None,
            tags: Vec::new(),
        }
    }

    pub fn add_event(&mut self, event: SequenceEvent) {
        let event_end = event.timestamp + event.duration.unwrap_or(0.0);
        if event_end > self.total_duration.unwrap_or(0.0) {
            self.total_duration = Some(event_end);
        }
        self.events.push(event);
    }
}

/// Backend capability flags.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BackendCapabilities {
    pub audio: bool,
    pub animation: bool,
    pub video_capture: bool,
    pub bidirectional: bool,
    pub environment_control: bool,
    pub streaming: bool,
    pub multi_agent: bool,
    pub procedural_animation: bool,
    pub physics_simulation: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_emotion_vector_lerp() {
        let a = EmotionVector::new(0.0, 0.0, 0.0);
        let b = EmotionVector::new(1.0, 1.0, 1.0);

        let mid = a.lerp(&b, 0.5);
        assert!((mid.pleasure - 0.5).abs() < 0.001);
        assert!((mid.arousal - 0.5).abs() < 0.001);
        assert!((mid.dominance - 0.5).abs() < 0.001);
    }

    #[test]
    fn test_emotion_type_from_str() {
        assert_eq!("happy".parse::<EmotionType>().unwrap(), EmotionType::Happy);
        assert_eq!("ANGRY".parse::<EmotionType>().unwrap(), EmotionType::Angry);
        assert!("invalid".parse::<EmotionType>().is_err());
    }

    #[test]
    fn test_gesture_type_from_str() {
        assert_eq!("wave".parse::<GestureType>().unwrap(), GestureType::Wave);
        assert_eq!(
            "thumbs_up".parse::<GestureType>().unwrap(),
            GestureType::ThumbsUp
        );
        assert!("invalid".parse::<GestureType>().is_err());
    }
}

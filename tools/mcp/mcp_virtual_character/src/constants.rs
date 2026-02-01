//! Constants for Virtual Character MCP Server.
//!
//! This module provides a single source of truth for:
//! - VRCEmote value mappings
//! - Gesture and emotion enumerations
//! - Default configuration values

use crate::types::{EmotionType, GestureType};
use std::collections::HashMap;

/// VRCEmote system values.
///
/// VRChat uses integer-based emotes that map to avatar gesture wheel positions.
/// Wheel positions (clockwise from top):
/// 0=None/Clear, 1=Wave, 2=Clap, 3=Point, 4=Cheer, 5=Dance, 6=Backflip, 7=Sadness, 8=Die
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(i32)]
pub enum VRCEmoteValue {
    None = 0,
    Wave = 1,
    Clap = 2,
    Point = 3,
    Cheer = 4,
    Dance = 5,
    Backflip = 6,
    Sadness = 7,
    Die = 8,
}

impl VRCEmoteValue {
    pub const MIN: i32 = 0;
    pub const MAX: i32 = 8;

    /// Get VRCEmote from integer value.
    pub fn from_i32(value: i32) -> Option<Self> {
        match value {
            0 => Some(VRCEmoteValue::None),
            1 => Some(VRCEmoteValue::Wave),
            2 => Some(VRCEmoteValue::Clap),
            3 => Some(VRCEmoteValue::Point),
            4 => Some(VRCEmoteValue::Cheer),
            5 => Some(VRCEmoteValue::Dance),
            6 => Some(VRCEmoteValue::Backflip),
            7 => Some(VRCEmoteValue::Sadness),
            8 => Some(VRCEmoteValue::Die),
            _ => None,
        }
    }

    /// Get display name for this emote.
    pub fn name(&self) -> &'static str {
        match self {
            VRCEmoteValue::None => "none/clear",
            VRCEmoteValue::Wave => "wave",
            VRCEmoteValue::Clap => "clap",
            VRCEmoteValue::Point => "point",
            VRCEmoteValue::Cheer => "cheer",
            VRCEmoteValue::Dance => "dance",
            VRCEmoteValue::Backflip => "backflip",
            VRCEmoteValue::Sadness => "sadness",
            VRCEmoteValue::Die => "die",
        }
    }

    /// Get VRCEmote from name.
    pub fn from_name(name: &str) -> Option<Self> {
        match name.to_lowercase().as_str() {
            "none" | "none/clear" | "clear" | "reset" => Some(VRCEmoteValue::None),
            "wave" => Some(VRCEmoteValue::Wave),
            "clap" => Some(VRCEmoteValue::Clap),
            "point" => Some(VRCEmoteValue::Point),
            "cheer" | "thumbs_up" => Some(VRCEmoteValue::Cheer),
            "dance" => Some(VRCEmoteValue::Dance),
            "backflip" => Some(VRCEmoteValue::Backflip),
            "sadness" => Some(VRCEmoteValue::Sadness),
            "die" => Some(VRCEmoteValue::Die),
            _ => None,
        }
    }
}

impl From<VRCEmoteValue> for i32 {
    fn from(val: VRCEmoteValue) -> i32 {
        val as i32
    }
}

/// Get VRCEmote display name from value.
pub fn get_vrcemote_name(value: i32) -> &'static str {
    VRCEmoteValue::from_i32(value)
        .map(|e| e.name())
        .unwrap_or("unknown")
}

/// Get VRCEmote value from name.
pub fn get_vrcemote_value(name: &str) -> i32 {
    VRCEmoteValue::from_name(name)
        .map(|e| e as i32)
        .unwrap_or(0)
}

/// Lazy-initialized emotion to VRCEmote mapping.
pub fn emotion_to_vrcemote() -> HashMap<EmotionType, i32> {
    let mut map = HashMap::new();
    map.insert(EmotionType::Neutral, VRCEmoteValue::None as i32);
    map.insert(EmotionType::Happy, VRCEmoteValue::Cheer as i32);
    map.insert(EmotionType::Sad, VRCEmoteValue::Sadness as i32);
    map.insert(EmotionType::Angry, VRCEmoteValue::Point as i32);
    map.insert(EmotionType::Surprised, VRCEmoteValue::Backflip as i32);
    map.insert(EmotionType::Fearful, VRCEmoteValue::Die as i32);
    map.insert(EmotionType::Disgusted, VRCEmoteValue::None as i32);
    map.insert(EmotionType::Contemptuous, VRCEmoteValue::None as i32);
    map.insert(EmotionType::Excited, VRCEmoteValue::Dance as i32);
    map.insert(EmotionType::Calm, VRCEmoteValue::None as i32);
    map
}

/// Lazy-initialized gesture to VRCEmote mapping.
pub fn gesture_to_vrcemote() -> HashMap<GestureType, i32> {
    let mut map = HashMap::new();
    map.insert(GestureType::None, VRCEmoteValue::None as i32);
    map.insert(GestureType::Wave, VRCEmoteValue::Wave as i32);
    map.insert(GestureType::Point, VRCEmoteValue::Point as i32);
    map.insert(GestureType::ThumbsUp, VRCEmoteValue::Cheer as i32);
    map.insert(GestureType::Nod, VRCEmoteValue::Clap as i32);
    map.insert(GestureType::ShakeHead, VRCEmoteValue::None as i32);
    map.insert(GestureType::Clap, VRCEmoteValue::Clap as i32);
    map.insert(GestureType::Dance, VRCEmoteValue::Dance as i32);
    map.insert(GestureType::Backflip, VRCEmoteValue::Backflip as i32);
    map.insert(GestureType::Cheer, VRCEmoteValue::Cheer as i32);
    map.insert(GestureType::Sadness, VRCEmoteValue::Sadness as i32);
    map.insert(GestureType::Die, VRCEmoteValue::Die as i32);
    map
}

// =============================================================================
// Default Configuration Values
// =============================================================================

/// Default VRChat host address.
pub const DEFAULT_VRCHAT_HOST: &str = "127.0.0.1";

/// VRChat receives OSC on this port.
pub const DEFAULT_OSC_IN_PORT: u16 = 9000;

/// VRChat sends OSC on this port.
pub const DEFAULT_OSC_OUT_PORT: u16 = 9001;

/// Default MCP server port.
pub const DEFAULT_MCP_SERVER_PORT: u16 = 8020;

/// Default storage service port.
pub const DEFAULT_STORAGE_PORT: u16 = 8021;

/// Health check interval in seconds.
pub const DEFAULT_HEALTH_CHECK_INTERVAL: u64 = 30;

/// Auto-connect delay in seconds.
pub const DEFAULT_AUTO_CONNECT_DELAY: u64 = 2;

/// Temp file cleanup delay in seconds.
pub const DEFAULT_TEMP_FILE_CLEANUP_DELAY: u64 = 10;

/// Subprocess timeout in seconds.
pub const DEFAULT_SUBPROCESS_TIMEOUT: f32 = 10.0;

/// Audio conversion timeout in seconds.
pub const DEFAULT_AUDIO_CONVERSION_TIMEOUT: f32 = 5.0;

/// Download timeout in seconds.
pub const DEFAULT_DOWNLOAD_TIMEOUT: u64 = 30;

/// Default audio device name.
pub const DEFAULT_AUDIO_DEVICE: &str = "VoiceMeeter Input";

/// Minimum audio size in bytes.
pub const MIN_AUDIO_SIZE: usize = 100;

/// Maximum reconnection attempts.
pub const DEFAULT_MAX_RECONNECT_ATTEMPTS: u32 = 3;

/// Emote timeout in seconds.
pub const DEFAULT_EMOTE_TIMEOUT: u64 = 10;

/// Movement auto-stop duration in seconds.
pub const DEFAULT_MOVEMENT_DURATION: f32 = 2.0;

// =============================================================================
// VRCEmote Description for Tool Documentation
// =============================================================================

/// Description of VRCEmote values for tool documentation.
pub const VRCEMOTE_DESCRIPTION: &str = "VRCEmote value: 0=clear, 1=wave, 2=clap, 3=point, 4=cheer, 5=dance, 6=backflip, 7=sadness, 8=die";

/// Get emotion from ElevenLabs audio expression tag.
pub fn get_emotion_from_tag(tag: &str) -> Option<(EmotionType, f32)> {
    // Normalize tag (remove brackets if present)
    let normalized = tag
        .trim_start_matches('[')
        .trim_end_matches(']')
        .to_lowercase();

    match normalized.as_str() {
        // Happy emotions
        "laughs" | "giggles" | "chuckles" => Some((EmotionType::Happy, 0.9)),
        "smiles" | "grins" => Some((EmotionType::Happy, 0.6)),
        "pleased" | "delighted" => Some((EmotionType::Happy, 0.7)),

        // Sad emotions
        "sighs" | "sighing" => Some((EmotionType::Sad, 0.5)),
        "cries" | "crying" | "sobs" | "sobbing" => Some((EmotionType::Sad, 0.9)),
        "sniffles" | "whimpers" => Some((EmotionType::Sad, 0.7)),

        // Angry emotions
        "growls" | "snarls" => Some((EmotionType::Angry, 0.8)),
        "scoffs" | "huffs" => Some((EmotionType::Angry, 0.5)),
        "shouts" | "yells" => Some((EmotionType::Angry, 0.9)),

        // Surprised emotions
        "gasps" | "gasping" => Some((EmotionType::Surprised, 0.8)),
        "exclaims" => Some((EmotionType::Surprised, 0.7)),

        // Fearful emotions
        "trembles" | "trembling" => Some((EmotionType::Fearful, 0.7)),
        "screams" | "screaming" => Some((EmotionType::Fearful, 0.9)),
        "whimper" => Some((EmotionType::Fearful, 0.6)),

        // Neutral/calm
        "whispers" | "whisper" => Some((EmotionType::Calm, 0.5)),
        "murmurs" | "mutters" => Some((EmotionType::Calm, 0.4)),
        "hums" | "humming" => Some((EmotionType::Calm, 0.5)),

        // Excited
        "cheers" | "cheering" => Some((EmotionType::Excited, 0.9)),
        "excitedly" => Some((EmotionType::Excited, 0.8)),

        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vrcemote_value_from_i32() {
        assert_eq!(VRCEmoteValue::from_i32(0), Some(VRCEmoteValue::None));
        assert_eq!(VRCEmoteValue::from_i32(5), Some(VRCEmoteValue::Dance));
        assert_eq!(VRCEmoteValue::from_i32(9), None);
        assert_eq!(VRCEmoteValue::from_i32(-1), None);
    }

    #[test]
    fn test_vrcemote_value_from_name() {
        assert_eq!(VRCEmoteValue::from_name("wave"), Some(VRCEmoteValue::Wave));
        assert_eq!(
            VRCEmoteValue::from_name("thumbs_up"),
            Some(VRCEmoteValue::Cheer)
        );
        assert_eq!(VRCEmoteValue::from_name("reset"), Some(VRCEmoteValue::None));
        assert_eq!(VRCEmoteValue::from_name("invalid"), None);
    }

    #[test]
    fn test_get_emotion_from_tag() {
        let (emotion, intensity) = get_emotion_from_tag("[laughs]").unwrap();
        assert_eq!(emotion, EmotionType::Happy);
        assert!((intensity - 0.9).abs() < 0.001);

        let (emotion, _) = get_emotion_from_tag("cries").unwrap();
        assert_eq!(emotion, EmotionType::Sad);

        assert!(get_emotion_from_tag("unknown_tag").is_none());
    }
}

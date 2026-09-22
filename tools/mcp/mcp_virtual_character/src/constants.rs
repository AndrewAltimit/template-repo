//! Constants for the Virtual Character MCP server.
//!
//! Single source of truth for:
//! - VRCEmote values and the emotion/gesture -> VRCEmote mappings
//! - Default network / timing configuration
//! - The set of high-level behaviors accepted by `execute_behavior`

use crate::types::{EmotionType, GestureType};

/// VRCEmote system values.
///
/// VRChat avatars built on the default action menu expose an integer
/// `VRCEmote` parameter whose values map to gesture-wheel positions:
/// 0=None/Clear, 1=Wave, 2=Clap, 3=Point, 4=Cheer, 5=Dance, 6=Backflip,
/// 7=Sadness, 8=Die.
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
    /// Smallest valid VRCEmote value.
    pub const MIN: i32 = 0;
    /// Largest valid VRCEmote value.
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

    /// Get VRCEmote from name (case-insensitive, accepts a few aliases).
    pub fn from_name(name: &str) -> Option<Self> {
        match name.trim().to_lowercase().as_str() {
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

/// Get VRCEmote display name from value (`"unknown"` if out of range).
pub fn get_vrcemote_name(value: i32) -> &'static str {
    VRCEmoteValue::from_i32(value)
        .map(|e| e.name())
        .unwrap_or("unknown")
}

/// VRCEmote value used to express an emotion.
///
/// Emotions without a sensible wheel animation map to `None` (0), which the
/// VRChat backend treats as "record the emotion but do not touch the emote"
/// (except `neutral`, which clears any active emote).
pub fn vrcemote_for_emotion(emotion: EmotionType) -> VRCEmoteValue {
    match emotion {
        EmotionType::Happy => VRCEmoteValue::Cheer,
        EmotionType::Sad => VRCEmoteValue::Sadness,
        EmotionType::Angry => VRCEmoteValue::Point,
        EmotionType::Surprised => VRCEmoteValue::Backflip,
        EmotionType::Fearful => VRCEmoteValue::Die,
        EmotionType::Excited => VRCEmoteValue::Dance,
        EmotionType::Neutral
        | EmotionType::Disgusted
        | EmotionType::Contemptuous
        | EmotionType::Calm => VRCEmoteValue::None,
    }
}

/// VRCEmote value used to perform a gesture.
///
/// Gestures with no wheel equivalent (`thumbs_down`, `shake_head`, `shrug`,
/// `crossed_arms`, `thinking`) map to `None` (0) and are not sent; `none`
/// clears any active emote.
pub fn vrcemote_for_gesture(gesture: GestureType) -> VRCEmoteValue {
    match gesture {
        GestureType::Wave => VRCEmoteValue::Wave,
        GestureType::Point => VRCEmoteValue::Point,
        GestureType::ThumbsUp | GestureType::Cheer => VRCEmoteValue::Cheer,
        GestureType::Nod | GestureType::Clap => VRCEmoteValue::Clap,
        GestureType::Dance => VRCEmoteValue::Dance,
        GestureType::Backflip => VRCEmoteValue::Backflip,
        GestureType::Sadness => VRCEmoteValue::Sadness,
        GestureType::Die => VRCEmoteValue::Die,
        GestureType::None
        | GestureType::ThumbsDown
        | GestureType::ShakeHead
        | GestureType::Shrug
        | GestureType::CrossedArms
        | GestureType::Thinking => VRCEmoteValue::None,
    }
}

// =============================================================================
// High-level behaviors
// =============================================================================

/// Behaviors accepted by the `execute_behavior` tool.
pub const SUPPORTED_BEHAVIORS: &[&str] = &["greet", "dance", "sit", "stand", "jump", "crouch"];

// =============================================================================
// Default Configuration Values
// =============================================================================

/// Default VRChat host address.
pub const DEFAULT_VRCHAT_HOST: &str = "127.0.0.1";

/// VRChat receives OSC on this port (we send to it).
pub const DEFAULT_OSC_IN_PORT: u16 = 9000;

/// VRChat sends OSC on this port (we listen on it).
pub const DEFAULT_OSC_OUT_PORT: u16 = 9001;

/// Seconds after which an active VRCEmote is automatically toggled off.
pub const DEFAULT_EMOTE_TIMEOUT_SECS: f64 = 10.0;

/// Movement auto-stop duration in seconds.
pub const DEFAULT_MOVEMENT_DURATION: f64 = 2.0;

/// Upper bound on a single movement command's duration, in seconds.
pub const MAX_MOVEMENT_DURATION: f64 = 60.0;

/// Default audio output device name (VoiceMeeter virtual cable input).
pub const DEFAULT_AUDIO_DEVICE: &str = "VoiceMeeter Input";

/// Description of VRCEmote values for tool documentation.
pub const VRCEMOTE_DESCRIPTION: &str = "VRCEmote value: 0=clear, 1=wave, 2=clap, 3=point, 4=cheer, 5=dance, 6=backflip, 7=sadness, 8=die";

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
    fn test_vrcemote_roundtrip() {
        for v in VRCEmoteValue::MIN..=VRCEmoteValue::MAX {
            let e = VRCEmoteValue::from_i32(v).unwrap();
            assert_eq!(i32::from(e), v);
            assert_eq!(VRCEmoteValue::from_name(e.name()), Some(e));
        }
        assert_eq!(get_vrcemote_name(42), "unknown");
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
    fn test_emotion_and_gesture_mappings() {
        assert_eq!(
            vrcemote_for_emotion(EmotionType::Happy),
            VRCEmoteValue::Cheer
        );
        assert_eq!(
            vrcemote_for_emotion(EmotionType::Neutral),
            VRCEmoteValue::None
        );
        assert_eq!(vrcemote_for_gesture(GestureType::Wave), VRCEmoteValue::Wave);
        assert_eq!(
            vrcemote_for_gesture(GestureType::ThumbsUp),
            VRCEmoteValue::Cheer
        );
        assert_eq!(
            vrcemote_for_gesture(GestureType::Shrug),
            VRCEmoteValue::None
        );
    }
}

//! Platform-neutral data types shared by the backends and the MCP tools.

use serde::{Deserialize, Deserializer, Serialize};

/// Information about a top-level window.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WindowInfo {
    /// Window identifier (X11 window XID or Win32 HWND, as a decimal string).
    pub id: String,
    /// Window title (may be empty).
    pub title: String,
    /// Executable name of the owning process, when it can be determined.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub process_name: Option<String>,
    /// Owning process id, when it can be determined.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pid: Option<u32>,
    /// Absolute X position of the window on the virtual desktop.
    pub x: i32,
    /// Absolute Y position of the window on the virtual desktop.
    pub y: i32,
    /// Window width in pixels.
    pub width: u32,
    /// Window height in pixels.
    pub height: u32,
    /// Whether the window is currently shown (mapped and not minimized).
    pub visible: bool,
    /// Whether the window is minimized (iconified).
    pub minimized: bool,
    /// Whether the window is maximized.
    pub maximized: bool,
}

/// Information about a physical screen / monitor.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ScreenInfo {
    /// Sequential screen index (0-based) as used by `screenshot_screen`.
    pub id: u32,
    /// Output / device name (e.g. `HDMI-1`, `\\.\DISPLAY1`).
    pub name: String,
    /// Absolute X position of the screen on the virtual desktop.
    pub x: i32,
    /// Absolute Y position of the screen on the virtual desktop.
    pub y: i32,
    /// Horizontal resolution in pixels.
    pub width: u32,
    /// Vertical resolution in pixels.
    pub height: u32,
    /// Whether this is the primary screen.
    pub is_primary: bool,
    /// DPI scale factor (1.0 = 96 DPI). Always 1.0 on X11.
    pub scale: f64,
}

/// An axis-aligned rectangle in absolute desktop coordinates.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rect {
    /// Left edge.
    pub x: i32,
    /// Top edge.
    pub y: i32,
    /// Width in pixels.
    pub width: u32,
    /// Height in pixels.
    pub height: u32,
}

impl Rect {
    /// Create a rectangle.
    pub const fn new(x: i32, y: i32, width: u32, height: u32) -> Self {
        Self {
            x,
            y,
            width,
            height,
        }
    }

    /// Exclusive right edge (computed in i64 so it can never overflow).
    pub fn right(&self) -> i64 {
        i64::from(self.x) + i64::from(self.width)
    }

    /// Exclusive bottom edge (computed in i64 so it can never overflow).
    pub fn bottom(&self) -> i64 {
        i64::from(self.y) + i64::from(self.height)
    }

    /// Intersection of two rectangles, or `None` if they do not overlap.
    pub fn intersect(&self, other: &Rect) -> Option<Rect> {
        let left = i64::from(self.x).max(i64::from(other.x));
        let top = i64::from(self.y).max(i64::from(other.y));
        let right = self.right().min(other.right());
        let bottom = self.bottom().min(other.bottom());
        if right <= left || bottom <= top {
            return None;
        }
        // All values are bounded by the i32/u32 inputs, so these conversions
        // cannot fail; fall back to "no overlap" rather than panicking.
        Some(Rect {
            x: i32::try_from(left).ok()?,
            y: i32::try_from(top).ok()?,
            width: u32::try_from(right - left).ok()?,
            height: u32::try_from(bottom - top).ok()?,
        })
    }
}

/// Implements case-insensitive `FromStr` + `Deserialize` for a simple enum.
macro_rules! str_enum {
    ($ty:ident, $what:literal, { $($($name:literal)|+ => $variant:ident),+ $(,)? }) => {
        impl std::str::FromStr for $ty {
            type Err = String;

            fn from_str(s: &str) -> Result<Self, Self::Err> {
                match s.trim().to_ascii_lowercase().as_str() {
                    $($($name)|+ => Ok(Self::$variant),)+
                    _ => Err(format!(
                        concat!("Invalid ", $what, " '{}' (expected one of: {})"),
                        s,
                        [$($($name),+),+].join(", ")
                    )),
                }
            }
        }

        impl<'de> Deserialize<'de> for $ty {
            fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
                let s = String::deserialize(d)?;
                s.parse().map_err(serde::de::Error::custom)
            }
        }
    };
}

/// Mouse button.
#[derive(Debug, Clone, Copy, Default, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum MouseButton {
    /// Primary button.
    #[default]
    Left,
    /// Secondary button.
    Right,
    /// Wheel button.
    Middle,
}

str_enum!(MouseButton, "mouse button", {
    "left" => Left,
    "right" => Right,
    "middle" => Middle,
});

/// Scroll axis.
#[derive(Debug, Clone, Copy, Default, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ScrollDirection {
    /// Vertical wheel (positive = down).
    #[default]
    Vertical,
    /// Horizontal wheel (positive = right).
    Horizontal,
}

str_enum!(ScrollDirection, "scroll direction", {
    "vertical" => Vertical,
    "horizontal" => Horizontal,
});

/// Keyboard modifier accepted by `send_key`.
#[derive(Debug, Clone, Copy, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum KeyModifier {
    /// Control.
    Ctrl,
    /// Alt / Option.
    Alt,
    /// Shift.
    Shift,
    /// Windows key (same physical key as `Super`).
    Win,
    /// Super / Meta / Command.
    Super,
}

str_enum!(KeyModifier, "modifier", {
    "ctrl" | "control" => Ctrl,
    "alt" | "option" => Alt,
    "shift" => Shift,
    "win" | "windows" => Win,
    "super" | "meta" | "cmd" | "command" => Super,
});

/// Outcome of a `type_text` operation.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct TypeReport {
    /// Number of characters that were sent as key events.
    pub typed: usize,
    /// Characters that could not be typed with the current keyboard layout.
    pub skipped: Vec<char>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mouse_button_parse_is_case_insensitive() {
        assert_eq!("left".parse::<MouseButton>().unwrap(), MouseButton::Left);
        assert_eq!("Right".parse::<MouseButton>().unwrap(), MouseButton::Right);
        assert_eq!(
            " MIDDLE ".parse::<MouseButton>().unwrap(),
            MouseButton::Middle
        );
        let err = "fourth".parse::<MouseButton>().unwrap_err();
        assert!(err.contains("left, right, middle"), "{err}");
    }

    #[test]
    fn scroll_direction_parse() {
        assert_eq!(
            "vertical".parse::<ScrollDirection>().unwrap(),
            ScrollDirection::Vertical
        );
        assert_eq!(
            "Horizontal".parse::<ScrollDirection>().unwrap(),
            ScrollDirection::Horizontal
        );
        assert!("diagonal".parse::<ScrollDirection>().is_err());
    }

    #[test]
    fn key_modifier_parse_aliases() {
        assert_eq!("ctrl".parse::<KeyModifier>().unwrap(), KeyModifier::Ctrl);
        assert_eq!("control".parse::<KeyModifier>().unwrap(), KeyModifier::Ctrl);
        assert_eq!("Alt".parse::<KeyModifier>().unwrap(), KeyModifier::Alt);
        assert_eq!("SHIFT".parse::<KeyModifier>().unwrap(), KeyModifier::Shift);
        assert_eq!("meta".parse::<KeyModifier>().unwrap(), KeyModifier::Super);
        assert_eq!("windows".parse::<KeyModifier>().unwrap(), KeyModifier::Win);
        assert!("hyper".parse::<KeyModifier>().is_err());
    }

    #[test]
    fn enums_deserialize_via_from_str() {
        let b: MouseButton = serde_json::from_value(serde_json::json!("RIGHT")).unwrap();
        assert_eq!(b, MouseButton::Right);
        assert!(serde_json::from_value::<MouseButton>(serde_json::json!(3)).is_err());
        assert!(serde_json::from_value::<KeyModifier>(serde_json::json!("nope")).is_err());
    }

    #[test]
    fn rect_intersection() {
        let screen = Rect::new(0, 0, 1920, 1080);
        assert_eq!(
            Rect::new(-10, -10, 20, 20).intersect(&screen),
            Some(Rect::new(0, 0, 10, 10))
        );
        assert_eq!(
            Rect::new(1900, 1000, 100, 100).intersect(&screen),
            Some(Rect::new(1900, 1000, 20, 80))
        );
        assert_eq!(Rect::new(1920, 0, 10, 10).intersect(&screen), None);
        assert_eq!(Rect::new(0, 0, 0, 10).intersect(&screen), None);
        // Extreme values must not overflow.
        assert_eq!(
            Rect::new(i32::MAX, i32::MAX, u32::MAX, u32::MAX).intersect(&screen),
            None
        );
        assert_eq!(
            Rect::new(i32::MIN, i32::MIN, u32::MAX, u32::MAX).intersect(&screen),
            Some(Rect::new(0, 0, 1920, 1080))
        );
    }
}

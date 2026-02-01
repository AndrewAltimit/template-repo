//! Data types for desktop control.

use serde::{Deserialize, Serialize};

/// Window information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowInfo {
    /// Window identifier (platform-specific)
    pub id: String,
    /// Window title
    pub title: String,
    /// Process name if available
    #[serde(skip_serializing_if = "Option::is_none")]
    pub process_name: Option<String>,
    /// Window position
    pub x: i32,
    pub y: i32,
    /// Window size
    pub width: u32,
    pub height: u32,
    /// Whether window is visible
    pub visible: bool,
    /// Whether window is minimized
    pub minimized: bool,
    /// Whether window is maximized
    pub maximized: bool,
}

impl WindowInfo {
    /// Convert to dictionary for JSON output
    #[allow(dead_code)]
    pub fn to_dict(&self) -> serde_json::Value {
        serde_json::json!({
            "id": self.id,
            "title": self.title,
            "process_name": self.process_name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "visible": self.visible,
            "minimized": self.minimized,
            "maximized": self.maximized
        })
    }
}

/// Screen/monitor information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenInfo {
    /// Screen identifier
    pub id: u32,
    /// Screen name
    pub name: String,
    /// Screen position (x, y)
    pub x: i32,
    pub y: i32,
    /// Screen resolution
    pub width: u32,
    pub height: u32,
    /// Whether this is the primary screen
    pub is_primary: bool,
    /// Scale factor (DPI scaling)
    #[serde(default = "default_scale")]
    pub scale: f64,
}

fn default_scale() -> f64 {
    1.0
}

impl ScreenInfo {
    /// Convert to dictionary for JSON output
    #[allow(dead_code)]
    pub fn to_dict(&self) -> serde_json::Value {
        serde_json::json!({
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary,
            "scale": self.scale
        })
    }
}

/// Mouse button type
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum MouseButton {
    #[default]
    Left,
    Right,
    Middle,
}

impl std::str::FromStr for MouseButton {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "left" => Ok(Self::Left),
            "right" => Ok(Self::Right),
            "middle" => Ok(Self::Middle),
            _ => Err(format!("Invalid mouse button: {}", s)),
        }
    }
}

/// Scroll direction
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ScrollDirection {
    #[default]
    Vertical,
    Horizontal,
}

impl std::str::FromStr for ScrollDirection {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "vertical" => Ok(Self::Vertical),
            "horizontal" => Ok(Self::Horizontal),
            _ => Err(format!("Invalid scroll direction: {}", s)),
        }
    }
}

/// Key modifier
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum KeyModifier {
    Ctrl,
    Alt,
    Shift,
    Win,
    Super,
}

impl std::str::FromStr for KeyModifier {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "ctrl" | "control" => Ok(Self::Ctrl),
            "alt" => Ok(Self::Alt),
            "shift" => Ok(Self::Shift),
            "win" | "windows" => Ok(Self::Win),
            "super" | "meta" => Ok(Self::Super),
            _ => Err(format!("Invalid modifier: {}", s)),
        }
    }
}

/// Screenshot result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct ScreenshotResult {
    /// Output file path
    pub output_path: String,
    /// Image format
    pub format: String,
    /// Size in bytes
    pub size_bytes: usize,
    /// Image dimensions
    pub width: u32,
    pub height: u32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mouse_button_parse() {
        assert_eq!("left".parse::<MouseButton>().unwrap(), MouseButton::Left);
        assert_eq!("Right".parse::<MouseButton>().unwrap(), MouseButton::Right);
        assert_eq!(
            "MIDDLE".parse::<MouseButton>().unwrap(),
            MouseButton::Middle
        );
    }

    #[test]
    fn test_scroll_direction_parse() {
        assert_eq!(
            "vertical".parse::<ScrollDirection>().unwrap(),
            ScrollDirection::Vertical
        );
        assert_eq!(
            "Horizontal".parse::<ScrollDirection>().unwrap(),
            ScrollDirection::Horizontal
        );
    }

    #[test]
    fn test_key_modifier_parse() {
        assert_eq!("ctrl".parse::<KeyModifier>().unwrap(), KeyModifier::Ctrl);
        assert_eq!("Alt".parse::<KeyModifier>().unwrap(), KeyModifier::Alt);
        assert_eq!("SHIFT".parse::<KeyModifier>().unwrap(), KeyModifier::Shift);
        assert_eq!("control".parse::<KeyModifier>().unwrap(), KeyModifier::Ctrl);
    }
}

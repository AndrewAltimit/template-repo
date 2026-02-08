//! Skin theme -- color scheme and visual properties.
//!
//! The theme defines the color palette and optional WM visual overrides
//! for a skin. Loaded from `theme.toml`.

use serde::Deserialize;

use crate::backend::Color;
use crate::wm::WmTheme;

/// Color scheme for a skin.
#[derive(Debug, Clone, Deserialize)]
pub struct SkinTheme {
    /// Main background color.
    #[serde(default = "default_bg")]
    pub background: String,
    /// Primary accent color (active elements, highlights).
    #[serde(default = "default_primary")]
    pub primary: String,
    /// Secondary color (borders, separators).
    #[serde(default = "default_secondary")]
    pub secondary: String,
    /// Default text color.
    #[serde(default = "default_text")]
    pub text: String,
    /// Dimmed/secondary text color.
    #[serde(default = "default_dim_text")]
    pub dim_text: String,
    /// Status bar background color.
    #[serde(default = "default_status_bar")]
    pub status_bar: String,
    /// Terminal prompt color.
    #[serde(default = "default_prompt")]
    pub prompt: String,
    /// Terminal output text color.
    #[serde(default = "default_output")]
    pub output: String,
    /// Terminal error text color.
    #[serde(default = "default_error")]
    pub error: String,
    /// Whether the WM is visually themed by this skin.
    #[serde(default)]
    pub wm_theme: Option<WmThemeOverrides>,
}

/// Optional overrides for the window manager theme.
#[derive(Debug, Clone, Deserialize)]
pub struct WmThemeOverrides {
    pub titlebar_height: Option<u32>,
    pub border_width: Option<u32>,
    pub titlebar_active: Option<String>,
    pub titlebar_inactive: Option<String>,
    pub titlebar_text: Option<String>,
    pub frame_color: Option<String>,
    pub content_bg: Option<String>,
    pub btn_close: Option<String>,
    pub btn_minimize: Option<String>,
    pub btn_maximize: Option<String>,
    pub button_size: Option<u32>,
    pub resize_handle_size: Option<u32>,
    pub titlebar_font_size: Option<u16>,
}

fn default_bg() -> String {
    "#1A1A2D".to_string()
}
fn default_primary() -> String {
    "#3264C8".to_string()
}
fn default_secondary() -> String {
    "#505050".to_string()
}
fn default_text() -> String {
    "#FFFFFF".to_string()
}
fn default_dim_text() -> String {
    "#808080".to_string()
}
fn default_status_bar() -> String {
    "#283C5A".to_string()
}
fn default_prompt() -> String {
    "#00FF00".to_string()
}
fn default_output() -> String {
    "#CCCCCC".to_string()
}
fn default_error() -> String {
    "#FF4444".to_string()
}

impl Default for SkinTheme {
    fn default() -> Self {
        Self {
            background: default_bg(),
            primary: default_primary(),
            secondary: default_secondary(),
            text: default_text(),
            dim_text: default_dim_text(),
            status_bar: default_status_bar(),
            prompt: default_prompt(),
            output: default_output(),
            error: default_error(),
            wm_theme: None,
        }
    }
}

impl SkinTheme {
    /// Parse the background color string to a `Color`.
    pub fn background_color(&self) -> Color {
        parse_hex_color(&self.background).unwrap_or(Color::BLACK)
    }

    /// Parse the primary color string to a `Color`.
    pub fn primary_color(&self) -> Color {
        parse_hex_color(&self.primary).unwrap_or(Color::WHITE)
    }

    /// Parse the text color string to a `Color`.
    pub fn text_color(&self) -> Color {
        parse_hex_color(&self.text).unwrap_or(Color::WHITE)
    }

    /// Parse the prompt color string to a `Color`.
    pub fn prompt_color(&self) -> Color {
        parse_hex_color(&self.prompt).unwrap_or(Color::rgb(0, 255, 0))
    }

    /// Parse the output color string to a `Color`.
    pub fn output_color(&self) -> Color {
        parse_hex_color(&self.output).unwrap_or(Color::rgb(204, 204, 204))
    }

    /// Parse the error color string to a `Color`.
    pub fn error_color(&self) -> Color {
        parse_hex_color(&self.error).unwrap_or(Color::rgb(255, 68, 68))
    }

    /// Build a `WmTheme` from the defaults plus any overrides.
    pub fn build_wm_theme(&self) -> WmTheme {
        let mut theme = WmTheme::default();
        if let Some(ref ov) = self.wm_theme {
            if let Some(h) = ov.titlebar_height {
                theme.titlebar_height = h;
            }
            if let Some(w) = ov.border_width {
                theme.border_width = w;
            }
            if let Some(ref c) = ov.titlebar_active {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.titlebar_active_color = parsed;
                }
            }
            if let Some(ref c) = ov.titlebar_inactive {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.titlebar_inactive_color = parsed;
                }
            }
            if let Some(ref c) = ov.titlebar_text {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.titlebar_text_color = parsed;
                }
            }
            if let Some(ref c) = ov.frame_color {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.frame_color = parsed;
                }
            }
            if let Some(ref c) = ov.content_bg {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.content_bg_color = parsed;
                }
            }
            if let Some(ref c) = ov.btn_close {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.btn_close_color = parsed;
                }
            }
            if let Some(ref c) = ov.btn_minimize {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.btn_minimize_color = parsed;
                }
            }
            if let Some(ref c) = ov.btn_maximize {
                if let Some(parsed) = parse_hex_color(c) {
                    theme.btn_maximize_color = parsed;
                }
            }
            if let Some(s) = ov.button_size {
                theme.button_size = s;
            }
            if let Some(s) = ov.resize_handle_size {
                theme.resize_handle_size = s;
            }
            if let Some(s) = ov.titlebar_font_size {
                theme.titlebar_font_size = s;
            }
        }
        theme
    }
}

/// Parse "#RRGGBB" or "#RRGGBBAA" into a `Color`.
pub fn parse_hex_color(s: &str) -> Option<Color> {
    let s = s.strip_prefix('#')?;
    if s.len() == 6 {
        let r = u8::from_str_radix(&s[0..2], 16).ok()?;
        let g = u8::from_str_radix(&s[2..4], 16).ok()?;
        let b = u8::from_str_radix(&s[4..6], 16).ok()?;
        Some(Color::rgb(r, g, b))
    } else if s.len() == 8 {
        let r = u8::from_str_radix(&s[0..2], 16).ok()?;
        let g = u8::from_str_radix(&s[2..4], 16).ok()?;
        let b = u8::from_str_radix(&s[4..6], 16).ok()?;
        let a = u8::from_str_radix(&s[6..8], 16).ok()?;
        Some(Color::rgba(r, g, b, a))
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_theme_parses() {
        let theme = SkinTheme::default();
        assert_ne!(theme.background_color(), Color::WHITE);
        assert_eq!(theme.prompt_color(), Color::rgb(0, 255, 0));
    }

    #[test]
    fn parse_hex_colors() {
        assert_eq!(parse_hex_color("#FF0000"), Some(Color::rgb(255, 0, 0)));
        assert_eq!(
            parse_hex_color("#00FF0080"),
            Some(Color::rgba(0, 255, 0, 128))
        );
        assert_eq!(parse_hex_color("invalid"), None);
        assert_eq!(parse_hex_color("#GG0000"), None);
    }

    #[test]
    fn deserialize_from_toml() {
        let toml = r##"
background = "#000000"
primary = "#00FF00"
text = "#00FF00"
prompt = "#00FF00"
output = "#00CC00"
error = "#FF0000"
"##;
        let theme: SkinTheme = toml::from_str(toml).unwrap();
        assert_eq!(theme.background_color(), Color::rgb(0, 0, 0));
        assert_eq!(theme.text_color(), Color::rgb(0, 255, 0));
    }

    #[test]
    fn wm_theme_overrides() {
        let toml = r##"
[wm_theme]
titlebar_height = 32
titlebar_active = "#0000FF"
button_size = 20
"##;
        let theme: SkinTheme = toml::from_str(toml).unwrap();
        let wm = theme.build_wm_theme();
        assert_eq!(wm.titlebar_height, 32);
        assert_eq!(wm.titlebar_active_color, Color::rgb(0, 0, 255));
        assert_eq!(wm.button_size, 20);
        // Non-overridden values remain default.
        assert_eq!(wm.border_width, 1);
    }

    #[test]
    fn no_wm_overrides_returns_default() {
        let theme = SkinTheme::default();
        let wm = theme.build_wm_theme();
        assert_eq!(wm.titlebar_height, 24);
    }
}

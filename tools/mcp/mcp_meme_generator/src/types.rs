//! Types for meme template configuration (`templates/config/*.json`).
//!
//! These mirror `templates/config/template_schema.json`. Deserialization is
//! strict about types (a wrong type fails the whole template, which the loader
//! reports), while semantic checks (sizes, colors, bounds) live in
//! [`crate::templates`].

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Center position of a text area, in template-image pixels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Position {
    /// Horizontal center of the text area.
    pub x: i32,
    /// Vertical center of the text area.
    pub y: i32,
}

/// Horizontal alignment of each wrapped line inside its text area.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TextAlign {
    /// Lines start at the left edge of the area.
    Left,
    /// Lines are centered on `position.x` (default).
    #[default]
    Center,
    /// Lines end at the right edge of the area.
    Right,
}

/// A rectangular region of the template that receives one caption.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextArea {
    /// Area identifier used as the key in `generate_meme`'s `texts`.
    pub id: String,
    /// Center of the area.
    pub position: Position,
    /// Maximum rendered line width in pixels (text is wrapped to fit).
    pub width: i32,
    /// Maximum rendered block height in pixels.
    pub height: i32,
    /// Font size (px) used when `auto_resize` is false.
    pub default_font_size: i32,
    /// Largest font size tried by auto-resize.
    #[serde(default = "default_max_font_size")]
    pub max_font_size: i32,
    /// Smallest font size tried by auto-resize.
    #[serde(default = "default_min_font_size")]
    pub min_font_size: i32,
    /// Horizontal alignment.
    #[serde(default)]
    pub text_align: TextAlign,
    /// Fill color (named color or `#RGB` / `#RRGGBB` / `#RRGGBBAA`).
    #[serde(default = "default_text_color")]
    pub text_color: String,
    /// Outline color (same syntax as `text_color`).
    #[serde(default = "default_stroke_color")]
    pub stroke_color: String,
    /// Outline radius in pixels (0 disables the outline).
    #[serde(default = "default_stroke_width")]
    pub stroke_width: i32,
    /// Recommended maximum characters (exceeding it only produces a warning).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_chars: Option<i32>,
    /// Example / pattern text for this area.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub recommended_text: Option<String>,
    /// How this area is meant to be used.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub usage: Option<String>,
}

fn default_max_font_size() -> i32 {
    80
}
fn default_min_font_size() -> i32 {
    12
}
fn default_text_color() -> String {
    "white".to_string()
}
fn default_stroke_color() -> String {
    "black".to_string()
}
fn default_stroke_width() -> i32 {
    2
}

/// A full template configuration file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateConfig {
    /// Human-readable template name.
    pub name: String,
    /// Image filename, relative to the templates directory. Must be a plain
    /// file name (no directories), which the loader enforces.
    pub template_file: String,
    /// What the meme is and when to use it.
    #[serde(default)]
    pub description: String,
    /// Caption areas.
    pub text_areas: Vec<TextArea>,
    /// Usage rules / guidelines for agents.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub usage_rules: Vec<String>,
    /// Where the meme comes from and why it is funny.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cultural_context: Option<String>,
    /// Notes about where text should go.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text_positioning_note: Option<String>,
    /// Example captions.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub examples: Vec<TemplateExample>,
}

/// One example caption set: area id -> text, plus an optional explanation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateExample {
    /// Why the example works.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub explanation: Option<String>,
    /// Area id -> caption text (ordered for stable output).
    #[serde(flatten)]
    pub texts: BTreeMap<String, String>,
}

/// Compact template description returned by `list_meme_templates`.
#[derive(Debug, Clone, Serialize)]
pub struct TemplateSummary {
    /// Template id (config file stem) passed to `generate_meme`.
    pub id: String,
    /// Human-readable name.
    pub name: String,
    /// Short description.
    pub description: String,
    /// Area ids accepted in `texts`, in drawing order.
    pub text_areas: Vec<String>,
    /// Template image `[width, height]` in pixels.
    pub image_size: [u32; 2],
}

/// Result of a single upload attempt.
#[derive(Debug, Clone, Serialize, Default, PartialEq)]
pub struct UploadResult {
    /// Whether the upload succeeded.
    pub success: bool,
    /// Page / share URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    /// Direct image URL suitable for embedding (markdown `![](...)`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embed_url: Option<String>,
    /// Service that produced the URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub service: Option<String>,
    /// Failure reason (for a failed attempt, or all attempts combined).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    /// Retention notes.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
}

impl UploadResult {
    /// A failed result carrying `error`.
    pub fn failure(error: impl Into<String>) -> Self {
        Self {
            success: false,
            error: Some(error.into()),
            ..Default::default()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn text_area_defaults_apply() {
        let area: TextArea = serde_json::from_value(json!({
            "id": "top",
            "position": {"x": 10, "y": 20},
            "width": 100,
            "height": 50,
            "default_font_size": 30
        }))
        .unwrap();
        assert_eq!(area.max_font_size, 80);
        assert_eq!(area.min_font_size, 12);
        assert_eq!(area.text_align, TextAlign::Center);
        assert_eq!(area.text_color, "white");
        assert_eq!(area.stroke_color, "black");
        assert_eq!(area.stroke_width, 2);
    }

    #[test]
    fn unknown_alignment_is_rejected() {
        let res: Result<TextAlign, _> = serde_json::from_value(json!("justify"));
        assert!(res.is_err());
    }

    #[test]
    fn example_flattens_texts_and_explanation() {
        let ex: TemplateExample = serde_json::from_value(json!({
            "top": "a",
            "bottom": "b",
            "explanation": "why"
        }))
        .unwrap();
        assert_eq!(ex.explanation.as_deref(), Some("why"));
        assert_eq!(ex.texts.len(), 2);
        assert_eq!(ex.texts["top"], "a");
    }
}

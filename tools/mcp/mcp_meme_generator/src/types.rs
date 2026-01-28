//! Types for meme template configuration.

use serde::{Deserialize, Serialize};

/// Position coordinates for text placement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub x: i32,
    pub y: i32,
}

/// Text area configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextArea {
    /// Area identifier (e.g., "top", "bottom")
    pub id: String,
    /// Center position for text
    pub position: Position,
    /// Maximum width for text wrapping
    pub width: i32,
    /// Maximum height for text area
    pub height: i32,
    /// Default font size
    pub default_font_size: i32,
    /// Maximum font size for auto-resize
    #[serde(default = "default_max_font_size")]
    pub max_font_size: i32,
    /// Minimum font size for auto-resize
    #[serde(default = "default_min_font_size")]
    pub min_font_size: i32,
    /// Text alignment: "center", "left", or "right"
    #[serde(default = "default_text_align")]
    pub text_align: String,
    /// Text color
    #[serde(default = "default_text_color")]
    pub text_color: String,
    /// Stroke/outline color
    #[serde(default = "default_stroke_color")]
    pub stroke_color: String,
    /// Stroke width
    #[serde(default = "default_stroke_width")]
    pub stroke_width: i32,
    /// Maximum characters (optional limit)
    #[serde(default)]
    pub max_chars: Option<i32>,
    /// Recommended text pattern
    #[serde(default)]
    pub recommended_text: Option<String>,
    /// Usage description
    #[serde(default)]
    pub usage: Option<String>,
}

fn default_max_font_size() -> i32 {
    80
}
fn default_min_font_size() -> i32 {
    12
}
fn default_text_align() -> String {
    "center".to_string()
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

/// Template configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateConfig {
    /// Template name
    pub name: String,
    /// Template image filename
    pub template_file: String,
    /// Template description
    #[serde(default)]
    pub description: String,
    /// Text areas for overlay
    pub text_areas: Vec<TextArea>,
    /// Usage rules/guidelines
    #[serde(default)]
    pub usage_rules: Vec<String>,
    /// Cultural context
    #[serde(default)]
    pub cultural_context: Option<String>,
    /// Text positioning notes
    #[serde(default)]
    pub text_positioning_note: Option<String>,
    /// Example usages
    #[serde(default)]
    pub examples: Vec<TemplateExample>,
}

/// Example usage for a template
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateExample {
    #[serde(flatten)]
    pub texts: std::collections::HashMap<String, String>,
    #[serde(default)]
    pub explanation: Option<String>,
}

/// Summary of a template for listing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateSummary {
    pub id: String,
    pub name: String,
    pub description: String,
    pub text_areas: Vec<String>,
}

/// Result of meme generation
#[derive(Debug, Clone, Serialize, Default)]
pub struct MemeResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub template_used: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_data: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_kb: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub share_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embed_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub upload_service: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub visual_feedback: Option<VisualFeedback>,
}

/// Visual feedback thumbnail
#[derive(Debug, Clone, Serialize)]
pub struct VisualFeedback {
    pub format: String,
    pub encoding: String,
    pub data: String,
    pub size_kb: f64,
}

/// Upload result
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UploadResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embed_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub service: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
}

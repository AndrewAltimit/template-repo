//! Types for content creation server.

use serde::{Deserialize, Serialize};

/// Result of LaTeX compilation
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CompileResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub container_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub page_count: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file_size_kb: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub compile_time_seconds: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preview_paths: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warnings: Option<Vec<String>>,
}

/// Result of Manim animation creation
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ManimResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
}

/// Result of PDF preview generation
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PreviewResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preview_paths: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pdf_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub page_count: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pages_exported: Option<Vec<i32>>,
}

/// Output format for LaTeX compilation
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OutputFormat {
    Pdf,
    Dvi,
    Ps,
    Png,
    Svg,
}

impl OutputFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            OutputFormat::Pdf => "pdf",
            OutputFormat::Dvi => "dvi",
            OutputFormat::Ps => "ps",
            OutputFormat::Png => "png",
            OutputFormat::Svg => "svg",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "pdf" => Some(OutputFormat::Pdf),
            "dvi" => Some(OutputFormat::Dvi),
            "ps" => Some(OutputFormat::Ps),
            "png" => Some(OutputFormat::Png),
            "svg" => Some(OutputFormat::Svg),
            _ => None,
        }
    }
}

/// LaTeX document template
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LatexTemplate {
    Article,
    Report,
    Book,
    Beamer,
    Custom,
}

impl LatexTemplate {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "article" => LatexTemplate::Article,
            "report" => LatexTemplate::Report,
            "book" => LatexTemplate::Book,
            "beamer" => LatexTemplate::Beamer,
            _ => LatexTemplate::Custom,
        }
    }

    pub fn wrap_content(&self, content: &str) -> String {
        match self {
            LatexTemplate::Custom => content.to_string(),
            LatexTemplate::Article => {
                format!(
                    "\\documentclass{{article}}\n\\begin{{document}}\n{}\n\\end{{document}}",
                    content
                )
            }
            LatexTemplate::Report => {
                format!(
                    "\\documentclass{{report}}\n\\begin{{document}}\n{}\n\\end{{document}}",
                    content
                )
            }
            LatexTemplate::Book => {
                format!(
                    "\\documentclass{{book}}\n\\begin{{document}}\n{}\n\\end{{document}}",
                    content
                )
            }
            LatexTemplate::Beamer => {
                format!(
                    "\\documentclass{{beamer}}\n\\begin{{document}}\n{}\n\\end{{document}}",
                    content
                )
            }
        }
    }
}

/// Response mode for tool output
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResponseMode {
    Minimal,
    Standard,
}

impl ResponseMode {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "minimal" => ResponseMode::Minimal,
            _ => ResponseMode::Standard,
        }
    }
}

/// Manim output format
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ManimFormat {
    Mp4,
    Gif,
    Png,
    Webm,
}

impl ManimFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            ManimFormat::Mp4 => "mp4",
            ManimFormat::Gif => "gif",
            ManimFormat::Png => "png",
            ManimFormat::Webm => "webm",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "mp4" => Some(ManimFormat::Mp4),
            "gif" => Some(ManimFormat::Gif),
            "png" => Some(ManimFormat::Png),
            "webm" => Some(ManimFormat::Webm),
            _ => None,
        }
    }
}

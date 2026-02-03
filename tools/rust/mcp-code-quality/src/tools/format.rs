//! Code formatting tools

use std::path::Path;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::Language;
use crate::error::Result;
use crate::subprocess::run_command;

/// Request for format_check operation
#[derive(Debug, Deserialize)]
pub struct FormatCheckRequest {
    pub path: String,
    #[serde(default = "default_language")]
    pub language: String,
}

fn default_language() -> String {
    "python".to_string()
}

/// Response for format_check operation
#[derive(Debug, Serialize)]
pub struct FormatCheckResponse {
    pub success: bool,
    pub formatted: bool,
    pub language: String,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub diff: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Check code formatting without modifying files
pub async fn format_check(
    path: &Path,
    language: Language,
    timeout: Duration,
) -> Result<FormatCheckResponse> {
    let (cmd, args) = get_format_check_command(language, path)?;

    let result = run_command(cmd, &args, None, timeout).await?;

    Ok(FormatCheckResponse {
        success: true,
        formatted: result.success,
        language: format!("{:?}", language).to_lowercase(),
        path: path.display().to_string(),
        diff: if result.stdout.is_empty() {
            None
        } else {
            Some(result.stdout)
        },
        message: if result.success {
            Some("Code is properly formatted".to_string())
        } else {
            Some("Code needs formatting".to_string())
        },
    })
}

/// Request for autoformat operation
#[derive(Debug, Deserialize)]
pub struct AutoformatRequest {
    pub path: String,
    #[serde(default = "default_language")]
    pub language: String,
}

/// Response for autoformat operation
#[derive(Debug, Serialize)]
pub struct AutoformatResponse {
    pub success: bool,
    pub formatted: bool,
    pub language: String,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stdout: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stderr: Option<String>,
}

/// Auto-format code files
pub async fn autoformat(
    path: &Path,
    language: Language,
    timeout: Duration,
) -> Result<AutoformatResponse> {
    let (cmd, args) = get_autoformat_command(language, path)?;

    let result = run_command(cmd, &args, None, timeout).await?;

    Ok(AutoformatResponse {
        success: result.success,
        formatted: result.success,
        language: format!("{:?}", language).to_lowercase(),
        path: path.display().to_string(),
        message: if result.success {
            Some("Code formatted successfully".to_string())
        } else {
            Some("Formatting failed".to_string())
        },
        stdout: if result.stdout.is_empty() {
            None
        } else {
            Some(result.stdout)
        },
        stderr: if result.stderr.is_empty() {
            None
        } else {
            Some(result.stderr)
        },
    })
}

/// Get the command and args for format checking
/// Prefers modern tools: ruff for Python (faster than black)
fn get_format_check_command(
    language: Language,
    path: &Path,
) -> Result<(&'static str, Vec<String>)> {
    let path_str = path.display().to_string();

    match language {
        // Use ruff format (10-100x faster than black, drop-in compatible)
        Language::Python => Ok((
            "ruff",
            vec!["format".to_string(), "--check".to_string(), path_str],
        )),
        Language::JavaScript | Language::TypeScript => {
            Ok(("prettier", vec!["--check".to_string(), path_str]))
        },
        Language::Go => Ok(("gofmt", vec!["-l".to_string(), path_str])),
        Language::Rust => Ok((
            "cargo",
            vec!["fmt".to_string(), "--".to_string(), "--check".to_string()],
        )),
    }
}

/// Get the command and args for autoformatting
/// Prefers modern tools: ruff for Python (faster than black)
fn get_autoformat_command(language: Language, path: &Path) -> Result<(&'static str, Vec<String>)> {
    let path_str = path.display().to_string();

    match language {
        // Use ruff format (10-100x faster than black, drop-in compatible)
        Language::Python => Ok(("ruff", vec!["format".to_string(), path_str])),
        Language::JavaScript | Language::TypeScript => {
            Ok(("prettier", vec!["--write".to_string(), path_str]))
        },
        Language::Go => Ok(("gofmt", vec!["-w".to_string(), path_str])),
        Language::Rust => Ok(("cargo", vec!["fmt".to_string()])),
    }
}

/// Convert format check response to JSON for MCP
impl FormatCheckResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "formatted": self.formatted,
            "language": self.language,
            "path": self.path,
            "diff": self.diff,
            "message": self.message,
        })
    }
}

impl AutoformatResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "formatted": self.formatted,
            "language": self.language,
            "path": self.path,
            "message": self.message,
            "stdout": self.stdout,
            "stderr": self.stderr,
        })
    }
}

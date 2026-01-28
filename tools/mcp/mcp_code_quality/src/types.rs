//! Data types for the code quality MCP server.

use serde::{Deserialize, Serialize};

/// Programming language for formatters
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    Python,
    Javascript,
    Typescript,
    Go,
    Rust,
}

impl Language {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "python" => Some(Self::Python),
            "javascript" => Some(Self::Javascript),
            "typescript" => Some(Self::Typescript),
            "go" => Some(Self::Go),
            "rust" => Some(Self::Rust),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Python => "python",
            Self::Javascript => "javascript",
            Self::Typescript => "typescript",
            Self::Go => "go",
            Self::Rust => "rust",
        }
    }
}

/// Linter tool
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Linter {
    Flake8,
    Ruff,
    Eslint,
    Golint,
    Clippy,
}

impl Linter {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "flake8" => Some(Self::Flake8),
            "ruff" => Some(Self::Ruff),
            "eslint" => Some(Self::Eslint),
            "golint" => Some(Self::Golint),
            "clippy" => Some(Self::Clippy),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Flake8 => "flake8",
            Self::Ruff => "ruff",
            Self::Eslint => "eslint",
            Self::Golint => "golint",
            Self::Clippy => "clippy",
        }
    }
}

/// Severity level for security scanning
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    Low,
    Medium,
    High,
}

impl Severity {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "low" => Some(Self::Low),
            "medium" => Some(Self::Medium),
            "high" => Some(Self::High),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Low => "low",
            Self::Medium => "medium",
            Self::High => "high",
        }
    }
}

/// Tool execution result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub passed: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub formatted: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub command: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issues: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub findings: Option<Vec<serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finding_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vulnerabilities: Option<Vec<serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vulnerability_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub returncode: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub allowed_paths: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub supported_languages: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub supported_linters: Option<Vec<String>>,
}

impl ToolResult {
    pub fn success() -> Self {
        Self {
            success: true,
            error: None,
            error_type: None,
            passed: None,
            formatted: None,
            output: None,
            command: None,
            issues: None,
            issue_count: None,
            findings: None,
            finding_count: None,
            vulnerabilities: None,
            vulnerability_count: None,
            returncode: None,
            allowed_paths: None,
            supported_languages: None,
            supported_linters: None,
        }
    }

    pub fn error(message: impl Into<String>, error_type: impl Into<String>) -> Self {
        Self {
            success: false,
            error: Some(message.into()),
            error_type: Some(error_type.into()),
            passed: None,
            formatted: None,
            output: None,
            command: None,
            issues: None,
            issue_count: None,
            findings: None,
            finding_count: None,
            vulnerabilities: None,
            vulnerability_count: None,
            returncode: None,
            allowed_paths: None,
            supported_languages: None,
            supported_linters: None,
        }
    }
}

/// Audit log entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub timestamp: String,
    pub operation: String,
    pub path: String,
    pub success: bool,
    #[serde(default)]
    pub details: serde_json::Value,
}

/// Tool status for get_status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolStatus {
    pub available: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

/// Server status response
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerStatus {
    pub server: String,
    pub version: String,
    pub timeout_seconds: u64,
    pub allowed_paths: Vec<String>,
    pub rate_limiting_enabled: bool,
    pub audit_log_path: String,
    pub tools: std::collections::HashMap<String, ToolStatus>,
}

/// Rate limit configuration
#[derive(Debug, Clone, Copy)]
pub struct RateLimitConfig {
    pub calls: usize,
    pub period_secs: u64,
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            calls: 100,
            period_secs: 60,
        }
    }
}

//! Type definitions for Codex MCP server.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Consultation mode for Codex
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum ConsultMode {
    /// Generate new code from scratch
    Generate,
    /// Complete partial code
    Complete,
    /// Refactor existing code
    Refactor,
    /// Explain code functionality
    Explain,
    /// Quick one-shot task
    #[default]
    Quick,
}

impl ConsultMode {
    /// Parse from string
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "generate" => Self::Generate,
            "complete" => Self::Complete,
            "refactor" => Self::Refactor,
            "explain" => Self::Explain,
            _ => Self::Quick,
        }
    }

    /// Get prompt prefix for this mode
    pub fn prompt_prefix(&self) -> &'static str {
        match self {
            Self::Generate => "Generate code for the following requirement:",
            Self::Complete => "Complete the following code:",
            Self::Refactor => "Refactor the following code for better quality:",
            Self::Explain => "Explain the following code:",
            Self::Quick => "Code task:",
        }
    }
}

/// Configuration for Codex integration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodexConfig {
    /// Whether Codex integration is enabled
    pub enabled: bool,
    /// Whether auto-consultation is enabled
    pub auto_consult: bool,
    /// Path to Codex auth file
    pub auth_path: String,
    /// Timeout for Codex operations in seconds
    pub timeout_secs: u64,
    /// Maximum context length
    pub max_context_length: usize,
    /// Whether to log consultations
    pub log_consultations: bool,
    /// Whether to include history in prompts
    pub include_history: bool,
    /// Maximum history entries to keep
    pub max_history_entries: usize,
    /// Whether to bypass sandbox (only in containerized environments)
    pub bypass_sandbox: bool,
}

impl Default for CodexConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            auto_consult: true,
            auth_path: dirs::home_dir()
                .map(|h| {
                    h.join(".codex")
                        .join("auth.json")
                        .to_string_lossy()
                        .to_string()
                })
                .unwrap_or_else(|| "~/.codex/auth.json".to_string()),
            timeout_secs: 300,
            max_context_length: 8000,
            log_consultations: true,
            include_history: true,
            max_history_entries: 5,
            bypass_sandbox: false,
        }
    }
}

impl CodexConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        let mut config = Self::default();

        if let Ok(val) = std::env::var("CODEX_ENABLED") {
            config.enabled = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("CODEX_AUTO_CONSULT") {
            config.auto_consult = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("CODEX_AUTH_PATH") {
            config.auth_path = val;
        }
        if let Some(timeout) = std::env::var("CODEX_TIMEOUT")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.timeout_secs = timeout;
        }
        if let Some(max) = std::env::var("CODEX_MAX_CONTEXT")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.max_context_length = max;
        }
        if let Ok(val) = std::env::var("CODEX_LOG_CONSULTATIONS") {
            config.log_consultations = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("CODEX_INCLUDE_HISTORY") {
            config.include_history = val.to_lowercase() == "true";
        }
        if let Some(max) = std::env::var("CODEX_MAX_HISTORY")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.max_history_entries = max;
        }
        if let Ok(val) = std::env::var("CODEX_BYPASS_SANDBOX") {
            config.bypass_sandbox = val.to_lowercase() == "true";
        }

        config
    }
}

/// A single history entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryEntry {
    /// Timestamp of the interaction
    pub timestamp: DateTime<Utc>,
    /// The query that was sent
    pub query: String,
    /// The mode used
    pub mode: ConsultMode,
    /// Whether it was successful
    pub success: bool,
    /// Output summary (truncated)
    pub output_summary: Option<String>,
}

/// Statistics for Codex usage
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CodexStats {
    /// Total consultations
    pub consultations: u64,
    /// Total errors
    pub errors: u64,
    /// Last consultation timestamp
    pub last_consultation: Option<DateTime<Utc>>,
}

/// Result of a Codex consultation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsultResult {
    /// Status of the operation
    pub status: ConsultStatus,
    /// Output from Codex (if successful)
    pub output: Option<String>,
    /// Error message (if failed)
    pub error: Option<String>,
    /// Mode that was used
    pub mode: ConsultMode,
    /// Additional message
    pub message: Option<String>,
}

/// Status of a consultation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ConsultStatus {
    /// Successful consultation
    Success,
    /// Consultation failed with error
    Error,
    /// Codex is disabled
    Disabled,
}

impl ConsultResult {
    /// Create a success result
    pub fn success(output: String, mode: ConsultMode) -> Self {
        Self {
            status: ConsultStatus::Success,
            output: Some(output),
            error: None,
            mode,
            message: Some("Codex executed successfully".to_string()),
        }
    }

    /// Create an error result
    pub fn error(error: impl Into<String>, mode: ConsultMode) -> Self {
        Self {
            status: ConsultStatus::Error,
            output: None,
            error: Some(error.into()),
            mode,
            message: None,
        }
    }

    /// Create a disabled result
    #[allow(dead_code)]
    pub fn disabled(message: impl Into<String>) -> Self {
        Self {
            status: ConsultStatus::Disabled,
            output: None,
            error: None,
            mode: ConsultMode::Quick,
            message: Some(message.into()),
        }
    }
}

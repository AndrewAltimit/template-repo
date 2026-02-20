//! Type definitions for Gemini MCP server.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Configuration for Gemini integration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeminiConfig {
    /// Whether Gemini integration is enabled
    pub enabled: bool,
    /// Whether auto-consultation is enabled
    pub auto_consult: bool,
    /// Gemini CLI command (default: "gemini")
    pub cli_command: String,
    /// Timeout for Gemini operations in seconds
    pub timeout_secs: u64,
    /// Rate limit delay between consultations in seconds
    pub rate_limit_delay: f64,
    /// Maximum context length
    pub max_context_length: usize,
    /// Whether to log consultations
    pub log_consultations: bool,
    /// Model to use (optional)
    pub model: Option<String>,
    /// Whether to include history in prompts
    pub include_history: bool,
    /// Maximum history entries to keep
    pub max_history_entries: usize,
    /// Whether to use container mode
    pub use_container: bool,
    /// Container image for Gemini
    pub container_image: String,
    /// Container script path
    pub container_script: String,
    /// Whether to use YOLO mode in container
    pub yolo_mode: bool,
    /// Debug mode
    pub debug_mode: bool,
    /// Sandbox mode
    pub sandbox_mode: bool,
}

impl Default for GeminiConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            auto_consult: true,
            cli_command: "gemini".to_string(),
            timeout_secs: 600,
            rate_limit_delay: 2.0,
            max_context_length: 100000,
            log_consultations: true,
            model: Some("gemini-3.1-pro-preview".to_string()),
            include_history: true,
            max_history_entries: 10,
            use_container: true,
            container_image: "gemini-corporate-proxy:latest".to_string(),
            container_script: "/workspace/automation/corporate-proxy/gemini/scripts/run.sh"
                .to_string(),
            yolo_mode: false,
            debug_mode: false,
            sandbox_mode: false,
        }
    }
}

impl GeminiConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        let mut config = Self::default();

        if let Ok(val) = std::env::var("GEMINI_ENABLED") {
            config.enabled = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("GEMINI_AUTO_CONSULT") {
            config.auto_consult = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("GEMINI_CLI_COMMAND") {
            config.cli_command = val;
        }
        if let Some(timeout) = std::env::var("GEMINI_TIMEOUT")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.timeout_secs = timeout;
        }
        if let Some(delay) = std::env::var("GEMINI_RATE_LIMIT")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.rate_limit_delay = delay;
        }
        if let Some(max) = std::env::var("GEMINI_MAX_CONTEXT")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.max_context_length = max;
        }
        if let Ok(val) = std::env::var("GEMINI_LOG_CONSULTATIONS") {
            config.log_consultations = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("GEMINI_MODEL") {
            if !val.is_empty() {
                config.model = Some(val);
            }
        }
        if let Ok(val) = std::env::var("GEMINI_INCLUDE_HISTORY") {
            config.include_history = val.to_lowercase() == "true";
        }
        if let Some(max) = std::env::var("GEMINI_MAX_HISTORY")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.max_history_entries = max;
        }
        if let Ok(val) = std::env::var("GEMINI_USE_CONTAINER") {
            config.use_container = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("GEMINI_CONTAINER_IMAGE") {
            config.container_image = val;
        }
        if let Ok(val) = std::env::var("GEMINI_CONTAINER_SCRIPT") {
            config.container_script = val;
        }
        if let Ok(val) = std::env::var("GEMINI_YOLO_MODE") {
            config.yolo_mode = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("GEMINI_DEBUG") {
            config.debug_mode = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("GEMINI_SANDBOX") {
            config.sandbox_mode = val.to_lowercase() == "true";
        }

        config
    }
}

/// A single history entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryEntry {
    /// The query that was sent
    pub query: String,
    /// The response received
    pub response: String,
}

/// Statistics for Gemini usage
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GeminiStats {
    /// Total consultations
    pub consultations: u64,
    /// Completed consultations
    pub completed: u64,
    /// Total errors
    pub errors: u64,
    /// Total execution time in seconds
    pub total_execution_time: f64,
    /// Last consultation timestamp
    pub last_consultation: Option<DateTime<Utc>>,
}

/// Status of a consultation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ConsultStatus {
    /// Successful consultation
    Success,
    /// Consultation failed with error
    Error,
    /// Gemini is disabled
    Disabled,
    /// Consultation timed out
    Timeout,
}

/// Result of a Gemini consultation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsultResult {
    /// Status of the operation
    pub status: ConsultStatus,
    /// Response from Gemini (if successful)
    pub response: Option<String>,
    /// Error message (if failed)
    pub error: Option<String>,
    /// Execution time in seconds
    pub execution_time: f64,
    /// Consultation ID
    pub consultation_id: String,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
}

impl ConsultResult {
    /// Create a success result
    pub fn success(response: String, execution_time: f64, consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Success,
            response: Some(response),
            error: None,
            execution_time,
            consultation_id,
            timestamp: Utc::now(),
        }
    }

    /// Create an error result
    pub fn error(error: impl Into<String>, consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Error,
            response: None,
            error: Some(error.into()),
            execution_time: 0.0,
            consultation_id,
            timestamp: Utc::now(),
        }
    }

    /// Create a disabled result
    pub fn disabled(consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Disabled,
            response: None,
            error: Some("Gemini integration is disabled".to_string()),
            execution_time: 0.0,
            consultation_id,
            timestamp: Utc::now(),
        }
    }

    /// Create a timeout result
    pub fn timeout(timeout_secs: u64, consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Timeout,
            response: None,
            error: Some(format!(
                "Gemini CLI timed out after {} seconds",
                timeout_secs
            )),
            execution_time: timeout_secs as f64,
            consultation_id,
            timestamp: Utc::now(),
        }
    }
}

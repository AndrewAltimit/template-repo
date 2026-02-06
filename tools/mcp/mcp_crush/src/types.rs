//! Type definitions for Crush MCP server.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Configuration for Crush integration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CrushConfig {
    /// Whether Crush integration is enabled
    pub enabled: bool,
    /// Whether auto-consultation is enabled
    pub auto_consult: bool,
    /// OpenRouter API key
    pub api_key: String,
    /// Timeout for Crush operations in seconds
    pub timeout_secs: u64,
    /// Maximum prompt length
    pub max_prompt_length: usize,
    /// Whether to log consultations
    pub log_consultations: bool,
    /// Whether to include history in prompts
    pub include_history: bool,
    /// Maximum history entries to keep
    pub max_history_entries: usize,
    /// Docker service name for container execution
    pub docker_service: String,
    /// Use quiet mode (suppress TTY features)
    pub quiet_mode: bool,
}

impl Default for CrushConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            auto_consult: true,
            api_key: String::new(),
            timeout_secs: 300,
            max_prompt_length: 4000,
            log_consultations: true,
            include_history: true,
            max_history_entries: 5,
            docker_service: "openrouter-agents".to_string(),
            quiet_mode: true,
        }
    }
}

impl CrushConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        let mut config = Self::default();

        if let Ok(val) = std::env::var("CRUSH_ENABLED") {
            config.enabled = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("CRUSH_AUTO_CONSULT") {
            config.auto_consult = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("OPENROUTER_API_KEY") {
            config.api_key = val;
        }
        if let Some(timeout) = std::env::var("CRUSH_TIMEOUT")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.timeout_secs = timeout;
        }
        if let Some(max) = std::env::var("CRUSH_MAX_PROMPT")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.max_prompt_length = max;
        }
        if let Ok(val) = std::env::var("CRUSH_LOG_CONSULTATIONS") {
            config.log_consultations = val.to_lowercase() == "true";
        }
        if let Ok(val) = std::env::var("CRUSH_INCLUDE_HISTORY") {
            config.include_history = val.to_lowercase() == "true";
        }
        if let Some(max) = std::env::var("CRUSH_MAX_HISTORY")
            .ok()
            .and_then(|v| v.parse().ok())
        {
            config.max_history_entries = max;
        }
        if let Ok(val) = std::env::var("CRUSH_DOCKER_SERVICE") {
            config.docker_service = val;
        }
        if let Ok(val) = std::env::var("CRUSH_QUIET_MODE") {
            config.quiet_mode = val.to_lowercase() == "true";
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

/// Statistics for Crush usage
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CrushStats {
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
    /// Crush is disabled
    Disabled,
    /// Consultation timed out
    Timeout,
}

/// Result of a Crush consultation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsultResult {
    /// Status of the operation
    pub status: ConsultStatus,
    /// Response from Crush (if successful)
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
            error: Some("Crush integration is disabled".to_string()),
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
            error: Some(format!("Crush timed out after {} seconds", timeout_secs)),
            execution_time: timeout_secs as f64,
            consultation_id,
            timestamp: Utc::now(),
        }
    }
}

//! Type definitions for OpenCode MCP server.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// OpenCode configuration
#[derive(Debug, Clone)]
pub struct OpenCodeConfig {
    /// Whether OpenCode integration is enabled
    pub enabled: bool,
    /// Whether to auto-consult on uncertainty detection
    pub auto_consult: bool,
    /// OpenRouter API key
    pub api_key: String,
    /// Model to use for code generation
    pub model: String,
    /// Timeout in seconds for API calls
    pub timeout_secs: u64,
    /// Maximum prompt length
    pub max_prompt_length: usize,
    /// Whether to log consultations
    pub log_consultations: bool,
    /// Whether to include history in prompts
    pub include_history: bool,
    /// Maximum number of history entries to keep
    pub max_history_entries: usize,
}

impl OpenCodeConfig {
    /// Create configuration from environment variables
    pub fn from_env() -> Self {
        Self {
            enabled: std::env::var("OPENCODE_ENABLED")
                .map(|v| v.to_lowercase() != "false" && v != "0")
                .unwrap_or(true),
            auto_consult: std::env::var("OPENCODE_AUTO_CONSULT")
                .map(|v| v.to_lowercase() != "false" && v != "0")
                .unwrap_or(true),
            api_key: std::env::var("OPENROUTER_API_KEY").unwrap_or_default(),
            model: std::env::var("OPENCODE_MODEL")
                .unwrap_or_else(|_| "qwen/qwen-2.5-coder-32b-instruct".to_string()),
            timeout_secs: std::env::var("OPENCODE_TIMEOUT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(300),
            max_prompt_length: std::env::var("OPENCODE_MAX_PROMPT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(8000),
            log_consultations: std::env::var("OPENCODE_LOG_CONSULTATIONS")
                .map(|v| v.to_lowercase() != "false" && v != "0")
                .unwrap_or(true),
            include_history: std::env::var("OPENCODE_INCLUDE_HISTORY")
                .map(|v| v.to_lowercase() != "false" && v != "0")
                .unwrap_or(true),
            max_history_entries: std::env::var("OPENCODE_MAX_HISTORY")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(5),
        }
    }
}

/// Consultation mode for OpenCode
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsultMode {
    /// Generate code from requirements
    Generate,
    /// Refactor existing code
    Refactor,
    /// Review code for issues
    Review,
    /// Explain code functionality
    Explain,
    /// Quick response mode
    Quick,
}

impl ConsultMode {
    /// Parse mode from string
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "generate" => Self::Generate,
            "refactor" => Self::Refactor,
            "review" => Self::Review,
            "explain" => Self::Explain,
            _ => Self::Quick,
        }
    }

    /// Get the system prompt for this mode
    pub fn system_prompt(&self) -> &'static str {
        match self {
            Self::Generate => {
                "You are an expert code generator. Generate clean, well-documented code \
                 based on the requirements provided. Include type hints and docstrings where appropriate."
            },
            Self::Refactor => {
                "You are an expert code refactoring assistant. Analyze the provided code \
                 and suggest improvements for readability, performance, and maintainability. \
                 Provide the refactored code with explanations for changes."
            },
            Self::Review => {
                "You are an expert code reviewer. Analyze the provided code for potential \
                 bugs, security issues, performance problems, and style violations. \
                 Provide specific, actionable feedback."
            },
            Self::Explain => {
                "You are an expert code explainer. Provide clear, detailed explanations \
                 of how the provided code works. Include information about the algorithms, \
                 data structures, and patterns used."
            },
            Self::Quick => {
                "You are a helpful coding assistant. Provide concise, accurate responses \
                 to coding questions. Focus on practical solutions."
            },
        }
    }
}

/// Status of a consultation
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsultStatus {
    /// Consultation completed successfully
    Success,
    /// Consultation failed with an error
    Error,
    /// Consultation disabled
    Disabled,
    /// Consultation timed out
    Timeout,
}

/// Result of a consultation
#[derive(Debug, Clone)]
pub struct ConsultResult {
    /// Status of the consultation
    pub status: ConsultStatus,
    /// Response from OpenCode (if successful)
    pub response: Option<String>,
    /// Error message (if failed)
    pub error: Option<String>,
    /// Execution time in seconds
    pub execution_time: Option<f64>,
    /// Unique consultation ID
    pub _consultation_id: String,
    /// Timestamp of the consultation
    pub _timestamp: DateTime<Utc>,
}

impl ConsultResult {
    /// Create a successful result
    pub fn success(response: String, execution_time: f64, consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Success,
            response: Some(response),
            error: None,
            execution_time: Some(execution_time),
            _consultation_id: consultation_id,
            _timestamp: Utc::now(),
        }
    }

    /// Create an error result
    pub fn error<S: Into<String>>(error: S, consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Error,
            response: None,
            error: Some(error.into()),
            execution_time: None,
            _consultation_id: consultation_id,
            _timestamp: Utc::now(),
        }
    }

    /// Create a disabled result
    pub fn disabled(consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Disabled,
            response: None,
            error: Some("OpenCode integration is disabled".to_string()),
            execution_time: None,
            _consultation_id: consultation_id,
            _timestamp: Utc::now(),
        }
    }

    /// Create a timeout result
    pub fn timeout(timeout_secs: u64, consultation_id: String) -> Self {
        Self {
            status: ConsultStatus::Timeout,
            response: None,
            error: Some(format!("OpenCode timed out after {} seconds", timeout_secs)),
            execution_time: None,
            _consultation_id: consultation_id,
            _timestamp: Utc::now(),
        }
    }
}

/// History entry for conversation tracking
#[derive(Debug, Clone)]
pub struct HistoryEntry {
    /// The query that was sent
    pub query: String,
    /// The response received
    pub response: String,
}

/// Statistics for OpenCode integration
#[derive(Debug, Clone, Default)]
pub struct OpenCodeStats {
    /// Total number of consultations
    pub consultations: u64,
    /// Number of completed consultations
    pub completed: u64,
    /// Number of errors
    pub errors: u64,
    /// Total execution time in seconds
    pub total_execution_time: f64,
    /// Last consultation timestamp
    pub last_consultation: Option<DateTime<Utc>>,
}

/// OpenRouter API request message
#[derive(Debug, Serialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

/// OpenRouter API request
#[derive(Debug, Serialize)]
pub struct ChatCompletionRequest {
    pub model: String,
    pub messages: Vec<ChatMessage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
}

/// OpenRouter API response choice
#[derive(Debug, Deserialize)]
pub struct ChatChoice {
    pub message: ChatResponseMessage,
}

/// OpenRouter API response message
#[derive(Debug, Deserialize)]
pub struct ChatResponseMessage {
    pub content: String,
}

/// OpenRouter API response
#[derive(Debug, Deserialize)]
pub struct ChatCompletionResponse {
    pub choices: Vec<ChatChoice>,
}

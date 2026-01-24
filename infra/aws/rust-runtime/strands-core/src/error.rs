//! Error types for the Strands agent framework.

use thiserror::Error;

/// Core error type for the Strands framework.
#[derive(Error, Debug)]
pub enum StrandsError {
    /// Model provider error
    #[error("Model error: {message}")]
    Model {
        message: String,
        #[source]
        source: Option<Box<dyn std::error::Error + Send + Sync>>,
    },

    /// Context window overflow - conversation too large
    #[error("Context window overflow: {message}")]
    ContextWindowOverflow { message: String },

    /// Model was throttled - rate limit exceeded
    #[error("Model throttled: {message}")]
    ModelThrottled { message: String },

    /// Tool execution error
    #[error("Tool error: {tool_name} - {message}")]
    Tool {
        tool_name: String,
        message: String,
        #[source]
        source: Option<Box<dyn std::error::Error + Send + Sync>>,
    },

    /// Tool not found
    #[error("Tool not found: {tool_name}")]
    ToolNotFound { tool_name: String },

    /// Invalid tool input
    #[error("Invalid tool input for {tool_name}: {message}")]
    InvalidToolInput { tool_name: String, message: String },

    /// Session error
    #[error("Session error: {message}")]
    Session {
        message: String,
        #[source]
        source: Option<Box<dyn std::error::Error + Send + Sync>>,
    },

    /// Guardrail blocked content
    #[error("Content blocked by guardrail: {message}")]
    GuardrailBlocked { message: String },

    /// Configuration error
    #[error("Configuration error: {message}")]
    Configuration { message: String },

    /// Serialization/deserialization error
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// IO error
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// Agent is already processing a request
    #[error("Agent is busy - concurrent invocation not allowed")]
    AgentBusy,

    /// Maximum iterations exceeded
    #[error("Maximum iterations ({max}) exceeded")]
    MaxIterationsExceeded { max: u32 },

    /// Internal error
    #[error("Internal error: {message}")]
    Internal { message: String },
}

impl StrandsError {
    /// Create a model error.
    pub fn model(message: impl Into<String>) -> Self {
        Self::Model {
            message: message.into(),
            source: None,
        }
    }

    /// Create a model error with source.
    pub fn model_with_source(
        message: impl Into<String>,
        source: impl std::error::Error + Send + Sync + 'static,
    ) -> Self {
        Self::Model {
            message: message.into(),
            source: Some(Box::new(source)),
        }
    }

    /// Create a context window overflow error.
    pub fn context_overflow(message: impl Into<String>) -> Self {
        Self::ContextWindowOverflow {
            message: message.into(),
        }
    }

    /// Create a throttled error.
    pub fn throttled(message: impl Into<String>) -> Self {
        Self::ModelThrottled {
            message: message.into(),
        }
    }

    /// Create a tool error.
    pub fn tool(tool_name: impl Into<String>, message: impl Into<String>) -> Self {
        Self::Tool {
            tool_name: tool_name.into(),
            message: message.into(),
            source: None,
        }
    }

    /// Create a tool error with source.
    pub fn tool_with_source(
        tool_name: impl Into<String>,
        message: impl Into<String>,
        source: impl std::error::Error + Send + Sync + 'static,
    ) -> Self {
        Self::Tool {
            tool_name: tool_name.into(),
            message: message.into(),
            source: Some(Box::new(source)),
        }
    }

    /// Create a tool not found error.
    pub fn tool_not_found(tool_name: impl Into<String>) -> Self {
        Self::ToolNotFound {
            tool_name: tool_name.into(),
        }
    }

    /// Create a session error.
    pub fn session(message: impl Into<String>) -> Self {
        Self::Session {
            message: message.into(),
            source: None,
        }
    }

    /// Create a configuration error.
    pub fn config(message: impl Into<String>) -> Self {
        Self::Configuration {
            message: message.into(),
        }
    }

    /// Create an internal error.
    pub fn internal(message: impl Into<String>) -> Self {
        Self::Internal {
            message: message.into(),
        }
    }

    /// Check if this error is retryable.
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            StrandsError::ModelThrottled { .. } | StrandsError::ContextWindowOverflow { .. }
        )
    }
}

/// Result type alias for Strands operations.
pub type Result<T> = std::result::Result<T, StrandsError>;

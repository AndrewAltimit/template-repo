//! Error types for economic agent operations.

use thiserror::Error;

/// Core error type for economic agent operations.
#[derive(Debug, Error)]
pub enum EconomicAgentError {
    /// Agent state has not been initialized.
    #[error("agent not initialized")]
    NotInitialized,

    /// Insufficient funds for the requested operation.
    #[error("insufficient capital: need {required}, have {available}")]
    InsufficientCapital { required: f64, available: f64 },

    /// Invalid company stage transition.
    #[error("invalid stage transition from {from} to {to}")]
    InvalidStageTransition { from: String, to: String },

    /// Task not found.
    #[error("task not found: {id}")]
    TaskNotFound { id: String },

    /// Task already claimed by another agent.
    #[error("task {id} already claimed")]
    TaskAlreadyClaimed { id: String },

    /// Submission failed validation.
    #[error("submission rejected: {reason}")]
    SubmissionRejected { reason: String },

    /// Network or API error.
    #[error("network error: {0}")]
    Network(String),

    /// Configuration error.
    #[error("configuration error: {0}")]
    Configuration(String),

    /// Internal error.
    #[error("internal error: {0}")]
    Internal(String),
}

/// Alias for Result with EconomicAgentError.
pub type Result<T> = std::result::Result<T, EconomicAgentError>;

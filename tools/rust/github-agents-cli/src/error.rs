//! Error types for the GitHub Agents CLI.

use thiserror::Error;

/// Result type for the GitHub Agents CLI
pub type Result<T> = std::result::Result<T, Error>;

/// Error types for the GitHub Agents CLI
#[derive(Error, Debug)]
pub enum Error {
    /// Monitor subprocess failed
    #[error("Monitor failed: {0}")]
    MonitorFailed(String),

    /// GitHub CLI not available
    #[error("GitHub CLI (gh) not found")]
    GhNotFound,

    /// GitHub CLI not authenticated
    #[error("GitHub CLI not authenticated")]
    GhNotAuthenticated,

    /// GitHub CLI command failed
    #[error("GitHub CLI command failed (exit code {exit_code}): {stderr}")]
    GhCommandFailed {
        exit_code: i32,
        stdout: String,
        stderr: String,
    },

    /// Git not found
    #[error("Git not found")]
    GitNotFound,

    /// Git command failed
    #[error("Git command failed (exit code {exit_code})")]
    GitCommandFailed {
        exit_code: i32,
        stdout: String,
        stderr: String,
    },

    /// GitHub token not found
    #[error("GitHub token not found in environment (GITHUB_TOKEN or GH_TOKEN)")]
    GitHubTokenNotFound,

    /// Monitor was interrupted
    #[error("Monitor interrupted by user")]
    Interrupted,

    /// I/O error
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// JSON parsing error
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// YAML parsing error
    #[error("YAML error: {0}")]
    Yaml(#[from] serde_yaml::Error),

    /// Configuration error
    #[error("Configuration error: {0}")]
    Config(String),

    /// Agent not available
    #[error("Agent '{name}' is not available: {reason}")]
    AgentNotAvailable { name: String, reason: String },

    /// Agent execution failed
    #[error("Agent '{name}' failed with exit code {exit_code}: {stderr}")]
    AgentExecutionFailed {
        name: String,
        exit_code: i32,
        stdout: String,
        stderr: String,
    },

    /// Agent timed out
    #[error("Agent '{name}' timed out after {timeout}s")]
    AgentTimeout {
        name: String,
        timeout: u64,
        stdout: String,
        stderr: String,
    },

    /// Security check failed
    #[error("Security check failed: {0}")]
    SecurityCheck(String),

    /// Environment variable not set
    #[error("Environment variable not set: {0}")]
    EnvNotSet(String),

    /// HTTP error
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    /// Board manager error
    #[error("Board error: {0}")]
    Board(String),
}

impl Error {
    /// Get the exit code for this error
    pub fn exit_code(&self) -> i32 {
        match self {
            Error::Interrupted => 130,
            Error::GhNotFound | Error::GhNotAuthenticated => 2,
            Error::GitHubTokenNotFound => 3,
            Error::AgentNotAvailable { .. } => 5,
            Error::AgentExecutionFailed { .. } => 6,
            Error::AgentTimeout { .. } => 7,
            Error::SecurityCheck(_) => 8,
            _ => 1,
        }
    }

    /// Get help text for this error
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            Error::GhNotFound => Some(
                "Make sure the GitHub CLI is installed:\n\
                 1. Install: https://cli.github.com/",
            ),
            Error::GhNotAuthenticated => Some(
                "Make sure the GitHub CLI is authenticated:\n\
                 gh auth login",
            ),
            Error::GitHubTokenNotFound => Some(
                "Set the GITHUB_TOKEN or GH_TOKEN environment variable:\n\
                 export GITHUB_TOKEN=ghp_...",
            ),
            Error::GitNotFound => Some(
                "Make sure Git is installed:\n\
                 apt install git  # or equivalent for your system",
            ),
            _ => None,
        }
    }
}

//! Error types for the GitHub Agents CLI.

use thiserror::Error;

/// Error types for the GitHub Agents CLI
#[derive(Error, Debug)]
pub enum Error {
    /// Python monitor subprocess failed
    #[error("Python monitor failed: {0}")]
    MonitorFailed(String),

    /// Python not found or not configured
    #[error("Python interpreter not found")]
    PythonNotFound,

    /// GitHub CLI not available
    #[error("GitHub CLI (gh) not found or not authenticated")]
    GhNotFound,

    /// Monitor was interrupted
    #[error("Monitor interrupted by user")]
    Interrupted,

    /// I/O error
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// JSON parsing error
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
}

impl Error {
    /// Get the exit code for this error
    pub fn exit_code(&self) -> i32 {
        match self {
            Error::Interrupted => 130,
            Error::GhNotFound => 2,
            Error::PythonNotFound => 3,
            _ => 1,
        }
    }

    /// Get help text for this error
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            Error::GhNotFound => Some(
                "Make sure the GitHub CLI is installed and authenticated:\n\
                 1. Install: https://cli.github.com/\n\
                 2. Authenticate: gh auth login",
            ),
            Error::PythonNotFound => Some(
                "Make sure Python 3 is installed and the github_agents package is available:\n\
                 1. pip install -e ./packages/github_agents",
            ),
            _ => None,
        }
    }
}

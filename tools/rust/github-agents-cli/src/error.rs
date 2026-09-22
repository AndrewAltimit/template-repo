//! Error types for the GitHub Agents CLI.
//!
//! Each variant maps to a documented process exit code (see
//! [`Error::exit_code`]); workflows rely on non-zero exits and on the
//! `service unavailable (transient)` text for graceful skipping.

use thiserror::Error;

/// Result type for the GitHub Agents CLI
pub type Result<T> = std::result::Result<T, Error>;

/// Error types for the GitHub Agents CLI
#[derive(Error, Debug)]
pub enum Error {
    /// A monitor or subprocess step failed (e.g. timed out)
    #[error("Monitor failed: {0}")]
    MonitorFailed(String),

    /// GitHub CLI not available
    #[error("GitHub CLI (gh) not found")]
    GhNotFound,

    /// GitHub CLI not authenticated
    #[error("GitHub CLI not authenticated")]
    GhNotAuthenticated,

    /// GitHub CLI command failed
    #[error("GitHub CLI command failed (exit code {exit_code}): {}", stderr.trim())]
    GhCommandFailed {
        exit_code: i32,
        stdout: String,
        stderr: String,
    },

    /// Git not found
    #[error("Git not found")]
    GitNotFound,

    /// Git command failed
    #[error("Git command failed (exit code {exit_code}): {}", stderr.trim())]
    GitCommandFailed {
        exit_code: i32,
        stdout: String,
        stderr: String,
    },

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

    /// Agent not available (unknown, disabled by policy, or not installed)
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
                 gh auth login   (or set GITHUB_TOKEN / GH_TOKEN)",
            ),
            Error::GitNotFound => Some(
                "Make sure Git is installed:\n\
                 apt install git  # or equivalent for your system",
            ),
            Error::EnvNotSet(var) if var == "GITHUB_REPOSITORY" => {
                Some("Set GITHUB_REPOSITORY to owner/repo (set automatically in GitHub Actions)")
            },
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exit_codes_are_stable() {
        assert_eq!(Error::Interrupted.exit_code(), 130);
        assert_eq!(Error::GhNotFound.exit_code(), 2);
        assert_eq!(
            Error::AgentNotAvailable {
                name: "x".into(),
                reason: "y".into()
            }
            .exit_code(),
            5
        );
        assert_eq!(Error::SecurityCheck("x".into()).exit_code(), 8);
        assert_eq!(Error::Config("x".into()).exit_code(), 1);
    }

    #[test]
    fn transient_text_is_preserved_in_display() {
        let e = Error::AgentExecutionFailed {
            name: "claude".into(),
            exit_code: 1,
            stdout: String::new(),
            stderr: "service unavailable (transient): 503".into(),
        };
        assert!(e.to_string().contains("service unavailable (transient)"));
    }
}

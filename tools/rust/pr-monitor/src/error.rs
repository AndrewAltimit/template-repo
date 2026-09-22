//! Error types for pr-monitor
//!
//! All errors follow a fail-closed principle with helpful guidance for users.

use thiserror::Error;

/// Exit code used for errors and (by default) for timeouts.
pub const EXIT_FAILURE: i32 = 1;

/// Exit code used when the user interrupts monitoring (standard for SIGINT).
pub const EXIT_INTERRUPTED: i32 = 130;

/// Main error type for pr-monitor
#[derive(Debug, Error)]
pub enum Error {
    /// The `gh` binary could not be found on `PATH`
    #[error("GitHub CLI (gh) was not found on PATH")]
    GhNotFound,

    /// Failed to execute gh command (spawn / IO failure)
    #[error("Failed to execute gh command: {0}")]
    GhExecution(#[from] std::io::Error),

    /// gh command failed with non-zero exit code
    #[error("gh command failed with exit code {code}: {stderr}")]
    GhFailed { code: i32, stderr: String },

    /// GitHub reported a (primary or secondary) rate limit
    #[error("GitHub API rate limit hit: {message}")]
    RateLimited { message: String },

    /// The GraphQL API returned errors
    #[error("GitHub GraphQL error: {0}")]
    GraphQl(String),

    /// The pull request does not exist or is not accessible
    #[error("Pull request #{pr_number} was not found (or is not accessible)")]
    PrNotFound { pr_number: u32 },

    /// `--repo` value was not of the form OWNER/REPO
    #[error("Invalid repository '{0}': expected OWNER/REPO")]
    InvalidRepo(String),

    /// Failed to parse gh output as JSON
    #[error("Failed to parse gh output as JSON: {0}")]
    JsonParse(#[from] serde_json::Error),

    /// Failed to parse timestamp
    #[error("Failed to parse timestamp '{timestamp}': {reason}")]
    TimestampParse { timestamp: String, reason: String },

    /// Failed to get commit timestamp
    #[error("Failed to get commit timestamp for {sha}: {reason}")]
    CommitLookup { sha: String, reason: String },

    /// Timeout with no relevant comments
    #[error("Timeout after {seconds} seconds with no relevant comments")]
    Timeout { seconds: u64 },

    /// Interrupted by user (Ctrl+C)
    #[error("Interrupted by user")]
    Interrupted,
}

impl Error {
    /// Returns additional help text for specific errors
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            Error::GhNotFound => Some(
                "Install the GitHub CLI (https://cli.github.com/) and authenticate:\n\
                   gh auth login",
            ),
            Error::GhExecution(_) | Error::GhFailed { .. } | Error::GraphQl(_) => Some(
                "Ensure gh CLI is installed and authenticated:\n\
                   gh auth login\n\
                   gh auth status",
            ),
            Error::RateLimited { .. } => Some(
                "GitHub throttled the requests. Increase --poll-interval or wait for the\n\
                 rate limit window to reset (gh api rate_limit).",
            ),
            Error::PrNotFound { .. } => Some(
                "Verify the PR exists (gh pr view NUMBER) and that you are in the right\n\
                 repository, or pass --repo OWNER/REPO.",
            ),
            Error::CommitLookup { .. } => Some(
                "The commit SHA may not exist or you may not have access.\n\
                 Verify the commit exists: git log --oneline | grep SHA",
            ),
            Error::Timeout { .. } => Some(
                "No relevant comments were detected within the timeout period.\n\
                 Increase timeout with --timeout flag or check PR manually.",
            ),
            Error::Interrupted => Some("Monitoring was interrupted by Ctrl+C."),
            _ => None,
        }
    }

    /// Exit code for this error.
    ///
    /// `timeout_code` is the code used for [`Error::Timeout`] (configurable via
    /// `--timeout-exit-code`, default 1).
    pub fn exit_code(&self, timeout_code: i32) -> i32 {
        match self {
            Error::Timeout { .. } => timeout_code,
            Error::Interrupted => EXIT_INTERRUPTED,
            _ => EXIT_FAILURE,
        }
    }

    /// Whether a polling failure is worth retrying rather than aborting.
    ///
    /// Network blips, 5xx responses and rate limits are transient; missing
    /// binaries, authentication problems and unknown PRs are not.
    pub fn is_transient(&self) -> bool {
        match self {
            Error::RateLimited { .. } | Error::JsonParse(_) | Error::GraphQl(_) => true,
            Error::GhFailed { stderr, .. } => !is_auth_failure(stderr),
            _ => false,
        }
    }
}

/// Heuristic for gh stderr output that indicates an authentication problem.
pub(crate) fn is_auth_failure(stderr: &str) -> bool {
    let lower = stderr.to_ascii_lowercase();
    lower.contains("gh auth login")
        || lower.contains("http 401")
        || lower.contains("bad credentials")
        || lower.contains("authentication")
        || lower.contains("not logged in")
}

/// Heuristic for gh stderr output that indicates a rate limit.
pub(crate) fn is_rate_limit(stderr: &str) -> bool {
    let lower = stderr.to_ascii_lowercase();
    lower.contains("rate limit") || lower.contains("abuse detection")
}

/// Result type alias for pr-monitor operations
pub type Result<T> = std::result::Result<T, Error>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exit_codes() {
        assert_eq!(Error::Timeout { seconds: 5 }.exit_code(1), 1);
        assert_eq!(Error::Timeout { seconds: 5 }.exit_code(2), 2);
        assert_eq!(Error::Interrupted.exit_code(2), 130);
        assert_eq!(Error::GhNotFound.exit_code(2), 1);
        assert_eq!(Error::PrNotFound { pr_number: 1 }.exit_code(2), 1);
    }

    #[test]
    fn test_transient_classification() {
        let blip = Error::GhFailed {
            code: 1,
            stderr: "HTTP 502: Bad Gateway".to_string(),
        };
        assert!(blip.is_transient());

        let auth = Error::GhFailed {
            code: 4,
            stderr: "To get started with GitHub CLI, please run:  gh auth login".to_string(),
        };
        assert!(!auth.is_transient());

        assert!(
            Error::RateLimited {
                message: "API rate limit exceeded".to_string()
            }
            .is_transient()
        );
        assert!(!Error::PrNotFound { pr_number: 3 }.is_transient());
        assert!(!Error::GhNotFound.is_transient());
    }

    #[test]
    fn test_stderr_heuristics() {
        assert!(is_rate_limit("gh: API rate limit exceeded for user ID 1"));
        assert!(is_rate_limit("You have exceeded a secondary rate limit"));
        assert!(!is_rate_limit("HTTP 502"));
        assert!(is_auth_failure("HTTP 401: Bad credentials"));
        assert!(!is_auth_failure("HTTP 502: Bad Gateway"));
    }
}

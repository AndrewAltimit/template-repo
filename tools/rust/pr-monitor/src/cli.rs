//! CLI argument parsing for pr-monitor

use std::path::PathBuf;

use clap::Parser;

use crate::analysis::{DEFAULT_ADMIN_USER, ResponseType};

/// Monitor a GitHub PR for admin or AI reviewer comments
#[derive(Parser, Debug)]
#[command(name = "pr-monitor")]
#[command(author, version, about, long_about = None)]
#[command(after_help = "EXAMPLES:
    pr-monitor 123                          # Monitor PR #123
    pr-monitor 123 --timeout 1800           # Monitor for 30 minutes
    pr-monitor 123 --json                   # Output only JSON (quiet mode)
    pr-monitor 123 --since-commit abc1234   # Only monitor comments after commit
    pr-monitor 123 --type ai_agent_review   # Wait for an AI code review only
    pr-monitor 123 --since-commit HEAD --timeout 0   # One-shot: anything pending?

WATCHED BY DEFAULT:
    The admin user, github-actions (Claude / OpenRouter review pipeline, CI
    status table), GitHub Copilot code review, and the Claude GitHub App.
    Conversation comments and PR reviews (with inline comments) are covered.

EXIT CODES:
    0 - Found relevant comment (output as JSON)
    1 - Timeout or error (no relevant comment found)
        (use --timeout-exit-code to give timeouts a distinct code)
    130 - Interrupted by user (Ctrl+C)")]
pub struct Args {
    /// PR number to monitor
    pub pr_number: u32,

    /// Timeout in seconds (default: 600 = 10 minutes; 0 = check existing comments once)
    #[arg(long, default_value = "600")]
    pub timeout: u64,

    /// Poll interval in seconds (default: 5, minimum: 1)
    #[arg(long, default_value = "5", value_parser = clap::value_parser!(u64).range(1..))]
    pub poll_interval: u64,

    /// Output only JSON (suppress stderr progress messages; warnings still print)
    #[arg(long)]
    pub json: bool,

    /// Only monitor comments after this commit (SHA or local ref such as HEAD).
    /// Existing comments after the commit that need a response are reported
    /// immediately.
    #[arg(long, value_name = "SHA")]
    pub since_commit: Option<String>,

    /// Repository to monitor (default: the repository of the current directory)
    #[arg(long, short = 'R', value_name = "OWNER/REPO")]
    pub repo: Option<String>,

    /// Admin user whose comments and commands are always relevant
    #[arg(
        long,
        value_name = "LOGIN",
        env = "PR_MONITOR_ADMIN_USER",
        default_value = DEFAULT_ADMIN_USER
    )]
    pub admin_user: String,

    /// Only watch these authors (repeatable or comma-separated). Replaces the
    /// default admin + review-bot set; other comments from these authors are
    /// reported as `user_comment`.
    #[arg(long = "author", value_name = "LOGIN", value_delimiter = ',')]
    pub authors: Vec<String>,

    /// Only report these response types (repeatable or comma-separated):
    /// admin_command, admin_comment, admin_approval, ai_agent_review,
    /// ci_results, user_comment
    #[arg(long = "type", value_name = "TYPE", value_delimiter = ',')]
    pub types: Vec<ResponseType>,

    /// Exit code used when the timeout expires (default: 1, same as errors)
    #[arg(
        long,
        value_name = "CODE",
        default_value = "1",
        value_parser = clap::value_parser!(i32).range(1..=255)
    )]
    pub timeout_exit_code: i32,

    /// Print the JSON decision on a single line instead of pretty-printed
    #[arg(long)]
    pub compact: bool,

    /// Deprecated and ignored (reserved for a config file that was never implemented)
    #[arg(long, hide = true)]
    pub config: Option<PathBuf>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::CommandFactory;

    #[test]
    fn test_cli_definition_is_valid() {
        Args::command().debug_assert();
    }

    #[test]
    fn test_defaults_preserved() {
        let args = Args::try_parse_from(["pr-monitor", "48"]).unwrap();
        assert_eq!(args.pr_number, 48);
        assert_eq!(args.timeout, 600);
        assert_eq!(args.poll_interval, 5);
        assert!(!args.json);
        assert!(args.since_commit.is_none());
        assert_eq!(args.timeout_exit_code, 1);
        assert!(args.authors.is_empty());
        assert!(args.types.is_empty());
    }

    #[test]
    fn test_legacy_invocation() {
        let args = Args::try_parse_from([
            "pr-monitor",
            "48",
            "--since-commit",
            "abc1234",
            "--timeout",
            "1800",
            "--poll-interval",
            "10",
            "--json",
        ])
        .unwrap();
        assert_eq!(args.since_commit.as_deref(), Some("abc1234"));
        assert_eq!(args.timeout, 1800);
        assert_eq!(args.poll_interval, 10);
        assert!(args.json);
    }

    #[test]
    fn test_filters_parse() {
        let args = Args::try_parse_from([
            "pr-monitor",
            "1",
            "--type",
            "ai_agent_review,admin_command",
            "--type",
            "ci-results",
            "--author",
            "a,b",
            "--author",
            "c",
        ])
        .unwrap();
        assert_eq!(
            args.types,
            vec![
                ResponseType::AiAgentReview,
                ResponseType::AdminCommand,
                ResponseType::CiResults
            ]
        );
        assert_eq!(args.authors, vec!["a", "b", "c"]);
    }

    #[test]
    fn test_invalid_values_rejected() {
        assert!(Args::try_parse_from(["pr-monitor", "1", "--type", "bogus"]).is_err());
        assert!(Args::try_parse_from(["pr-monitor", "1", "--poll-interval", "0"]).is_err());
        assert!(Args::try_parse_from(["pr-monitor", "1", "--timeout-exit-code", "0"]).is_err());
        assert!(Args::try_parse_from(["pr-monitor", "abc"]).is_err());
    }
}

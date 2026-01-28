//! CLI argument definitions.

use clap::Parser;

/// Process code review JSON output from AgentCore.
#[derive(Parser, Debug)]
#[command(name = "code-review-processor")]
#[command(version, about, long_about = None)]
pub struct Args {
    /// Path to JSON file from AgentCore (or '-' for stdin)
    #[arg(short, long, default_value = "-")]
    pub input: String,

    /// Post review as a GitHub comment
    #[arg(long)]
    pub post_comment: bool,

    /// Commit file changes to the repository
    #[arg(long)]
    pub commit_changes: bool,

    /// Create a PR with the changes
    #[arg(long)]
    pub create_pr: bool,

    /// PR number to comment on (for --post-comment)
    #[arg(long)]
    pub pr_number: Option<u64>,

    /// Repository (owner/repo format)
    #[arg(long, env = "GITHUB_REPOSITORY")]
    pub repository: Option<String>,

    /// Branch to commit to (default: creates new branch)
    #[arg(long)]
    pub branch: Option<String>,

    /// Base branch for PR (default: main)
    #[arg(long, default_value = "main")]
    pub base_branch: String,

    /// Commit message for changes
    #[arg(long, default_value = "Apply code review fixes")]
    pub commit_message: String,

    /// Dry run - print actions without executing
    #[arg(long)]
    pub dry_run: bool,

    /// Output format (text or json)
    #[arg(long, default_value = "text")]
    pub output_format: String,
}

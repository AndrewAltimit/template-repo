//! CLI argument definitions.

use anyhow::{Result, bail};
use clap::{Parser, ValueEnum};

use crate::review::Severity;

/// Process code review JSON output from AgentCore.
///
/// Reads a `/code-review` response (the full endpoint envelope or the bare
/// review object), then optionally posts the review as a PR comment, applies
/// and commits the proposed fixes, and opens a PR with them.
///
/// Exit codes: 0 success, 1 error, 2 invalid arguments, 3 severity at or
/// above --fail-on-severity.
#[derive(Parser, Debug, Clone)]
#[command(name = "code-review-processor")]
#[command(version, about, long_about)]
pub struct Args {
    /// Path to JSON file from AgentCore (or '-' for stdin)
    #[arg(short, long, default_value = "-")]
    pub input: String,

    /// Post review as a GitHub comment (requires --pr-number and a repository)
    #[arg(long)]
    pub post_comment: bool,

    /// Apply the proposed file changes and commit them on the current branch
    #[arg(long)]
    pub commit_changes: bool,

    /// Apply the proposed file changes on a new branch, push it, and open a PR
    #[arg(long)]
    pub create_pr: bool,

    /// Push the current branch to origin after --commit-changes
    #[arg(long)]
    pub push: bool,

    /// PR number to comment on (for --post-comment)
    #[arg(long, value_parser = clap::value_parser!(u64).range(1..))]
    pub pr_number: Option<u64>,

    /// Repository (owner/repo format)
    #[arg(long, env = "GITHUB_REPOSITORY")]
    pub repository: Option<String>,

    /// Name of the branch --create-pr creates (default: code-review-fixes-<unix time>)
    #[arg(long)]
    pub branch: Option<String>,

    /// Base branch for PR (default: main)
    #[arg(long, default_value = "main")]
    pub base_branch: String,

    /// Commit message for changes
    #[arg(long, default_value = "Apply code review fixes")]
    pub commit_message: String,

    /// Dry run - print actions without executing (patches are still checked)
    #[arg(long)]
    pub dry_run: bool,

    /// Output format for stdout: `text` prints the PR URL (if one was created),
    /// `json` prints a machine-readable summary of everything that happened
    #[arg(long, value_enum, default_value_t = OutputFormat::Text)]
    pub output_format: OutputFormat,

    /// Post the review markdown verbatim, without the metadata footer
    #[arg(long)]
    pub raw_comment: bool,

    /// Exit with code 3 when the review severity is at or above this level
    /// (critical, high, medium, low, info). Actions still run first.
    #[arg(long, value_name = "LEVEL", value_parser = parse_severity_arg)]
    pub fail_on_severity: Option<Severity>,
}

/// Format of the result written to stdout.
#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum OutputFormat {
    /// Human-oriented: only the created PR URL is printed.
    Text,
    /// A JSON summary object.
    Json,
}

impl Args {
    /// Whether any action flag that talks to git or GitHub was given.
    pub fn has_actions(&self) -> bool {
        self.post_comment || self.commit_changes || self.create_pr
    }

    /// Validate flag combinations and return the repository if one is needed.
    ///
    /// Runs before any side effect so that a bad invocation changes nothing.
    pub fn validate(&self) -> Result<Option<&str>> {
        if self.post_comment && self.pr_number.is_none() {
            bail!("--post-comment requires --pr-number");
        }
        if self.push && !self.commit_changes && !self.create_pr {
            bail!("--push requires --commit-changes");
        }
        if self.commit_message.trim().is_empty() {
            bail!("--commit-message must not be empty");
        }

        let needs_repository = self.post_comment || self.create_pr;
        let repository = match self.repository.as_deref().map(str::trim) {
            Some(repo) if !repo.is_empty() => {
                validate_repository(repo)?;
                Some(repo)
            },
            _ if needs_repository => {
                bail!("Repository not specified. Use --repository or set GITHUB_REPOSITORY")
            },
            _ => None,
        };
        Ok(repository)
    }
}

/// Check that `repo` looks like `owner/name`.
fn validate_repository(repo: &str) -> Result<()> {
    let valid_part = |p: &str| {
        !p.is_empty()
            && p.chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'))
    };
    match repo.split_once('/') {
        Some((owner, name)) if valid_part(owner) && valid_part(name) => Ok(()),
        _ => bail!("Invalid repository {repo:?}; expected owner/repo"),
    }
}

fn parse_severity_arg(value: &str) -> Result<Severity, String> {
    Severity::parse(value).ok_or_else(|| {
        let names: Vec<_> = Severity::ALL.iter().map(|s| s.as_str()).collect();
        format!(
            "unknown severity {value:?}; expected one of {}",
            names.join(", ")
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(extra: &[&str]) -> Result<Args, clap::Error> {
        let mut argv = vec!["code-review-processor"];
        argv.extend_from_slice(extra);
        Args::try_parse_from(argv)
    }

    #[test]
    fn defaults_match_documented_interface() {
        let a = args(&[]).unwrap();
        assert_eq!(a.input, "-");
        assert_eq!(a.base_branch, "main");
        assert_eq!(a.commit_message, "Apply code review fixes");
        assert_eq!(a.output_format, OutputFormat::Text);
        assert!(!a.has_actions());
    }

    #[test]
    fn output_format_values() {
        assert_eq!(
            args(&["--output-format", "json"]).unwrap().output_format,
            OutputFormat::Json
        );
        assert!(args(&["--output-format", "yaml"]).is_err());
    }

    #[test]
    fn pr_number_must_be_positive() {
        assert!(args(&["--pr-number", "0"]).is_err());
        assert!(args(&["--pr-number", "-3"]).is_err());
        assert_eq!(args(&["--pr-number", "12"]).unwrap().pr_number, Some(12));
    }

    #[test]
    fn severity_threshold_parses_synonyms() {
        let a = args(&["--fail-on-severity", "HIGH"]).unwrap();
        assert_eq!(a.fail_on_severity, Some(Severity::High));
        assert!(args(&["--fail-on-severity", "banana"]).is_err());
    }

    #[test]
    fn validation_rules() {
        let v = |extra: &[&str]| {
            args(extra)
                .unwrap()
                .validate()
                .map(|r| r.map(str::to_owned))
        };

        assert!(v(&["--post-comment", "--repository", "o/r"]).is_err());
        assert_eq!(
            v(&["--post-comment", "--pr-number", "1", "--repository", "o/r"]).unwrap(),
            Some("o/r".into())
        );
        assert!(v(&["--create-pr", "--repository", "not-a-repo"]).is_err());
        assert!(v(&["--create-pr", "--repository", "o/r/x"]).is_err());
        assert!(v(&["--push"]).is_err());
        assert!(v(&["--commit-changes", "--commit-message", "  "]).is_err());
        // Committing locally does not need a repository.
        assert!(v(&["--commit-changes"]).is_ok());
    }
}

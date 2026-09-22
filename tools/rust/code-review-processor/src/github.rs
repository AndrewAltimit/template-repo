//! GitHub operations via the `gh` CLI.
//!
//! Bodies are passed on stdin (`--body-file -`), so no temp files are written
//! and no shell escaping is involved.

use anyhow::Result;
use tracing::{info, warn};

use crate::command::Runner;

/// GitHub client backed by the `gh` CLI.
pub struct GitHubClient {
    runner: Runner,
    dry_run: bool,
}

impl GitHubClient {
    /// Create a client; in dry-run mode nothing is sent to GitHub.
    pub fn new(dry_run: bool) -> Self {
        Self {
            runner: Runner::new(),
            dry_run,
        }
    }

    /// Post `body` as a comment on PR `pr_number`.
    pub fn post_pr_comment(&self, repository: &str, pr_number: u64, body: &str) -> Result<()> {
        if self.dry_run {
            info!(
                chars = body.chars().count(),
                "[DRY RUN] Would post comment to {repository} PR #{pr_number}"
            );
            return Ok(());
        }
        let pr = pr_number.to_string();
        self.runner.run_ok(
            "gh",
            &[
                "pr",
                "comment",
                &pr,
                "--repo",
                repository,
                "--body-file",
                "-",
            ],
            Some(body),
        )?;
        info!("Posted review comment to {repository} PR #{pr_number}");
        Ok(())
    }

    /// Create a pull request and return `(number, url)`.
    ///
    /// The number is `0` if it cannot be parsed from `gh`'s output.
    pub fn create_pr(
        &self,
        repository: &str,
        title: &str,
        body: &str,
        head: &str,
        base: &str,
    ) -> Result<(u64, String)> {
        if self.dry_run {
            info!("[DRY RUN] Would create PR {title:?} ({head} -> {base}) in {repository}");
            return Ok((0, format!("https://github.com/{repository}/pull/0")));
        }
        let stdout = self.runner.run_ok(
            "gh",
            &[
                "pr",
                "create",
                "--repo",
                repository,
                "--title",
                title,
                "--body-file",
                "-",
                "--head",
                head,
                "--base",
                base,
            ],
            Some(body),
        )?;
        let (number, url) = parse_pr_url(&stdout);
        if number == 0 {
            warn!(output = %stdout.trim(), "Could not parse PR number from gh output");
        }
        Ok((number, url))
    }
}

/// Extract `(number, url)` from `gh pr create` output.
///
/// `gh` may print warnings before the URL, so the last line containing
/// `/pull/` wins; otherwise the last non-empty line is returned with number 0.
pub fn parse_pr_url(stdout: &str) -> (u64, String) {
    let lines: Vec<&str> = stdout
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .collect();
    let Some(url) = lines
        .iter()
        .rev()
        .find(|l| l.contains("/pull/"))
        .or(lines.last())
    else {
        return (0, String::new());
    };
    let number = url
        .rsplit("/pull/")
        .next()
        .and_then(|tail| tail.split(|c: char| !c.is_ascii_digit()).next())
        .and_then(|digits| digits.parse().ok())
        .unwrap_or(0);
    (number, (*url).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dry_run_does_not_invoke_gh() {
        let client = GitHubClient::new(true);
        assert!(
            client
                .post_pr_comment("owner/repo", 123, "Test comment")
                .is_ok()
        );
        let (number, url) = client
            .create_pr("owner/repo", "Title", "Body", "feature", "main")
            .unwrap();
        assert_eq!(number, 0);
        assert_eq!(url, "https://github.com/owner/repo/pull/0");
    }

    #[test]
    fn pr_url_parsing() {
        assert_eq!(
            parse_pr_url("https://github.com/o/r/pull/42\n"),
            (42, "https://github.com/o/r/pull/42".to_string())
        );
        assert_eq!(
            parse_pr_url("Warning: 1 uncommitted change\n\nhttps://github.com/o/r/pull/7\n").0,
            7
        );
        assert_eq!(parse_pr_url("https://github.com/o/r/pull/9/files").0, 9);
        assert_eq!(parse_pr_url("something odd").0, 0);
        assert_eq!(parse_pr_url(""), (0, String::new()));
    }
}

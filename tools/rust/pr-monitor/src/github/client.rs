//! GitHub API client using the `gh` CLI
//!
//! All PR data is fetched with a single GraphQL query per poll that returns the
//! newest 100 conversation comments and the newest 50 submitted reviews (each
//! with up to 100 inline comments) plus the PR state and head SHA. Older pages
//! are only fetched on demand (for `--since-commit` backlog checks).

use std::process::Command;

use chrono::{DateTime, Utc};

use crate::error::{Error, Result, is_rate_limit};
use crate::github::PrSource;
use crate::github::types::{
    Comment, Connection, GqlResponse, IssueCommentNode, OlderPage, PrNode, PrSnapshot, RepoData,
    ReviewNode,
};

/// Fields fetched for every review (shared by the snapshot and backfill queries)
const REVIEW_FRAGMENT: &str = "
fragment ReviewFields on PullRequestReview {
  id
  author { login }
  body
  state
  submittedAt
  url
  commit { oid }
  comments(first: 100) {
    nodes { id author { login } body createdAt url path line originalLine }
  }
}";

/// Newest comments + reviews, PR state and head SHA in one request
const SNAPSHOT_QUERY: &str = "
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      state
      headRefOid
      comments(last: 100) {
        pageInfo { hasPreviousPage startCursor }
        nodes { id author { login } body createdAt url }
      }
      reviews(last: 50) {
        pageInfo { hasPreviousPage startCursor }
        nodes { ...ReviewFields }
      }
    }
  }
}";

/// Older conversation comments (backward pagination)
const OLDER_COMMENTS_QUERY: &str = "
query($owner: String!, $repo: String!, $pr: Int!, $before: String!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      comments(last: 100, before: $before) {
        pageInfo { hasPreviousPage startCursor }
        nodes { id author { login } body createdAt url }
      }
    }
  }
}";

/// Older reviews (backward pagination)
const OLDER_REVIEWS_QUERY: &str = "
query($owner: String!, $repo: String!, $pr: Int!, $before: String!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviews(last: 50, before: $before) {
        pageInfo { hasPreviousPage startCursor }
        nodes { ...ReviewFields }
      }
    }
  }
}";

/// Explicit repository (`--repo OWNER/REPO`)
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RepoSpec {
    pub owner: String,
    pub name: String,
}

impl RepoSpec {
    /// Parse `OWNER/REPO` (a `github.com/` or `https://github.com/` prefix is tolerated)
    pub fn parse(value: &str) -> Result<Self> {
        let trimmed = value
            .trim()
            .trim_start_matches("https://")
            .trim_start_matches("github.com/")
            .trim_end_matches(".git")
            .trim_end_matches('/');
        let mut parts = trimmed.split('/');
        match (parts.next(), parts.next(), parts.next()) {
            (Some(owner), Some(name), None) if valid_segment(owner) && valid_segment(name) => {
                Ok(Self {
                    owner: owner.to_string(),
                    name: name.to_string(),
                })
            },
            _ => Err(Error::InvalidRepo(value.to_string())),
        }
    }
}

fn valid_segment(s: &str) -> bool {
    !s.is_empty()
        && !s.starts_with('-')
        && s.chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'))
}

/// GitHub client using the `gh` CLI for API access
#[derive(Debug, Clone, Default)]
pub struct GhClient {
    repo: Option<RepoSpec>,
}

impl GhClient {
    /// Client for the repository of the current directory (resolved by `gh`)
    pub fn new() -> Self {
        Self::default()
    }

    /// Client for an explicit repository
    pub fn with_repo(repo: RepoSpec) -> Self {
        Self { repo: Some(repo) }
    }

    /// Check that the gh CLI is installed.
    ///
    /// Authentication is not checked here: `gh auth status` fails if *any*
    /// configured host has a problem, and the first real API call surfaces auth
    /// errors with a clear message anyway.
    pub fn check_available() -> Result<()> {
        gh_command()
            .arg("--version")
            .output()
            .map_err(map_spawn_error)?;
        Ok(())
    }

    /// Fetch the newest comments and reviews for a PR
    pub fn fetch_snapshot(&self, pr_number: u32) -> Result<PrSnapshot> {
        let out = self.graphql(
            pr_number,
            &format!("{SNAPSHOT_QUERY}\n{REVIEW_FRAGMENT}"),
            None,
        )?;
        parse_snapshot(&out, pr_number)
    }

    /// Fetch the page of conversation comments preceding `before`
    pub fn fetch_older_comments(&self, pr_number: u32, before: &str) -> Result<OlderPage> {
        let out = self.graphql(pr_number, OLDER_COMMENTS_QUERY, Some(before))?;
        let pr = parse_pr_node(&out, pr_number)?;
        Ok(comments_page(pr.comments))
    }

    /// Fetch the page of reviews preceding `before`
    pub fn fetch_older_reviews(&self, pr_number: u32, before: &str) -> Result<OlderPage> {
        let query = format!("{OLDER_REVIEWS_QUERY}\n{REVIEW_FRAGMENT}");
        let out = self.graphql(pr_number, &query, Some(before))?;
        let pr = parse_pr_node(&out, pr_number)?;
        Ok(reviews_page(pr.reviews))
    }

    /// Get all conversation comments for a PR (newest 100).
    ///
    /// Kept for library compatibility; the monitor uses [`GhClient::fetch_snapshot`].
    pub fn get_pr_comments(&self, pr_number: u32) -> Result<Vec<Comment>> {
        let snapshot = self.fetch_snapshot(pr_number)?;
        Ok(snapshot
            .events
            .into_iter()
            .take(snapshot.comment_count)
            .collect())
    }

    /// Resolve a commit (SHA or local ref such as `HEAD`) to its committer timestamp.
    ///
    /// Full or abbreviated hex SHAs are looked up through the GitHub API first
    /// (so commits that only exist remotely work), falling back to the local git
    /// repository (so commits that have not been pushed yet also work). Other
    /// refs are resolved locally only: `commits/HEAD` on the API would resolve
    /// against the default branch, not the local checkout.
    pub fn get_commit_time(&self, commit: &str) -> Result<DateTime<Utc>> {
        let commit = commit.trim();
        if commit.is_empty() || commit.starts_with('-') || commit.contains(char::is_whitespace) {
            return Err(Error::CommitLookup {
                sha: commit.to_string(),
                reason: "not a valid commit reference".to_string(),
            });
        }

        if !is_hex_sha(commit) {
            return local_commit_time(commit);
        }

        match self.api_commit_time(commit) {
            Ok(time) => Ok(time),
            Err(api_err) => local_commit_time(commit).map_err(|_| api_err),
        }
    }

    fn api_commit_time(&self, sha: &str) -> Result<DateTime<Utc>> {
        let endpoint = match &self.repo {
            Some(r) => format!("repos/{}/{}/commits/{sha}", r.owner, r.name),
            None => format!("repos/{{owner}}/{{repo}}/commits/{sha}"),
        };
        let out = run_gh(&[
            "api".to_string(),
            endpoint,
            "--jq".to_string(),
            ".commit.committer.date".to_string(),
        ])
        .map_err(|e| Error::CommitLookup {
            sha: sha.to_string(),
            reason: e.to_string(),
        })?;
        parse_timestamp(String::from_utf8_lossy(&out).trim().trim_matches('"'))
    }

    fn graphql(&self, pr_number: u32, query: &str, before: Option<&str>) -> Result<Vec<u8>> {
        let mut args = vec![
            "api".to_string(),
            "graphql".to_string(),
            "-f".to_string(),
            format!("query={query}"),
        ];
        match &self.repo {
            Some(r) => {
                args.extend(["-f".to_string(), format!("owner={}", r.owner)]);
                args.extend(["-f".to_string(), format!("repo={}", r.name)]);
            },
            None => {
                // gh fills {owner}/{repo} placeholders in -F fields from the
                // current directory's repository (or GH_REPO).
                args.extend(["-F".to_string(), "owner={owner}".to_string()]);
                args.extend(["-F".to_string(), "repo={repo}".to_string()]);
            },
        }
        args.extend(["-F".to_string(), format!("pr={pr_number}")]);
        if let Some(cursor) = before {
            args.extend(["-f".to_string(), format!("before={cursor}")]);
        }

        run_gh(&args).map_err(|e| match e {
            Error::GhFailed { ref stderr, .. } if is_pr_not_found(stderr) => {
                Error::PrNotFound { pr_number }
            },
            other => other,
        })
    }
}

impl PrSource for GhClient {
    fn snapshot(&self, pr_number: u32) -> Result<PrSnapshot> {
        self.fetch_snapshot(pr_number)
    }

    fn older_comments(&self, pr_number: u32, before: &str) -> Result<OlderPage> {
        self.fetch_older_comments(pr_number, before)
    }

    fn older_reviews(&self, pr_number: u32, before: &str) -> Result<OlderPage> {
        self.fetch_older_reviews(pr_number, before)
    }
}

// ============================================================================
// Process helpers
// ============================================================================

fn gh_command() -> Command {
    let mut cmd = Command::new("gh");
    // Never block on interactive prompts or print update banners.
    cmd.env("GH_PROMPT_DISABLED", "1")
        .env("GH_NO_UPDATE_NOTIFIER", "1");
    cmd
}

fn map_spawn_error(e: std::io::Error) -> Error {
    if e.kind() == std::io::ErrorKind::NotFound {
        Error::GhNotFound
    } else {
        Error::GhExecution(e)
    }
}

fn run_gh(args: &[String]) -> Result<Vec<u8>> {
    let output = gh_command().args(args).output().map_err(map_spawn_error)?;
    if output.status.success() {
        return Ok(output.stdout);
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    if is_rate_limit(&stderr) {
        return Err(Error::RateLimited { message: stderr });
    }
    Err(Error::GhFailed {
        code: output.status.code().unwrap_or(-1),
        stderr,
    })
}

fn is_pr_not_found(stderr: &str) -> bool {
    stderr.contains("Could not resolve to a PullRequest")
}

fn is_hex_sha(s: &str) -> bool {
    (4..=40).contains(&s.len()) && s.chars().all(|c| c.is_ascii_hexdigit())
}

fn local_commit_time(commit: &str) -> Result<DateTime<Utc>> {
    let output = Command::new("git")
        .args([
            "show",
            "-s",
            "--format=%cI",
            &format!("{commit}^{{commit}}"),
            "--",
        ])
        .output()
        .map_err(|e| Error::CommitLookup {
            sha: commit.to_string(),
            reason: format!("failed to run git: {e}"),
        })?;
    if !output.status.success() {
        return Err(Error::CommitLookup {
            sha: commit.to_string(),
            reason: String::from_utf8_lossy(&output.stderr).trim().to_string(),
        });
    }
    parse_timestamp(String::from_utf8_lossy(&output.stdout).trim())
}

fn parse_timestamp(s: &str) -> Result<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(s)
        .map(|dt| dt.with_timezone(&Utc))
        .map_err(|e| Error::TimestampParse {
            timestamp: s.to_string(),
            reason: e.to_string(),
        })
}

// ============================================================================
// Response parsing (pure, unit-tested)
// ============================================================================

fn parse_pr_node(bytes: &[u8], pr_number: u32) -> Result<PrNode> {
    let response: GqlResponse<RepoData> = serde_json::from_slice(bytes)?;

    let not_found = response
        .errors
        .iter()
        .any(|e| e.kind.as_deref() == Some("NOT_FOUND") || is_pr_not_found(&e.message));
    if not_found {
        return Err(Error::PrNotFound { pr_number });
    }

    let pr = response
        .data
        .and_then(|d| d.repository)
        .and_then(|r| r.pull_request);

    match pr {
        Some(pr) => Ok(pr),
        None if !response.errors.is_empty() => Err(Error::GraphQl(
            response
                .errors
                .iter()
                .map(|e| e.message.as_str())
                .collect::<Vec<_>>()
                .join("; "),
        )),
        None => Err(Error::PrNotFound { pr_number }),
    }
}

fn comments_page(conn: Option<Connection<IssueCommentNode>>) -> OlderPage {
    match conn {
        Some(conn) => OlderPage {
            cursor: conn.previous_cursor(),
            events: conn
                .nodes
                .into_iter()
                .flatten()
                .map(Comment::from)
                .collect(),
        },
        None => OlderPage::default(),
    }
}

fn reviews_page(conn: Option<Connection<ReviewNode>>) -> OlderPage {
    match conn {
        Some(conn) => OlderPage {
            cursor: conn.previous_cursor(),
            events: conn
                .nodes
                .into_iter()
                .flatten()
                .filter_map(ReviewNode::into_comment)
                .collect(),
        },
        None => OlderPage::default(),
    }
}

/// Parse the snapshot query output
pub(crate) fn parse_snapshot(bytes: &[u8], pr_number: u32) -> Result<PrSnapshot> {
    let pr = parse_pr_node(bytes, pr_number)?;
    let comments = comments_page(pr.comments);
    let reviews = reviews_page(pr.reviews);

    let comment_count = comments.events.len();
    let review_count = reviews.events.len();
    let mut events = comments.events;
    events.extend(reviews.events);

    Ok(PrSnapshot {
        state: pr.state,
        head_sha: pr.head_ref_oid,
        events,
        comment_count,
        review_count,
        older_comments_cursor: comments.cursor,
        older_reviews_cursor: reviews.cursor,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::github::types::CommentKind;

    const SNAPSHOT: &str = r###"{
      "data": {"repository": {"pullRequest": {
        "state": "OPEN",
        "headRefOid": "deadbeef",
        "comments": {
          "pageInfo": {"hasPreviousPage": true, "startCursor": "Y3Vyc29yOjE="},
          "nodes": [
            {"id": "IC_1", "author": {"login": "AndrewAltimit"}, "body": "hi",
             "createdAt": "2026-01-01T00:00:00Z", "url": "https://x/1"},
            {"id": "IC_2", "author": null, "body": "from a deleted user",
             "createdAt": "2026-01-01T00:01:00Z", "url": null},
            null
          ]
        },
        "reviews": {
          "pageInfo": {"hasPreviousPage": false, "startCursor": null},
          "nodes": [
            {"id": "PRR_1", "author": {"login": "copilot-pull-request-reviewer"},
             "body": "## Pull Request Overview", "state": "COMMENTED",
             "submittedAt": "2026-01-01T00:02:00Z", "url": null,
             "commit": {"oid": "deadbeef"}, "comments": {"nodes": []}},
            {"id": "PRR_2", "author": {"login": "AndrewAltimit"}, "body": "",
             "state": "PENDING", "submittedAt": null, "url": null,
             "commit": null, "comments": {"nodes": []}}
          ]
        }
      }}}
    }"###;

    #[test]
    fn test_parse_snapshot() {
        let snap = parse_snapshot(SNAPSHOT.as_bytes(), 1).unwrap();
        assert_eq!(snap.state, "OPEN");
        assert_eq!(snap.head_sha, "deadbeef");
        assert_eq!(snap.comment_count, 2);
        // Pending review is dropped
        assert_eq!(snap.review_count, 1);
        assert_eq!(snap.events.len(), 3);
        assert_eq!(snap.events[1].author.login, "ghost");
        assert_eq!(snap.events[2].kind, CommentKind::Review);
        assert_eq!(snap.older_comments_cursor.as_deref(), Some("Y3Vyc29yOjE="));
        assert!(snap.older_reviews_cursor.is_none());
    }

    #[test]
    fn test_parse_snapshot_pr_not_found() {
        let body = r#"{"data": {"repository": {"pullRequest": null}},
            "errors": [{"type": "NOT_FOUND", "message":
            "Could not resolve to a PullRequest with the number of 999."}]}"#;
        assert!(matches!(
            parse_snapshot(body.as_bytes(), 999),
            Err(Error::PrNotFound { pr_number: 999 })
        ));

        let body = r#"{"data": {"repository": null}}"#;
        assert!(matches!(
            parse_snapshot(body.as_bytes(), 5),
            Err(Error::PrNotFound { pr_number: 5 })
        ));
    }

    #[test]
    fn test_parse_snapshot_other_graphql_error() {
        let body = r#"{"data": null, "errors": [{"message": "Something went wrong"}]}"#;
        match parse_snapshot(body.as_bytes(), 5) {
            Err(Error::GraphQl(msg)) => assert!(msg.contains("Something went wrong")),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn test_parse_snapshot_invalid_json() {
        assert!(matches!(
            parse_snapshot(b"not json", 1),
            Err(Error::JsonParse(_))
        ));
    }

    #[test]
    fn test_repo_spec_parse() {
        let spec = RepoSpec::parse("AndrewAltimit/template-repo").unwrap();
        assert_eq!(spec.owner, "AndrewAltimit");
        assert_eq!(spec.name, "template-repo");
        let spec = RepoSpec::parse("https://github.com/o/r.git").unwrap();
        assert_eq!((spec.owner.as_str(), spec.name.as_str()), ("o", "r"));

        for bad in ["", "owner", "a/b/c", "-x/y", "o/ r", "o/"] {
            assert!(RepoSpec::parse(bad).is_err(), "should reject {bad:?}");
        }
    }

    #[test]
    fn test_is_hex_sha() {
        assert!(is_hex_sha("abc1234"));
        assert!(is_hex_sha("0123456789abcdef0123456789abcdef01234567"));
        assert!(!is_hex_sha("HEAD"));
        assert!(!is_hex_sha("abc"));
        assert!(!is_hex_sha("main"));
        assert!(!is_hex_sha("../../x"));
    }

    #[test]
    fn test_parse_timestamp() {
        let t = parse_timestamp("2026-01-02T03:04:05+02:00").unwrap();
        assert_eq!(t.to_rfc3339(), "2026-01-02T01:04:05+00:00");
        assert!(parse_timestamp("yesterday").is_err());
    }

    #[test]
    fn test_invalid_commit_reference_rejected() {
        let client = GhClient::new();
        for bad in ["", "--output=x", "a b"] {
            assert!(matches!(
                client.get_commit_time(bad),
                Err(Error::CommitLookup { .. })
            ));
        }
    }
}

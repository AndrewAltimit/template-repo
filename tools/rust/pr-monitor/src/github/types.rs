//! GitHub data model for pr-monitor
//!
//! [`Comment`] is the unit the monitor reasons about. It represents one of:
//!
//! - an issue-style PR conversation comment ([`CommentKind::IssueComment`]),
//! - a submitted pull request review, including its inline comments
//!   ([`CommentKind::Review`]), or
//! - a single inline review comment ([`CommentKind::ReviewComment`]); these only
//!   appear nested inside a review's `inline_comments`.
//!
//! The GraphQL wire types used to build these live at the bottom of this module
//! and are crate-private.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Deserializer, Serialize};

/// Login used by GitHub for deleted accounts (the API returns `author: null`).
pub const GHOST_LOGIN: &str = "ghost";

/// Author information from GitHub
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Author {
    pub login: String,
}

impl Author {
    /// Placeholder author for deleted accounts
    pub fn ghost() -> Self {
        Self {
            login: GHOST_LOGIN.to_string(),
        }
    }
}

/// Accept `null` authors (deleted accounts) instead of failing the whole poll.
fn deserialize_author<'de, D>(deserializer: D) -> std::result::Result<Author, D::Error>
where
    D: Deserializer<'de>,
{
    Ok(Option::<Author>::deserialize(deserializer)?.unwrap_or_else(Author::ghost))
}

/// What kind of GitHub object a [`Comment`] was built from
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CommentKind {
    /// Conversation-tab comment (`gh pr comment`)
    #[default]
    IssueComment,
    /// Submitted pull request review (approve / request changes / comment)
    Review,
    /// Inline comment on a diff line (always attached to a review)
    ReviewComment,
}

/// Comment (or review) from a GitHub PR
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Comment {
    /// GraphQL node ID (stable across edits; used to detect new items)
    #[serde(default)]
    pub id: String,

    /// Source object type
    #[serde(default)]
    pub kind: CommentKind,

    #[serde(default = "Author::ghost", deserialize_with = "deserialize_author")]
    pub author: Author,

    #[serde(default)]
    pub body: String,

    /// Creation time (submission time for reviews)
    #[serde(rename = "createdAt")]
    pub created_at: DateTime<Utc>,

    /// Permalink to the comment on github.com
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,

    /// Review state (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, `DISMISSED`)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub review_state: Option<String>,

    /// Commit the review was submitted against
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub commit_sha: Option<String>,

    /// File path for inline review comments
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,

    /// Line number for inline review comments (current line, else original line)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub line: Option<u64>,

    /// Inline comments attached to a review
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub inline_comments: Vec<Comment>,
}

impl Comment {
    /// Minimal constructor, mostly useful for tests and library consumers.
    pub fn new(author: &str, body: &str, created_at: DateTime<Utc>) -> Self {
        Self {
            id: String::new(),
            kind: CommentKind::IssueComment,
            author: Author {
                login: author.to_string(),
            },
            body: body.to_string(),
            created_at,
            url: None,
            review_state: None,
            commit_sha: None,
            path: None,
            line: None,
            inline_comments: Vec::new(),
        }
    }
}

/// Legacy `gh pr view --json comments` response shape
#[derive(Debug, Deserialize)]
pub struct PrCommentsResponse {
    pub comments: Vec<Comment>,
}

/// Point-in-time view of a PR's conversation
#[derive(Debug, Clone, Default)]
pub struct PrSnapshot {
    /// PR state (`OPEN`, `CLOSED`, `MERGED`)
    pub state: String,
    /// Current head commit SHA
    pub head_sha: String,
    /// Issue comments followed by submitted reviews (each group oldest first)
    pub events: Vec<Comment>,
    /// Number of issue comments in `events`
    pub comment_count: usize,
    /// Number of reviews in `events`
    pub review_count: usize,
    /// Cursor for fetching older issue comments, if the window was truncated
    pub older_comments_cursor: Option<String>,
    /// Cursor for fetching older reviews, if the window was truncated
    pub older_reviews_cursor: Option<String>,
}

/// A page of older items fetched with a `before` cursor
#[derive(Debug, Clone, Default)]
pub struct OlderPage {
    /// Items in the page, oldest first
    pub events: Vec<Comment>,
    /// Cursor for the next (older) page, if any
    pub cursor: Option<String>,
}

// ============================================================================
// GraphQL wire types (crate-private)
// ============================================================================

#[derive(Debug, Deserialize)]
pub(crate) struct GqlResponse<T> {
    pub data: Option<T>,
    #[serde(default)]
    pub errors: Vec<GqlError>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct GqlError {
    #[serde(default)]
    pub message: String,
    #[serde(default, rename = "type")]
    pub kind: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct RepoData {
    pub repository: Option<RepoNode>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct RepoNode {
    #[serde(rename = "pullRequest")]
    pub pull_request: Option<PrNode>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct PrNode {
    #[serde(default)]
    pub state: String,
    #[serde(rename = "headRefOid", default)]
    pub head_ref_oid: String,
    pub comments: Option<Connection<IssueCommentNode>>,
    pub reviews: Option<Connection<ReviewNode>>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct Connection<T> {
    #[serde(default = "Vec::new")]
    pub nodes: Vec<Option<T>>,
    #[serde(rename = "pageInfo")]
    pub page_info: Option<PageInfo>,
}

impl<T> Connection<T> {
    /// Cursor for the previous page when one exists
    pub fn previous_cursor(&self) -> Option<String> {
        self.page_info
            .as_ref()
            .filter(|p| p.has_previous_page)
            .and_then(|p| p.start_cursor.clone())
    }
}

#[derive(Debug, Deserialize)]
pub(crate) struct PageInfo {
    #[serde(rename = "hasPreviousPage", default)]
    pub has_previous_page: bool,
    #[serde(rename = "startCursor")]
    pub start_cursor: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct IssueCommentNode {
    pub id: String,
    #[serde(default = "Author::ghost", deserialize_with = "deserialize_author")]
    pub author: Author,
    #[serde(default)]
    pub body: String,
    #[serde(rename = "createdAt")]
    pub created_at: DateTime<Utc>,
    pub url: Option<String>,
}

impl From<IssueCommentNode> for Comment {
    fn from(n: IssueCommentNode) -> Self {
        Comment {
            id: n.id,
            url: n.url,
            ..Comment::new(&n.author.login, &n.body, n.created_at)
        }
    }
}

#[derive(Debug, Deserialize)]
pub(crate) struct CommitRef {
    pub oid: String,
}

#[derive(Debug, Deserialize)]
pub(crate) struct ReviewNode {
    pub id: String,
    #[serde(default = "Author::ghost", deserialize_with = "deserialize_author")]
    pub author: Author,
    #[serde(default)]
    pub body: String,
    #[serde(default)]
    pub state: String,
    /// `null` for pending (unsubmitted) reviews
    #[serde(rename = "submittedAt")]
    pub submitted_at: Option<DateTime<Utc>>,
    pub url: Option<String>,
    pub commit: Option<CommitRef>,
    pub comments: Option<Connection<ReviewCommentNode>>,
}

impl ReviewNode {
    /// Convert into a [`Comment`]; pending reviews (no submission time) yield `None`.
    pub fn into_comment(self) -> Option<Comment> {
        if self.state.eq_ignore_ascii_case("PENDING") {
            return None;
        }
        let submitted_at = self.submitted_at?;
        let inline_comments = self
            .comments
            .map(|c| c.nodes.into_iter().flatten().map(Comment::from).collect())
            .unwrap_or_default();
        Some(Comment {
            id: self.id,
            kind: CommentKind::Review,
            url: self.url,
            review_state: Some(self.state),
            commit_sha: self.commit.map(|c| c.oid),
            inline_comments,
            ..Comment::new(&self.author.login, &self.body, submitted_at)
        })
    }
}

#[derive(Debug, Deserialize)]
pub(crate) struct ReviewCommentNode {
    pub id: String,
    #[serde(default = "Author::ghost", deserialize_with = "deserialize_author")]
    pub author: Author,
    #[serde(default)]
    pub body: String,
    #[serde(rename = "createdAt")]
    pub created_at: DateTime<Utc>,
    pub url: Option<String>,
    pub path: Option<String>,
    pub line: Option<u64>,
    #[serde(rename = "originalLine")]
    pub original_line: Option<u64>,
}

impl From<ReviewCommentNode> for Comment {
    fn from(n: ReviewCommentNode) -> Self {
        Comment {
            id: n.id,
            kind: CommentKind::ReviewComment,
            url: n.url,
            path: n.path,
            line: n.line.or(n.original_line),
            ..Comment::new(&n.author.login, &n.body, n.created_at)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_comment() {
        let json = r#"{
            "author": {"login": "TestUser"},
            "body": "Test comment body",
            "createdAt": "2025-01-15T10:30:00Z"
        }"#;

        let comment: Comment = serde_json::from_str(json).unwrap();
        assert_eq!(comment.author.login, "TestUser");
        assert_eq!(comment.body, "Test comment body");
        assert_eq!(comment.kind, CommentKind::IssueComment);
    }

    #[test]
    fn test_deserialize_null_author_as_ghost() {
        let json = r#"{"author": null, "body": "x", "createdAt": "2025-01-15T10:30:00Z"}"#;
        let comment: Comment = serde_json::from_str(json).unwrap();
        assert_eq!(comment.author.login, GHOST_LOGIN);

        let json = r#"{"body": "x", "createdAt": "2025-01-15T10:30:00Z"}"#;
        let comment: Comment = serde_json::from_str(json).unwrap();
        assert_eq!(comment.author.login, GHOST_LOGIN);
    }

    #[test]
    fn test_deserialize_pr_comments_response() {
        let json = r#"{
            "comments": [
                {
                    "author": {"login": "User1"},
                    "body": "First comment",
                    "createdAt": "2025-01-15T10:00:00Z"
                },
                {
                    "author": {"login": "User2"},
                    "body": "Second comment",
                    "createdAt": "2025-01-15T11:00:00Z"
                }
            ]
        }"#;

        let response: PrCommentsResponse = serde_json::from_str(json).unwrap();
        assert_eq!(response.comments.len(), 2);
        assert_eq!(response.comments[0].author.login, "User1");
        assert_eq!(response.comments[1].author.login, "User2");
    }

    #[test]
    fn test_pending_review_is_skipped() {
        let json = r#"{
            "id": "R1", "author": {"login": "a"}, "body": "", "state": "PENDING",
            "submittedAt": null, "url": null, "commit": null, "comments": null
        }"#;
        let node: ReviewNode = serde_json::from_str(json).unwrap();
        assert!(node.into_comment().is_none());
    }

    #[test]
    fn test_review_conversion_keeps_inline_comments() {
        let json = r###"{
            "id": "R2",
            "author": {"login": "copilot-pull-request-reviewer"},
            "body": "## Pull Request Overview",
            "state": "COMMENTED",
            "submittedAt": "2026-01-01T00:00:00Z",
            "url": "https://github.com/o/r/pull/1#pullrequestreview-2",
            "commit": {"oid": "abc123"},
            "comments": {"nodes": [
                {"id": "C1", "author": {"login": "copilot-pull-request-reviewer"},
                 "body": "nit", "createdAt": "2026-01-01T00:00:00Z", "url": null,
                 "path": "src/lib.rs", "line": null, "originalLine": 7}
            ]}
        }"###;
        let node: ReviewNode = serde_json::from_str(json).unwrap();
        let review = node.into_comment().unwrap();
        assert_eq!(review.kind, CommentKind::Review);
        assert_eq!(review.review_state.as_deref(), Some("COMMENTED"));
        assert_eq!(review.commit_sha.as_deref(), Some("abc123"));
        assert_eq!(review.inline_comments.len(), 1);
        let inline = &review.inline_comments[0];
        assert_eq!(inline.kind, CommentKind::ReviewComment);
        assert_eq!(inline.path.as_deref(), Some("src/lib.rs"));
        assert_eq!(inline.line, Some(7));
    }
}

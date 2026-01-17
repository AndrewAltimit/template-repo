//! GitHub API types for pr-monitor

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Author information from GitHub
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Author {
    pub login: String,
}

/// Comment from GitHub PR
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Comment {
    pub author: Author,
    pub body: String,
    #[serde(rename = "createdAt")]
    pub created_at: DateTime<Utc>,
}

/// PR view response structure (subset we care about)
#[derive(Debug, Deserialize)]
pub struct PrCommentsResponse {
    pub comments: Vec<Comment>,
}

/// Commit info for timestamp lookup (reserved for direct API use)
#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct CommitInfo {
    pub commit: CommitDetails,
}

/// Commit details (reserved for direct API use)
#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct CommitDetails {
    pub committer: CommitterInfo,
}

/// Committer info with timestamp (reserved for direct API use)
#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct CommitterInfo {
    pub date: DateTime<Utc>,
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
}

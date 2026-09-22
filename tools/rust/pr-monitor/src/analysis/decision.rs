//! Decision output types for pr-monitor
//!
//! The core fields (`needs_response`, `priority`, `response_type`,
//! `action_required`, `comment.{author,timestamp,body}`) match the JSON output
//! of the original Python implementation for drop-in compatibility. Everything
//! else is additive and omitted when empty.

use serde::{Deserialize, Serialize};

use crate::github::CommentKind;

/// Priority level for response
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "lowercase")]
pub enum Priority {
    High,
    Normal,
    Low,
}

impl Priority {
    /// Sort key: lower is more urgent
    pub fn rank(self) -> u8 {
        match self {
            Priority::High => 0,
            Priority::Normal => 1,
            Priority::Low => 2,
        }
    }
}

/// Type of response needed
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum ResponseType {
    /// Admin `[Action][Agent]` trigger or legacy `[ADMIN]` command
    AdminCommand,
    /// Any other admin comment or review with content
    AdminComment,
    /// Admin approved the PR without further comments
    AdminApproval,
    /// Code review from an AI reviewer (Claude, OpenRouter, Copilot, ...)
    AiAgentReview,
    /// `PR Validation Results` status table
    CiResults,
    /// Comment from an author explicitly watched with `--author`
    UserComment,
}

impl ResponseType {
    /// All variants, in CLI help order
    pub const ALL: [ResponseType; 6] = [
        ResponseType::AdminCommand,
        ResponseType::AdminComment,
        ResponseType::AdminApproval,
        ResponseType::AiAgentReview,
        ResponseType::CiResults,
        ResponseType::UserComment,
    ];

    /// snake_case name as used in JSON output
    pub fn as_str(self) -> &'static str {
        match self {
            ResponseType::AdminCommand => "admin_command",
            ResponseType::AdminComment => "admin_comment",
            ResponseType::AdminApproval => "admin_approval",
            ResponseType::AiAgentReview => "ai_agent_review",
            ResponseType::CiResults => "ci_results",
            ResponseType::UserComment => "user_comment",
        }
    }
}

impl std::str::FromStr for ResponseType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let normalized = s.trim().to_ascii_lowercase().replace('-', "_");
        ResponseType::ALL
            .into_iter()
            .find(|t| t.as_str() == normalized)
            .ok_or_else(|| {
                let valid: Vec<_> = ResponseType::ALL.iter().map(|t| t.as_str()).collect();
                format!("unknown type '{s}' (valid: {})", valid.join(", "))
            })
    }
}

/// Simplified comment for output
#[derive(Debug, Clone, Serialize)]
pub struct CommentSummary {
    pub author: String,
    pub timestamp: String,
    pub body: String,
    /// GraphQL node ID
    #[serde(skip_serializing_if = "String::is_empty")]
    pub id: String,
    /// `issue_comment` or `review`
    pub kind: CommentKind,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
}

/// Inline (diff) comment attached to a review
#[derive(Debug, Clone, Serialize)]
pub struct InlineComment {
    pub author: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<u64>,
    pub body: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
}

/// Metadata extracted from reviews, triggers and CI tables
#[derive(Debug, Clone, Default, Serialize)]
pub struct ReviewMetadata {
    /// Commit SHA from review marker or review object (for security validation)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub commit_sha: Option<String>,

    /// Unique review identifier (timestamp-based)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_id: Option<String>,

    /// Action from [Action][Agent] trigger format
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trigger_action: Option<String>,

    /// Agent from [Action][Agent] trigger format
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trigger_agent: Option<String>,

    /// Whether an agent response to this review already exists on the PR
    #[serde(skip_serializing_if = "is_false")]
    pub already_responded: bool,

    /// Reviewer slug (`claude`, `openrouter`, `copilot`, ...)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reviewer: Option<String>,

    /// GitHub review state for PR reviews (`APPROVED`, `CHANGES_REQUESTED`, ...)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_state: Option<String>,

    /// The reviewed commit is no longer the PR head
    #[serde(skip_serializing_if = "is_false")]
    pub outdated: bool,

    /// Inline comments attached to a PR review
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub inline_comments: Vec<InlineComment>,

    /// Failed checks listed in a CI results table
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub failed_checks: Vec<String>,
}

fn is_false(b: &bool) -> bool {
    !*b
}

/// Final decision output (superset of the Python output format)
#[derive(Debug, Serialize)]
pub struct Decision {
    pub needs_response: bool,
    pub priority: Priority,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_type: Option<ResponseType>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action_required: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_metadata: Option<ReviewMetadata>,
    pub comment: CommentSummary,
    /// PR number that was monitored
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pr_number: Option<u32>,
    /// PR head commit at the time the comment was detected
    #[serde(skip_serializing_if = "Option::is_none")]
    pub head_sha: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn summary(author: &str, body: &str) -> CommentSummary {
        CommentSummary {
            author: author.to_string(),
            timestamp: "2025-01-15T10:00:00Z".to_string(),
            body: body.to_string(),
            id: String::new(),
            kind: CommentKind::IssueComment,
            url: None,
        }
    }

    #[test]
    fn test_priority_serialization() {
        assert_eq!(serde_json::to_string(&Priority::High).unwrap(), "\"high\"");
        assert_eq!(
            serde_json::to_string(&Priority::Normal).unwrap(),
            "\"normal\""
        );
        assert_eq!(serde_json::to_string(&Priority::Low).unwrap(), "\"low\"");
        assert!(Priority::High.rank() < Priority::Normal.rank());
        assert!(Priority::Normal.rank() < Priority::Low.rank());
    }

    #[test]
    fn test_response_type_serialization_matches_as_str() {
        for t in ResponseType::ALL {
            assert_eq!(
                serde_json::to_string(&t).unwrap(),
                format!("\"{}\"", t.as_str())
            );
        }
    }

    #[test]
    fn test_response_type_from_str() {
        assert_eq!(
            "ai_agent_review".parse::<ResponseType>(),
            Ok(ResponseType::AiAgentReview)
        );
        assert_eq!(
            "Admin-Command".parse::<ResponseType>(),
            Ok(ResponseType::AdminCommand)
        );
        let err = "bogus".parse::<ResponseType>().unwrap_err();
        assert!(err.contains("ci_results"));
    }

    #[test]
    fn test_decision_serialization() {
        let decision = Decision {
            needs_response: true,
            priority: Priority::High,
            response_type: Some(ResponseType::AdminCommand),
            action_required: Some("Execute admin command".to_string()),
            review_metadata: None,
            comment: summary("TestUser", "[ADMIN] Do something"),
            pr_number: None,
            head_sha: None,
        };

        let json = serde_json::to_string_pretty(&decision).unwrap();
        assert!(json.contains("\"needs_response\": true"));
        assert!(json.contains("\"priority\": \"high\""));
        assert!(json.contains("\"response_type\": \"admin_command\""));
        assert!(json.contains("\"kind\": \"issue_comment\""));
        // Empty optional fields are omitted
        assert!(!json.contains("\"url\""));
        assert!(!json.contains("\"id\""));
        assert!(!json.contains("head_sha"));
    }

    #[test]
    fn test_review_metadata_serialization() {
        let metadata = ReviewMetadata {
            commit_sha: Some("abc123".to_string()),
            review_id: Some("2026-01-18-10-30-00".to_string()),
            ..Default::default()
        };

        let json = serde_json::to_string(&metadata).unwrap();
        assert!(json.contains("\"commit_sha\":\"abc123\""));
        assert!(json.contains("\"review_id\":\"2026-01-18-10-30-00\""));
        // false / empty values are skipped
        assert!(!json.contains("already_responded"));
        assert!(!json.contains("outdated"));
        assert!(!json.contains("inline_comments"));
        assert!(!json.contains("failed_checks"));
    }

    #[test]
    fn test_trigger_metadata_serialization() {
        let metadata = ReviewMetadata {
            trigger_action: Some("approved".to_string()),
            trigger_agent: Some("claude".to_string()),
            ..Default::default()
        };

        let json = serde_json::to_string(&metadata).unwrap();
        assert!(json.contains("\"trigger_action\":\"approved\""));
        assert!(json.contains("\"trigger_agent\":\"claude\""));
    }

    #[test]
    fn test_decision_with_metadata() {
        let decision = Decision {
            needs_response: true,
            priority: Priority::Normal,
            response_type: Some(ResponseType::AiAgentReview),
            action_required: Some("Address AI agent code review feedback".to_string()),
            review_metadata: Some(ReviewMetadata {
                commit_sha: Some("def456".to_string()),
                review_id: Some("2026-01-18-12-00-00".to_string()),
                reviewer: Some("claude".to_string()),
                inline_comments: vec![InlineComment {
                    author: "copilot-pull-request-reviewer".to_string(),
                    path: Some("src/main.rs".to_string()),
                    line: Some(10),
                    body: "nit".to_string(),
                    url: None,
                }],
                ..Default::default()
            }),
            comment: summary("github-actions[bot]", "## Claude AI Review\n..."),
            pr_number: Some(12),
            head_sha: Some("def456".to_string()),
        };

        let json = serde_json::to_string_pretty(&decision).unwrap();
        assert!(json.contains("\"ai_agent_review\""));
        assert!(json.contains("\"commit_sha\": \"def456\""));
        assert!(json.contains("\"review_id\": \"2026-01-18-12-00-00\""));
        assert!(json.contains("\"reviewer\": \"claude\""));
        assert!(json.contains("\"path\": \"src/main.rs\""));
        assert!(json.contains("\"pr_number\": 12"));
    }
}

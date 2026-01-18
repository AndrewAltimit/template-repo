//! Decision output types for pr-monitor
//!
//! These types match the JSON output format of the original Python implementation
//! for drop-in compatibility.

use serde::Serialize;

/// Priority level for response
#[derive(Debug, Clone, Copy, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Priority {
    High,
    Normal,
    Low,
}

/// Type of response needed
#[derive(Debug, Clone, Copy, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ResponseType {
    AdminCommand,
    AdminComment,
    GeminiReview,
    CodexReview,
    CiResults,
}

/// Simplified comment for output
#[derive(Debug, Clone, Serialize)]
pub struct CommentSummary {
    pub author: String,
    pub timestamp: String,
    pub body: String,
}

/// Metadata extracted from AI reviews (ported from Python monitors/pr.py)
#[derive(Debug, Clone, Serialize)]
pub struct ReviewMetadata {
    /// Commit SHA from review marker (for security validation)
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

    /// Whether a response marker already exists for this review
    #[serde(skip_serializing_if = "is_false")]
    pub already_responded: bool,
}

fn is_false(b: &bool) -> bool {
    !*b
}

/// Final decision output (matches Python output format)
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
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_priority_serialization() {
        assert_eq!(serde_json::to_string(&Priority::High).unwrap(), "\"high\"");
        assert_eq!(
            serde_json::to_string(&Priority::Normal).unwrap(),
            "\"normal\""
        );
        assert_eq!(serde_json::to_string(&Priority::Low).unwrap(), "\"low\"");
    }

    #[test]
    fn test_response_type_serialization() {
        assert_eq!(
            serde_json::to_string(&ResponseType::AdminCommand).unwrap(),
            "\"admin_command\""
        );
        assert_eq!(
            serde_json::to_string(&ResponseType::GeminiReview).unwrap(),
            "\"gemini_review\""
        );
    }

    #[test]
    fn test_decision_serialization() {
        let decision = Decision {
            needs_response: true,
            priority: Priority::High,
            response_type: Some(ResponseType::AdminCommand),
            action_required: Some("Execute admin command".to_string()),
            review_metadata: None,
            comment: CommentSummary {
                author: "TestUser".to_string(),
                timestamp: "2025-01-15T10:00:00Z".to_string(),
                body: "[ADMIN] Do something".to_string(),
            },
        };

        let json = serde_json::to_string_pretty(&decision).unwrap();
        assert!(json.contains("\"needs_response\": true"));
        assert!(json.contains("\"priority\": \"high\""));
        assert!(json.contains("\"response_type\": \"admin_command\""));
    }

    #[test]
    fn test_review_metadata_serialization() {
        let metadata = ReviewMetadata {
            commit_sha: Some("abc123".to_string()),
            review_id: Some("2026-01-18-10-30-00".to_string()),
            trigger_action: None,
            trigger_agent: None,
            already_responded: false,
        };

        let json = serde_json::to_string(&metadata).unwrap();
        assert!(json.contains("\"commit_sha\":\"abc123\""));
        assert!(json.contains("\"review_id\":\"2026-01-18-10-30-00\""));
        // already_responded=false should be skipped
        assert!(!json.contains("already_responded"));
    }

    #[test]
    fn test_trigger_metadata_serialization() {
        let metadata = ReviewMetadata {
            commit_sha: None,
            review_id: None,
            trigger_action: Some("approved".to_string()),
            trigger_agent: Some("claude".to_string()),
            already_responded: false,
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
            response_type: Some(ResponseType::GeminiReview),
            action_required: Some("Address Gemini code review feedback".to_string()),
            review_metadata: Some(ReviewMetadata {
                commit_sha: Some("def456".to_string()),
                review_id: Some("2026-01-18-12-00-00".to_string()),
                trigger_action: None,
                trigger_agent: None,
                already_responded: false,
            }),
            comment: CommentSummary {
                author: "github-actions[bot]".to_string(),
                timestamp: "2026-01-18T12:00:00Z".to_string(),
                body: "## Gemini AI Review\n...".to_string(),
            },
        };

        let json = serde_json::to_string_pretty(&decision).unwrap();
        assert!(json.contains("\"gemini_review\""));
        assert!(json.contains("\"commit_sha\": \"def456\""));
        assert!(json.contains("\"review_id\": \"2026-01-18-12-00-00\""));
    }
}

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

/// Final decision output (matches Python output format)
#[derive(Debug, Serialize)]
pub struct Decision {
    pub needs_response: bool,
    pub priority: Priority,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_type: Option<ResponseType>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action_required: Option<String>,
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
}

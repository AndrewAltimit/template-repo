//! Comment classification logic
//!
//! Ported from pr_monitor_agent.py:analyze_comment()

use std::fmt;

use crate::analysis::decision::{CommentSummary, Decision, Priority, ResponseType};
use crate::github::Comment;

/// Action to take in response to a comment
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    ExecuteAdminCommand,
    ReviewAdminFeedback,
    AddressGeminiReview,
    ReviewCiResults,
}

impl fmt::Display for Action {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Action::ExecuteAdminCommand => write!(f, "Execute admin command and respond"),
            Action::ReviewAdminFeedback => write!(f, "Review and respond to admin feedback"),
            Action::AddressGeminiReview => write!(f, "Address Gemini code review feedback"),
            Action::ReviewCiResults => write!(f, "Review CI results if failures present"),
        }
    }
}

/// Classification result for a comment
#[derive(Debug, Clone)]
pub struct Classification {
    pub needs_response: bool,
    pub priority: Priority,
    pub response_type: Option<ResponseType>,
    pub action: Option<Action>,
}

impl Classification {
    /// Create a decision from this classification and the original comment
    pub fn into_decision(self, comment: &Comment) -> Decision {
        Decision {
            needs_response: self.needs_response,
            priority: self.priority,
            response_type: self.response_type,
            action_required: self.action.map(|a| a.to_string()),
            comment: CommentSummary {
                author: comment.author.login.clone(),
                timestamp: comment.created_at.to_rfc3339(),
                body: comment.body.clone(),
            },
        }
    }
}

/// Default admin user (repository owner)
pub const DEFAULT_ADMIN_USER: &str = "AndrewAltimit";

/// Classify a comment and determine appropriate response
pub fn classify(comment: &Comment, admin_user: &str) -> Classification {
    let author = &comment.author.login;
    let body = &comment.body;

    // Admin commands (highest priority)
    if author == admin_user {
        if body.contains("[ADMIN]") {
            return Classification {
                needs_response: true,
                priority: Priority::High,
                response_type: Some(ResponseType::AdminCommand),
                action: Some(Action::ExecuteAdminCommand),
            };
        }
        return Classification {
            needs_response: true,
            priority: Priority::Normal,
            response_type: Some(ResponseType::AdminComment),
            action: Some(Action::ReviewAdminFeedback),
        };
    }

    // GitHub Actions bot
    if author.contains("github-actions") {
        if body.contains("Gemini") {
            return Classification {
                needs_response: true,
                priority: Priority::Normal,
                response_type: Some(ResponseType::GeminiReview),
                action: Some(Action::AddressGeminiReview),
            };
        }
        if body.contains("PR Validation Results") {
            return Classification {
                needs_response: false,
                priority: Priority::Low,
                response_type: Some(ResponseType::CiResults),
                action: Some(Action::ReviewCiResults),
            };
        }
    }

    // Default: not relevant (won't be reached in practice since we filter first)
    Classification {
        needs_response: false,
        priority: Priority::Low,
        response_type: None,
        action: None,
    }
}

/// Check if a comment author is relevant for monitoring
pub fn is_relevant_author(author: &str, admin_user: &str) -> bool {
    author == admin_user || author.contains("github-actions")
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn make_comment(author: &str, body: &str) -> Comment {
        Comment {
            author: crate::github::Author {
                login: author.to_string(),
            },
            body: body.to_string(),
            created_at: Utc::now(),
        }
    }

    #[test]
    fn test_admin_command_classification() {
        let comment = make_comment("AndrewAltimit", "[ADMIN] Please fix the tests");
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::High);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AdminCommand)
        );
        assert_eq!(classification.action, Some(Action::ExecuteAdminCommand));
    }

    #[test]
    fn test_admin_comment_classification() {
        let comment = make_comment("AndrewAltimit", "Looks good, but maybe add more tests?");
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::Normal);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AdminComment)
        );
        assert_eq!(classification.action, Some(Action::ReviewAdminFeedback));
    }

    #[test]
    fn test_gemini_review_classification() {
        let comment = make_comment(
            "github-actions[bot]",
            "## Gemini Code Review\n\nThis looks good overall...",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::Normal);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::GeminiReview)
        );
        assert_eq!(classification.action, Some(Action::AddressGeminiReview));
    }

    #[test]
    fn test_ci_results_classification() {
        let comment = make_comment(
            "github-actions[bot]",
            "## PR Validation Results\n\nAll checks passed!",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(!classification.needs_response);
        assert_eq!(classification.priority, Priority::Low);
        assert_eq!(classification.response_type, Some(ResponseType::CiResults));
    }

    #[test]
    fn test_irrelevant_comment_classification() {
        let comment = make_comment("random-user", "Nice work!");
        let classification = classify(&comment, "AndrewAltimit");

        assert!(!classification.needs_response);
        assert_eq!(classification.priority, Priority::Low);
        assert!(classification.response_type.is_none());
    }

    #[test]
    fn test_is_relevant_author() {
        assert!(is_relevant_author("AndrewAltimit", "AndrewAltimit"));
        assert!(is_relevant_author("github-actions[bot]", "AndrewAltimit"));
        assert!(is_relevant_author("github-actions", "AndrewAltimit"));
        assert!(!is_relevant_author("random-user", "AndrewAltimit"));
        assert!(!is_relevant_author("other-admin", "AndrewAltimit"));
    }
}

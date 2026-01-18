//! Comment classification logic
//!
//! Enhanced with patterns ported from Python monitors/pr.py

use std::fmt;

use once_cell::sync::Lazy;
use regex::Regex;

use crate::analysis::decision::{CommentSummary, Decision, Priority, ResponseType, ReviewMetadata};
use crate::github::Comment;

/// Action to take in response to a comment
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    ExecuteAdminCommand,
    ReviewAdminFeedback,
    AddressGeminiReview,
    AddressCodexReview,
    ReviewCiResults,
}

impl fmt::Display for Action {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Action::ExecuteAdminCommand => write!(f, "Execute admin command and respond"),
            Action::ReviewAdminFeedback => write!(f, "Review and respond to admin feedback"),
            Action::AddressGeminiReview => write!(f, "Address Gemini code review feedback"),
            Action::AddressCodexReview => write!(f, "Address Codex code review feedback"),
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
    /// Extracted metadata for AI reviews (commit SHA, response markers)
    pub review_metadata: Option<ReviewMetadata>,
}

impl Classification {
    /// Create a decision from this classification and the original comment
    pub fn into_decision(self, comment: &Comment) -> Decision {
        Decision {
            needs_response: self.needs_response,
            priority: self.priority,
            response_type: self.response_type,
            action_required: self.action.map(|a| a.to_string()),
            review_metadata: self.review_metadata,
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

// ============================================================================
// Regex patterns ported from Python monitors/pr.py
// ============================================================================

/// Patterns to detect Gemini review comments
static GEMINI_PATTERNS: Lazy<[Regex; 4]> = Lazy::new(|| {
    [
        Regex::new(r"(?i)(?:gemini|google)\s*(?:ai\s*)?(?:code\s*)?review").unwrap(),
        Regex::new(r"(?i)##\s*(?:ai\s*)?code\s*review").unwrap(),
        Regex::new(r"(?i)automated\s*(?:code\s*)?review\s*(?:by|from)\s*gemini").unwrap(),
        Regex::new(r"(?i)\*\*gemini\s*review\*\*").unwrap(),
    ]
});

/// Patterns to detect Codex review comments
static CODEX_PATTERNS: Lazy<[Regex; 5]> = Lazy::new(|| {
    [
        Regex::new(r"(?i)(?:codex|openai)\s*(?:ai\s*)?(?:code\s*)?review").unwrap(),
        Regex::new(r"(?i)##\s*codex\s*(?:ai\s*)?(?:code\s*)?review").unwrap(),
        Regex::new(r"(?i)automated\s*(?:code\s*)?review\s*(?:by|from)\s*codex").unwrap(),
        Regex::new(r"(?i)\*\*codex\s*review\*\*").unwrap(),
        Regex::new(r"(?i)codex-review-marker:commit:").unwrap(),
    ]
});

/// Pattern to extract commit SHA from Gemini review marker
static GEMINI_COMMIT_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?i)gemini-review-marker:commit:([a-f0-9]+)").unwrap());

/// Pattern to extract commit SHA from Codex review marker
static CODEX_COMMIT_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?i)codex-review-marker:commit:([a-f0-9]+)").unwrap());

/// Pattern to detect existing agent response to a comment
#[allow(dead_code)] // Part of public API for library consumers
static RESPONSE_MARKER_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"<!-- ai-agent-(?:gemini|codex|consolidated)-response:([^>]+) -->").unwrap()
});

/// Pattern to detect [Action][Agent] trigger format
static TRIGGER_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?i)\[([A-Za-z]+)\](?:\[([A-Za-z]+)\])?").unwrap());

// ============================================================================
// Classification functions
// ============================================================================

/// Check if comment body matches Gemini review patterns
fn is_gemini_review(body: &str) -> bool {
    // Must contain actual review marker or header, not just status table mention
    if body.contains("gemini-review-marker") || body.contains("## Gemini AI") {
        return true;
    }

    // Check against Python patterns
    for pattern in GEMINI_PATTERNS.iter() {
        if pattern.is_match(body) {
            // Exclude CI status tables that mention reviews
            if !body.contains("PR Validation Results") {
                return true;
            }
        }
    }

    false
}

/// Check if comment body matches Codex review patterns
fn is_codex_review(body: &str) -> bool {
    // Must contain actual review marker or header
    if body.contains("codex-review-marker") || body.contains("## Codex AI") {
        return true;
    }

    // Check against Python patterns
    for pattern in CODEX_PATTERNS.iter() {
        if pattern.is_match(body) {
            // Exclude CI status tables
            if !body.contains("PR Validation Results") {
                return true;
            }
        }
    }

    false
}

/// Extract commit SHA from Gemini review marker
pub fn extract_gemini_commit_sha(body: &str) -> Option<String> {
    GEMINI_COMMIT_PATTERN
        .captures(body)
        .map(|caps| caps.get(1).unwrap().as_str().to_string())
}

/// Extract commit SHA from Codex review marker
pub fn extract_codex_commit_sha(body: &str) -> Option<String> {
    CODEX_COMMIT_PATTERN
        .captures(body)
        .map(|caps| caps.get(1).unwrap().as_str().to_string())
}

/// Check if a response marker exists for the given review ID
#[allow(dead_code)] // Part of public API for library consumers
pub fn has_response_marker(comments: &[Comment], review_id: &str) -> bool {
    for comment in comments {
        if let Some(caps) = RESPONSE_MARKER_PATTERN.captures(&comment.body) {
            let marker_id = caps.get(1).unwrap().as_str();
            if marker_id.contains(review_id) {
                return true;
            }
        }
    }
    false
}

/// Extract trigger info from comment: (action, optional_agent)
pub fn extract_trigger(body: &str) -> Option<(String, Option<String>)> {
    TRIGGER_PATTERN.captures(body).map(|caps| {
        let action = caps.get(1).unwrap().as_str().to_lowercase();
        let agent = caps.get(2).map(|m| m.as_str().to_lowercase());
        (action, agent)
    })
}

/// Classify a comment and determine appropriate response
pub fn classify(comment: &Comment, admin_user: &str) -> Classification {
    let author = &comment.author.login;
    let body = &comment.body;

    // Admin commands (highest priority)
    if author == admin_user {
        // Check for trigger format [Action][Agent]
        if let Some((action, agent)) = extract_trigger(body) {
            let valid_actions = ["approved", "review", "close", "summarize", "debug"];
            if valid_actions.contains(&action.as_str()) {
                return Classification {
                    needs_response: true,
                    priority: Priority::High,
                    response_type: Some(ResponseType::AdminCommand),
                    action: Some(Action::ExecuteAdminCommand),
                    review_metadata: Some(ReviewMetadata {
                        commit_sha: None,
                        review_id: None,
                        trigger_action: Some(action),
                        trigger_agent: agent,
                        already_responded: false,
                    }),
                };
            }
        }

        // Legacy [ADMIN] format
        if body.contains("[ADMIN]") {
            return Classification {
                needs_response: true,
                priority: Priority::High,
                response_type: Some(ResponseType::AdminCommand),
                action: Some(Action::ExecuteAdminCommand),
                review_metadata: None,
            };
        }

        return Classification {
            needs_response: true,
            priority: Priority::Normal,
            response_type: Some(ResponseType::AdminComment),
            action: Some(Action::ReviewAdminFeedback),
            review_metadata: None,
        };
    }

    // GitHub Actions bot
    if author.contains("github-actions") {
        // Check for Gemini review
        if is_gemini_review(body) {
            let commit_sha = extract_gemini_commit_sha(body);
            let review_id = generate_review_id(comment);

            return Classification {
                needs_response: true,
                priority: Priority::Normal,
                response_type: Some(ResponseType::GeminiReview),
                action: Some(Action::AddressGeminiReview),
                review_metadata: Some(ReviewMetadata {
                    commit_sha,
                    review_id: Some(review_id),
                    trigger_action: None,
                    trigger_agent: None,
                    already_responded: false,
                }),
            };
        }

        // Check for Codex review
        if is_codex_review(body) {
            let commit_sha = extract_codex_commit_sha(body);
            let review_id = generate_review_id(comment);

            return Classification {
                needs_response: true,
                priority: Priority::Normal,
                response_type: Some(ResponseType::CodexReview),
                action: Some(Action::AddressCodexReview),
                review_metadata: Some(ReviewMetadata {
                    commit_sha,
                    review_id: Some(review_id),
                    trigger_action: None,
                    trigger_agent: None,
                    already_responded: false,
                }),
            };
        }

        // CI status table (not actionable, just informational)
        if body.contains("PR Validation Results") {
            return Classification {
                needs_response: false,
                priority: Priority::Low,
                response_type: Some(ResponseType::CiResults),
                action: Some(Action::ReviewCiResults),
                review_metadata: None,
            };
        }
    }

    // Default: not relevant
    Classification {
        needs_response: false,
        priority: Priority::Low,
        response_type: None,
        action: None,
        review_metadata: None,
    }
}

/// Generate a unique review ID from comment timestamp
fn generate_review_id(comment: &Comment) -> String {
    comment.created_at.format("%Y-%m-%d-%H-%M-%S").to_string()
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
    fn test_admin_trigger_format() {
        let comment = make_comment("AndrewAltimit", "[Approved][Claude] looks good");
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::High);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AdminCommand)
        );

        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.trigger_action, Some("approved".to_string()));
        assert_eq!(metadata.trigger_agent, Some("claude".to_string()));
    }

    #[test]
    fn test_admin_trigger_without_agent() {
        let comment = make_comment("AndrewAltimit", "[Approved] go ahead");
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.trigger_action, Some("approved".to_string()));
        assert!(metadata.trigger_agent.is_none());
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
            "## Gemini AI Incremental Review\n<!-- gemini-review-marker:commit:abc123 -->\n\nThis looks good overall...",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::Normal);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::GeminiReview)
        );
        assert_eq!(classification.action, Some(Action::AddressGeminiReview));

        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.commit_sha, Some("abc123".to_string()));
        assert!(metadata.review_id.is_some());
    }

    #[test]
    fn test_codex_review_classification() {
        let comment = make_comment(
            "github-actions[bot]",
            "## Codex AI Code Review\n<!-- codex-review-marker:commit:def456 -->\n\nLGTM",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::Normal);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::CodexReview)
        );
        assert_eq!(classification.action, Some(Action::AddressCodexReview));

        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.commit_sha, Some("def456".to_string()));
    }

    #[test]
    fn test_status_table_not_classified_as_review() {
        // Status table contains "Gemini review" text but shouldn't be classified as actual review
        let comment = make_comment(
            "github-actions[bot]",
            "## PR Validation Results\n\n| Check | Status |\n| Gemini review | :white_check_mark: |",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(!classification.needs_response);
        assert_eq!(classification.response_type, Some(ResponseType::CiResults));
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

    #[test]
    fn test_extract_gemini_commit_sha() {
        let body = "Some review text\n<!-- gemini-review-marker:commit:abc123def -->\nMore text";
        assert_eq!(
            extract_gemini_commit_sha(body),
            Some("abc123def".to_string())
        );

        let body_no_marker = "Some review without marker";
        assert_eq!(extract_gemini_commit_sha(body_no_marker), None);
    }

    #[test]
    fn test_extract_codex_commit_sha() {
        let body = "Review\n<!-- codex-review-marker:commit:789abcdef -->";
        assert_eq!(
            extract_codex_commit_sha(body),
            Some("789abcdef".to_string())
        );
    }

    #[test]
    fn test_extract_trigger() {
        assert_eq!(
            extract_trigger("[Approved][Claude] go ahead"),
            Some(("approved".to_string(), Some("claude".to_string())))
        );
        assert_eq!(
            extract_trigger("[Review] please"),
            Some(("review".to_string(), None))
        );
        assert_eq!(extract_trigger("no trigger here"), None);
    }

    #[test]
    fn test_gemini_pattern_matching() {
        // Should match
        assert!(is_gemini_review("## Gemini AI Code Review"));
        assert!(is_gemini_review(
            "Automated code review by Gemini\nSome feedback"
        ));
        assert!(is_gemini_review("**gemini review**"));
        assert!(is_gemini_review("<!-- gemini-review-marker:commit:abc -->"));

        // Should not match
        assert!(!is_gemini_review(
            "## PR Validation Results\n| Gemini review | passed |"
        ));
        assert!(!is_gemini_review("random comment"));
    }

    #[test]
    fn test_codex_pattern_matching() {
        // Should match
        assert!(is_codex_review("## Codex AI Code Review"));
        assert!(is_codex_review("Automated review from Codex"));
        assert!(is_codex_review("**codex review**"));
        assert!(is_codex_review("codex-review-marker:commit:abc"));

        // Should not match
        assert!(!is_codex_review(
            "## PR Validation Results\n| Codex review | passed |"
        ));
        assert!(!is_codex_review("random comment"));
    }
}

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
    AddressAiAgentReview,
    ReviewCiResults,
}

impl fmt::Display for Action {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Action::ExecuteAdminCommand => write!(f, "Execute admin command and respond"),
            Action::ReviewAdminFeedback => write!(f, "Review and respond to admin feedback"),
            Action::AddressAiAgentReview => write!(f, "Address AI agent code review feedback"),
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
// Regex patterns for detecting AI agent review comments
// ============================================================================
//
// All AI reviewers (Claude, Gemini, OpenRouter, Codex, etc.) post comments using
// the same canonical format produced by the review pipeline:
//   ## {Agent} AI [Incremental] {Type} Review
//   <!-- {agent}-review-marker:commit:{sha} -->
//
// Detection looks for either the marker (most reliable) or a heading line
// containing both "AI" and "Review" tokens.

/// HTML comment marker: `<!-- {agent}-review-marker:commit:{sha} -->`
/// Capture group 1 is the agent slug, capture group 2 is the commit SHA.
static AI_REVIEW_MARKER_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?i)<!--\s*([a-z0-9_-]+)-review-marker:commit:([a-f0-9]+)\s*-->").unwrap()
});

/// Heading line containing both "AI" and "Review" tokens (e.g.
/// `## Claude AI Security & Correctness Review`,
/// `## OpenRouter AI Code Review`).
/// Anchored to a line that starts with `##` so status tables and inline
/// mentions don't false-positive.
///
/// NOTE: This pattern requires `AI` to appear BEFORE `Review` on the heading
/// line, matching the canonical format produced by the review pipeline. A
/// heading that puts the tokens in the reverse order (e.g.
/// `## Code Review AI Summary`) will not match. If a future reviewer adopts
/// such a format, update this pattern accordingly.
static AI_REVIEW_HEADER_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?im)^\s*##[^\n]*\bAI\b[^\n]*\bReview\b").unwrap());

/// Pattern to detect existing agent response to a comment.
/// `(?i)` matches the case-insensitivity of `AI_REVIEW_MARKER_PATTERN` so
/// mixed-case agent slugs (if ever emitted) are still detected.
///
/// NOTE: The pattern requires a literal single space before `-->`
/// (`([^>]+) -->`). Markers without that space (e.g. `...:abc123-->`) will
/// silently fail to match. This matches the canonical format produced by the
/// response pipeline; future marker generators must preserve the trailing
/// ` -->` (space + arrow) suffix.
#[allow(dead_code)] // Part of public API for library consumers
static RESPONSE_MARKER_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?i)<!-- ai-agent-[a-z0-9_-]+-response:([^>]+) -->").unwrap());

/// Pattern to detect [Action][Agent] trigger format
static TRIGGER_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?i)\[([A-Za-z]+)\](?:\[([A-Za-z]+)\])?").unwrap());

// ============================================================================
// Classification functions
// ============================================================================

/// Check if a comment body is an AI agent code review.
///
/// Matches the canonical review-pipeline format used by all reviewers
/// (Claude, Gemini, OpenRouter, Codex, ...). Status tables that happen to
/// reference reviews are excluded so they get classified as `CiResults`.
fn is_ai_agent_review(body: &str) -> bool {
    if body.contains("PR Validation Results") {
        return false;
    }
    AI_REVIEW_MARKER_PATTERN.is_match(body) || AI_REVIEW_HEADER_PATTERN.is_match(body)
}

/// Extract commit SHA from any AI agent review marker
pub fn extract_review_commit_sha(body: &str) -> Option<String> {
    AI_REVIEW_MARKER_PATTERN
        .captures(body)
        .and_then(|caps| caps.get(2).map(|m| m.as_str().to_string()))
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
        // AI agent review (Claude, Gemini, OpenRouter, Codex, ...)
        if is_ai_agent_review(body) {
            let commit_sha = extract_review_commit_sha(body);
            let review_id = generate_review_id(comment);

            return Classification {
                needs_response: true,
                priority: Priority::Normal,
                response_type: Some(ResponseType::AiAgentReview),
                action: Some(Action::AddressAiAgentReview),
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
    fn test_claude_review_classification() {
        let comment = make_comment(
            "github-actions[bot]",
            "## Claude AI Security & Correctness Review\n<!-- claude-review-marker:commit:abc123 -->\n\nThis looks good overall...",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::Normal);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );
        assert_eq!(classification.action, Some(Action::AddressAiAgentReview));

        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.commit_sha, Some("abc123".to_string()));
        assert!(metadata.review_id.is_some());
    }

    #[test]
    fn test_openrouter_review_classification() {
        let comment = make_comment(
            "github-actions[bot]",
            "## Openrouter AI Incremental General Review\n<!-- openrouter-review-marker:commit:def456 -->\n\n*This is an incremental review focusing on changes since the last review.*\n\n## Issues (if any)\n\n(none)",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );
        assert_eq!(classification.action, Some(Action::AddressAiAgentReview));

        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.commit_sha, Some("def456".to_string()));
    }

    #[test]
    fn test_gemini_review_still_classified() {
        // Legacy Gemini review format must still classify as an AI agent review.
        let comment = make_comment(
            "github-actions[bot]",
            "## Gemini AI Incremental Review\n<!-- gemini-review-marker:commit:789abc -->\n\nLGTM",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );
        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.commit_sha, Some("789abc".to_string()));
    }

    #[test]
    fn test_codex_review_still_classified() {
        // Legacy Codex review format must still classify as an AI agent review.
        let comment = make_comment(
            "github-actions[bot]",
            "## Codex AI Code Review\n<!-- codex-review-marker:commit:0123abcd -->\n\nLGTM",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );
        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.commit_sha, Some("0123abcd".to_string()));
    }

    #[test]
    fn test_review_response_agent_not_classified_as_review() {
        // Review Response Agent comments are responses, not reviews — must not match.
        let comment = make_comment(
            "github-actions[bot]",
            "## Review Response Agent (Iteration 1)\n<!-- agent-metadata:type=review-fix:iteration=1 -->\n\n**Status:** Changes committed, pushing...",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(!classification.needs_response);
        assert!(classification.response_type.is_none());
    }

    #[test]
    fn test_status_table_not_classified_as_review() {
        // Status table mentions reviews in cells but shouldn't be classified as a review.
        let comment = make_comment(
            "github-actions[bot]",
            "## PR Validation Results\n\n| Check | Status |\n|-------|--------|\n| Claude security-review | pass |\n| Openrouter review | pass |",
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
    fn test_extract_review_commit_sha() {
        // Works for any agent slug
        for (body, expected) in [
            (
                "<!-- claude-review-marker:commit:abc123def -->",
                Some("abc123def".to_string()),
            ),
            (
                "<!-- openrouter-review-marker:commit:cafe1234 -->",
                Some("cafe1234".to_string()),
            ),
            (
                "<!-- gemini-review-marker:commit:beef5678 -->",
                Some("beef5678".to_string()),
            ),
            (
                "<!-- codex-review-marker:commit:0123abcd -->",
                Some("0123abcd".to_string()),
            ),
            ("Some review without marker", None),
        ] {
            assert_eq!(extract_review_commit_sha(body), expected, "body: {body}");
        }
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
    fn test_ai_review_pattern_matching() {
        // Headers from each known reviewer (canonical format)
        for body in [
            "## Claude AI Security & Correctness Review",
            "## Claude AI Architecture & Quality Review",
            "## Claude AI Incremental Security & Correctness Review",
            "## Openrouter AI General Review",
            "## OpenRouter AI Code Review",
            "## Openrouter AI Incremental General Review",
            "## Gemini AI Incremental Review",
            "## Codex AI Code Review",
        ] {
            assert!(is_ai_agent_review(body), "expected match: {body}");
        }

        // Markers alone are sufficient
        for body in [
            "<!-- claude-review-marker:commit:abc -->",
            "<!-- openrouter-review-marker:commit:abc -->",
            "<!-- gemini-review-marker:commit:abc -->",
            "<!-- codex-review-marker:commit:abc -->",
        ] {
            assert!(is_ai_agent_review(body), "expected match: {body}");
        }

        // Must NOT match
        for body in [
            // Status tables that mention reviews
            "## PR Validation Results\n| Claude security-review | pass |",
            "## PR Validation Results\n| Openrouter review | pass |",
            // Review Response Agent (these are responses, not reviews)
            "## Review Response Agent (Iteration 5)",
            // Inline mention without canonical heading
            "I just got a review from gemini",
            // Random comment
            "random comment",
            // Heading without "AI" token
            "## Code Review Summary",
        ] {
            assert!(!is_ai_agent_review(body), "expected no match: {body}");
        }
    }
}

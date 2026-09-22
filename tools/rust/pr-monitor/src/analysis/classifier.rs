//! Comment classification logic
//!
//! Decides whether a PR comment or review is something an agent waiting on
//! feedback should act on. Classification is purely a function of the comment
//! (author, body, review state, inline comments) and the configured admin user.

use std::fmt;
use std::sync::LazyLock;

use regex::Regex;

use crate::analysis::decision::{
    CommentSummary, Decision, InlineComment, Priority, ResponseType, ReviewMetadata,
};
use crate::github::{Comment, CommentKind};

/// Action to take in response to a comment
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    ExecuteAdminCommand,
    ReviewAdminFeedback,
    NoteAdminApproval,
    AddressAiAgentReview,
    ReviewCiResults,
    FixFailingCi,
    RespondToComment,
}

impl fmt::Display for Action {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let text = match self {
            Action::ExecuteAdminCommand => "Execute admin command and respond",
            Action::ReviewAdminFeedback => "Review and respond to admin feedback",
            Action::NoteAdminApproval => "Admin approved the PR; no response required",
            Action::AddressAiAgentReview => "Address AI agent code review feedback",
            Action::ReviewCiResults => "Review CI results if failures present",
            Action::FixFailingCi => "Investigate and fix failing CI checks",
            Action::RespondToComment => "Review and respond to comment",
        };
        f.write_str(text)
    }
}

/// Classification result for a comment
#[derive(Debug, Clone)]
pub struct Classification {
    pub needs_response: bool,
    pub priority: Priority,
    pub response_type: Option<ResponseType>,
    pub action: Option<Action>,
    /// Extracted metadata (review commit SHA, trigger, failed checks, ...)
    pub review_metadata: Option<ReviewMetadata>,
}

impl Classification {
    /// Classification for comments the monitor does not care about
    pub fn irrelevant() -> Self {
        Self {
            needs_response: false,
            priority: Priority::Low,
            response_type: None,
            action: None,
            review_metadata: None,
        }
    }

    fn new(needs_response: bool, priority: Priority, kind: ResponseType, action: Action) -> Self {
        Self {
            needs_response,
            priority,
            response_type: Some(kind),
            action: Some(action),
            review_metadata: None,
        }
    }

    fn with_metadata(mut self, metadata: ReviewMetadata) -> Self {
        self.review_metadata = Some(metadata);
        self
    }

    /// Whether this comment was recognised as one of the known response types
    pub fn is_recognized(&self) -> bool {
        self.response_type.is_some()
    }

    /// Create a decision from this classification and the original comment.
    ///
    /// PR review details (state, inline comments) are attached to
    /// `review_metadata` so a consumer can act on them without another API call.
    pub fn into_decision(self, comment: &Comment) -> Decision {
        let mut metadata = self.review_metadata;
        if comment.kind == CommentKind::Review {
            let m = metadata.get_or_insert_with(ReviewMetadata::default);
            m.review_state.clone_from(&comment.review_state);
            if m.commit_sha.is_none() {
                m.commit_sha.clone_from(&comment.commit_sha);
            }
            m.inline_comments = comment
                .inline_comments
                .iter()
                .map(|c| InlineComment {
                    author: c.author.login.clone(),
                    path: c.path.clone(),
                    line: c.line,
                    body: c.body.clone(),
                    url: c.url.clone(),
                })
                .collect();
        }

        Decision {
            needs_response: self.needs_response,
            priority: self.priority,
            response_type: self.response_type,
            action_required: self.action.map(|a| a.to_string()),
            review_metadata: metadata,
            comment: CommentSummary {
                author: comment.author.login.clone(),
                timestamp: comment.created_at.to_rfc3339(),
                body: comment.body.clone(),
                id: comment.id.clone(),
                kind: comment.kind,
                url: comment.url.clone(),
            },
            pr_number: None,
            head_sha: None,
        }
    }
}

/// Default admin user (repository owner)
pub const DEFAULT_ADMIN_USER: &str = "AndrewAltimit";

/// Trigger actions accepted in the `[Action][Agent]` format
pub const VALID_TRIGGER_ACTIONS: [&str; 7] = [
    "approved",
    "review",
    "close",
    "summarize",
    "debug",
    "fix",
    "implement",
];

/// Bot accounts whose comments/reviews are monitored (normalized logins).
///
/// - `github-actions`: review pipeline (Claude, OpenRouter) and CI status tables
/// - `copilot-pull-request-reviewer` / `copilot`: GitHub Copilot code review
///   (GraphQL and REST report different logins)
/// - `claude`: Claude GitHub App
const REVIEW_BOTS: [&str; 4] = [
    "github-actions",
    "copilot-pull-request-reviewer",
    "copilot",
    "claude",
];

// ============================================================================
// Regex patterns
// ============================================================================
//
// All pipeline reviewers post comments using the same canonical format:
//   ## {Agent} AI [Incremental] {Type} Review
//   <!-- {agent}-review-marker:commit:{sha} -->
//
// Detection looks for either the marker (most reliable) or a heading line
// containing both "AI" and "Review" tokens. Markers from retired reviewers
// (e.g. gemini, codex) still match because the slug is generic.

/// HTML comment marker: `<!-- {agent}-review-marker:commit:{sha} -->`
/// Capture group 1 is the agent slug, capture group 2 is the commit SHA.
static AI_REVIEW_MARKER_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)<!--\s*([a-z0-9_-]+)-review-marker(?::commit:([a-f0-9]+))?\s*-->")
        .expect("valid regex")
});

/// Heading line containing both "AI" and "Review" tokens (e.g.
/// `## Claude AI Security & Correctness Review`, `## OpenRouter AI Code Review`).
/// Anchored to a line starting with `##` so status tables and inline mentions
/// don't false-positive. Capture group 1 is the text before `AI` (the agent).
///
/// NOTE: `AI` must appear BEFORE `Review` on the heading line, matching the
/// canonical format produced by the review pipeline.
static AI_REVIEW_HEADER_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?im)^\s*##\s*([^\n]*?)\s*\bAI\b[^\n]*\bReview\b").expect("valid regex")
});

/// Legacy agent response marker: `<!-- ai-agent-{agent}-response:{review_id} -->`
static RESPONSE_MARKER_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)<!--\s*ai-agent-[a-z0-9_-]+-response:([^>]+?)\s*-->").expect("valid regex")
});

/// Agent metadata marker emitted by the review-response / failure-fix agents:
/// `<!-- agent-metadata:type={type}:iteration={n} -->`. Capture 1 is the type.
static AGENT_METADATA_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)<!--\s*agent-metadata:type=([a-z0-9_-]+)").expect("valid regex")
});

/// `[Action]` or `[Action][Agent]` trigger
static TRIGGER_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\[([A-Za-z]+)\](?:\[([A-Za-z]+)\])?").expect("valid regex"));

/// CI status table row: `| check name | fail |`
static CI_FAIL_ROW_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?im)^\s*\|\s*([^|\n]+?)\s*\|\s*(?:fail|failure|failed)\s*\|")
        .expect("valid regex")
});

// ============================================================================
// Author helpers
// ============================================================================

/// Lowercase a login and strip the `[bot]` suffix used by the REST API
pub fn normalize_login(login: &str) -> String {
    let lower = login.trim().to_ascii_lowercase();
    lower.strip_suffix("[bot]").unwrap_or(&lower).to_string()
}

/// Case-insensitive login comparison that ignores the `[bot]` suffix
pub fn logins_match(a: &str, b: &str) -> bool {
    normalize_login(a) == normalize_login(b)
}

/// Whether the login belongs to one of the monitored review bots
pub fn is_review_bot(login: &str) -> bool {
    let normalized = normalize_login(login);
    REVIEW_BOTS.contains(&normalized.as_str())
}

fn is_copilot(login: &str) -> bool {
    matches!(
        normalize_login(login).as_str(),
        "copilot-pull-request-reviewer" | "copilot"
    )
}

/// Check if a comment author is relevant for monitoring (admin or review bot)
pub fn is_relevant_author(author: &str, admin_user: &str) -> bool {
    logins_match(author, admin_user) || is_review_bot(author)
}

// ============================================================================
// Body helpers
// ============================================================================

/// Whether a body was produced by an automation agent rather than a human.
///
/// Agents post with the admin's token (so they appear as the admin user) and
/// sometimes via github-actions; their comments carry an `agent-metadata`
/// marker, a legacy `ai-agent-*-response` marker, or the Claude Code footer.
/// Treating these as admin feedback would make the monitor wake up on the
/// agent's own output.
pub fn is_agent_generated(body: &str) -> bool {
    AGENT_METADATA_PATTERN.is_match(body)
        || RESPONSE_MARKER_PATTERN.is_match(body)
        || body.contains("Generated with [Claude Code]")
}

/// Check if a comment body is an AI agent code review.
///
/// Status tables that happen to reference reviews are excluded so they get
/// classified as `CiResults`.
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

/// Extract the reviewer slug from the review marker, else from the heading
pub fn extract_reviewer(body: &str) -> Option<String> {
    if let Some(slug) = AI_REVIEW_MARKER_PATTERN
        .captures(body)
        .and_then(|caps| caps.get(1))
    {
        return Some(slug.as_str().to_ascii_lowercase());
    }
    AI_REVIEW_HEADER_PATTERN
        .captures(body)
        .and_then(|caps| caps.get(1))
        .and_then(|m| m.as_str().split_whitespace().next())
        .map(|word| {
            word.chars()
                .filter(|c| c.is_ascii_alphanumeric() || *c == '-')
                .collect::<String>()
                .to_ascii_lowercase()
        })
        .filter(|s| !s.is_empty())
}

/// Check if a legacy response marker exists for the given review ID
pub fn has_response_marker(comments: &[Comment], review_id: &str) -> bool {
    comments.iter().any(|comment| {
        RESPONSE_MARKER_PATTERN
            .captures_iter(&comment.body)
            .filter_map(|caps| caps.get(1))
            .any(|m| m.as_str().contains(review_id))
    })
}

/// Whether an automated agent already responded to `review`.
///
/// True if a legacy response marker references the review ID, or if a
/// review-fix agent comment was posted after the review. Push failures,
/// "no changes" (`review-fix-hallucination`) and iteration-limit notices do not
/// count as a response.
pub fn has_prior_response(review: &Comment, review_id: &str, events: &[Comment]) -> bool {
    if has_response_marker(events, review_id) {
        return true;
    }
    events.iter().any(|e| {
        e.created_at > review.created_at
            && !e.body.contains(":limit-reached")
            && AGENT_METADATA_PATTERN
                .captures(&e.body)
                .and_then(|caps| caps.get(1))
                .is_some_and(|t| t.as_str().eq_ignore_ascii_case("review-fix"))
    })
}

/// Extract the first valid `[Action]` / `[Action][Agent]` trigger: (action, agent).
///
/// Unknown actions (checkboxes like `[x]`, `[ADMIN]`) and markdown links
/// (`[Review](https://...)`) are skipped.
pub fn extract_trigger(body: &str) -> Option<(String, Option<String>)> {
    TRIGGER_PATTERN.captures_iter(body).find_map(|caps| {
        let whole = caps.get(0)?;
        if body[whole.end()..].starts_with('(') {
            return None;
        }
        let action = caps.get(1)?.as_str().to_ascii_lowercase();
        if !VALID_TRIGGER_ACTIONS.contains(&action.as_str()) {
            return None;
        }
        let agent = caps.get(2).map(|m| m.as_str().to_ascii_lowercase());
        Some((action, agent))
    })
}

/// Names of failed checks in a `PR Validation Results` table
pub fn extract_failed_checks(body: &str) -> Vec<String> {
    CI_FAIL_ROW_PATTERN
        .captures_iter(body)
        .filter_map(|caps| caps.get(1))
        .map(|m| m.as_str().to_string())
        .collect()
}

/// Generate a review ID from the comment timestamp
fn generate_review_id(comment: &Comment) -> String {
    comment.created_at.format("%Y-%m-%d-%H-%M-%S").to_string()
}

fn has_content(comment: &Comment) -> bool {
    !comment.body.trim().is_empty() || !comment.inline_comments.is_empty()
}

fn review_state_is(comment: &Comment, state: &str) -> bool {
    comment
        .review_state
        .as_deref()
        .is_some_and(|s| s.eq_ignore_ascii_case(state))
}

// ============================================================================
// Classification
// ============================================================================

/// Classify a comment or review and determine the appropriate response
pub fn classify(comment: &Comment, admin_user: &str) -> Classification {
    let author = &comment.author.login;
    let body = &comment.body;

    if is_agent_generated(body) {
        return Classification::irrelevant();
    }

    if logins_match(author, admin_user) {
        return classify_admin(comment);
    }

    if is_review_bot(author) {
        return classify_bot(comment);
    }

    Classification::irrelevant()
}

fn classify_admin(comment: &Comment) -> Classification {
    let body = &comment.body;

    // [Action][Agent] trigger (highest priority)
    if let Some((action, agent)) = extract_trigger(body) {
        return Classification::new(
            true,
            Priority::High,
            ResponseType::AdminCommand,
            Action::ExecuteAdminCommand,
        )
        .with_metadata(ReviewMetadata {
            trigger_action: Some(action),
            trigger_agent: agent,
            ..Default::default()
        });
    }

    // Legacy [ADMIN] format
    if body.contains("[ADMIN]") {
        return Classification::new(
            true,
            Priority::High,
            ResponseType::AdminCommand,
            Action::ExecuteAdminCommand,
        );
    }

    if comment.kind == CommentKind::Review {
        if review_state_is(comment, "CHANGES_REQUESTED") {
            return Classification::new(
                true,
                Priority::High,
                ResponseType::AdminComment,
                Action::ReviewAdminFeedback,
            );
        }
        if !has_content(comment) {
            if review_state_is(comment, "APPROVED") {
                return Classification::new(
                    false,
                    Priority::Normal,
                    ResponseType::AdminApproval,
                    Action::NoteAdminApproval,
                );
            }
            // Empty COMMENTED / DISMISSED reviews carry no feedback
            return Classification::irrelevant();
        }
    }

    Classification::new(
        true,
        Priority::Normal,
        ResponseType::AdminComment,
        Action::ReviewAdminFeedback,
    )
}

fn classify_bot(comment: &Comment) -> Classification {
    let body = &comment.body;

    // GitHub Copilot code review (always a PR review object)
    if is_copilot(&comment.author.login) {
        if comment.kind != CommentKind::Review || !has_content(comment) {
            return Classification::irrelevant();
        }
        let no_findings = comment.inline_comments.is_empty()
            && body.to_ascii_lowercase().contains("generated no comments");
        let (needs_response, priority) = if no_findings {
            (false, Priority::Low)
        } else {
            (true, Priority::Normal)
        };
        return Classification::new(
            needs_response,
            priority,
            ResponseType::AiAgentReview,
            Action::AddressAiAgentReview,
        )
        .with_metadata(ReviewMetadata {
            commit_sha: comment.commit_sha.clone(),
            review_id: Some(generate_review_id(comment)),
            reviewer: Some("copilot".to_string()),
            ..Default::default()
        });
    }

    // Pipeline AI reviews (Claude, OpenRouter, ...)
    if is_ai_agent_review(body) {
        return Classification::new(
            true,
            Priority::Normal,
            ResponseType::AiAgentReview,
            Action::AddressAiAgentReview,
        )
        .with_metadata(ReviewMetadata {
            commit_sha: extract_review_commit_sha(body),
            review_id: Some(generate_review_id(comment)),
            reviewer: extract_reviewer(body),
            ..Default::default()
        });
    }

    // CI status table: informational unless something failed
    if body.contains("PR Validation Results") {
        let failed_checks = extract_failed_checks(body);
        let classification = if failed_checks.is_empty() {
            Classification::new(
                false,
                Priority::Low,
                ResponseType::CiResults,
                Action::ReviewCiResults,
            )
        } else {
            Classification::new(
                true,
                Priority::Normal,
                ResponseType::CiResults,
                Action::FixFailingCi,
            )
            .with_metadata(ReviewMetadata {
                failed_checks,
                ..Default::default()
            })
        };
        return classification;
    }

    Classification::irrelevant()
}

/// Classification for a comment from an author watched explicitly via `--author`
/// that did not match any other category.
pub fn user_comment() -> Classification {
    Classification::new(
        true,
        Priority::Normal,
        ResponseType::UserComment,
        Action::RespondToComment,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, TimeZone, Utc};

    fn make_comment(author: &str, body: &str) -> Comment {
        Comment::new(
            author,
            body,
            Utc.with_ymd_and_hms(2026, 1, 18, 10, 30, 0).unwrap(),
        )
    }

    fn make_review(author: &str, body: &str, state: &str, inline: usize) -> Comment {
        let mut c = make_comment(author, body);
        c.kind = CommentKind::Review;
        c.review_state = Some(state.to_string());
        c.commit_sha = Some("feedface".to_string());
        c.inline_comments = (0..inline)
            .map(|i| {
                let mut ic = make_comment(author, &format!("inline {i}"));
                ic.kind = CommentKind::ReviewComment;
                ic.path = Some("src/lib.rs".to_string());
                ic.line = Some(10 + i as u64);
                ic
            })
            .collect();
        c
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
    fn test_admin_login_is_case_insensitive() {
        let comment = make_comment("andrewaltimit", "please rename this");
        let classification = classify(&comment, "AndrewAltimit");
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AdminComment)
        );
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
    fn test_admin_trigger_after_link_and_checkbox() {
        // Earlier bracketed text (checkbox, markdown link) must not hide the trigger.
        let comment = make_comment(
            "AndrewAltimit",
            "- [x] see [docs](https://example.com)\n\n[Review][Claude]",
        );
        let metadata = classify(&comment, "AndrewAltimit").review_metadata.unwrap();
        assert_eq!(metadata.trigger_action.as_deref(), Some("review"));
        assert_eq!(metadata.trigger_agent.as_deref(), Some("claude"));
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
    fn test_agent_comment_posted_with_admin_token_is_ignored() {
        for body in [
            "## Review Response Agent (Iteration 1)\n<!-- agent-metadata:type=review-fix:iteration=1 -->\n\nDone",
            "<!-- agent-metadata:type=failure-fix:iteration=2 -->\nFixed lint",
            "Addressed feedback\n<!-- ai-agent-claude-response:2026-01-08-12-34-56 -->",
            "Summary of changes\n\nGenerated with [Claude Code](https://claude.com/claude-code)",
        ] {
            let classification = classify(&make_comment("AndrewAltimit", body), "AndrewAltimit");
            assert!(!classification.is_recognized(), "should ignore: {body}");
        }
    }

    #[test]
    fn test_admin_review_states() {
        let admin = "AndrewAltimit";

        let approved = classify(&make_review(admin, "", "APPROVED", 0), admin);
        assert_eq!(approved.response_type, Some(ResponseType::AdminApproval));
        assert!(!approved.needs_response);

        let changes = classify(&make_review(admin, "", "CHANGES_REQUESTED", 0), admin);
        assert_eq!(changes.response_type, Some(ResponseType::AdminComment));
        assert_eq!(changes.priority, Priority::High);

        let inline_only = classify(&make_review(admin, "", "COMMENTED", 2), admin);
        assert_eq!(inline_only.response_type, Some(ResponseType::AdminComment));
        assert!(inline_only.needs_response);

        let empty = classify(&make_review(admin, "  ", "COMMENTED", 0), admin);
        assert!(!empty.is_recognized());

        let approved_with_note =
            classify(&make_review(admin, "LGTM, one nit", "APPROVED", 0), admin);
        assert_eq!(
            approved_with_note.response_type,
            Some(ResponseType::AdminComment)
        );
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
        assert_eq!(metadata.reviewer.as_deref(), Some("claude"));
        assert_eq!(metadata.review_id.as_deref(), Some("2026-01-18-10-30-00"));
    }

    #[test]
    fn test_openrouter_review_classification() {
        let comment = make_comment(
            "github-actions",
            "## Openrouter AI Incremental General Review\n<!-- openrouter-review-marker:commit:def456 -->\n\n*This is an incremental review focusing on changes since the last review.*\n\n## Issues (if any)\n\n(none)",
        );
        let classification = classify(&comment, "AndrewAltimit");

        assert!(classification.needs_response);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );

        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.commit_sha, Some("def456".to_string()));
        assert_eq!(metadata.reviewer.as_deref(), Some("openrouter"));
    }

    #[test]
    fn test_review_marker_without_commit() {
        // Reviews posted without a commit SHA use a bare marker
        let comment = make_comment("github-actions[bot]", "<!-- claude-review-marker -->\nLGTM");
        let classification = classify(&comment, "AndrewAltimit");
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );
        let metadata = classification.review_metadata.unwrap();
        assert!(metadata.commit_sha.is_none());
        assert_eq!(metadata.reviewer.as_deref(), Some("claude"));
    }

    #[test]
    fn test_retired_reviewer_markers_still_classified() {
        // Markers are generic over the agent slug, so reviews from retired
        // reviewers on old PRs still classify correctly.
        for (body, slug) in [
            (
                "## Gemini AI Incremental Review\n<!-- gemini-review-marker:commit:789abc -->",
                "gemini",
            ),
            (
                "## Codex AI Code Review\n<!-- codex-review-marker:commit:0123abcd -->",
                "codex",
            ),
        ] {
            let classification = classify(&make_comment("github-actions[bot]", body), "x");
            assert_eq!(
                classification.response_type,
                Some(ResponseType::AiAgentReview)
            );
            let metadata = classification.review_metadata.unwrap();
            assert_eq!(metadata.reviewer.as_deref(), Some(slug));
        }
    }

    #[test]
    fn test_copilot_review_classification() {
        let review = make_review(
            "copilot-pull-request-reviewer",
            "## Pull Request Overview\n\nThis PR refactors the poller.",
            "COMMENTED",
            3,
        );
        let classification = classify(&review, "AndrewAltimit");
        assert!(classification.needs_response);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );
        let decision = classification.into_decision(&review);
        let metadata = decision.review_metadata.unwrap();
        assert_eq!(metadata.reviewer.as_deref(), Some("copilot"));
        assert_eq!(metadata.commit_sha.as_deref(), Some("feedface"));
        assert_eq!(metadata.review_state.as_deref(), Some("COMMENTED"));
        assert_eq!(metadata.inline_comments.len(), 3);
        assert_eq!(metadata.inline_comments[1].line, Some(11));
    }

    #[test]
    fn test_copilot_review_without_findings() {
        let review = make_review(
            "Copilot",
            "## Pull Request Overview\n\nCopilot reviewed 2 out of 2 changed files in this pull request and generated no comments.",
            "COMMENTED",
            0,
        );
        let classification = classify(&review, "AndrewAltimit");
        assert!(!classification.needs_response);
        assert_eq!(classification.priority, Priority::Low);
        assert_eq!(
            classification.response_type,
            Some(ResponseType::AiAgentReview)
        );
    }

    #[test]
    fn test_review_response_agent_not_classified_as_review() {
        // Review Response Agent comments are responses, not reviews.
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
        assert_eq!(classification.action, Some(Action::ReviewCiResults));
    }

    #[test]
    fn test_ci_results_with_failures_need_response() {
        let comment = make_comment(
            "github-actions[bot]",
            "## PR Validation Results\n\n| Check | Status |\n|-------|--------|\n| Format check | pass |\n| Full lint | fail |\n| Test suite | fail |\n| Gaea2 | skip |",
        );
        let classification = classify(&comment, "AndrewAltimit");
        assert!(classification.needs_response);
        assert_eq!(classification.priority, Priority::Normal);
        assert_eq!(classification.action, Some(Action::FixFailingCi));
        let metadata = classification.review_metadata.unwrap();
        assert_eq!(metadata.failed_checks, vec!["Full lint", "Test suite"]);
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
    fn test_unrecognized_bot_comment_is_irrelevant() {
        let comment = make_comment("github-actions[bot]", "Deployed preview to https://x");
        assert!(!classify(&comment, "AndrewAltimit").is_recognized());
    }

    #[test]
    fn test_is_relevant_author() {
        assert!(is_relevant_author("AndrewAltimit", "AndrewAltimit"));
        assert!(is_relevant_author("andrewaltimit", "AndrewAltimit"));
        assert!(is_relevant_author("github-actions[bot]", "AndrewAltimit"));
        assert!(is_relevant_author("github-actions", "AndrewAltimit"));
        assert!(is_relevant_author(
            "copilot-pull-request-reviewer",
            "AndrewAltimit"
        ));
        assert!(is_relevant_author("Copilot", "AndrewAltimit"));
        assert!(is_relevant_author("claude[bot]", "AndrewAltimit"));
        assert!(!is_relevant_author("random-user", "AndrewAltimit"));
        assert!(!is_relevant_author("other-admin", "AndrewAltimit"));
        assert!(!is_relevant_author("claudette", "AndrewAltimit"));
    }

    #[test]
    fn test_extract_review_commit_sha() {
        for (body, expected) in [
            (
                "<!-- claude-review-marker:commit:abc123def -->",
                Some("abc123def".to_string()),
            ),
            (
                "<!-- openrouter-review-marker:commit:cafe1234 -->",
                Some("cafe1234".to_string()),
            ),
            ("<!-- claude-review-marker -->", None),
            ("Some review without marker", None),
        ] {
            assert_eq!(extract_review_commit_sha(body), expected, "body: {body}");
        }
    }

    #[test]
    fn test_extract_reviewer_from_heading() {
        assert_eq!(
            extract_reviewer("## OpenRouter AI Code Review").as_deref(),
            Some("openrouter")
        );
        assert_eq!(
            extract_reviewer("## Claude AI Architecture & Quality Review").as_deref(),
            Some("claude")
        );
        assert_eq!(extract_reviewer("## AI Review").as_deref(), None);
        assert_eq!(extract_reviewer("nothing"), None);
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
        assert_eq!(extract_trigger("[ADMIN] do it"), None);
        assert_eq!(extract_trigger("see [Review](https://x)"), None);
        assert_eq!(extract_trigger("- [x] done"), None);
    }

    #[test]
    fn test_has_response_marker() {
        let comments = vec![make_comment(
            "AndrewAltimit",
            "<!-- ai-agent-claude-response:2026-01-18-10-30-00-IC_1 -->",
        )];
        assert!(has_response_marker(&comments, "2026-01-18-10-30-00"));
        assert!(!has_response_marker(&comments, "2026-01-18-11-00-00"));
        assert!(!has_response_marker(&[], "x"));
    }

    #[test]
    fn test_has_prior_response() {
        let review = make_comment(
            "github-actions[bot]",
            "## Claude AI Code Review\n<!-- claude-review-marker:commit:abc -->",
        );
        let id = generate_review_id(&review);

        let mut later_fix = make_comment(
            "AndrewAltimit",
            "## Review Response Agent (Iteration 1)\n<!-- agent-metadata:type=review-fix:iteration=1 -->",
        );
        later_fix.created_at = review.created_at + Duration::minutes(3);

        let mut earlier_fix = later_fix.clone();
        earlier_fix.created_at = review.created_at - Duration::minutes(3);

        let mut later_failure_fix = later_fix.clone();
        later_failure_fix.body = "<!-- agent-metadata:type=failure-fix:iteration=1 -->".into();

        assert!(has_prior_response(
            &review,
            &id,
            &[review.clone(), later_fix.clone()]
        ));
        assert!(!has_prior_response(
            &review,
            &id,
            &[earlier_fix, review.clone()]
        ));
        assert!(!has_prior_response(&review, &id, &[later_failure_fix]));

        let mut limit_notice = later_fix.clone();
        limit_notice.body =
            "<!-- agent-metadata:type=review-fix:iteration=5:limit-reached -->".into();
        assert!(!has_prior_response(&review, &id, &[limit_notice]));

        let mut no_changes = later_fix.clone();
        no_changes.body =
            "<!-- agent-metadata:type=review-fix-hallucination:iteration=2 -->".into();
        assert!(!has_prior_response(&review, &id, &[no_changes]));
    }

    #[test]
    fn test_extract_failed_checks() {
        let body = "| Check | Status |\n|---|---|\n| A | fail |\n| B | pass |\n|C|failure|";
        assert_eq!(extract_failed_checks(body), vec!["A", "C"]);
        assert!(extract_failed_checks("all good").is_empty());
    }

    #[test]
    fn test_normalize_login() {
        assert_eq!(normalize_login("GitHub-Actions[bot]"), "github-actions");
        assert_eq!(normalize_login(" Copilot "), "copilot");
        assert!(logins_match("AndrewAltimit", "andrewaltimit"));
        assert!(!logins_match("a", "b"));
    }

    #[test]
    fn test_ai_review_pattern_matching() {
        for body in [
            "## Claude AI Security & Correctness Review",
            "## Claude AI Architecture & Quality Review",
            "## Claude AI Incremental Security & Correctness Review",
            "## Openrouter AI General Review",
            "## OpenRouter AI Code Review",
            "## Openrouter AI Incremental General Review",
        ] {
            assert!(is_ai_agent_review(body), "expected match: {body}");
        }

        for body in [
            "<!-- claude-review-marker:commit:abc -->",
            "<!-- openrouter-review-marker:commit:abc -->",
        ] {
            assert!(is_ai_agent_review(body), "expected match: {body}");
        }

        for body in [
            "## PR Validation Results\n| Claude security-review | pass |",
            "## PR Validation Results\n| Openrouter review | pass |",
            "## Review Response Agent (Iteration 5)",
            "I just got a review from openrouter",
            "random comment",
            "## Code Review Summary",
        ] {
            assert!(!is_ai_agent_review(body), "expected no match: {body}");
        }
    }
}

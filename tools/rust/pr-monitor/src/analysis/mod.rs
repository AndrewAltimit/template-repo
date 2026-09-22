//! Comment analysis and classification

mod classifier;
mod decision;

pub use classifier::{
    Action, Classification, DEFAULT_ADMIN_USER, VALID_TRIGGER_ACTIONS, classify,
    extract_failed_checks, extract_review_commit_sha, extract_reviewer, extract_trigger,
    has_prior_response, has_response_marker, is_agent_generated, is_relevant_author, is_review_bot,
    logins_match, normalize_login, user_comment,
};
pub use decision::{
    CommentSummary, Decision, InlineComment, Priority, ResponseType, ReviewMetadata,
};

//! Comment analysis and classification

mod classifier;
mod decision;

// Public API exports (some may not be used internally but are part of the library interface)
#[allow(unused_imports)]
pub use classifier::{
    Action, Classification, DEFAULT_ADMIN_USER, classify, extract_codex_commit_sha,
    extract_gemini_commit_sha, extract_trigger, has_response_marker, is_relevant_author,
};
#[allow(unused_imports)]
pub use decision::{CommentSummary, Decision, Priority, ResponseType, ReviewMetadata};

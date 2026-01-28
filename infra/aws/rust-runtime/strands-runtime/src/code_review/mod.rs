//! Code review endpoint and types.
//!
//! Provides a secure endpoint for AI-powered code reviews with:
//! - Untrusted payload isolation
//! - Prompt injection detection
//! - Structured JSON responses

pub mod endpoint;
pub mod request;
pub mod schema;

pub use endpoint::invoke_code_review;
pub use request::{
    CodeReviewRequest, CodeReviewResponse, FileChange, ReviewResult, ReviewSeverity, ReviewStatus,
    SecurityDeniedResponse, UsageResponse,
};
pub use schema::{get_schema, get_system_prompt, REVIEW_ONLY_SCHEMA, REVIEW_WITH_FIXES_SCHEMA};

//! Security helpers for AI agent coordination.
//!
//! - [`judgement`]: heuristics for deciding whether to auto-apply a review
//!   suggestion, ask the owner, or dismiss it as a false positive
//! - [`trust`]: bucketing comments by author trust level from `.agents.yaml`

pub mod judgement;
pub mod trust;

pub use judgement::{AgentJudgement, AssessmentContext};
pub use trust::{Comment, TrustBucketer, TrustConfig, TrustLevel};

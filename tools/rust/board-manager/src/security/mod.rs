//! Security module for AI agent coordination.
//!
//! This module provides:
//! - Agent judgement system for assessing when to auto-fix vs ask for guidance
//! - Trust bucketing for categorizing comments by author trust level

pub mod judgement;
pub mod trust;

pub use judgement::{AgentJudgement, AssessmentContext, FixCategory, JudgementResult};
pub use trust::{
    bucket_comments_for_context, Comment, TrustBucketer, TrustConfig, TrustLevel,
};

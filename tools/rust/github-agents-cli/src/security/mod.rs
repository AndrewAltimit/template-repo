//! Security module for GitHub AI Agents.
//!
//! Provides authorization, rate limiting, trigger parsing, prompt-injection
//! hardening and commit-level validation for agent operations.

pub mod commit;
pub mod manager;
pub mod trigger;
pub mod trust;

pub use manager::{CommentView, SecurityManager, TriggerInfo};
pub use trigger::{AGENT_COMMENT_MARKER, TRIGGER_RESPONSE_MARKER, neutralize_triggers};

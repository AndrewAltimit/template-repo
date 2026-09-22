//! PR Review module for automated code review.
//!
//! This module provides functionality for reviewing pull requests using
//! configurable AI agents (Claude, OpenRouter, OpenCode, Crush).
//!
//! # Features
//!
//! - Profile-based reviewers (`review-profiles.yaml`)
//! - Incremental reviews (only review changes since last trusted review)
//! - Trust-based comment bucketing (Admin/Trusted/Community)
//! - Hallucination detection (verify file/line references)
//! - Brevity enforcement with automatic condensation
//! - Reaction image integration
//! - Prompt-injection hardening: reviewer configuration is read from the
//!   base branch when a PR modifies it, and model output is neutralized
//!   before posting
//!
//! # Configuration
//!
//! Configuration is loaded from `.agents.yaml` under the `pr_review` section.

pub mod agents;
pub mod condenser;
pub mod config;
pub mod diff;
pub mod editor;
pub mod prompt;
pub mod reactions;
pub mod reviewer;
pub mod sanitize;
pub mod verification;

pub use config::PRReviewConfig;
pub use reviewer::PRReviewer;

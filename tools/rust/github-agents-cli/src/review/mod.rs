//! PR Review module for automated code review.
//!
//! This module provides functionality for reviewing pull requests using
//! configurable AI agents (Gemini, Claude, OpenRouter).
//!
//! # Features
//!
//! - Multi-agent support with fallback
//! - Incremental reviews (only review changes since last review)
//! - Trust-based comment bucketing (Admin/Trusted/Community)
//! - Hallucination detection (verify file/line references)
//! - Brevity enforcement with automatic condensation
//! - Reaction image integration
//!
//! # Configuration
//!
//! Configuration is loaded from `.agents.yaml` under the `pr_review` section.

pub mod agents;
pub mod condenser;
pub mod config;
pub mod diff;
pub mod prompt;
pub mod reactions;
pub mod reviewer;
pub mod verification;

pub use config::PRReviewConfig;
pub use reviewer::PRReviewer;

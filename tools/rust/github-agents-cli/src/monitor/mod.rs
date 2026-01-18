//! Monitor implementations for GitHub issues and PRs.
//!
//! This module provides native Rust monitoring capabilities for GitHub issues and PRs.
//! It supports both one-shot and continuous monitoring modes.
//!
//! # Available Monitors
//!
//! - **IssueMonitor** - Monitors GitHub issues for automation triggers
//! - **PrMonitor** - Monitors PRs for review feedback and triggers
//! - **RefinementMonitor** - Multi-agent backlog refinement

mod base;
mod issue;
mod pr;
mod refinement;

pub use base::Monitor;
pub use issue::IssueMonitor;
pub use pr::PrMonitor;
pub use refinement::{RefinementConfig, RefinementMonitor, RefinementResult};

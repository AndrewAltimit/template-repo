//! Monitor implementations for GitHub issues and PRs.
//!
//! # Available Monitors
//!
//! - **IssueMonitor** - Monitors GitHub issues for automation triggers
//! - **PrMonitor** - Monitors PRs for automation triggers (with commit pinning)
//! - **RefinementMonitor** - Multi-agent backlog refinement

mod base;
mod issue;
mod pr;
mod refinement;

pub use base::Monitor;
pub use issue::IssueMonitor;
pub use pr::PrMonitor;
pub use refinement::{RefinementConfig, RefinementMonitor};

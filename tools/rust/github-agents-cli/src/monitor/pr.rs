//! PR monitor implementation.
//!
//! Monitors GitHub PRs for review feedback and automation triggers.

use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use tracing::info;

use super::{run_continuous_impl, run_python_monitor, Monitor};
use crate::error::Error;

/// PR monitor that watches for review feedback and automation triggers.
///
/// Currently delegates to the Python implementation for full functionality.
/// For simple PR monitoring (watching for comments), consider using the
/// dedicated `pr-monitor` Rust tool in `tools/rust/pr-monitor/`.
///
/// Future versions may implement native Rust monitoring for the full
/// feature set including Gemini/Codex review processing.
pub struct PrMonitor {
    running: Arc<AtomicBool>,
}

impl PrMonitor {
    /// Create a new PR monitor
    pub fn new(running: Arc<AtomicBool>) -> Self {
        Self { running }
    }
}

impl Monitor for PrMonitor {
    fn process_items(&self) -> Result<(), Error> {
        info!("Processing PRs...");
        run_python_monitor("github_agents.cli", &["pr-monitor"], &self.running)
    }

    fn run_continuous(&self, interval_secs: u64) -> Result<(), Error> {
        let running = self.running.clone();
        run_continuous_impl(|| self.process_items(), interval_secs, &running)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pr_monitor_creation() {
        let running = Arc::new(AtomicBool::new(true));
        let _monitor = PrMonitor::new(running);
        // Monitor created successfully
    }
}

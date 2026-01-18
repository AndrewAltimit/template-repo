//! Issue monitor implementation.
//!
//! Monitors GitHub issues for automation triggers from authorized users.

use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use tracing::info;

use super::{run_continuous_impl, run_python_monitor, Monitor};
use crate::error::Error;

/// Issue monitor that watches for automation triggers on GitHub issues.
///
/// Currently delegates to the Python implementation for full functionality.
/// Future versions may implement native Rust monitoring.
pub struct IssueMonitor {
    running: Arc<AtomicBool>,
}

impl IssueMonitor {
    /// Create a new issue monitor
    pub fn new(running: Arc<AtomicBool>) -> Self {
        Self { running }
    }
}

impl Monitor for IssueMonitor {
    fn process_items(&self) -> Result<(), Error> {
        info!("Processing issues...");
        run_python_monitor("github_agents.cli", &["issue-monitor"], &self.running)
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
    fn test_issue_monitor_creation() {
        let running = Arc::new(AtomicBool::new(true));
        let _monitor = IssueMonitor::new(running);
        // Monitor created successfully
    }
}

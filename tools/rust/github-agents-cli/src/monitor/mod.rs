//! Monitor implementations for GitHub issues and PRs.
//!
//! This module provides monitoring capabilities that can either:
//! 1. Delegate to Python monitors via subprocess (current implementation)
//! 2. Run native Rust monitoring logic (future enhancement)

mod issue;
mod pr;

pub use issue::IssueMonitor;
pub use pr::PrMonitor;

use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use tracing::{debug, info, warn};

use crate::error::Error;

/// Check if a command is available in PATH
fn command_exists(cmd: &str) -> bool {
    Command::new("which")
        .arg(cmd)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

/// Check if Python and the github_agents package are available
pub fn check_python_available() -> Result<(), Error> {
    // Check for python3
    if !command_exists("python3") {
        return Err(Error::PythonNotFound);
    }

    // Check if github_agents is importable
    let output = Command::new("python3")
        .args(["-c", "import github_agents"])
        .output()?;

    if !output.status.success() {
        return Err(Error::PythonNotFound);
    }

    debug!("Python and github_agents package available");
    Ok(())
}

/// Check if GitHub CLI is available and authenticated
pub fn check_gh_available() -> Result<(), Error> {
    if !command_exists("gh") {
        return Err(Error::GhNotFound);
    }

    // Check authentication
    let output = Command::new("gh").args(["auth", "status"]).output()?;

    if !output.status.success() {
        return Err(Error::GhNotFound);
    }

    debug!("GitHub CLI available and authenticated");
    Ok(())
}

/// Base trait for monitors
pub trait Monitor {
    /// Process items once
    fn process_items(&self) -> Result<(), Error>;

    /// Run continuously with the given interval
    fn run_continuous(&self, interval_secs: u64) -> Result<(), Error>;
}

/// Common implementation for running a Python monitor
fn run_python_monitor(module: &str, args: &[&str], running: &Arc<AtomicBool>) -> Result<(), Error> {
    check_python_available()?;
    check_gh_available()?;

    info!("Delegating to Python monitor: {}", module);

    let mut cmd_args = vec!["-m", module];
    cmd_args.extend(args);

    let mut child = Command::new("python3").args(&cmd_args).spawn()?;

    // Wait for completion or interruption
    loop {
        if !running.load(Ordering::SeqCst) {
            info!("Stopping Python monitor...");
            // Try to kill gracefully
            let _ = child.kill();
            return Err(Error::Interrupted);
        }

        match child.try_wait()? {
            Some(status) => {
                if status.success() {
                    return Ok(());
                } else {
                    let code = status.code().unwrap_or(-1);
                    return Err(Error::MonitorFailed(format!("Exit code: {}", code)));
                }
            }
            None => {
                // Still running, wait a bit
                thread::sleep(Duration::from_millis(100));
            }
        }
    }
}

/// Common implementation for continuous monitoring
fn run_continuous_impl<F>(
    process_fn: F,
    interval_secs: u64,
    running: &Arc<AtomicBool>,
) -> Result<(), Error>
where
    F: Fn() -> Result<(), Error>,
{
    let interval = Duration::from_secs(interval_secs);

    while running.load(Ordering::SeqCst) {
        match process_fn() {
            Ok(()) => {
                info!("Monitor cycle completed, sleeping for {}s", interval_secs);
            }
            Err(Error::Interrupted) => {
                info!("Monitor interrupted");
                return Ok(());
            }
            Err(e) => {
                warn!("Monitor error (will retry): {}", e);
            }
        }

        // Sleep in small increments to check for interruption
        let mut remaining = interval;
        while remaining > Duration::ZERO && running.load(Ordering::SeqCst) {
            let sleep_time = remaining.min(Duration::from_secs(1));
            thread::sleep(sleep_time);
            remaining = remaining.saturating_sub(sleep_time);
        }
    }

    info!("Monitor stopped");
    Ok(())
}

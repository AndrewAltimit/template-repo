//! Polling loop for PR comment monitoring
//!
//! Ported from monitor.sh - polls GitHub PR for new comments at regular intervals

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};

use chrono::{DateTime, Utc};

use crate::analysis::{Classification, DEFAULT_ADMIN_USER, classify, is_relevant_author};
use crate::error::{Error, Result};
use crate::github::{Comment, GhClient};

/// PR comment poller
pub struct Poller {
    pr_number: u32,
    poll_interval: Duration,
    timeout: Duration,
    since_time: Option<DateTime<Utc>>,
    admin_user: String,
    running: Arc<AtomicBool>,
}

impl Poller {
    /// Create a new poller
    pub fn new(
        pr_number: u32,
        poll_interval: Duration,
        timeout: Duration,
        since_time: Option<DateTime<Utc>>,
        running: Arc<AtomicBool>,
    ) -> Self {
        Self {
            pr_number,
            poll_interval,
            timeout,
            since_time,
            admin_user: DEFAULT_ADMIN_USER.to_string(),
            running,
        }
    }

    /// Run the polling loop until a relevant comment is found or timeout
    ///
    /// Returns Ok(Some(comment, classification)) when found, Ok(None) should not happen
    /// as we return Err(Timeout) instead.
    pub fn run(&self, quiet: bool) -> Result<(Comment, Classification)> {
        let start = Instant::now();

        // First check: if since_commit provided, check existing comments
        if let Some(comment_and_class) = self.check_existing_comments(quiet)? {
            return Ok(comment_and_class);
        }

        // Get initial comment count
        let mut last_count = GhClient::get_comment_count(self.pr_number)?;
        let mut checks = 0;

        if !quiet {
            eprintln!(
                "Starting monitoring (poll interval: {}s, timeout: {}s)",
                self.poll_interval.as_secs(),
                self.timeout.as_secs()
            );
            eprintln!("Initial comment count: {}", last_count);
            eprintln!();
        }

        // Polling loop
        loop {
            // Check for interrupt
            if !self.running.load(Ordering::SeqCst) {
                return Err(Error::Interrupted);
            }

            thread::sleep(self.poll_interval);
            checks += 1;

            // Check timeout
            let elapsed = start.elapsed();
            if elapsed >= self.timeout {
                return Err(Error::Timeout {
                    seconds: self.timeout.as_secs(),
                });
            }

            // Get current comment count
            let current_count = GhClient::get_comment_count(self.pr_number)?;

            if !quiet {
                let remaining = self.timeout.as_secs().saturating_sub(elapsed.as_secs());
                eprint!(
                    "\r[{:02}:{:02}] Check #{}: {} comments ({}s remaining)    ",
                    elapsed.as_secs() / 60,
                    elapsed.as_secs() % 60,
                    checks,
                    current_count,
                    remaining
                );
            }

            if current_count > last_count {
                if !quiet {
                    eprintln!();
                    eprintln!(
                        "New comments detected! ({} -> {})",
                        last_count, current_count
                    );
                }

                // Fetch all comments and check the new ones
                let comments = GhClient::get_pr_comments(self.pr_number)?;

                for comment in comments.iter().skip(last_count) {
                    if self.is_relevant(comment) && self.passes_time_filter(comment) {
                        let classification = classify(comment, &self.admin_user);
                        if !quiet {
                            eprintln!(
                                "Found relevant comment from {} (type: {:?})",
                                comment.author.login, classification.response_type
                            );
                        }
                        return Ok((comment.clone(), classification));
                    }
                }

                last_count = current_count;
                if !quiet {
                    eprintln!("New comments were not relevant, continuing...");
                    eprintln!();
                }
            }
        }
    }

    /// Check existing comments for any relevant ones after since_time
    fn check_existing_comments(&self, quiet: bool) -> Result<Option<(Comment, Classification)>> {
        if self.since_time.is_none() {
            return Ok(None);
        }

        if !quiet {
            eprintln!("Checking existing comments after since-commit timestamp...");
        }

        let comments = GhClient::get_pr_comments(self.pr_number)?;

        for comment in &comments {
            if self.is_relevant(comment) && self.passes_time_filter(comment) {
                let classification = classify(comment, &self.admin_user);
                if classification.needs_response {
                    if !quiet {
                        eprintln!(
                            "Found existing relevant comment from {} at {}",
                            comment.author.login,
                            comment.created_at.format("%Y-%m-%d %H:%M:%S")
                        );
                    }
                    return Ok(Some((comment.clone(), classification)));
                }
            }
        }

        if !quiet {
            eprintln!("No relevant existing comments found after the commit timestamp.");
            eprintln!();
        }

        Ok(None)
    }

    /// Check if comment author is relevant for monitoring
    fn is_relevant(&self, comment: &Comment) -> bool {
        is_relevant_author(&comment.author.login, &self.admin_user)
    }

    /// Check if comment passes the time filter (if since_time is set)
    fn passes_time_filter(&self, comment: &Comment) -> bool {
        match &self.since_time {
            Some(since) => comment.created_at > *since,
            None => true,
        }
    }
}

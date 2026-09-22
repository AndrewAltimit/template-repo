//! Minimal blocking HTTP helpers for health checks.

use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use reqwest::blocking::Client;

/// Build a blocking client with a per-request timeout. Build it once and
/// reuse it across polling iterations.
pub fn client(timeout: Duration) -> Result<Client> {
    Client::builder()
        .timeout(timeout)
        .build()
        .context("failed to build HTTP client")
}

/// True if `GET url` returns a 2xx status.
pub fn get_ok(client: &Client, url: &str) -> bool {
    client
        .get(url)
        .send()
        .is_ok_and(|r| r.status().is_success())
}

/// True if `GET url` returns a 2xx or 3xx status (web UIs often redirect).
pub fn get_ok_or_redirect(client: &Client, url: &str) -> bool {
    client.get(url).send().is_ok_and(|r| {
        let s = r.status();
        s.is_success() || s.is_redirection()
    })
}

/// Poll `check` every `interval` until it returns true or `timeout` elapses.
/// `on_tick` runs after each failed attempt (e.g. to print a progress dot).
/// Never sleeps past the deadline. Returns whether the check succeeded.
pub fn poll_until(
    timeout: Duration,
    interval: Duration,
    mut check: impl FnMut() -> bool,
    mut on_tick: impl FnMut(),
) -> bool {
    let start = Instant::now();
    loop {
        if check() {
            return true;
        }
        let elapsed = start.elapsed();
        if elapsed >= timeout {
            return false;
        }
        on_tick();
        std::thread::sleep(interval.min(timeout - elapsed));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn poll_until_succeeds_after_retries() {
        let mut calls = 0;
        let ok = poll_until(
            Duration::from_secs(5),
            Duration::from_millis(1),
            || {
                calls += 1;
                calls >= 3
            },
            || {},
        );
        assert!(ok);
        assert_eq!(calls, 3);
    }

    #[test]
    fn poll_until_times_out() {
        let mut ticks = 0;
        let ok = poll_until(
            Duration::from_millis(20),
            Duration::from_millis(5),
            || false,
            || ticks += 1,
        );
        assert!(!ok);
        assert!(ticks >= 1);
    }

    #[test]
    fn poll_until_zero_timeout_checks_once() {
        let mut calls = 0;
        let ok = poll_until(
            Duration::ZERO,
            Duration::from_secs(1),
            || {
                calls += 1;
                false
            },
            || {},
        );
        assert!(!ok);
        assert_eq!(calls, 1);
    }
}

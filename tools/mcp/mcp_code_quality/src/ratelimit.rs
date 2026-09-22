//! Per-operation sliding-window rate limiting.

use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, Instant};

/// Sliding window of `calls` per `period`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RateLimitConfig {
    pub calls: usize,
    pub period: Duration,
}

impl RateLimitConfig {
    const fn per_minute(calls: usize) -> Self {
        Self {
            calls,
            period: Duration::from_secs(60),
        }
    }
}

/// Built-in limits, per operation name. Unknown operations get 100/minute.
pub fn limit_for(operation: &str) -> RateLimitConfig {
    match operation {
        "format_check" => RateLimitConfig::per_minute(100),
        "lint" | "autoformat" => RateLimitConfig::per_minute(50),
        "type_check" | "check_markdown_links" => RateLimitConfig::per_minute(30),
        "run_tests" | "security_scan" => RateLimitConfig::per_minute(20),
        "audit_dependencies" => RateLimitConfig::per_minute(10),
        _ => RateLimitConfig::per_minute(100),
    }
}

/// Operations that are rate limited (used for status reporting).
pub const LIMITED_OPERATIONS: &[&str] = &[
    "format_check",
    "lint",
    "autoformat",
    "run_tests",
    "type_check",
    "security_scan",
    "audit_dependencies",
    "check_markdown_links",
];

/// Sliding-window limiter keyed by operation name.
#[derive(Debug)]
pub struct RateLimiter {
    enabled: bool,
    windows: Mutex<HashMap<String, Vec<Instant>>>,
}

impl RateLimiter {
    /// New limiter; when `enabled` is false every call is admitted.
    pub fn new(enabled: bool) -> Self {
        Self {
            enabled,
            windows: Mutex::new(HashMap::new()),
        }
    }

    /// Whether limiting is active.
    pub fn enabled(&self) -> bool {
        self.enabled
    }

    /// Admit a call now, recording it, or return how long until a slot frees.
    pub fn check(&self, operation: &str) -> Result<(), Duration> {
        self.check_at(operation, Instant::now(), limit_for(operation))
    }

    fn check_at(
        &self,
        operation: &str,
        now: Instant,
        cfg: RateLimitConfig,
    ) -> Result<(), Duration> {
        if !self.enabled {
            return Ok(());
        }
        let mut windows = self.windows.lock().unwrap_or_else(|e| e.into_inner());
        let stamps = windows.entry(operation.to_string()).or_default();
        stamps.retain(|t| now.saturating_duration_since(*t) < cfg.period);
        if stamps.len() >= cfg.calls {
            let oldest = stamps.first().copied().unwrap_or(now);
            return Err(cfg
                .period
                .saturating_sub(now.saturating_duration_since(oldest)));
        }
        stamps.push(now);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disabled_always_admits() {
        let rl = RateLimiter::new(false);
        let cfg = RateLimitConfig::per_minute(1);
        let now = Instant::now();
        for _ in 0..10 {
            assert!(rl.check_at("x", now, cfg).is_ok());
        }
    }

    #[test]
    fn enforces_window_and_recovers() {
        let rl = RateLimiter::new(true);
        let cfg = RateLimitConfig {
            calls: 2,
            period: Duration::from_secs(10),
        };
        let t0 = Instant::now();
        assert!(rl.check_at("op", t0, cfg).is_ok());
        assert!(rl.check_at("op", t0, cfg).is_ok());
        let wait = rl
            .check_at("op", t0 + Duration::from_secs(3), cfg)
            .unwrap_err();
        assert_eq!(wait, Duration::from_secs(7));
        // Other operations are independent.
        assert!(rl.check_at("other", t0, cfg).is_ok());
        // After the window passes, calls are admitted again.
        assert!(rl.check_at("op", t0 + Duration::from_secs(11), cfg).is_ok());
    }

    #[test]
    fn built_in_limits() {
        assert_eq!(limit_for("audit_dependencies").calls, 10);
        assert_eq!(limit_for("format_check").calls, 100);
        assert_eq!(limit_for("run_tests").calls, 20);
        assert_eq!(limit_for("unknown").calls, 100);
        for op in LIMITED_OPERATIONS {
            assert!(limit_for(op).calls > 0);
        }
    }
}

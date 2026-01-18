//! Security utilities - path validation, rate limiting, audit logging

use std::collections::HashMap;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;

use chrono::Utc;
use serde::Serialize;
use tokio::sync::Mutex;
use tracing::{info, warn};

use crate::config::{get_rate_limit, Config};
use crate::error::{Result, ToolError};

/// Path validator for ensuring operations stay within allowed directories
#[derive(Debug, Clone)]
pub struct PathValidator {
    allowed_paths: Vec<PathBuf>,
}

impl PathValidator {
    pub fn new(allowed_paths: Vec<PathBuf>) -> Self {
        Self { allowed_paths }
    }

    /// Validate that a path is within allowed directories
    ///
    /// This resolves symlinks and checks if the path is a descendant
    /// of any allowed path, preventing path traversal attacks.
    pub fn validate(&self, path: &str) -> Result<PathBuf> {
        let path = Path::new(path);

        // Try to canonicalize (resolve symlinks and make absolute)
        let resolved = path.canonicalize().map_err(|e| {
            ToolError::PathValidation(format!(
                "Failed to resolve path '{}': {}",
                path.display(),
                e
            ))
        })?;

        // Check if resolved path is under any allowed path
        for allowed in &self.allowed_paths {
            // Canonicalize the allowed path too (may fail if doesn't exist)
            if let Ok(allowed_resolved) = allowed.canonicalize() {
                if resolved.starts_with(&allowed_resolved) {
                    return Ok(resolved);
                }
            } else if resolved.starts_with(allowed) {
                // Fallback: check without canonicalizing allowed path
                return Ok(resolved);
            }
        }

        Err(ToolError::PathValidation(format!(
            "Path '{}' is not within allowed directories",
            path.display()
        )))
    }
}

/// Rate limiter using sliding window algorithm
#[derive(Debug)]
pub struct RateLimiter {
    /// Map of operation -> list of timestamps
    tracker: Arc<Mutex<HashMap<String, Vec<Instant>>>>,
    enabled: bool,
}

impl RateLimiter {
    pub fn new(enabled: bool) -> Self {
        Self {
            tracker: Arc::new(Mutex::new(HashMap::new())),
            enabled,
        }
    }

    /// Check if an operation is within rate limits
    ///
    /// Returns Ok(()) if allowed, Err if rate limited
    pub async fn check(&self, operation: &str) -> Result<()> {
        if !self.enabled {
            return Ok(());
        }

        let config = get_rate_limit(operation);
        let now = Instant::now();
        let window_start = now - std::time::Duration::from_secs(config.period_secs);

        let mut tracker = self.tracker.lock().await;
        let timestamps = tracker.entry(operation.to_string()).or_default();

        // Clean old entries outside the window
        timestamps.retain(|&t| t > window_start);

        // Check if we're over the limit
        if timestamps.len() >= config.calls {
            return Err(ToolError::RateLimit(operation.to_string()));
        }

        // Record this call
        timestamps.push(now);

        Ok(())
    }
}

/// Audit logger for compliance tracking
#[derive(Debug, Clone)]
pub struct AuditLogger {
    log_path: PathBuf,
    fallback_path: PathBuf,
}

/// Audit log entry structure
#[derive(Debug, Serialize)]
struct AuditEntry {
    timestamp: String,
    operation: String,
    path: Option<String>,
    success: bool,
    details: serde_json::Value,
}

impl AuditLogger {
    pub fn new(log_path: PathBuf) -> Self {
        Self {
            log_path,
            fallback_path: PathBuf::from("/tmp/mcp-code-quality-audit.log"),
        }
    }

    /// Log an operation for audit purposes
    pub fn log(
        &self,
        operation: &str,
        path: Option<&str>,
        success: bool,
        details: serde_json::Value,
    ) {
        let entry = AuditEntry {
            timestamp: Utc::now().to_rfc3339(),
            operation: operation.to_string(),
            path: path.map(String::from),
            success,
            details,
        };

        let line = match serde_json::to_string(&entry) {
            Ok(s) => s,
            Err(e) => {
                warn!("Failed to serialize audit entry: {}", e);
                return;
            }
        };

        // Try primary log path
        if self.write_to_file(&self.log_path, &line).is_ok() {
            return;
        }

        // Try fallback path
        if self.write_to_file(&self.fallback_path, &line).is_ok() {
            info!("Wrote audit log to fallback path");
            return;
        }

        // Last resort: log to tracing
        warn!("Could not write audit log to file, logging here: {}", line);
    }

    fn write_to_file(&self, path: &Path, line: &str) -> std::io::Result<()> {
        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let mut file = OpenOptions::new().create(true).append(true).open(path)?;

        writeln!(file, "{}", line)?;
        Ok(())
    }
}

impl Default for AuditLogger {
    fn default() -> Self {
        Self::new(Config::from_env().audit_log_path)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_path_validator_valid_path() {
        let validator = PathValidator::new(vec![PathBuf::from("/tmp")]);

        // Create a temp file to validate
        let temp_dir = std::env::temp_dir();
        let result = validator.validate(temp_dir.to_str().unwrap());
        assert!(result.is_ok());
    }

    #[test]
    fn test_path_validator_invalid_path() {
        let validator = PathValidator::new(vec![PathBuf::from("/nonexistent")]);
        let result = validator.validate("/etc/passwd");
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_rate_limiter_allows_within_limit() {
        let limiter = RateLimiter::new(true);

        // Should allow first few calls
        for _ in 0..5 {
            assert!(limiter.check("format_check").await.is_ok());
        }
    }

    #[tokio::test]
    async fn test_rate_limiter_disabled() {
        let limiter = RateLimiter::new(false);

        // Should always allow when disabled
        for _ in 0..200 {
            assert!(limiter.check("format_check").await.is_ok());
        }
    }
}

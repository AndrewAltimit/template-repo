//! Configuration for the MCP Code Quality server

use std::env;
use std::path::PathBuf;
use std::time::Duration;

/// Server configuration loaded from environment variables
#[derive(Debug, Clone)]
pub struct Config {
    /// HTTP server port
    pub port: u16,

    /// Command timeout in seconds
    pub timeout: Duration,

    /// Allowed paths for file operations (comma-separated)
    pub allowed_paths: Vec<PathBuf>,

    /// Audit log file path
    pub audit_log_path: PathBuf,

    /// Whether rate limiting is enabled
    pub rate_limit_enabled: bool,

    /// Host to bind to
    pub host: String,
}

impl Config {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        let port = env::var("MCP_CODE_QUALITY_PORT")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(8010);

        let timeout_secs = env::var("MCP_CODE_QUALITY_TIMEOUT")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(600);

        let allowed_paths_str = env::var("MCP_CODE_QUALITY_ALLOWED_PATHS")
            .unwrap_or_else(|_| "/workspace,/app,/home,/tmp".to_string());

        let allowed_paths = allowed_paths_str
            .split(',')
            .map(|s| PathBuf::from(s.trim()))
            .collect();

        let audit_log_path = env::var("MCP_CODE_QUALITY_AUDIT_LOG")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("/var/log/mcp-code-quality/audit.log"));

        let rate_limit_enabled = env::var("MCP_CODE_QUALITY_RATE_LIMIT")
            .map(|s| s.to_lowercase() != "false")
            .unwrap_or(true);

        let host = env::var("MCP_CODE_QUALITY_HOST").unwrap_or_else(|_| "0.0.0.0".to_string());

        Config {
            port,
            timeout: Duration::from_secs(timeout_secs),
            allowed_paths,
            audit_log_path,
            rate_limit_enabled,
            host,
        }
    }
}

impl Default for Config {
    fn default() -> Self {
        Self::from_env()
    }
}

/// Rate limit configuration per operation
#[derive(Debug, Clone, Copy)]
pub struct RateLimitConfig {
    /// Maximum calls allowed
    pub calls: usize,
    /// Time period in seconds
    pub period_secs: u64,
}

impl RateLimitConfig {
    pub const fn new(calls: usize, period_secs: u64) -> Self {
        Self { calls, period_secs }
    }
}

/// Get rate limit config for an operation
pub fn get_rate_limit(operation: &str) -> RateLimitConfig {
    match operation {
        "format_check" => RateLimitConfig::new(100, 60),
        "lint" => RateLimitConfig::new(50, 60),
        "autoformat" => RateLimitConfig::new(50, 60),
        "run_tests" => RateLimitConfig::new(20, 60),
        "type_check" => RateLimitConfig::new(30, 60),
        "security_scan" => RateLimitConfig::new(20, 60),
        "audit_dependencies" => RateLimitConfig::new(10, 60),
        "check_markdown_links" => RateLimitConfig::new(20, 60),
        "get_status" => RateLimitConfig::new(200, 60),
        "get_audit_log" => RateLimitConfig::new(50, 60),
        _ => RateLimitConfig::new(100, 60), // Default
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = Config::from_env();
        assert_eq!(config.port, 8010);
        assert_eq!(config.timeout, Duration::from_secs(600));
        assert!(config.rate_limit_enabled);
    }

    #[test]
    fn test_rate_limit_configs() {
        assert_eq!(get_rate_limit("format_check").calls, 100);
        assert_eq!(get_rate_limit("lint").calls, 50);
        assert_eq!(get_rate_limit("run_tests").calls, 20);
        assert_eq!(get_rate_limit("audit_dependencies").calls, 10);
    }
}

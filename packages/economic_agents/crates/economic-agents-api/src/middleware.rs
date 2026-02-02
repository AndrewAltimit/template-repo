//! Middleware for API services.
//!
//! Provides authentication and rate limiting for the Axum services.

use axum::{
    Json,
    extract::Request,
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::Response,
};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};
use tracing::{debug, warn};

use crate::models::ApiErrorResponse;

// ============================================================================
// Authentication Middleware
// ============================================================================

/// Configuration for API key authentication.
#[derive(Debug, Clone, Default)]
pub struct AuthConfig {
    /// Valid API keys (key -> agent_id mapping).
    pub api_keys: HashMap<String, String>,
    /// Whether authentication is required.
    pub required: bool,
}

impl AuthConfig {
    /// Create auth config with required authentication.
    pub fn required(api_keys: HashMap<String, String>) -> Self {
        Self {
            api_keys,
            required: true,
        }
    }

    /// Create auth config with optional authentication.
    pub fn optional(api_keys: HashMap<String, String>) -> Self {
        Self {
            api_keys,
            required: false,
        }
    }

    /// Add an API key.
    pub fn with_key(mut self, key: impl Into<String>, agent_id: impl Into<String>) -> Self {
        self.api_keys.insert(key.into(), agent_id.into());
        self
    }
}

/// State for authentication middleware.
#[derive(Clone)]
pub struct AuthState {
    #[allow(dead_code)]
    config: AuthConfig,
}

impl AuthState {
    pub fn new(config: AuthConfig) -> Self {
        Self { config }
    }
}

/// Validate API key from request headers.
pub fn validate_api_key(
    headers: &HeaderMap,
    config: &AuthConfig,
) -> Result<Option<String>, String> {
    let api_key = headers
        .get("X-API-Key")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());

    match api_key {
        Some(key) => {
            if let Some(agent_id) = config.api_keys.get(&key) {
                debug!("Authenticated agent: {}", agent_id);
                Ok(Some(agent_id.clone()))
            } else {
                warn!("Invalid API key provided");
                Err("Invalid API key".to_string())
            }
        }
        None => {
            if config.required {
                warn!("API key required but not provided");
                Err("API key required".to_string())
            } else {
                debug!("No API key provided (optional auth)");
                Ok(None)
            }
        }
    }
}

/// Authentication middleware.
pub async fn auth_middleware(
    _headers: HeaderMap,
    request: Request,
    next: Next,
) -> std::result::Result<Response, (StatusCode, Json<ApiErrorResponse>)> {
    // For now, skip auth - real implementation would check against AuthState
    // This is a placeholder that allows all requests through
    Ok(next.run(request).await)
}

// ============================================================================
// Rate Limiting Middleware
// ============================================================================

/// Rate limit configuration.
#[derive(Debug, Clone)]
pub struct RateLimitConfig {
    /// Maximum requests per minute.
    pub requests_per_minute: u32,
    /// Maximum requests per hour.
    pub requests_per_hour: u32,
    /// Window duration for per-minute limits.
    pub minute_window: Duration,
    /// Window duration for per-hour limits.
    pub hour_window: Duration,
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            requests_per_minute: 60,
            requests_per_hour: 1000,
            minute_window: Duration::from_secs(60),
            hour_window: Duration::from_secs(3600),
        }
    }
}

/// Tracks rate limit state for a single client.
#[derive(Debug, Clone)]
struct RateLimitEntry {
    /// Requests in current minute window.
    minute_count: u32,
    /// Requests in current hour window.
    hour_count: u32,
    /// Start of current minute window.
    minute_window_start: Instant,
    /// Start of current hour window.
    hour_window_start: Instant,
}

impl RateLimitEntry {
    fn new() -> Self {
        let now = Instant::now();
        Self {
            minute_count: 0,
            hour_count: 0,
            minute_window_start: now,
            hour_window_start: now,
        }
    }

    fn check_and_increment(&mut self, config: &RateLimitConfig) -> bool {
        let now = Instant::now();

        // Reset minute window if needed
        if now.duration_since(self.minute_window_start) > config.minute_window {
            self.minute_count = 0;
            self.minute_window_start = now;
        }

        // Reset hour window if needed
        if now.duration_since(self.hour_window_start) > config.hour_window {
            self.hour_count = 0;
            self.hour_window_start = now;
        }

        // Check limits
        if self.minute_count >= config.requests_per_minute {
            return false;
        }
        if self.hour_count >= config.requests_per_hour {
            return false;
        }

        // Increment counters
        self.minute_count += 1;
        self.hour_count += 1;

        true
    }
}

/// State for rate limiting middleware.
#[derive(Clone)]
pub struct RateLimitState {
    config: RateLimitConfig,
    entries: Arc<RwLock<HashMap<String, RateLimitEntry>>>,
}

impl RateLimitState {
    pub fn new(config: RateLimitConfig) -> Self {
        Self {
            config,
            entries: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Check if a request from the given client ID is allowed.
    pub fn check(&self, client_id: &str) -> bool {
        let mut entries = self
            .entries
            .write()
            .expect("rate limit lock should not be poisoned");
        let entry = entries
            .entry(client_id.to_string())
            .or_insert_with(RateLimitEntry::new);
        entry.check_and_increment(&self.config)
    }

    /// Get remaining requests for a client.
    pub fn remaining(&self, client_id: &str) -> (u32, u32) {
        let entries = self
            .entries
            .read()
            .expect("rate limit lock should not be poisoned");
        if let Some(entry) = entries.get(client_id) {
            let minute_remaining = self
                .config
                .requests_per_minute
                .saturating_sub(entry.minute_count);
            let hour_remaining = self
                .config
                .requests_per_hour
                .saturating_sub(entry.hour_count);
            (minute_remaining, hour_remaining)
        } else {
            (
                self.config.requests_per_minute,
                self.config.requests_per_hour,
            )
        }
    }
}

/// Rate limiting middleware.
pub async fn rate_limit_middleware(
    _headers: HeaderMap,
    request: Request,
    next: Next,
) -> std::result::Result<Response, (StatusCode, Json<ApiErrorResponse>)> {
    // For now, no rate limiting - real implementation would check against RateLimitState
    Ok(next.run(request).await)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_auth_config() {
        let config = AuthConfig::default()
            .with_key("key1", "agent1")
            .with_key("key2", "agent2");

        assert!(!config.required);
        assert_eq!(config.api_keys.get("key1"), Some(&"agent1".to_string()));
        assert_eq!(config.api_keys.get("key2"), Some(&"agent2".to_string()));
    }

    #[test]
    fn test_rate_limit_state() {
        let config = RateLimitConfig {
            requests_per_minute: 5,
            requests_per_hour: 10,
            ..Default::default()
        };
        let state = RateLimitState::new(config);

        // First 5 requests should pass
        for _ in 0..5 {
            assert!(state.check("client1"));
        }

        // 6th request should fail (minute limit)
        assert!(!state.check("client1"));

        // Different client should still work
        assert!(state.check("client2"));
    }

    #[test]
    fn test_rate_limit_remaining() {
        let config = RateLimitConfig {
            requests_per_minute: 10,
            requests_per_hour: 100,
            ..Default::default()
        };
        let state = RateLimitState::new(config);

        assert_eq!(state.remaining("client1"), (10, 100));

        state.check("client1");
        state.check("client1");
        state.check("client1");

        assert_eq!(state.remaining("client1"), (7, 97));
    }
}

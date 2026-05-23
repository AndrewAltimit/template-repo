//! Shared HTTP client construction for MCP servers.
//!
//! Most servers that talk to an upstream HTTP service hand-roll the same
//! `reqwest::Client::builder().timeout(..).build().expect(..)` block, each with
//! a different total timeout and none with a connect timeout. This module
//! centralizes that so every client gets a consistent connect timeout and the
//! build failure is surfaced as an error rather than a bespoke `expect` string.
//!
//! ```no_run
//! use std::time::Duration;
//! use mcp_core::http;
//!
//! // Fallible: propagate the (rare) builder error.
//! let client = http::build_client(Duration::from_secs(30))?;
//!
//! // Infallible: never panics; falls back to a default client if the builder
//! // fails so a server can still start.
//! let client = http::build_client_or_default(Duration::from_secs(30));
//! # Ok::<(), reqwest::Error>(())
//! ```

use std::time::Duration;

/// Default connection-establishment timeout applied to all clients built here.
///
/// Bounds the time spent opening a TCP/TLS connection so a dead or unreachable
/// host fails fast instead of waiting for the (longer) total request timeout.
pub const DEFAULT_CONNECT_TIMEOUT: Duration = Duration::from_secs(10);

/// Build a [`reqwest::Client`] with a total request `timeout` and the shared
/// [`DEFAULT_CONNECT_TIMEOUT`].
///
/// Returns the builder error instead of panicking; callers that construct
/// infallibly (e.g. a `new() -> Self`) can use [`build_client_or_default`].
pub fn build_client(timeout: Duration) -> reqwest::Result<reqwest::Client> {
    reqwest::Client::builder()
        .timeout(timeout)
        .connect_timeout(DEFAULT_CONNECT_TIMEOUT)
        .build()
}

/// Like [`build_client`] but never fails: if the builder errors (rare, e.g. a
/// TLS backend that fails to initialize), fall back to [`reqwest::Client::new`]
/// so the server can still start. The fallback loses the configured timeouts,
/// which is strictly better than aborting startup.
pub fn build_client_or_default(timeout: Duration) -> reqwest::Client {
    build_client(timeout).unwrap_or_else(|_| reqwest::Client::new())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_client_succeeds_with_typical_timeout() {
        assert!(build_client(Duration::from_secs(30)).is_ok());
    }

    #[test]
    fn build_client_or_default_always_returns_client() {
        // Should not panic for any reasonable timeout, including zero.
        let _ = build_client_or_default(Duration::from_secs(0));
        let _ = build_client_or_default(Duration::from_secs(300));
    }
}

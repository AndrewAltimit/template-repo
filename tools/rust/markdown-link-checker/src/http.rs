//! External (HTTP/HTTPS) link validation.
//!
//! Each URL is probed with `HEAD`, falling back to `GET` when the server
//! rejects or mishandles `HEAD`. Requests are bounded by a global concurrency
//! limit and a per-host limit, and transient failures (timeouts, connection
//! errors, 408/429/5xx) are retried with exponential backoff that honors
//! `Retry-After`.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use anyhow::{Context, Result};
use reqwest::header::{HeaderMap, RETRY_AFTER};
use reqwest::{Client, Method, StatusCode, Url};
use tokio::sync::Semaphore;

/// Tunables for [`HttpChecker`].
#[derive(Debug, Clone)]
pub struct HttpOptions {
    /// Per-request timeout.
    pub timeout: Duration,
    /// Maximum requests in flight overall.
    pub concurrency: usize,
    /// Maximum requests in flight to any single host.
    pub per_host: usize,
    /// Retries after the first attempt for transient failures.
    pub max_retries: u32,
    /// First backoff delay; doubles on each retry.
    pub retry_base: Duration,
    /// Upper bound for any single wait (including `Retry-After`).
    pub max_retry_wait: Duration,
    /// Extra status codes treated as success (e.g. 403 for bot-hostile sites).
    pub accept: Vec<u16>,
    /// Maximum redirects to follow.
    pub max_redirects: usize,
}

impl Default for HttpOptions {
    fn default() -> Self {
        Self {
            timeout: Duration::from_secs(10),
            concurrency: 10,
            per_host: 4,
            max_retries: 2,
            retry_base: Duration::from_millis(500),
            max_retry_wait: Duration::from_secs(30),
            accept: Vec::new(),
            max_redirects: 10,
        }
    }
}

/// Result of one probe round.
enum Probe {
    Ok,
    Fail(String),
    Retry {
        reason: String,
        wait: Option<Duration>,
    },
}

/// Shared, cloneable-by-`Arc` HTTP link checker.
#[derive(Debug)]
pub struct HttpChecker {
    client: Client,
    global: Semaphore,
    hosts: Mutex<HashMap<String, Arc<Semaphore>>>,
    options: HttpOptions,
}

impl HttpChecker {
    /// Build a checker with its own connection pool.
    pub fn new(options: HttpOptions) -> Result<Self> {
        let client = Client::builder()
            .timeout(options.timeout)
            .connect_timeout(options.timeout)
            .redirect(reqwest::redirect::Policy::limited(options.max_redirects))
            .user_agent(concat!("md-link-checker/", env!("CARGO_PKG_VERSION")))
            .build()
            .context("Failed to build HTTP client")?;
        Ok(Self {
            client,
            global: Semaphore::new(options.concurrency.max(1)),
            hosts: Mutex::new(HashMap::new()),
            options,
        })
    }

    /// Check one URL. `Err` carries a human-readable reason.
    pub async fn check(&self, url: &str) -> Result<(), String> {
        let parsed = Url::parse(url).map_err(|e| format!("Invalid URL: {e}"))?;
        let host = self.host_semaphore(parsed.host_str().unwrap_or_default());

        let mut attempt = 0;
        loop {
            let probe = {
                let _host = host.acquire().await.map_err(|e| e.to_string())?;
                let _global = self.global.acquire().await.map_err(|e| e.to_string())?;
                self.probe(&parsed).await
            };
            match probe {
                Probe::Ok => return Ok(()),
                Probe::Fail(reason) => return Err(reason),
                Probe::Retry { reason, wait } => {
                    if attempt >= self.options.max_retries {
                        return Err(if attempt == 0 {
                            reason
                        } else {
                            format!("{reason} (after {attempt} retries)")
                        });
                    }
                    let backoff = self.options.retry_base * 2u32.saturating_pow(attempt);
                    let delay = wait.unwrap_or(backoff).min(self.options.max_retry_wait);
                    tokio::time::sleep(delay).await;
                    attempt += 1;
                },
            }
        }
    }

    fn host_semaphore(&self, host: &str) -> Arc<Semaphore> {
        let mut hosts = self.hosts.lock().unwrap_or_else(|e| e.into_inner());
        hosts
            .entry(host.to_ascii_lowercase())
            .or_insert_with(|| Arc::new(Semaphore::new(self.options.per_host.max(1))))
            .clone()
    }

    fn accepted(&self, status: StatusCode) -> bool {
        status.is_success() || self.options.accept.contains(&status.as_u16())
    }

    /// HEAD, then GET unless HEAD succeeded or was rate limited.
    async fn probe(&self, url: &Url) -> Probe {
        match self.client.request(Method::HEAD, url.clone()).send().await {
            Ok(resp) if self.accepted(resp.status()) => return Probe::Ok,
            Ok(resp) if resp.status() == StatusCode::TOO_MANY_REQUESTS => {
                return Probe::Retry {
                    reason: status_reason(resp.status()),
                    wait: retry_after(resp.headers()),
                };
            },
            // Anything else: many servers mishandle HEAD, so ask again with GET.
            Ok(_) | Err(_) => {},
        }

        match self.client.request(Method::GET, url.clone()).send().await {
            Ok(resp) => {
                let status = resp.status();
                if self.accepted(status) {
                    Probe::Ok
                } else if is_transient(status) {
                    Probe::Retry {
                        reason: status_reason(status),
                        wait: retry_after(resp.headers()),
                    }
                } else {
                    Probe::Fail(status_reason(status))
                }
            },
            Err(e) if e.is_timeout() => Probe::Retry {
                reason: "Request timed out".to_string(),
                wait: None,
            },
            Err(e) if e.is_redirect() => Probe::Fail("Too many redirects".to_string()),
            Err(e) if e.is_connect() || e.is_request() => Probe::Retry {
                reason: format!("Connection failed: {}", root_cause(&e)),
                wait: None,
            },
            Err(e) => Probe::Fail(root_cause(&e)),
        }
    }
}

fn is_transient(status: StatusCode) -> bool {
    matches!(status.as_u16(), 408 | 429 | 500 | 502 | 503 | 504)
}

fn status_reason(status: StatusCode) -> String {
    match status.canonical_reason() {
        Some(reason) => format!("HTTP {} {reason}", status.as_u16()),
        None => format!("HTTP {}", status.as_u16()),
    }
}

/// Parse `Retry-After` given in seconds (HTTP-date values are ignored and
/// fall back to exponential backoff).
fn retry_after(headers: &HeaderMap) -> Option<Duration> {
    headers
        .get(RETRY_AFTER)?
        .to_str()
        .ok()?
        .trim()
        .parse::<u64>()
        .ok()
        .map(Duration::from_secs)
}

/// The innermost error message, which is what users actually need
/// ("dns error: ...", "certificate expired", ...).
fn root_cause(e: &(dyn std::error::Error + 'static)) -> String {
    let mut current = e;
    while let Some(source) = current.source() {
        current = source;
    }
    current.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn retry_after_parsing() {
        let mut headers = HeaderMap::new();
        assert_eq!(retry_after(&headers), None);
        headers.insert(RETRY_AFTER, "3".parse().unwrap());
        assert_eq!(retry_after(&headers), Some(Duration::from_secs(3)));
        headers.insert(
            RETRY_AFTER,
            "Wed, 21 Oct 2015 07:28:00 GMT".parse().unwrap(),
        );
        assert_eq!(retry_after(&headers), None);
    }

    #[test]
    fn status_text() {
        assert_eq!(status_reason(StatusCode::NOT_FOUND), "HTTP 404 Not Found");
        assert!(is_transient(StatusCode::SERVICE_UNAVAILABLE));
        assert!(!is_transient(StatusCode::NOT_FOUND));
    }
}

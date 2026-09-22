//! GitHub GraphQL and REST client with retry and rate-limit handling.
//!
//! Every request goes through a single retry loop. Each HTTP response is
//! classified by the pure [`classify_response`] function into "done",
//! "retry after N seconds" or "fail", which keeps the policy unit-testable:
//!
//! - Primary and secondary rate limits (HTTP 403/429 with rate-limit headers,
//!   or GraphQL `RATE_LIMITED` errors) wait for the advertised reset, up to
//!   [`MAX_RATE_LIMIT_WAIT_SECS`]; longer waits fail fast with
//!   [`BoardError::RateLimit`].
//! - 5xx responses and transient GraphQL errors ("Something went wrong",
//!   timeouts) are retried with exponential backoff, but only for idempotent
//!   requests (queries). Mutations are never replayed after the server may
//!   have processed them, so a claim comment is never posted twice.
//! - Permanent errors (401, other 4xx, `NOT_FOUND`, validation errors) fail
//!   immediately instead of burning retries.

use reqwest::{Client, RequestBuilder, header};
use serde_json::{Value, json};
use std::time::Duration;
use tokio::time::sleep;
use tracing::{debug, warn};

use crate::error::{BoardError, Result};

/// Default GitHub GraphQL endpoint (overridable via `GITHUB_GRAPHQL_URL`).
const DEFAULT_GRAPHQL_URL: &str = "https://api.github.com/graphql";

/// Default GitHub REST base URL (overridable via `GITHUB_API_URL`).
const DEFAULT_REST_URL: &str = "https://api.github.com";

/// Maximum attempts per request (first try included).
const MAX_ATTEMPTS: u32 = 5;

/// Initial backoff for transient failures.
const INITIAL_BACKOFF_SECS: u64 = 1;

/// Maximum backoff for transient failures.
const MAX_BACKOFF_SECS: u64 = 60;

/// Longest rate-limit reset we are willing to sleep for before giving up.
pub const MAX_RATE_LIMIT_WAIT_SECS: u64 = 300;

/// Fallback wait when a rate limit is reported without a usable reset hint.
const DEFAULT_RATE_LIMIT_WAIT_SECS: u64 = 60;

/// Default total request timeout in seconds.
const DEFAULT_HTTP_TIMEOUT_SECS: u64 = 30;

/// Connection-establishment timeout in seconds (fail fast on a dead host).
const CONNECT_TIMEOUT_SECS: u64 = 10;

/// Env var overriding the total request timeout.
const HTTP_TIMEOUT_ENV: &str = "BOARD_MANAGER_HTTP_TIMEOUT_SECS";

/// Rate-limit related response headers.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct RateLimitHeaders {
    /// `retry-after` (seconds).
    pub retry_after: Option<u64>,
    /// `x-ratelimit-remaining`.
    pub remaining: Option<u64>,
    /// `x-ratelimit-reset` (unix epoch seconds).
    pub reset: Option<i64>,
}

impl RateLimitHeaders {
    fn from_headers(headers: &header::HeaderMap) -> Self {
        let num = |name: &str| {
            headers
                .get(name)
                .and_then(|v| v.to_str().ok())
                .and_then(|v| v.trim().parse::<i64>().ok())
        };
        Self {
            retry_after: num("retry-after").and_then(|v| u64::try_from(v).ok()),
            remaining: num("x-ratelimit-remaining").and_then(|v| u64::try_from(v).ok()),
            reset: num("x-ratelimit-reset"),
        }
    }

    /// Seconds to wait before retrying, if the headers indicate a rate limit.
    pub fn wait_secs(&self, now_epoch: i64) -> Option<u64> {
        if let Some(secs) = self.retry_after {
            return Some(secs);
        }
        if self.remaining == Some(0) {
            let wait = self
                .reset
                .map(|reset| u64::try_from(reset - now_epoch).unwrap_or(0) + 1)
                .unwrap_or(DEFAULT_RATE_LIMIT_WAIT_SECS);
            return Some(wait);
        }
        None
    }
}

/// Kind of request being classified.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RequestKind {
    /// GraphQL query (idempotent, safe to replay).
    Query,
    /// GraphQL mutation (not safe to replay once the server saw it).
    Mutation,
    /// REST GET (idempotent).
    RestGet,
}

impl RequestKind {
    fn idempotent(self) -> bool {
        !matches!(self, RequestKind::Mutation)
    }

    fn is_graphql(self) -> bool {
        !matches!(self, RequestKind::RestGet)
    }
}

/// Result of classifying a single HTTP response.
#[derive(Debug)]
pub enum Outcome {
    /// Request succeeded; carries the GraphQL `data` or the REST body.
    Done(Value),
    /// Retry after waiting; `rate_limited` retries do not grow the backoff.
    Retry {
        wait_secs: Option<u64>,
        rate_limited: bool,
        reason: String,
    },
    /// Permanent failure.
    Fail(BoardError),
}

/// Classify an HTTP response. Pure function so the retry policy is testable.
pub fn classify_response(
    kind: RequestKind,
    status: u16,
    rate: &RateLimitHeaders,
    body: &str,
    now_epoch: i64,
) -> Outcome {
    let snippet = || truncate(body, 300);

    if status == 401 {
        return Outcome::Fail(BoardError::Auth(
            "401 Unauthorized - check GITHUB_PROJECTS_TOKEN / GITHUB_TOKEN".to_string(),
        ));
    }

    if status == 403 || status == 429 {
        let body_lower = body.to_lowercase();
        let wait = rate.wait_secs(now_epoch).or_else(|| {
            (status == 429 || body_lower.contains("rate limit"))
                .then_some(DEFAULT_RATE_LIMIT_WAIT_SECS)
        });
        return match wait {
            Some(w) => Outcome::Retry {
                wait_secs: Some(w),
                rate_limited: true,
                reason: format!("HTTP {status} rate limited"),
            },
            None => Outcome::Fail(BoardError::Auth(format!(
                "403 Forbidden - token lacks permission ({})",
                snippet()
            ))),
        };
    }

    if status >= 500 {
        let reason = format!("HTTP {status}: {}", snippet());
        return if kind.idempotent() {
            Outcome::Retry {
                wait_secs: None,
                rate_limited: false,
                reason,
            }
        } else {
            Outcome::Fail(BoardError::Api {
                status,
                message: format!("{} (mutation not retried)", snippet()),
            })
        };
    }

    if !(200..300).contains(&status) {
        return Outcome::Fail(BoardError::Api {
            status,
            message: snippet(),
        });
    }

    let parsed: Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(e) => return Outcome::Fail(BoardError::Json(e)),
    };

    if !kind.is_graphql() {
        return Outcome::Done(parsed);
    }

    classify_graphql_body(kind, parsed, rate, now_epoch)
}

/// Classify a successfully transported GraphQL body.
fn classify_graphql_body(
    kind: RequestKind,
    mut body: Value,
    rate: &RateLimitHeaders,
    now_epoch: i64,
) -> Outcome {
    let errors = parse_graphql_errors(&body);
    let data = body
        .get_mut("data")
        .map(Value::take)
        .filter(|d| !d.is_null());

    if errors.is_empty() {
        return match data {
            Some(d) => Outcome::Done(d),
            None => Outcome::Fail(BoardError::GraphQL("response contained no data".into())),
        };
    }

    let message = join_messages(&errors);

    if errors.iter().any(GraphQLError::is_rate_limit) {
        let wait = rate
            .wait_secs(now_epoch)
            .or_else(|| errors.iter().find_map(GraphQLError::retry_hint_secs))
            .unwrap_or(DEFAULT_RATE_LIMIT_WAIT_SECS);
        return Outcome::Retry {
            wait_secs: Some(wait),
            rate_limited: true,
            reason: message,
        };
    }

    // Mutations must be fully successful; partial data is a failure.
    if kind == RequestKind::Mutation {
        return Outcome::Fail(BoardError::GraphQL(message));
    }

    match data {
        // Queries may legitimately return partial data (e.g. user/org lookup
        // where one branch does not resolve). Callers inspect the data.
        Some(d) => {
            debug!("GraphQL query returned partial errors: {}", message);
            Outcome::Done(d)
        },
        None if errors.iter().any(GraphQLError::is_transient) => Outcome::Retry {
            wait_secs: None,
            rate_limited: false,
            reason: message,
        },
        None => Outcome::Fail(BoardError::GraphQL(message)),
    }
}

/// A single GraphQL error entry.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GraphQLError {
    pub message: String,
    /// GitHub's `type` extension (e.g. `NOT_FOUND`, `RATE_LIMITED`).
    pub error_type: Option<String>,
}

impl GraphQLError {
    fn is_rate_limit(&self) -> bool {
        self.error_type.as_deref() == Some("RATE_LIMITED")
            || self.message.to_lowercase().contains("rate limit")
    }

    fn is_transient(&self) -> bool {
        let msg = self.message.to_lowercase();
        self.error_type.as_deref() == Some("SERVICE_UNAVAILABLE")
            || msg.contains("something went wrong")
            || msg.contains("timeout")
            || msg.contains("timed out")
            || msg.contains("try again")
    }

    /// Parse hints like "try again in 30 seconds".
    fn retry_hint_secs(&self) -> Option<u64> {
        let msg = self.message.to_lowercase();
        let rest = &msg[msg.find("try again in ")? + "try again in ".len()..];
        let end = rest
            .find(|c: char| !c.is_ascii_digit())
            .unwrap_or(rest.len());
        rest[..end].parse().ok()
    }
}

/// Extract the `errors` array from a GraphQL response body.
pub fn parse_graphql_errors(body: &Value) -> Vec<GraphQLError> {
    body.get("errors")
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .map(|e| GraphQLError {
                    message: e
                        .get("message")
                        .and_then(Value::as_str)
                        .unwrap_or("unknown GraphQL error")
                        .to_string(),
                    error_type: e.get("type").and_then(Value::as_str).map(String::from),
                })
                .collect()
        })
        .unwrap_or_default()
}

fn join_messages(errors: &[GraphQLError]) -> String {
    errors
        .iter()
        .map(|e| match &e.error_type {
            Some(t) => format!("{} ({})", e.message, t),
            None => e.message.clone(),
        })
        .collect::<Vec<_>>()
        .join("; ")
}

/// Truncate a string to at most `max` bytes on a char boundary.
pub fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        return s.to_string();
    }
    let mut end = max;
    while !s.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}...", &s[..end])
}

/// GitHub API client (GraphQL + REST).
pub struct GraphQLClient {
    client: Client,
    token: String,
    graphql_url: String,
    rest_url: String,
}

impl GraphQLClient {
    /// Create a new client. Honors `GITHUB_GRAPHQL_URL` / `GITHUB_API_URL`
    /// (set automatically by GitHub Actions, including on GHES).
    pub fn new(token: String) -> Result<Self> {
        let timeout_secs = std::env::var(HTTP_TIMEOUT_ENV)
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .filter(|&s| s > 0)
            .unwrap_or(DEFAULT_HTTP_TIMEOUT_SECS);

        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .connect_timeout(Duration::from_secs(CONNECT_TIMEOUT_SECS))
            .user_agent(concat!("board-manager/", env!("CARGO_PKG_VERSION")))
            .build()?;

        let env_url = |name: &str, default: &str| {
            std::env::var(name)
                .ok()
                .filter(|v| !v.trim().is_empty())
                .unwrap_or_else(|| default.to_string())
                .trim_end_matches('/')
                .to_string()
        };

        Ok(Self {
            client,
            token,
            graphql_url: env_url("GITHUB_GRAPHQL_URL", DEFAULT_GRAPHQL_URL),
            rest_url: env_url("GITHUB_API_URL", DEFAULT_REST_URL),
        })
    }

    /// Run a GraphQL query and return its `data`. Partial errors are logged
    /// and tolerated; callers must handle missing branches.
    pub async fn query(&self, query: &str, variables: Value) -> Result<Value> {
        self.graphql(RequestKind::Query, query, variables).await
    }

    /// Run a GraphQL mutation and return its `data`. Any error fails.
    pub async fn mutate(&self, mutation: &str, variables: Value) -> Result<Value> {
        self.graphql(RequestKind::Mutation, mutation, variables)
            .await
    }

    async fn graphql(&self, kind: RequestKind, query: &str, variables: Value) -> Result<Value> {
        let payload = json!({ "query": query, "variables": variables });
        self.send_with_retry(kind, || {
            self.client
                .post(&self.graphql_url)
                .bearer_auth(&self.token)
                .json(&payload)
        })
        .await
    }

    /// Execute a REST GET request (path relative to the API root).
    pub async fn rest_get(&self, path: &str, params: &[(&str, &str)]) -> Result<Value> {
        let url = format!("{}{}", self.rest_url, path);
        self.send_with_retry(RequestKind::RestGet, || {
            self.client
                .get(&url)
                .bearer_auth(&self.token)
                .header(header::ACCEPT, "application/vnd.github+json")
                .query(params)
        })
        .await
    }

    async fn send_with_retry<F>(&self, kind: RequestKind, build: F) -> Result<Value>
    where
        F: Fn() -> RequestBuilder,
    {
        let mut backoff = INITIAL_BACKOFF_SECS;
        let mut last_reason = String::new();

        for attempt in 1..=MAX_ATTEMPTS {
            let outcome = match build().send().await {
                Ok(resp) => {
                    let status = resp.status().as_u16();
                    let rate = RateLimitHeaders::from_headers(resp.headers());
                    let body = resp.text().await?;
                    classify_response(kind, status, &rate, &body, chrono::Utc::now().timestamp())
                },
                Err(e) => classify_transport_error(kind, e),
            };

            match outcome {
                Outcome::Done(v) => return Ok(v),
                Outcome::Fail(e) => return Err(e),
                Outcome::Retry {
                    wait_secs,
                    rate_limited,
                    reason,
                } => {
                    if attempt == MAX_ATTEMPTS {
                        if rate_limited {
                            return Err(BoardError::RateLimit(wait_secs.unwrap_or(0)));
                        }
                        last_reason = reason;
                        break;
                    }
                    let wait = wait_secs.unwrap_or(backoff);
                    if rate_limited && wait > MAX_RATE_LIMIT_WAIT_SECS {
                        return Err(BoardError::RateLimit(wait));
                    }
                    warn!(
                        "GitHub request failed (attempt {}/{}): {}; retrying in {}s",
                        attempt, MAX_ATTEMPTS, reason, wait
                    );
                    sleep(Duration::from_secs(wait)).await;
                    if !rate_limited {
                        backoff = (backoff * 2).min(MAX_BACKOFF_SECS);
                    }
                    last_reason = reason;
                },
            }
        }

        Err(BoardError::GraphQL(format!(
            "request failed after {} attempts: {}",
            MAX_ATTEMPTS, last_reason
        )))
    }
}

/// Decide whether a transport-level error is retryable.
fn classify_transport_error(kind: RequestKind, e: reqwest::Error) -> Outcome {
    // A connection that never got established cannot have been processed,
    // so it is safe to retry even for mutations.
    if e.is_connect() || (kind.idempotent() && (e.is_timeout() || e.is_request())) {
        return Outcome::Retry {
            wait_secs: None,
            rate_limited: false,
            reason: e.to_string(),
        };
    }
    Outcome::Fail(BoardError::Http(e))
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOW: i64 = 1_700_000_000;

    fn none() -> RateLimitHeaders {
        RateLimitHeaders::default()
    }

    #[test]
    fn client_creation() {
        assert!(GraphQLClient::new("test_token".to_string()).is_ok());
    }

    #[test]
    fn success_returns_data() {
        let out = classify_response(RequestKind::Query, 200, &none(), r#"{"data":{"x":1}}"#, NOW);
        assert!(matches!(out, Outcome::Done(v) if v["x"] == 1));
    }

    #[test]
    fn unauthorized_fails_fast() {
        let out = classify_response(RequestKind::Query, 401, &none(), "", NOW);
        assert!(matches!(out, Outcome::Fail(BoardError::Auth(_))));
    }

    #[test]
    fn forbidden_without_rate_limit_is_auth_error() {
        let out = classify_response(
            RequestKind::Query,
            403,
            &none(),
            r#"{"message":"Resource not accessible"}"#,
            NOW,
        );
        assert!(matches!(out, Outcome::Fail(BoardError::Auth(_))));
    }

    #[test]
    fn secondary_rate_limit_uses_retry_after() {
        let rate = RateLimitHeaders {
            retry_after: Some(42),
            ..none()
        };
        let out = classify_response(RequestKind::Mutation, 403, &rate, "", NOW);
        assert!(matches!(
            out,
            Outcome::Retry {
                wait_secs: Some(42),
                rate_limited: true,
                ..
            }
        ));
    }

    #[test]
    fn primary_rate_limit_waits_until_reset() {
        let rate = RateLimitHeaders {
            remaining: Some(0),
            reset: Some(NOW + 10),
            ..none()
        };
        let out = classify_response(RequestKind::Query, 403, &rate, "", NOW);
        assert!(matches!(
            out,
            Outcome::Retry {
                wait_secs: Some(11),
                ..
            }
        ));
    }

    #[test]
    fn server_error_retried_only_for_idempotent() {
        let q = classify_response(RequestKind::Query, 502, &none(), "bad gateway", NOW);
        assert!(matches!(
            q,
            Outcome::Retry {
                rate_limited: false,
                ..
            }
        ));
        let m = classify_response(RequestKind::Mutation, 502, &none(), "bad gateway", NOW);
        assert!(matches!(
            m,
            Outcome::Fail(BoardError::Api { status: 502, .. })
        ));
    }

    #[test]
    fn client_error_not_retried() {
        let out = classify_response(RequestKind::RestGet, 422, &none(), "{}", NOW);
        assert!(matches!(
            out,
            Outcome::Fail(BoardError::Api { status: 422, .. })
        ));
    }

    #[test]
    fn graphql_rate_limited_error_retries() {
        let body = r#"{"errors":[{"type":"RATE_LIMITED","message":"API rate limit exceeded"}]}"#;
        let out = classify_response(RequestKind::Query, 200, &none(), body, NOW);
        assert!(matches!(
            out,
            Outcome::Retry {
                rate_limited: true,
                ..
            }
        ));
    }

    #[test]
    fn graphql_retry_hint_parsed() {
        let body = r#"{"errors":[{"message":"rate limit hit, try again in 17 seconds"}]}"#;
        let out = classify_response(RequestKind::Query, 200, &none(), body, NOW);
        assert!(matches!(
            out,
            Outcome::Retry {
                wait_secs: Some(17),
                ..
            }
        ));
    }

    #[test]
    fn graphql_not_found_fails_fast() {
        let body = r#"{"data":null,"errors":[{"type":"NOT_FOUND","message":"Could not resolve"}]}"#;
        let out = classify_response(RequestKind::Query, 200, &none(), body, NOW);
        assert!(matches!(out, Outcome::Fail(BoardError::GraphQL(m)) if m.contains("NOT_FOUND")));
    }

    #[test]
    fn graphql_transient_error_retries() {
        let body = r#"{"errors":[{"message":"Something went wrong while executing your query."}]}"#;
        let out = classify_response(RequestKind::Query, 200, &none(), body, NOW);
        assert!(matches!(out, Outcome::Retry { .. }));
    }

    #[test]
    fn query_partial_data_is_ok() {
        let body = r#"{"data":{"user":null,"organization":{"id":1}},
            "errors":[{"type":"NOT_FOUND","message":"Could not resolve to a User"}]}"#;
        let out = classify_response(RequestKind::Query, 200, &none(), body, NOW);
        assert!(matches!(out, Outcome::Done(v) if v["organization"]["id"] == 1));
    }

    #[test]
    fn mutation_partial_data_fails() {
        let body = r#"{"data":{"updateProjectV2ItemFieldValue":null},
            "errors":[{"message":"Field value invalid"}]}"#;
        let out = classify_response(RequestKind::Mutation, 200, &none(), body, NOW);
        assert!(matches!(out, Outcome::Fail(BoardError::GraphQL(_))));
    }

    #[test]
    fn invalid_json_fails() {
        let out = classify_response(RequestKind::Query, 200, &none(), "<html>", NOW);
        assert!(matches!(out, Outcome::Fail(BoardError::Json(_))));
    }

    #[test]
    fn truncate_respects_char_boundaries() {
        let s = "aaaa\u{00e9}\u{00e9}\u{00e9}";
        let t = truncate(s, 5);
        assert!(t.starts_with("aaaa"));
        assert!(t.ends_with("..."));
        assert_eq!(truncate("short", 10), "short");
    }
}

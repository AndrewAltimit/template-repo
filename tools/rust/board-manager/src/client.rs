//! GraphQL and REST HTTP client with retry logic.

use reqwest::{Client, header};
use serde_json::{Value, json};
use std::time::Duration;
use tokio::time::sleep;
use tracing::{debug, warn};

use crate::error::{BoardError, Result};
use crate::models::GraphQLResponse;

/// GitHub GraphQL API URL.
pub const GITHUB_API_URL: &str = "https://api.github.com/graphql";

/// GitHub REST API base URL.
pub const GITHUB_REST_API_URL: &str = "https://api.github.com";

/// Maximum retries for transient errors.
const MAX_RETRIES: u32 = 3;

/// Initial backoff duration.
const INITIAL_BACKOFF_SECS: u64 = 1;

/// Maximum backoff duration.
const MAX_BACKOFF_SECS: u64 = 60;

/// GraphQL client for GitHub API.
pub struct GraphQLClient {
    client: Client,
    token: String,
}

impl GraphQLClient {
    /// Create a new GraphQL client.
    pub fn new(token: String) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(BoardError::Http)?;

        Ok(Self { client, token })
    }

    /// Execute a GraphQL query with retry logic.
    pub async fn execute(&self, query: &str, variables: Option<Value>) -> Result<GraphQLResponse> {
        let mut backoff = INITIAL_BACKOFF_SECS;

        for attempt in 0..MAX_RETRIES {
            match self.execute_once(query, variables.clone()).await {
                Ok(response) => {
                    // Check for rate limit errors
                    if self.is_rate_limited(&response) {
                        return Err(BoardError::RateLimit(60)); // Default retry after
                    }

                    // Check for GraphQL errors without data
                    if !response.errors.is_empty() && response.data.is_none() {
                        let error_msg = response.get_error_message();
                        if attempt < MAX_RETRIES - 1 {
                            warn!(
                                "GraphQL error (attempt {}): {}, retrying in {}s",
                                attempt + 1,
                                error_msg,
                                backoff
                            );
                            sleep(Duration::from_secs(backoff)).await;
                            backoff = (backoff * 2).min(MAX_BACKOFF_SECS);
                            continue;
                        }
                        return Err(BoardError::GraphQL(error_msg));
                    }

                    return Ok(response);
                }
                Err(e) => {
                    // Don't retry client errors (4xx)
                    if let BoardError::Auth(_) = e {
                        return Err(e);
                    }

                    if attempt < MAX_RETRIES - 1 {
                        warn!(
                            "Request failed (attempt {}): {}, retrying in {}s",
                            attempt + 1,
                            e,
                            backoff
                        );
                        sleep(Duration::from_secs(backoff)).await;
                        backoff = (backoff * 2).min(MAX_BACKOFF_SECS);
                    } else {
                        return Err(e);
                    }
                }
            }
        }

        Err(BoardError::GraphQL(format!(
            "Operation failed after {} retries",
            MAX_RETRIES
        )))
    }

    /// Execute a single GraphQL request.
    async fn execute_once(&self, query: &str, variables: Option<Value>) -> Result<GraphQLResponse> {
        let mut payload = json!({ "query": query });
        if let Some(vars) = variables {
            payload["variables"] = vars;
        }

        debug!("Executing GraphQL query");

        let response = self
            .client
            .post(GITHUB_API_URL)
            .header(header::AUTHORIZATION, format!("Bearer {}", self.token))
            .header(header::CONTENT_TYPE, "application/json")
            .header(header::USER_AGENT, "board-manager/0.1.0")
            .json(&payload)
            .send()
            .await?;

        let status = response.status();

        if status == 401 {
            return Err(BoardError::Auth(
                "Authentication failed - check GITHUB_TOKEN".to_string(),
            ));
        }

        if status == 403 {
            return Err(BoardError::Auth(
                "Forbidden - check permissions".to_string(),
            ));
        }

        let body: Value = response.json().await?;

        let data = body.get("data").cloned();
        let errors = body
            .get("errors")
            .and_then(|e| e.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|e| {
                        Some(crate::models::GraphQLError {
                            message: e.get("message")?.as_str()?.to_string(),
                            path: e
                                .get("path")
                                .and_then(|p| p.as_array())
                                .map(|arr| {
                                    arr.iter()
                                        .filter_map(|v| v.as_str().map(|s| s.to_string()))
                                        .collect()
                                })
                                .unwrap_or_default(),
                            locations: e
                                .get("locations")
                                .and_then(|l| l.as_array())
                                .cloned()
                                .unwrap_or_default(),
                        })
                    })
                    .collect()
            })
            .unwrap_or_default();

        Ok(GraphQLResponse { data, errors })
    }

    /// Check if response indicates rate limiting.
    fn is_rate_limited(&self, response: &GraphQLResponse) -> bool {
        response
            .errors
            .iter()
            .any(|e| e.message.to_lowercase().contains("rate limit"))
    }

    /// Execute a REST API GET request with retry logic.
    pub async fn rest_get(&self, path: &str, params: Option<&[(&str, &str)]>) -> Result<Value> {
        let mut backoff = INITIAL_BACKOFF_SECS;

        for attempt in 0..MAX_RETRIES {
            match self.rest_get_once(path, params).await {
                Ok(response) => return Ok(response),
                Err(e) => {
                    // Don't retry client errors (4xx)
                    if let BoardError::Auth(_) = e {
                        return Err(e);
                    }

                    if attempt < MAX_RETRIES - 1 {
                        warn!(
                            "REST request failed (attempt {}): {}, retrying in {}s",
                            attempt + 1,
                            e,
                            backoff
                        );
                        sleep(Duration::from_secs(backoff)).await;
                        backoff = (backoff * 2).min(MAX_BACKOFF_SECS);
                    } else {
                        return Err(e);
                    }
                }
            }
        }

        Err(BoardError::GraphQL(format!(
            "REST operation failed after {} retries",
            MAX_RETRIES
        )))
    }

    /// Execute a single REST GET request.
    async fn rest_get_once(&self, path: &str, params: Option<&[(&str, &str)]>) -> Result<Value> {
        let url = format!("{}{}", GITHUB_REST_API_URL, path);
        debug!("Executing REST GET: {}", url);

        let mut request = self
            .client
            .get(&url)
            .header(header::AUTHORIZATION, format!("Bearer {}", self.token))
            .header(header::ACCEPT, "application/vnd.github.v3+json")
            .header(header::USER_AGENT, "board-manager/0.1.0");

        if let Some(query_params) = params {
            request = request.query(query_params);
        }

        let response = request.send().await?;
        let status = response.status();

        if status == 401 {
            return Err(BoardError::Auth(
                "Authentication failed - check GITHUB_TOKEN".to_string(),
            ));
        }

        if status == 403 {
            return Err(BoardError::Auth(
                "Forbidden - check permissions".to_string(),
            ));
        }

        if !status.is_success() {
            let error_body = response.text().await.unwrap_or_default();
            return Err(BoardError::GraphQL(format!(
                "REST API error: {} - {}",
                status, error_body
            )));
        }

        let body: Value = response.json().await?;
        Ok(body)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_graphql_client_creation() {
        // This test just verifies the client can be created
        let client = GraphQLClient::new("test_token".to_string());
        assert!(client.is_ok());
    }
}

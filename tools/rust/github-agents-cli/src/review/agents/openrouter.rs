//! OpenRouter API agent for PR reviews.
//!
//! Calls the OpenRouter API directly (no CLI dependency) for code reviews.
//! Uses OPENROUTER_API_KEY for authentication.

use std::time::Duration;

use async_trait::async_trait;

use super::ReviewAgent;
use crate::error::{Error, Result};
use crate::utils::truncate_str;

/// Default model for OpenRouter reviews
const DEFAULT_MODEL: &str = "qwen/qwen3.7-max";

/// OpenRouter API endpoint
const OPENROUTER_API_URL: &str = "https://openrouter.ai/api/v1/chat/completions";

/// Overall request timeout (large reviews can take several minutes).
const REQUEST_TIMEOUT: Duration = Duration::from_secs(600);

/// OpenRouter API agent for PR reviews
///
/// Calls the OpenRouter chat completions API directly, avoiding the need for
/// any CLI tool installation. Only requires OPENROUTER_API_KEY env var.
pub struct OpenRouterAgent {
    api_key: Option<String>,
    model: String,
    client: reqwest::Client,
}

impl OpenRouterAgent {
    /// Create a new OpenRouter agent
    pub fn new() -> Self {
        let api_key = std::env::var("OPENROUTER_API_KEY")
            .ok()
            .filter(|k| !k.trim().is_empty());
        if api_key.is_none() {
            tracing::debug!("OPENROUTER_API_KEY not set or empty");
        }

        let client = reqwest::Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .connect_timeout(Duration::from_secs(30))
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());

        Self {
            api_key,
            model: DEFAULT_MODEL.to_string(),
            client,
        }
    }

    /// Create with custom model
    pub fn with_model(model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!("Using OpenRouter model: {}", model);
        agent.model = model;
        agent
    }

    fn transient(detail: String) -> Error {
        Error::AgentExecutionFailed {
            name: "openrouter".to_string(),
            exit_code: 6,
            stdout: String::new(),
            stderr: format!("service unavailable (transient): {}", detail),
        }
    }

    /// Call the OpenRouter API
    async fn call_api(&self, prompt: &str) -> Result<String> {
        let api_key = self
            .api_key
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("OPENROUTER_API_KEY".to_string()))?;

        tracing::info!("Calling OpenRouter API with model: {}", self.model);

        let request_body = serde_json::json!({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.2
        });

        let response = self
            .client
            .post(OPENROUTER_API_URL)
            .bearer_auth(api_key)
            .header(
                "HTTP-Referer",
                "https://github.com/AndrewAltimit/template-repo",
            )
            .header("X-Title", "PR Review Agent")
            .json(&request_body)
            .send()
            .await
            .map_err(|e| {
                if e.is_connect() || e.is_timeout() {
                    Self::transient(e.to_string())
                } else {
                    Error::Config(format!("OpenRouter API request failed: {}", e))
                }
            })?;

        let status = response.status();
        let body = response
            .text()
            .await
            .map_err(|e| Self::transient(format!("failed to read response body: {}", e)))?;

        if !status.is_success() {
            let snippet = truncate_str(&body, 500);
            if matches!(status.as_u16(), 429 | 500 | 502 | 503 | 504) {
                return Err(Self::transient(format!("HTTP {} - {}", status, snippet)));
            }
            return Err(Error::Config(format!(
                "OpenRouter API returned HTTP {}: {}",
                status, snippet
            )));
        }

        extract_content(&body)
    }
}

/// Extract the assistant message from a chat-completions response body.
fn extract_content(body: &str) -> Result<String> {
    let json: serde_json::Value = serde_json::from_str(body)
        .map_err(|e| Error::Config(format!("Failed to parse OpenRouter response: {}", e)))?;

    if let Some(err) = json.get("error") {
        let message = err
            .get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("unknown error");
        return Err(Error::Config(format!("OpenRouter API error: {}", message)));
    }

    json.pointer("/choices/0/message/content")
        .and_then(|c| c.as_str())
        .filter(|c| !c.trim().is_empty())
        .map(str::to_string)
        .ok_or_else(|| {
            Error::Config(format!(
                "Unexpected OpenRouter response format: {}",
                truncate_str(body, 500)
            ))
        })
}

impl Default for OpenRouterAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for OpenRouterAgent {
    fn name(&self) -> &str {
        "openrouter"
    }

    fn model(&self) -> &str {
        &self.model
    }

    async fn is_available(&self) -> bool {
        self.api_key.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        self.call_api(prompt).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_without_api_key() {
        let agent = OpenRouterAgent::new();
        assert_eq!(agent.model, DEFAULT_MODEL);
    }

    #[test]
    fn test_with_model() {
        let agent = OpenRouterAgent::with_model("test/model".to_string());
        assert_eq!(agent.model, "test/model");
    }

    #[test]
    fn test_extract_content() {
        let ok = r#"{"choices":[{"message":{"content":"Looks good"}}]}"#;
        assert_eq!(extract_content(ok).unwrap(), "Looks good");

        let empty = r#"{"choices":[{"message":{"content":"  "}}]}"#;
        assert!(extract_content(empty).is_err());

        let err = r#"{"error":{"message":"bad key"}}"#;
        assert!(
            extract_content(err)
                .unwrap_err()
                .to_string()
                .contains("bad key")
        );

        assert!(extract_content("<html>").is_err());
    }
}

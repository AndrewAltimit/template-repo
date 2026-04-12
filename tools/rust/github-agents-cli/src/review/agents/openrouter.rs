//! OpenRouter API agent for PR reviews.
//!
//! Calls the OpenRouter API directly (no CLI dependency) for code reviews.
//! Uses OPENROUTER_API_KEY for authentication.

use async_trait::async_trait;

use super::ReviewAgent;
use crate::error::{Error, Result};

/// Default model for OpenRouter reviews
const DEFAULT_MODEL: &str = "qwen/qwen3.6-plus";

/// OpenRouter API endpoint
const OPENROUTER_API_URL: &str = "https://openrouter.ai/api/v1/chat/completions";

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
            .filter(|k| !k.is_empty());

        if api_key.is_some() {
            tracing::info!("OpenRouter API key found");
        } else {
            tracing::warn!("OPENROUTER_API_KEY not set or empty");
        }

        Self {
            api_key,
            model: DEFAULT_MODEL.to_string(),
            client: reqwest::Client::new(),
        }
    }

    /// Create with custom model
    pub fn with_model(model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!("Using OpenRouter model: {}", model);
        agent.model = model;
        agent
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
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.2
        });

        let response = tokio::time::timeout(
            std::time::Duration::from_secs(600), // 10 minute timeout
            self.client
                .post(OPENROUTER_API_URL)
                .header("Authorization", format!("Bearer {}", api_key))
                .header("Content-Type", "application/json")
                .header(
                    "HTTP-Referer",
                    "https://github.com/AndrewAltimit/template-repo",
                )
                .header("X-Title", "PR Review Agent")
                .json(&request_body)
                .send(),
        )
        .await
        .map_err(|_| Error::AgentExecutionFailed {
            name: "openrouter".to_string(),
            exit_code: 6,
            stdout: String::new(),
            stderr: "service unavailable (transient): OpenRouter API timed out after 10 minutes"
                .to_string(),
        })?
        .map_err(|e| {
            if e.is_connect() || e.is_timeout() {
                Error::AgentExecutionFailed {
                    name: "openrouter".to_string(),
                    exit_code: 6,
                    stdout: String::new(),
                    stderr: format!("service unavailable (transient): {}", e),
                }
            } else {
                Error::Config(format!("OpenRouter API request failed: {}", e))
            }
        })?;

        let status = response.status();
        let body = response
            .text()
            .await
            .map_err(|e| Error::Config(format!("Failed to read OpenRouter response: {}", e)))?;

        if !status.is_success() {
            // Check for transient errors
            if status.as_u16() == 429
                || status.as_u16() == 502
                || status.as_u16() == 503
                || status.as_u16() == 504
            {
                return Err(Error::AgentExecutionFailed {
                    name: "openrouter".to_string(),
                    exit_code: 6,
                    stdout: String::new(),
                    stderr: format!(
                        "service unavailable (transient): HTTP {} - {}",
                        status, body
                    ),
                });
            }
            return Err(Error::Config(format!(
                "OpenRouter API returned HTTP {}: {}",
                status, body
            )));
        }

        // Parse the response
        let json: serde_json::Value = serde_json::from_str(&body)
            .map_err(|e| Error::Config(format!("Failed to parse OpenRouter response: {}", e)))?;

        let content = json
            .get("choices")
            .and_then(|c| c.get(0))
            .and_then(|c| c.get("message"))
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_str())
            .ok_or_else(|| {
                let safe_end = body.floor_char_boundary(500);
                Error::Config(format!(
                    "Unexpected OpenRouter response format: {}",
                    &body[..safe_end]
                ))
            })?;

        Ok(content.to_string())
    }
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

    async fn condense(&self, review: &str, max_words: usize) -> Result<String> {
        let condense_prompt = format!(
            r#"Condense this code review to under {} words while keeping ALL actionable issues.

Rules:
- Keep ONLY actionable issues (bugs, security, required fixes)
- Remove generic praise and filler
- Remove duplicates
- Keep exactly ONE reaction image at the end
- Use bullet points

Review to condense:

{}
"#,
            max_words, review
        );

        self.call_api(&condense_prompt).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_without_api_key() {
        // Should not panic even without API key
        let agent = OpenRouterAgent::new();
        assert_eq!(agent.model, DEFAULT_MODEL);
    }

    #[test]
    fn test_with_model() {
        let agent = OpenRouterAgent::with_model("test/model".to_string());
        assert_eq!(agent.model, "test/model");
    }
}

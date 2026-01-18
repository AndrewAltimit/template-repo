//! Gemini API client for PR reviews.
//!
//! Uses the Gemini REST API directly for code reviews.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::time::Duration;

use super::ReviewAgent;
use crate::error::{Error, Result};

/// Default model for reviews
const DEFAULT_REVIEW_MODEL: &str = "gemini-2.0-flash";

/// Default model for condensation (faster)
const DEFAULT_CONDENSER_MODEL: &str = "gemini-2.0-flash";

/// API endpoint
const GEMINI_API_BASE: &str = "https://generativelanguage.googleapis.com/v1beta/models";

/// Maximum retries for rate limits
const MAX_RETRIES: usize = 5;

/// Gemini API request structure
#[derive(Debug, Serialize)]
struct GeminiRequest {
    contents: Vec<GeminiContent>,
    #[serde(rename = "generationConfig", skip_serializing_if = "Option::is_none")]
    generation_config: Option<GenerationConfig>,
}

#[derive(Debug, Serialize)]
struct GeminiContent {
    parts: Vec<GeminiPart>,
}

#[derive(Debug, Serialize)]
struct GeminiPart {
    text: String,
}

#[derive(Debug, Serialize)]
struct GenerationConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(rename = "maxOutputTokens", skip_serializing_if = "Option::is_none")]
    max_output_tokens: Option<u32>,
}

/// Gemini API response structure
#[derive(Debug, Deserialize)]
struct GeminiResponse {
    candidates: Option<Vec<GeminiCandidate>>,
    error: Option<GeminiError>,
}

#[derive(Debug, Deserialize)]
struct GeminiCandidate {
    content: GeminiResponseContent,
}

#[derive(Debug, Deserialize)]
struct GeminiResponseContent {
    parts: Vec<GeminiResponsePart>,
}

#[derive(Debug, Deserialize)]
struct GeminiResponsePart {
    text: String,
}

#[derive(Debug, Deserialize)]
struct GeminiError {
    message: String,
    code: Option<i32>,
}

/// Gemini agent for PR reviews
pub struct GeminiAgent {
    api_key: Option<String>,
    review_model: String,
    condenser_model: String,
    client: reqwest::Client,
}

impl GeminiAgent {
    /// Create a new Gemini agent
    pub fn new() -> Self {
        let api_key = std::env::var("GEMINI_API_KEY")
            .or_else(|_| std::env::var("GOOGLE_API_KEY"))
            .ok();

        Self {
            api_key,
            review_model: DEFAULT_REVIEW_MODEL.to_string(),
            condenser_model: DEFAULT_CONDENSER_MODEL.to_string(),
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(600))
                .build()
                .unwrap_or_default(),
        }
    }

    /// Create with custom models
    pub fn with_models(review_model: String, condenser_model: String) -> Self {
        let mut agent = Self::new();
        agent.review_model = review_model;
        agent.condenser_model = condenser_model;
        agent
    }

    /// Call the Gemini API
    async fn call_api(&self, model: &str, prompt: &str) -> Result<String> {
        let api_key = self
            .api_key
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("GEMINI_API_KEY or GOOGLE_API_KEY".to_string()))?;

        let url = format!(
            "{}/{}:generateContent?key={}",
            GEMINI_API_BASE, model, api_key
        );

        let request = GeminiRequest {
            contents: vec![GeminiContent {
                parts: vec![GeminiPart {
                    text: prompt.to_string(),
                }],
            }],
            generation_config: Some(GenerationConfig {
                temperature: Some(0.3),
                max_output_tokens: Some(8192),
            }),
        };

        let mut last_error = None;
        let mut retry_delay = Duration::from_secs(5);

        for attempt in 0..MAX_RETRIES {
            let response = self
                .client
                .post(&url)
                .json(&request)
                .send()
                .await
                .map_err(|e| Error::Http(e))?;

            let status = response.status();

            // Handle rate limits
            if status.as_u16() == 429 {
                if attempt < MAX_RETRIES - 1 {
                    tracing::warn!(
                        "Gemini rate limited (attempt {}), retrying in {:?}",
                        attempt + 1,
                        retry_delay
                    );
                    tokio::time::sleep(retry_delay).await;
                    retry_delay *= 2; // Exponential backoff
                    continue;
                }
            }

            let body = response.text().await.map_err(|e| Error::Http(e))?;

            if !status.is_success() {
                last_error = Some(Error::Config(format!(
                    "Gemini API error ({}): {}",
                    status, body
                )));

                // Retry on 5xx errors
                if status.is_server_error() && attempt < MAX_RETRIES - 1 {
                    tracing::warn!(
                        "Gemini server error (attempt {}), retrying in {:?}",
                        attempt + 1,
                        retry_delay
                    );
                    tokio::time::sleep(retry_delay).await;
                    retry_delay *= 2;
                    continue;
                }

                return Err(last_error.unwrap());
            }

            let gemini_response: GeminiResponse = serde_json::from_str(&body)
                .map_err(|e| Error::Config(format!("Failed to parse Gemini response: {}", e)))?;

            if let Some(error) = gemini_response.error {
                return Err(Error::Config(format!(
                    "Gemini API error: {}",
                    error.message
                )));
            }

            let text = gemini_response
                .candidates
                .and_then(|c| c.into_iter().next())
                .map(|c| {
                    c.content
                        .parts
                        .into_iter()
                        .map(|p| p.text)
                        .collect::<String>()
                })
                .unwrap_or_default();

            return Ok(text);
        }

        Err(last_error
            .unwrap_or_else(|| Error::Config("Gemini API failed after retries".to_string())))
    }
}

impl Default for GeminiAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for GeminiAgent {
    fn name(&self) -> &str {
        "gemini"
    }

    async fn is_available(&self) -> bool {
        self.api_key.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        self.call_api(&self.review_model, prompt).await
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

        self.call_api(&self.condenser_model, &condense_prompt).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gemini_agent_no_key() {
        // Clear env vars for test
        // SAFETY: This is a single-threaded test that doesn't rely on env vars being set elsewhere
        unsafe {
            std::env::remove_var("GEMINI_API_KEY");
            std::env::remove_var("GOOGLE_API_KEY");
        }

        let agent = GeminiAgent::new();
        assert!(agent.api_key.is_none());
    }
}

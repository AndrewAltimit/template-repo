//! OpenCode integration via OpenRouter API.

use chrono::Utc;
use reqwest::Client;
use std::time::{Duration, Instant};
use tracing::{debug, info};

use crate::types::{
    ChatCompletionRequest, ChatCompletionResponse, ChatMessage, ConsultMode, ConsultResult,
    HistoryEntry, OpenCodeConfig, OpenCodeStats,
};

const OPENROUTER_API_URL: &str = "https://openrouter.ai/api/v1/chat/completions";

/// OpenCode integration via OpenRouter API
pub struct OpenCodeIntegration {
    config: OpenCodeConfig,
    client: Client,
    history: Vec<HistoryEntry>,
    stats: OpenCodeStats,
    consultation_counter: u64,
}

impl OpenCodeIntegration {
    /// Create a new OpenCode integration
    pub fn new(config: OpenCodeConfig) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.timeout_secs))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            config,
            client,
            history: Vec::new(),
            stats: OpenCodeStats::default(),
            consultation_counter: 0,
        }
    }

    /// Consult OpenCode for code assistance
    pub async fn consult(&mut self, query: &str, mode: ConsultMode, force: bool) -> ConsultResult {
        self.consultation_counter += 1;
        let consultation_id = format!(
            "opencode_{}_{}_{}",
            Utc::now().timestamp(),
            self.consultation_counter,
            self.stats.consultations
        );

        self.stats.consultations += 1;
        self.stats.last_consultation = Some(Utc::now());

        // Check if enabled
        if !self.config.enabled && !force {
            return ConsultResult::disabled(consultation_id);
        }

        // Check if API key is configured
        if self.config.api_key.is_empty() {
            return ConsultResult::error(
                "OPENROUTER_API_KEY not configured. Please set it in environment variables.",
                consultation_id,
            );
        }

        let start = Instant::now();

        // Build messages with history
        let messages = self.build_messages(query, mode);

        // Make API request
        let result = self.call_openrouter(&messages).await;

        match result {
            Ok(response) => {
                let execution_time = start.elapsed().as_secs_f64();
                self.stats.completed += 1;
                self.stats.total_execution_time += execution_time;

                // Add to history
                if self.config.include_history {
                    self.add_to_history(query, &response);
                }

                if self.config.log_consultations {
                    info!(
                        "OpenCode consultation completed: id={}, time={:.2}s",
                        consultation_id, execution_time
                    );
                }

                ConsultResult::success(response, execution_time, consultation_id)
            }
            Err(e) => {
                self.stats.errors += 1;

                if e.contains("timed out") || e.contains("timeout") {
                    ConsultResult::timeout(self.config.timeout_secs, consultation_id)
                } else {
                    ConsultResult::error(e, consultation_id)
                }
            }
        }
    }

    /// Build messages for the API request
    fn build_messages(&self, query: &str, mode: ConsultMode) -> Vec<ChatMessage> {
        let mut messages = Vec::new();

        // System message with mode-specific prompt
        messages.push(ChatMessage {
            role: "system".to_string(),
            content: mode.system_prompt().to_string(),
        });

        // Add conversation history if enabled
        if self.config.include_history && !self.history.is_empty() {
            let start = self.history.len().saturating_sub(3);
            for entry in &self.history[start..] {
                messages.push(ChatMessage {
                    role: "user".to_string(),
                    content: self.truncate_text(&entry.query, 500),
                });
                messages.push(ChatMessage {
                    role: "assistant".to_string(),
                    content: self.truncate_text(&entry.response, 1000),
                });
            }
        }

        // User query
        let truncated_query = self.truncate_text(query, self.config.max_prompt_length);
        messages.push(ChatMessage {
            role: "user".to_string(),
            content: truncated_query,
        });

        messages
    }

    /// Call OpenRouter API
    async fn call_openrouter(&self, messages: &[ChatMessage]) -> Result<String, String> {
        let request = ChatCompletionRequest {
            model: self.config.model.clone(),
            messages: messages
                .iter()
                .map(|m| ChatMessage {
                    role: m.role.clone(),
                    content: m.content.clone(),
                })
                .collect(),
            max_tokens: Some(4096),
            temperature: Some(0.7),
        };

        debug!("Sending request to OpenRouter: model={}", self.config.model);

        let response = self
            .client
            .post(OPENROUTER_API_URL)
            .header("Authorization", format!("Bearer {}", self.config.api_key))
            .header("Content-Type", "application/json")
            .header(
                "HTTP-Referer",
                "https://github.com/AndrewAltimit/template-repo",
            )
            .header("X-Title", "MCP OpenCode Server")
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("Failed to send request: {}", e))?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(format!("API error ({}): {}", status, error_text));
        }

        let completion: ChatCompletionResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;

        completion
            .choices
            .first()
            .map(|c| c.message.content.clone())
            .ok_or_else(|| "No response from model".to_string())
    }

    /// Truncate text to a maximum length
    fn truncate_text(&self, text: &str, max_length: usize) -> String {
        if text.len() <= max_length {
            text.to_string()
        } else {
            format!("{}... [truncated]", &text[..max_length])
        }
    }

    /// Add an interaction to history
    fn add_to_history(&mut self, query: &str, response: &str) {
        self.history.push(HistoryEntry {
            query: query.to_string(),
            response: response.to_string(),
        });

        // Trim history if it exceeds max size
        let max = self.config.max_history_entries;
        if self.history.len() > max {
            self.history = self.history.split_off(self.history.len() - max);
        }
    }

    /// Clear conversation history
    pub fn clear_history(&mut self) -> usize {
        let count = self.history.len();
        self.history.clear();
        count
    }

    /// Get current statistics
    pub fn stats(&self) -> &OpenCodeStats {
        &self.stats
    }

    /// Get history size
    pub fn history_size(&self) -> usize {
        self.history.len()
    }

    /// Get the configuration
    pub fn config(&self) -> &OpenCodeConfig {
        &self.config
    }

    /// Toggle auto consultation
    pub fn toggle_auto_consult(&mut self, enable: Option<bool>) -> bool {
        match enable {
            Some(val) => self.config.auto_consult = val,
            None => self.config.auto_consult = !self.config.auto_consult,
        }
        self.config.auto_consult
    }
}

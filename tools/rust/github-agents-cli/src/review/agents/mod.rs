//! AI agent backends for PR reviews.
//!
//! Provides CLI-based abstractions for different AI agents (Gemini, Claude, Codex,
//! OpenCode, Crush). All agents use their respective CLI tools to leverage local
//! tools, MCP servers, and full agent capabilities.

pub mod claude;
pub mod codex;
pub mod crush;
pub mod gemini;
pub mod opencode;

use async_trait::async_trait;

use crate::error::Result;

/// Trait for review agents
#[async_trait]
pub trait ReviewAgent: Send + Sync {
    /// Get the agent name
    fn name(&self) -> &str;

    /// Get the model being used
    fn model(&self) -> &str;

    /// Check if the agent is available (CLI found, etc.)
    async fn is_available(&self) -> bool;

    /// Generate a review for the given prompt
    async fn review(&self, prompt: &str) -> Result<String>;

    /// Condense a review that's too long
    async fn condense(&self, review: &str, max_words: usize) -> Result<String>;
}

/// Check if subprocess stderr indicates a transient network error.
///
/// Used by agent implementations to distinguish transient failures (API outages,
/// network issues) from permanent configuration errors. Transient errors should
/// be reported as `Error::AgentExecutionFailed` (exit code 6) with a
/// "service unavailable" prefix so that workflow bash wrappers can match them
/// against known-transient patterns and gracefully skip.
pub(crate) fn is_transient_error(stderr: &str) -> bool {
    let lower = stderr.to_lowercase();
    lower.contains("fetch failed")
        || lower.contains("econnrefused")
        || lower.contains("etimedout")
        || lower.contains("econnreset")
        || lower.contains("enetunreach")
        || lower.contains("socket hang up")
        || lower.contains("network error")
        || lower.contains("dns resolution")
        || lower.contains("503")
        || lower.contains("502")
}

/// Select the appropriate review agent based on configuration
pub async fn select_agent(agent_name: &str) -> Option<Box<dyn ReviewAgent>> {
    select_agent_with_models(agent_name, None, None).await
}

/// Select agent with optional model overrides
pub async fn select_agent_with_models(
    agent_name: &str,
    review_model: Option<String>,
    condenser_model: Option<String>,
) -> Option<Box<dyn ReviewAgent>> {
    match agent_name.to_lowercase().as_str() {
        "gemini" => {
            let agent = match (review_model, condenser_model) {
                (Some(r), Some(c)) => gemini::GeminiAgent::with_models(r, c),
                (Some(r), None) => gemini::GeminiAgent::with_models(r.clone(), r),
                _ => gemini::GeminiAgent::new(),
            };
            if agent.is_available().await {
                Some(Box::new(agent))
            } else {
                tracing::warn!("Gemini CLI not available");
                None
            }
        },
        "claude" => {
            let agent = match review_model {
                Some(m) => claude::ClaudeAgent::with_model(m),
                None => claude::ClaudeAgent::new(),
            };
            if agent.is_available().await {
                Some(Box::new(agent))
            } else {
                tracing::warn!("Claude Code CLI not available");
                None
            }
        },
        "codex" => {
            let agent = match review_model {
                Some(m) => codex::CodexAgent::with_model(m),
                None => codex::CodexAgent::new(),
            };
            if agent.is_available().await {
                Some(Box::new(agent))
            } else {
                tracing::warn!("Codex CLI not available");
                None
            }
        },
        "opencode" => {
            let agent = match review_model {
                Some(m) => opencode::OpenCodeAgent::with_model(m),
                None => opencode::OpenCodeAgent::new(),
            };
            if agent.is_available().await {
                Some(Box::new(agent))
            } else {
                tracing::warn!("OpenCode CLI not available");
                None
            }
        },
        "crush" => {
            let agent = crush::CrushAgent::new();
            if agent.is_available().await {
                Some(Box::new(agent))
            } else {
                tracing::warn!("Crush CLI not available");
                None
            }
        },
        _ => {
            tracing::warn!("Unknown agent: {}", agent_name);
            None
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_transient_error_fetch_failed() {
        assert!(is_transient_error("TypeError: fetch failed"));
    }

    #[test]
    fn test_is_transient_error_econnrefused() {
        assert!(is_transient_error(
            "Error: connect ECONNREFUSED 127.0.0.1:443"
        ));
    }

    #[test]
    fn test_is_transient_error_503() {
        assert!(is_transient_error("HTTP 503 Service Unavailable"));
    }

    #[test]
    fn test_is_transient_error_502() {
        assert!(is_transient_error("502 Bad Gateway"));
    }

    #[test]
    fn test_is_transient_error_socket_hang_up() {
        assert!(is_transient_error("Error: socket hang up"));
    }

    #[test]
    fn test_is_transient_error_case_insensitive() {
        assert!(is_transient_error("FETCH FAILED"));
        assert!(is_transient_error("Network Error"));
    }

    #[test]
    fn test_is_not_transient_error() {
        assert!(!is_transient_error("Invalid API key"));
        assert!(!is_transient_error("Permission denied"));
        assert!(!is_transient_error("File not found"));
    }
}

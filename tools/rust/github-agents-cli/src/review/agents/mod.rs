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

    /// Check if the agent is available (CLI found, etc.)
    async fn is_available(&self) -> bool;

    /// Generate a review for the given prompt
    async fn review(&self, prompt: &str) -> Result<String>;

    /// Condense a review that's too long
    async fn condense(&self, review: &str, max_words: usize) -> Result<String>;
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
        }
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
        }
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
        }
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
        }
        "crush" => {
            let agent = crush::CrushAgent::new();
            if agent.is_available().await {
                Some(Box::new(agent))
            } else {
                tracing::warn!("Crush CLI not available");
                None
            }
        }
        _ => {
            tracing::warn!("Unknown agent: {}", agent_name);
            None
        }
    }
}

//! AI agent backends for PR reviews.
//!
//! Provides abstractions for different AI services (Gemini, Claude, OpenRouter).

pub mod gemini;

use async_trait::async_trait;

use crate::error::Result;

/// Trait for review agents
#[async_trait]
pub trait ReviewAgent: Send + Sync {
    /// Get the agent name
    fn name(&self) -> &str;

    /// Check if the agent is available (API key set, etc.)
    async fn is_available(&self) -> bool;

    /// Generate a review for the given prompt
    async fn review(&self, prompt: &str) -> Result<String>;

    /// Condense a review that's too long
    async fn condense(&self, review: &str, max_words: usize) -> Result<String>;
}

/// Select the appropriate review agent based on configuration
pub async fn select_agent(agent_name: &str) -> Option<Box<dyn ReviewAgent>> {
    match agent_name.to_lowercase().as_str() {
        "gemini" => {
            let agent = gemini::GeminiAgent::new();
            if agent.is_available().await {
                Some(Box::new(agent))
            } else {
                None
            }
        }
        // TODO: Add claude and openrouter backends
        _ => None,
    }
}

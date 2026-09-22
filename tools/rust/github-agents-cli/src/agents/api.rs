//! API-backed agents (no local CLI required).
//!
//! Wraps the OpenRouter review backend so monitors, backlog refinement and
//! codebase analysis can use it. API agents only produce text; they cannot
//! edit the repository.

use async_trait::async_trait;

use super::base::{Agent, AgentCapability, AgentContext};
use crate::error::Error;
use crate::review::agents::ReviewAgent;
use crate::review::agents::openrouter::OpenRouterAgent;

/// OpenRouter chat-completions agent.
pub struct OpenRouterApiAgent {
    inner: OpenRouterAgent,
}

impl OpenRouterApiAgent {
    /// Create the agent, honoring `OPENROUTER_MODEL` when set.
    pub fn new() -> Self {
        let inner = match std::env::var("OPENROUTER_MODEL") {
            Ok(model) if !model.trim().is_empty() => {
                OpenRouterAgent::with_model(model.trim().to_string())
            },
            _ => OpenRouterAgent::new(),
        };
        Self { inner }
    }
}

impl Default for OpenRouterApiAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Agent for OpenRouterApiAgent {
    fn name(&self) -> &str {
        "openrouter"
    }

    fn trigger_keyword(&self) -> &str {
        "OpenRouter"
    }

    async fn is_available(&self) -> bool {
        self.inner.is_available().await
    }

    fn capabilities(&self) -> Vec<AgentCapability> {
        vec![
            AgentCapability::CodeReview,
            AgentCapability::CodeExplanation,
            AgentCapability::Documentation,
        ]
    }

    fn priority(&self) -> u8 {
        40
    }

    async fn generate_code(&self, prompt: &str, _context: &AgentContext) -> Result<String, Error> {
        self.inner.review(prompt).await
    }
}

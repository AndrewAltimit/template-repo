//! AI Agent implementations for GitHub automation.
//!
//! This module provides the base traits and concrete implementations
//! for AI agents that can process GitHub issues and PRs.
//!
//! # Available Agents
//!
//! - **Claude**: Anthropic's Claude CLI (`claude --print`)
//! - **Gemini**: Google's Gemini CLI (`gemini prompt`)
//! - **Codex**: OpenAI's Codex CLI (`codex exec`)
//! - **OpenCode**: OpenRouter-based agent (`opencode run`)
//! - **Crush**: OpenRouter-based agent (`crush run`)
//!
//! # Example
//!
//! ```rust,ignore
//! use github_agents_cli::agents::{AgentRegistry, AgentContext};
//!
//! let registry = AgentRegistry::new();
//!
//! // Select best available agent
//! if let Some(agent) = registry.select_agent(None).await {
//!     let result = agent.generate_code("Hello", &AgentContext::default()).await?;
//! }
//!
//! // Or request a specific agent
//! if let Some(agent) = registry.select_agent(Some("Claude")).await {
//!     // Use Claude specifically
//! }
//! ```

mod base;
mod cli;
mod registry;

pub use base::{Agent, AgentCapability, AgentContext};
pub use cli::{CliAgent, CliAgentConfig};
pub use registry::{AgentRegistry, AgentStatus};

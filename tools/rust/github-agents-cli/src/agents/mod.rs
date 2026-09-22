//! AI Agent implementations for GitHub automation.
//!
//! This module provides the base traits and concrete implementations
//! for AI agents that can process GitHub issues and PRs.
//!
//! # Available Agents
//!
//! - **Claude**: Anthropic's Claude Code CLI (`claude --print`, prompt on stdin)
//! - **OpenCode**: OpenRouter-backed CLI (`opencode run -m openrouter/<model>`, stdin)
//! - **Crush**: OpenRouter-backed CLI (`crush run -q <prompt>`)
//! - **OpenRouter**: Direct OpenRouter API (text-only; review/analysis)
//!
//! # Disabled Agents
//!
//! Gemini (Google) and Codex (OpenAI) are disabled by project policy; see
//! [`DISABLED_AGENTS`]. Requests naming them fail with a clear
//! `AgentNotAvailable` error instead of silently falling back to another
//! agent.

mod api;
mod base;
mod cli;
mod registry;

pub use base::{Agent, AgentCapability, AgentContext};
pub use registry::AgentRegistry;

/// Agents that are intentionally disabled, with the reason shown to users.
pub const DISABLED_AGENTS: &[(&str, &str)] = &[
    (
        "gemini",
        "Gemini is disabled by project policy (Google AI principles now permit mass \
         surveillance and autonomous weapons use cases). Use claude or openrouter instead.",
    ),
    (
        "codex",
        "Codex is disabled by project policy (OpenAI partnerships enabling mass \
         surveillance and autonomous weapons). Use claude or openrouter instead.",
    ),
    (
        "openai",
        "OpenAI models are disabled by project policy. Use claude or openrouter instead.",
    ),
];

/// If `name` refers to a disabled agent, return the reason.
pub fn disabled_reason(name: &str) -> Option<&'static str> {
    let lower = name.trim().to_lowercase();
    DISABLED_AGENTS
        .iter()
        .find(|(n, _)| *n == lower)
        .map(|(_, reason)| *reason)
}

/// Split a comma-separated agent list, dropping (and warning about)
/// disabled or empty entries while preserving order and removing duplicates.
pub fn filter_agent_list(list: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for name in list.split(',').map(|s| s.trim().to_lowercase()) {
        if name.is_empty() || out.contains(&name) {
            continue;
        }
        if let Some(reason) = disabled_reason(&name) {
            tracing::warn!("Skipping agent '{}': {}", name, reason);
            continue;
        }
        out.push(name);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disabled_agents_detected() {
        assert!(disabled_reason("gemini").is_some());
        assert!(disabled_reason(" Codex ").is_some());
        assert!(disabled_reason("claude").is_none());
        assert!(disabled_reason("openrouter").is_none());
    }

    #[test]
    fn agent_list_filtering() {
        assert_eq!(filter_agent_list("claude,gemini"), vec!["claude"]);
        assert_eq!(
            filter_agent_list(" Claude , opencode,,claude,codex,crush"),
            vec!["claude", "opencode", "crush"]
        );
        assert!(filter_agent_list("gemini").is_empty());
    }
}

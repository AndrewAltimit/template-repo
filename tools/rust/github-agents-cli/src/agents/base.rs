//! Base traits for AI agents.
//!
//! Defines the core `Agent` trait that all AI agents must implement.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::error::Error;

/// Agent capabilities that determine what an agent can do.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentCapability {
    /// Can generate code from requirements
    CodeGeneration,
    /// Can review code and provide feedback
    CodeReview,
    /// Can analyze and explain code
    CodeExplanation,
    /// Can refactor existing code
    Refactoring,
    /// Can generate documentation
    Documentation,
    /// Can debug and fix issues
    Debugging,
    /// Can create tests
    TestGeneration,
}

/// Context provided to an agent for code generation or review.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AgentContext {
    /// Issue or PR number being processed
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_number: Option<i64>,
    /// Issue or PR title
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_title: Option<String>,
    /// Branch name for the implementation
    #[serde(skip_serializing_if = "Option::is_none")]
    pub branch_name: Option<String>,
    /// Mode of operation (e.g., "review", "implement")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<String>,
    /// Whether code generation should be suppressed
    #[serde(default)]
    pub no_code_generation: bool,
    /// Repository path
    #[serde(skip_serializing_if = "Option::is_none")]
    pub repo_path: Option<String>,
    /// Additional custom context
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

impl AgentContext {
    /// Create a new empty context.
    pub fn new() -> Self {
        Self::default()
    }

    /// Create a context for implementation.
    pub fn for_implementation(issue_number: i64, issue_title: &str, branch_name: &str) -> Self {
        Self {
            issue_number: Some(issue_number),
            issue_title: Some(issue_title.to_string()),
            branch_name: Some(branch_name.to_string()),
            mode: Some("implement".to_string()),
            ..Default::default()
        }
    }

    /// Create a context for review.
    pub fn for_review(issue_number: i64, issue_title: &str) -> Self {
        Self {
            issue_number: Some(issue_number),
            issue_title: Some(issue_title.to_string()),
            mode: Some("review".to_string()),
            no_code_generation: true,
            ..Default::default()
        }
    }
}

/// Base trait for all AI agents.
///
/// Agents are responsible for generating code, reviewing code,
/// and interacting with the codebase to implement changes.
#[async_trait]
pub trait Agent: Send + Sync {
    /// Get the agent's name.
    fn name(&self) -> &str;

    /// Get the keyword used to trigger this agent (e.g., "Claude", "Gemini").
    fn trigger_keyword(&self) -> &str;

    /// Check if the agent is available for use.
    ///
    /// This may check for required executables, API keys, or other dependencies.
    async fn is_available(&self) -> bool;

    /// Get the agent's capabilities.
    fn capabilities(&self) -> Vec<AgentCapability> {
        vec![AgentCapability::CodeGeneration]
    }

    /// Get the agent's priority for selection.
    ///
    /// Higher priority agents are preferred when multiple are available.
    /// Default priority is 50 (range: 0-100).
    fn priority(&self) -> u8 {
        50
    }

    /// Generate code based on a prompt and context.
    ///
    /// # Arguments
    ///
    /// * `prompt` - The task or question to process
    /// * `context` - Additional context for code generation
    ///
    /// # Returns
    ///
    /// Generated code or response as a string.
    async fn generate_code(&self, prompt: &str, context: &AgentContext) -> Result<String, Error>;

    /// Review code or an issue without making changes.
    ///
    /// Default implementation uses `generate_code` with review context.
    ///
    /// # Arguments
    ///
    /// * `prompt` - The review prompt
    ///
    /// # Returns
    ///
    /// Review feedback as a string.
    async fn review(&self, prompt: &str) -> Result<String, Error> {
        let context = AgentContext {
            mode: Some("review".to_string()),
            no_code_generation: true,
            ..Default::default()
        };
        self.generate_code(prompt, &context).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_context_for_implementation() {
        let ctx = AgentContext::for_implementation(42, "Fix bug", "fix-bug-42");
        assert_eq!(ctx.issue_number, Some(42));
        assert_eq!(ctx.issue_title, Some("Fix bug".to_string()));
        assert_eq!(ctx.branch_name, Some("fix-bug-42".to_string()));
        assert_eq!(ctx.mode, Some("implement".to_string()));
        assert!(!ctx.no_code_generation);
    }

    #[test]
    fn test_agent_context_for_review() {
        let ctx = AgentContext::for_review(123, "Review PR");
        assert_eq!(ctx.issue_number, Some(123));
        assert_eq!(ctx.issue_title, Some("Review PR".to_string()));
        assert_eq!(ctx.mode, Some("review".to_string()));
        assert!(ctx.no_code_generation);
    }
}

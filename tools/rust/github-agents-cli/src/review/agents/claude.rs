//! Claude Code CLI agent for PR reviews.
//!
//! Uses Claude Code (claude CLI) for code reviews, enabling access to local
//! tools, MCP servers, and the full Claude Code agent capabilities.

use std::time::Duration;

use async_trait::async_trait;
use tokio::process::Command;

use super::{ReviewAgent, run_review_cli};
use crate::error::{Error, Result};
use crate::security::trust::is_modified_in_pr;
use crate::utils::process::find_binary;

/// Claude can be thorough; allow 15 minutes per call.
const CLAUDE_TIMEOUT: Duration = Duration::from_secs(900);

/// MCP config used for the reaction-search tool.
const MCP_CONFIG: &str = ".mcp.json";

/// Claude Code CLI agent for PR reviews
pub struct ClaudeAgent {
    claude_path: Option<String>,
    model: String,
}

impl ClaudeAgent {
    /// Create a new Claude agent (default model: `sonnet`)
    pub fn new() -> Self {
        let claude_path = find_binary("CLAUDE_PATH", "claude");
        if claude_path.is_none() {
            tracing::warn!("Claude Code CLI not found in PATH");
        }
        Self {
            claude_path,
            model: "sonnet".to_string(),
        }
    }

    /// Create with custom model
    pub fn with_model(model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!("Using Claude model: {}", model);
        agent.model = model;
        agent
    }

    /// Whether the MCP config may be loaded.
    ///
    /// `.mcp.json` launches arbitrary local commands. When reviewing a PR that
    /// modifies it, loading it would execute attacker-chosen commands on the
    /// runner, so it is skipped.
    fn mcp_config_allowed() -> bool {
        if !std::path::Path::new(MCP_CONFIG).exists() {
            return false;
        }
        if is_modified_in_pr(MCP_CONFIG) {
            tracing::warn!(
                "{} is modified by this PR; not loading MCP servers from it",
                MCP_CONFIG
            );
            return false;
        }
        true
    }

    async fn call_cli(&self, prompt: &str) -> Result<String> {
        let claude_path = self
            .claude_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("Claude Code CLI not found in PATH".to_string()))?;

        tracing::info!("Calling Claude Code CLI with model: {}", self.model);

        // --print: non-interactive; --dangerously-skip-permissions: auto-approve
        // tool use (runner is sandboxed); prompt goes via stdin.
        let mut cmd = Command::new(claude_path);
        cmd.args(["--print", "--dangerously-skip-permissions", "--model"])
            .arg(&self.model);
        if Self::mcp_config_allowed() {
            cmd.args(["--mcp-config", MCP_CONFIG]);
        }

        run_review_cli("claude", cmd, Some(prompt), CLAUDE_TIMEOUT).await
    }
}

impl Default for ClaudeAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for ClaudeAgent {
    fn name(&self) -> &str {
        "claude"
    }

    fn model(&self) -> &str {
        &self.model
    }

    async fn is_available(&self) -> bool {
        self.claude_path.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        self.call_cli(prompt).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_with_model() {
        let agent = ClaudeAgent::with_model("haiku".to_string());
        assert_eq!(agent.model(), "haiku");
        assert_eq!(agent.name(), "claude");
    }
}

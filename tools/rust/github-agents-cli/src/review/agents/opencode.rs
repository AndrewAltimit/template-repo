//! OpenCode CLI agent for PR reviews.
//!
//! Uses the OpenCode CLI for code reviews via OpenRouter models.

use std::time::Duration;

use async_trait::async_trait;
use tokio::process::Command;

use super::{ReviewAgent, run_review_cli};
use crate::error::{Error, Result};
use crate::utils::process::find_binary;

/// Default model for OpenCode reviews (OpenRouter provider prefix included).
const DEFAULT_MODEL: &str = "openrouter/qwen/qwen3.7-max";

const OPENCODE_TIMEOUT: Duration = Duration::from_secs(600);

/// OpenCode CLI agent for PR reviews
pub struct OpenCodeAgent {
    opencode_path: Option<String>,
    model: String,
}

impl OpenCodeAgent {
    /// Create a new OpenCode agent
    pub fn new() -> Self {
        let opencode_path = find_binary("OPENCODE_PATH", "opencode");
        if opencode_path.is_none() {
            tracing::warn!("OpenCode CLI not found in PATH");
        }
        Self {
            opencode_path,
            model: DEFAULT_MODEL.to_string(),
        }
    }

    /// Create with custom model
    pub fn with_model(model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!("Using OpenCode model: {}", model);
        agent.model = model;
        agent
    }
}

impl Default for OpenCodeAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for OpenCodeAgent {
    fn name(&self) -> &str {
        "opencode"
    }

    fn model(&self) -> &str {
        &self.model
    }

    async fn is_available(&self) -> bool {
        self.opencode_path.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        let path = self
            .opencode_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("OpenCode CLI not found in PATH".to_string()))?;
        let mut cmd = Command::new(path);
        cmd.args(["run", "--model", &self.model]);
        run_review_cli("opencode", cmd, Some(prompt), OPENCODE_TIMEOUT).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_model_uses_openrouter() {
        assert!(DEFAULT_MODEL.starts_with("openrouter/"));
        let agent = OpenCodeAgent::with_model("x/y".to_string());
        assert_eq!(agent.model(), "x/y");
    }
}

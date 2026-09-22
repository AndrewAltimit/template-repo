//! Crush CLI agent for PR reviews.
//!
//! Uses the Crush CLI (Charmbracelet) with OpenRouter for fast code reviews.

use std::time::Duration;

use async_trait::async_trait;
use tokio::process::Command;

use super::{ReviewAgent, run_review_cli};
use crate::error::{Error, Result};
use crate::utils::process::find_binary;

/// Crush is optimized for fast responses.
const CRUSH_TIMEOUT: Duration = Duration::from_secs(300);

/// Crush takes the prompt as an argument; stay below the Linux per-argument
/// limit (128 KiB).
const MAX_PROMPT_BYTES: usize = 120 * 1024;

/// Crush CLI agent for PR reviews
pub struct CrushAgent {
    crush_path: Option<String>,
}

impl CrushAgent {
    /// Create a new Crush agent
    pub fn new() -> Self {
        let crush_path = find_binary("CRUSH_PATH", "crush");
        if crush_path.is_none() {
            tracing::warn!("Crush CLI not found in PATH");
        }
        Self { crush_path }
    }
}

impl Default for CrushAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for CrushAgent {
    fn name(&self) -> &str {
        "crush"
    }

    fn model(&self) -> &str {
        "openrouter" // Crush uses OpenRouter with environment-configured model
    }

    async fn is_available(&self) -> bool {
        self.crush_path.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        let path = self
            .crush_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("Crush CLI not found in PATH".to_string()))?;
        if prompt.len() > MAX_PROMPT_BYTES {
            return Err(Error::Config(format!(
                "Prompt of {} bytes is too large for the Crush CLI (limit {} bytes)",
                prompt.len(),
                MAX_PROMPT_BYTES
            )));
        }
        let mut cmd = Command::new(path);
        cmd.args(["run", prompt]);
        run_review_cli("crush", cmd, None, CRUSH_TIMEOUT).await
    }
}

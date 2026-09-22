//! AI agent backends for PR reviews.
//!
//! Active backends: Claude Code CLI, OpenCode CLI, Crush CLI and the
//! OpenRouter API. Gemini and Codex are disabled by project policy (see
//! [`crate::agents::DISABLED_AGENTS`]); requesting them fails with a clear
//! error.

pub mod claude;
pub mod crush;
pub mod opencode;
pub mod openrouter;

use std::time::Duration;

use async_trait::async_trait;
use tokio::process::Command;

use crate::agents::disabled_reason;
use crate::error::{Error, Result};
use crate::utils::process::{is_transient_error, run_with_timeout};
use crate::utils::text::strip_ansi_codes;

/// Trait for review agents
#[async_trait]
pub trait ReviewAgent: Send + Sync {
    /// Get the agent name
    fn name(&self) -> &str;

    /// Get the model being used
    fn model(&self) -> &str;

    /// Check if the agent is available (CLI found, API key set, etc.)
    async fn is_available(&self) -> bool;

    /// Generate a review for the given prompt
    async fn review(&self, prompt: &str) -> Result<String>;

    /// Condense a review that's too long
    async fn condense(&self, review: &str, max_words: usize) -> Result<String> {
        self.review(&condense_prompt(review, max_words)).await
    }
}

/// Prompt used to condense an over-long review.
pub fn condense_prompt(review: &str, max_words: usize) -> String {
    format!(
        r#"Condense this code review to under {max_words} words while keeping ALL actionable issues.

Rules:
- Keep ONLY actionable issues (bugs, security, required fixes)
- Remove generic praise and filler
- Remove duplicates
- Keep exactly ONE reaction image at the end
- Use bullet points

Review to condense:

{review}
"#
    )
}

/// Run a review CLI and turn its result into review text or a classified error.
///
/// Non-zero exits whose output looks like a network/service outage become
/// `Error::AgentExecutionFailed` with a `service unavailable (transient)`
/// prefix (exit code 6) so workflow wrappers can skip gracefully; other
/// failures (including timeouts and spawn failures) are configuration errors
/// (exit code 1), matching the historical CLI contract.
pub(crate) async fn run_review_cli(
    name: &str,
    cmd: Command,
    stdin: Option<&str>,
    timeout: Duration,
) -> Result<String> {
    tracing::info!("Calling {} CLI (timeout {}s)", name, timeout.as_secs());
    let output = run_with_timeout(name, cmd, stdin, timeout)
        .await
        .map_err(|e| Error::Config(format!("{} CLI failed: {}", name, e)))?;
    let stdout = String::from_utf8_lossy(&output.stdout);

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        tracing::error!("{} CLI failed with stderr: {}", name, stderr.trim());
        // Some CLIs report errors on stdout instead of stderr
        let combined = if stdout.trim().is_empty() {
            stderr.trim().to_string()
        } else {
            format!("{}\n{}", stderr.trim(), stdout.trim())
        };
        let exit_code = output.status.code().unwrap_or(1);

        if is_transient_error(&combined) {
            tracing::warn!("Transient network error detected from {} CLI", name);
            return Err(Error::AgentExecutionFailed {
                name: name.to_string(),
                exit_code,
                stdout: stdout.into_owned(),
                stderr: format!("service unavailable (transient): {}", combined),
            });
        }
        return Err(Error::Config(format!(
            "{} CLI exited with status {}: {}",
            name, output.status, combined
        )));
    }

    Ok(strip_ansi_codes(&stdout))
}

/// Select the appropriate review agent based on configuration
pub async fn select_agent(agent_name: &str) -> Result<Box<dyn ReviewAgent>> {
    select_agent_with_model(agent_name, None).await
}

/// Select a review agent with an optional model override.
///
/// Returns a descriptive error for disabled, unknown or unavailable agents.
pub async fn select_agent_with_model(
    agent_name: &str,
    model: Option<String>,
) -> Result<Box<dyn ReviewAgent>> {
    let name = agent_name.trim().to_lowercase();
    if let Some(reason) = disabled_reason(&name) {
        return Err(Error::AgentNotAvailable {
            name,
            reason: reason.to_string(),
        });
    }

    let agent: Box<dyn ReviewAgent> = match name.as_str() {
        "claude" => Box::new(match model {
            Some(m) => claude::ClaudeAgent::with_model(m),
            None => claude::ClaudeAgent::new(),
        }),
        "opencode" => Box::new(match model {
            Some(m) => opencode::OpenCodeAgent::with_model(m),
            None => opencode::OpenCodeAgent::new(),
        }),
        "crush" => Box::new(crush::CrushAgent::new()),
        "openrouter" => Box::new(match model {
            Some(m) => openrouter::OpenRouterAgent::with_model(m),
            None => openrouter::OpenRouterAgent::new(),
        }),
        _ => {
            return Err(Error::AgentNotAvailable {
                name,
                reason: "unknown review agent (expected claude, openrouter, opencode or crush)"
                    .to_string(),
            });
        },
    };

    if !agent.is_available().await {
        let reason = match agent.name() {
            "openrouter" => "OPENROUTER_API_KEY is not set",
            _ => "CLI not found (set <AGENT>_PATH or install it on PATH)",
        };
        return Err(Error::AgentNotAvailable {
            name,
            reason: reason.to_string(),
        });
    }
    Ok(agent)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn condense_prompt_mentions_limit() {
        let p = condense_prompt("long review", 123);
        assert!(p.contains("under 123 words"));
        assert!(p.contains("long review"));
    }

    #[tokio::test]
    async fn disabled_agents_rejected() {
        for name in ["gemini", "Codex"] {
            match select_agent(name).await {
                Err(Error::AgentNotAvailable { reason, .. }) => {
                    assert!(reason.contains("policy"))
                },
                _ => panic!("{name} should be rejected"),
            }
        }
    }

    #[tokio::test]
    async fn unknown_agent_rejected() {
        assert!(matches!(
            select_agent("nonexistent").await,
            Err(Error::AgentNotAvailable { .. })
        ));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn run_review_cli_classifies_transient_errors() {
        let mut cmd = Command::new("sh");
        cmd.args(["-c", "echo 'fetch failed' >&2; exit 1"]);
        match run_review_cli("sh", cmd, None, Duration::from_secs(5)).await {
            Err(Error::AgentExecutionFailed { stderr, .. }) => {
                assert!(stderr.starts_with("service unavailable (transient)"))
            },
            other => panic!("unexpected: {:?}", other.map(|_| ())),
        }

        let mut cmd = Command::new("sh");
        cmd.args(["-c", "cat"]);
        let out = run_review_cli("sh", cmd, Some("\x1b[1mok\x1b[0m"), Duration::from_secs(5))
            .await
            .unwrap();
        assert_eq!(out, "ok");
    }
}

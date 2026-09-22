//! CLI-based agent implementation.
//!
//! Each supported agent has its own CLI interface:
//! - Claude: `claude --print --dangerously-skip-permissions [--model M]`, prompt on stdin
//! - OpenCode: `opencode run -m openrouter/<model>`, prompt on stdin
//! - Crush: `crush run -q <prompt>`
//!
//! Prompts go through stdin wherever the CLI supports it so large issue
//! bodies and diffs never hit the kernel's per-argument size limit.

use async_trait::async_trait;
use std::env;
use std::time::Duration;
use tokio::process::Command;
use tokio::sync::OnceCell;
use tracing::{debug, info};

use super::base::{Agent, AgentCapability, AgentContext};
use crate::error::Error;
use crate::utils::process::{find_binary, is_transient_error, run_with_timeout};
use crate::utils::text::{strip_ansi_codes, truncate_str};

/// Default OpenRouter model for OpenCode/Crush (matches `.agents.yaml`).
pub const DEFAULT_OPENROUTER_MODEL: &str = "qwen/qwen3.7-max";

/// Crush receives its prompt as an argument; refuse prompts that would exceed
/// the Linux per-argument limit (128 KiB) rather than failing obscurely.
const MAX_ARG_PROMPT_BYTES: usize = 120 * 1024;

/// Supported CLI agents.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CliKind {
    Claude,
    OpenCode,
    Crush,
}

impl CliKind {
    fn name(self) -> &'static str {
        match self {
            CliKind::Claude => "claude",
            CliKind::OpenCode => "opencode",
            CliKind::Crush => "crush",
        }
    }

    fn keyword(self) -> &'static str {
        match self {
            CliKind::Claude => "Claude",
            CliKind::OpenCode => "OpenCode",
            CliKind::Crush => "Crush",
        }
    }

    fn path_env(self) -> &'static str {
        match self {
            CliKind::Claude => "CLAUDE_PATH",
            CliKind::OpenCode => "OPENCODE_PATH",
            CliKind::Crush => "CRUSH_PATH",
        }
    }

    fn priority(self) -> u8 {
        match self {
            CliKind::Claude => 100,
            CliKind::OpenCode => 80,
            CliKind::Crush => 60,
        }
    }

    fn capabilities(self) -> Vec<AgentCapability> {
        use AgentCapability::*;
        match self {
            CliKind::Claude => vec![
                CodeGeneration,
                CodeReview,
                CodeExplanation,
                Refactoring,
                Documentation,
                Debugging,
                TestGeneration,
            ],
            CliKind::OpenCode => vec![CodeGeneration, Refactoring, CodeReview],
            CliKind::Crush => vec![CodeGeneration, CodeReview],
        }
    }

    fn needs_openrouter_key(self) -> bool {
        matches!(self, CliKind::OpenCode | CliKind::Crush)
    }
}

/// A CLI-based agent that executes an external tool.
pub struct CliAgent {
    kind: CliKind,
    timeout: Duration,
    /// Resolved executable path (`None` = unavailable); probed once.
    resolved: OnceCell<Option<String>>,
}

impl CliAgent {
    /// Create an agent of the given kind.
    pub fn new(kind: CliKind, timeout_secs: u64) -> Self {
        Self {
            kind,
            timeout: Duration::from_secs(timeout_secs),
            resolved: OnceCell::new(),
        }
    }

    /// Create a Claude agent.
    pub fn claude(timeout_secs: u64) -> Self {
        Self::new(CliKind::Claude, timeout_secs)
    }

    /// Create an OpenCode agent.
    pub fn opencode(timeout_secs: u64) -> Self {
        Self::new(CliKind::OpenCode, timeout_secs)
    }

    /// Create a Crush agent.
    pub fn crush(timeout_secs: u64) -> Self {
        Self::new(CliKind::Crush, timeout_secs)
    }

    /// Resolve (once) the executable path.
    async fn executable(&self) -> Option<&str> {
        self.resolved
            .get_or_init(|| async {
                let kind = self.kind;
                if kind.needs_openrouter_key() && openrouter_key().is_none() {
                    debug!("Agent {} requires OPENROUTER_API_KEY", kind.name());
                    return None;
                }
                tokio::task::spawn_blocking(move || find_binary(kind.path_env(), kind.name()))
                    .await
                    .ok()
                    .flatten()
            })
            .await
            .as_deref()
    }

    /// OpenRouter model for OpenCode/Crush (`OPENCODE_MODEL` / `CRUSH_MODEL`).
    fn openrouter_model(&self) -> String {
        let var = match self.kind {
            CliKind::Crush => "CRUSH_MODEL",
            _ => "OPENCODE_MODEL",
        };
        env::var(var)
            .ok()
            .filter(|m| !m.trim().is_empty())
            .unwrap_or_else(|| DEFAULT_OPENROUTER_MODEL.to_string())
    }

    /// Build the command and stdin payload for this agent.
    fn build_command(&self, exe: &str, prompt: &str) -> Result<(Command, Option<String>), Error> {
        let mut cmd = Command::new(exe);
        let stdin = match self.kind {
            CliKind::Claude => {
                cmd.args(["--print", "--dangerously-skip-permissions"]);
                if let Ok(model) = env::var("CLAUDE_MODEL")
                    && !model.trim().is_empty()
                {
                    cmd.args(["--model", model.trim()]);
                }
                Some(prompt.to_string())
            },
            CliKind::OpenCode => {
                let model = self.openrouter_model();
                let model = if model.starts_with("openrouter/") {
                    model
                } else {
                    format!("openrouter/{model}")
                };
                cmd.args(["run", "-m", &model]);
                Some(prompt.to_string())
            },
            CliKind::Crush => {
                if prompt.len() > MAX_ARG_PROMPT_BYTES {
                    return Err(Error::AgentExecutionFailed {
                        name: self.kind.name().to_string(),
                        exit_code: -1,
                        stdout: String::new(),
                        stderr: format!(
                            "prompt of {} bytes exceeds the {} byte argument limit",
                            prompt.len(),
                            MAX_ARG_PROMPT_BYTES
                        ),
                    });
                }
                cmd.args(["run", "-q", prompt]);
                None
            },
        };

        if self.kind.needs_openrouter_key()
            && let Some(key) = openrouter_key()
        {
            cmd.env("OPENROUTER_API_KEY", &key);
            if self.kind == CliKind::Crush {
                // Crush talks to OpenRouter through its OpenAI-compatible provider
                cmd.env("OPENAI_API_KEY", &key);
            }
        }

        Ok((cmd, stdin))
    }

    /// Post-process stdout into the agent's response text.
    fn extract_response(&self, stdout: &str) -> String {
        let output = strip_ansi_codes(stdout);
        let output = output.trim();
        if self.kind == CliKind::OpenCode
            && output.starts_with('{')
            && output.ends_with('}')
            && let Ok(data) = serde_json::from_str::<serde_json::Value>(output)
        {
            for key in ["code", "response"] {
                if let Some(text) = data.get(key).and_then(|v| v.as_str()) {
                    return text.to_string();
                }
            }
        }
        output.to_string()
    }
}

fn openrouter_key() -> Option<String> {
    env::var("OPENROUTER_API_KEY")
        .ok()
        .filter(|k| !k.trim().is_empty())
}

#[async_trait]
impl Agent for CliAgent {
    fn name(&self) -> &str {
        self.kind.name()
    }

    fn trigger_keyword(&self) -> &str {
        self.kind.keyword()
    }

    async fn is_available(&self) -> bool {
        self.executable().await.is_some()
    }

    fn capabilities(&self) -> Vec<AgentCapability> {
        self.kind.capabilities()
    }

    fn priority(&self) -> u8 {
        self.kind.priority()
    }

    async fn generate_code(&self, prompt: &str, context: &AgentContext) -> Result<String, Error> {
        let name = self.kind.name();
        let exe = self
            .executable()
            .await
            .ok_or_else(|| Error::AgentNotAvailable {
                name: name.to_string(),
                reason: "CLI not found or required credentials missing".to_string(),
            })?
            .to_string();

        let prompt = match context.extra.get("code").and_then(|v| v.as_str()) {
            Some(code) => format!("Code Context:\n```\n{code}\n```\n\nTask: {prompt}"),
            None => prompt.to_string(),
        };

        info!(
            "Agent {} generating (mode: {}, prompt: {} bytes)",
            name,
            context.mode.as_deref().unwrap_or("default"),
            prompt.len()
        );

        let (cmd, stdin) = self.build_command(&exe, &prompt)?;
        let output = run_with_timeout(name, cmd, stdin.as_deref(), self.timeout).await?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        let stderr = String::from_utf8_lossy(&output.stderr);

        if !output.status.success() {
            let combined = format!("{}\n{}", stderr.trim(), truncate_str(stdout.trim(), 2000));
            let stderr = if is_transient_error(&combined) {
                format!("service unavailable (transient): {}", combined.trim())
            } else {
                combined.trim().to_string()
            };
            return Err(Error::AgentExecutionFailed {
                name: name.to_string(),
                exit_code: output.status.code().unwrap_or(-1),
                stdout: stdout.into_owned(),
                stderr,
            });
        }

        let response = self.extract_response(&stdout);
        if response.is_empty() {
            return Err(Error::AgentExecutionFailed {
                name: name.to_string(),
                exit_code: 0,
                stdout: String::new(),
                stderr: format!(
                    "agent returned an empty response; stderr: {}",
                    stderr.trim()
                ),
            });
        }
        Ok(response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cli_agent_creation() {
        let agent = CliAgent::claude(300);
        assert_eq!(agent.name(), "claude");
        assert_eq!(agent.trigger_keyword(), "Claude");
        assert_eq!(agent.priority(), 100);
        assert_eq!(CliAgent::opencode(1).trigger_keyword(), "OpenCode");
        assert_eq!(CliAgent::crush(1).name(), "crush");
    }

    #[test]
    fn test_cli_agent_capabilities() {
        let caps = CliAgent::claude(300).capabilities();
        assert!(caps.contains(&AgentCapability::CodeGeneration));
        assert!(caps.contains(&AgentCapability::CodeReview));
        assert!(
            CliAgent::crush(1)
                .capabilities()
                .contains(&AgentCapability::CodeReview)
        );
    }

    #[test]
    fn crush_rejects_oversized_prompt() {
        let agent = CliAgent::crush(1);
        let big = "x".repeat(MAX_ARG_PROMPT_BYTES + 1);
        assert!(agent.build_command("crush", &big).is_err());
        assert!(agent.build_command("crush", "small").is_ok());
    }

    #[test]
    fn claude_prompt_goes_to_stdin() {
        let agent = CliAgent::claude(1);
        let (_cmd, stdin) = agent.build_command("claude", "hello").unwrap();
        assert_eq!(stdin.as_deref(), Some("hello"));
    }

    #[test]
    fn opencode_json_response_extracted() {
        let agent = CliAgent::opencode(1);
        assert_eq!(agent.extract_response(r#"{"response":"hi"}"#), "hi");
        assert_eq!(agent.extract_response("\x1b[1mplain\x1b[0m\n"), "plain");
        let claude = CliAgent::claude(1);
        assert_eq!(
            claude.extract_response(r#"{"response":"hi"}"#),
            r#"{"response":"hi"}"#
        );
    }
}

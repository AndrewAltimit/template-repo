//! CLI-based agent implementation.
//!
//! Provides a base implementation for agents that run as CLI tools.
//! Each agent has its own specific CLI interface:
//! - Claude: `claude --print --dangerously-skip-permissions <prompt>`
//! - Gemini: `gemini prompt --model <model> --output-format text` (stdin)
//! - Codex: `codex exec --sandbox workspace-write --full-auto --json -- <prompt>`
//! - OpenCode: `opencode run -m <model>` (stdin)
//! - Crush: `crush run -q <prompt>`

use async_trait::async_trait;
use std::collections::HashMap;
use std::env;
use std::process::Stdio;
use std::time::Duration;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use tokio::time::timeout;
use tracing::{debug, error, info, warn};

use super::base::{Agent, AgentCapability, AgentContext};
use crate::error::Error;

/// Configuration for a CLI-based agent.
#[derive(Debug, Clone)]
pub struct CliAgentConfig {
    /// Name of the agent
    pub name: String,
    /// Trigger keyword (e.g., "Claude", "Gemini")
    pub trigger_keyword: String,
    /// Path to the executable
    pub executable: String,
    /// Command timeout in seconds
    pub timeout_secs: u64,
    /// Agent priority (0-100)
    pub priority: u8,
    /// Environment variables to set
    pub env_vars: HashMap<String, String>,
    /// Agent capabilities
    pub capabilities: Vec<AgentCapability>,
    /// Default model (for agents that support model selection)
    pub default_model: Option<String>,
}

impl Default for CliAgentConfig {
    fn default() -> Self {
        Self {
            name: "unknown".to_string(),
            trigger_keyword: "Unknown".to_string(),
            executable: String::new(),
            timeout_secs: 300,
            priority: 50,
            env_vars: HashMap::new(),
            capabilities: vec![AgentCapability::CodeGeneration],
            default_model: None,
        }
    }
}

/// A CLI-based agent that executes an external tool.
pub struct CliAgent {
    config: CliAgentConfig,
    /// Cached availability status
    available: Option<bool>,
}

impl CliAgent {
    /// Create a new CLI agent with the given configuration.
    pub fn new(config: CliAgentConfig) -> Self {
        Self {
            config,
            available: None,
        }
    }

    /// Create a Claude agent.
    ///
    /// Claude CLI uses: `claude --print --dangerously-skip-permissions <prompt>`
    pub fn claude(timeout_secs: u64) -> Self {
        Self::new(CliAgentConfig {
            name: "claude".to_string(),
            trigger_keyword: "Claude".to_string(),
            executable: "claude".to_string(),
            timeout_secs,
            priority: 100, // Highest priority - premium agent
            capabilities: vec![
                AgentCapability::CodeGeneration,
                AgentCapability::CodeReview,
                AgentCapability::CodeExplanation,
                AgentCapability::Refactoring,
                AgentCapability::Documentation,
                AgentCapability::Debugging,
                AgentCapability::TestGeneration,
            ],
            ..Default::default()
        })
    }

    /// Create a Gemini agent.
    ///
    /// Gemini CLI uses: `gemini prompt --model <model> --output-format text` with stdin
    pub fn gemini(timeout_secs: u64) -> Self {
        Self::new(CliAgentConfig {
            name: "gemini".to_string(),
            trigger_keyword: "Gemini".to_string(),
            executable: "gemini".to_string(),
            timeout_secs,
            priority: 90, // High priority
            default_model: Some("gemini-3-pro-preview".to_string()),
            capabilities: vec![
                AgentCapability::CodeGeneration,
                AgentCapability::CodeReview,
                AgentCapability::CodeExplanation,
            ],
            ..Default::default()
        })
    }

    /// Create an OpenCode agent.
    ///
    /// OpenCode CLI uses: `opencode run -m <model>` with stdin
    pub fn opencode(timeout_secs: u64) -> Self {
        let mut env_vars = HashMap::new();

        // Set up environment from system env
        if let Ok(api_key) = env::var("OPENROUTER_API_KEY") {
            env_vars.insert("OPENROUTER_API_KEY".to_string(), api_key);
        }

        Self::new(CliAgentConfig {
            name: "opencode".to_string(),
            trigger_keyword: "OpenCode".to_string(),
            executable: "opencode".to_string(),
            timeout_secs,
            priority: 80, // High priority as open-source alternative
            default_model: Some("qwen/qwen-2.5-coder-32b-instruct".to_string()),
            env_vars,
            capabilities: vec![
                AgentCapability::CodeGeneration,
                AgentCapability::Refactoring,
                AgentCapability::CodeReview,
            ],
        })
    }

    /// Create a Crush agent.
    ///
    /// Crush CLI uses: `crush run -q <prompt>`
    pub fn crush(timeout_secs: u64) -> Self {
        let mut env_vars = HashMap::new();

        // Set up environment from system env
        if let Ok(api_key) = env::var("OPENROUTER_API_KEY") {
            env_vars.insert("OPENROUTER_API_KEY".to_string(), api_key.clone());
            env_vars.insert("OPENAI_API_KEY".to_string(), api_key);
        }

        Self::new(CliAgentConfig {
            name: "crush".to_string(),
            trigger_keyword: "Crush".to_string(),
            executable: "crush".to_string(),
            timeout_secs,
            priority: 60,
            env_vars,
            capabilities: vec![AgentCapability::CodeGeneration],
            ..Default::default()
        })
    }

    /// Create a Codex agent.
    ///
    /// Codex CLI uses: `codex exec --sandbox workspace-write --full-auto --json -- <prompt>`
    pub fn codex(timeout_secs: u64) -> Self {
        Self::new(CliAgentConfig {
            name: "codex".to_string(),
            trigger_keyword: "Codex".to_string(),
            executable: "codex".to_string(),
            timeout_secs,
            priority: 85,
            default_model: Some("gpt-5.3-codex".to_string()),
            capabilities: vec![
                AgentCapability::CodeGeneration,
                AgentCapability::CodeReview,
                AgentCapability::Refactoring,
                AgentCapability::CodeExplanation,
            ],
            ..Default::default()
        })
    }

    /// Execute a command with the configured timeout.
    async fn execute_command(&self, args: &[&str]) -> Result<(String, String), Error> {
        let mut cmd = Command::new(&self.config.executable);
        cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());

        // Add environment variables
        for (key, value) in &self.config.env_vars {
            cmd.env(key, value);
        }

        debug!(
            "Executing {}: {} {}",
            self.config.name,
            self.config.executable,
            args.join(" ")
        );

        let child = cmd.spawn().map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                Error::AgentNotAvailable {
                    name: self.config.name.clone(),
                    reason: format!("Executable '{}' not found", self.config.executable),
                }
            } else {
                Error::Io(e)
            }
        })?;

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(Error::Io)?;
                let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                let stderr = String::from_utf8_lossy(&output.stderr).to_string();

                if output.status.success() {
                    Ok((stdout, stderr))
                } else {
                    Err(Error::AgentExecutionFailed {
                        name: self.config.name.clone(),
                        exit_code: output.status.code().unwrap_or(-1),
                        stdout,
                        stderr,
                    })
                }
            },
            Err(_) => {
                warn!(
                    "Agent {} timed out after {}s",
                    self.config.name, self.config.timeout_secs
                );
                Err(Error::AgentTimeout {
                    name: self.config.name.clone(),
                    timeout: self.config.timeout_secs,
                    stdout: String::new(),
                    stderr: String::new(),
                })
            },
        }
    }

    /// Execute a command with stdin input.
    async fn execute_command_with_stdin(
        &self,
        args: &[&str],
        stdin_input: &str,
    ) -> Result<(String, String), Error> {
        let mut cmd = Command::new(&self.config.executable);
        cmd.args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        // Add environment variables
        for (key, value) in &self.config.env_vars {
            cmd.env(key, value);
        }

        debug!(
            "Executing {} with stdin: {} {}",
            self.config.name,
            self.config.executable,
            args.join(" ")
        );

        let mut child = cmd.spawn().map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                Error::AgentNotAvailable {
                    name: self.config.name.clone(),
                    reason: format!("Executable '{}' not found", self.config.executable),
                }
            } else {
                Error::Io(e)
            }
        })?;

        // Write to stdin
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(stdin_input.as_bytes())
                .await
                .map_err(Error::Io)?;
            stdin.shutdown().await.map_err(Error::Io)?;
        }

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(Error::Io)?;
                let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                let stderr = String::from_utf8_lossy(&output.stderr).to_string();

                if output.status.success() {
                    Ok((stdout, stderr))
                } else {
                    Err(Error::AgentExecutionFailed {
                        name: self.config.name.clone(),
                        exit_code: output.status.code().unwrap_or(-1),
                        stdout,
                        stderr,
                    })
                }
            },
            Err(_) => {
                warn!(
                    "Agent {} timed out after {}s",
                    self.config.name, self.config.timeout_secs
                );
                Err(Error::AgentTimeout {
                    name: self.config.name.clone(),
                    timeout: self.config.timeout_secs,
                    stdout: String::new(),
                    stderr: String::new(),
                })
            },
        }
    }

    /// Check if the executable exists and can run.
    async fn check_executable(&self) -> bool {
        // Agent-specific availability checks
        match self.config.name.as_str() {
            "codex" => {
                // Codex requires auth file
                let home = env::var("HOME").unwrap_or_default();
                let auth_path = format!("{}/.codex/auth.json", home);
                if !std::path::Path::new(&auth_path).exists() {
                    debug!("Codex auth not found at {}", auth_path);
                    return false;
                }
            },
            "opencode" | "crush" => {
                // These require OPENROUTER_API_KEY
                if env::var("OPENROUTER_API_KEY").is_err() {
                    debug!("Agent {} requires OPENROUTER_API_KEY", self.config.name);
                    return false;
                }
            },
            _ => {},
        }

        // Try to run with --version or --help
        let result = Command::new(&self.config.executable)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .await;

        match result {
            Ok(status) => status.success(),
            Err(e) => {
                debug!("Agent {} not available: {}", self.config.name, e);
                false
            },
        }
    }

    /// Generate code using Claude CLI.
    async fn generate_with_claude(&self, prompt: &str) -> Result<String, Error> {
        // Claude: claude --print --dangerously-skip-permissions <prompt>
        let args = vec!["--print", "--dangerously-skip-permissions", prompt];
        let (stdout, stderr) = self.execute_command(&args).await?;

        if !stderr.is_empty() && stdout.trim().is_empty() {
            error!("Claude stderr: {}", stderr);
        }

        Ok(stdout.trim().to_string())
    }

    /// Generate code using Gemini CLI.
    async fn generate_with_gemini(&self, prompt: &str) -> Result<String, Error> {
        // Gemini: gemini prompt --model <model> --output-format text (stdin)
        let model = self
            .config
            .default_model
            .as_deref()
            .unwrap_or("gemini-3-pro-preview");

        let args = vec!["prompt", "--model", model, "--output-format", "text"];
        let (stdout, _stderr) = self.execute_command_with_stdin(&args, prompt).await?;

        Ok(stdout.trim().to_string())
    }

    /// Generate code using OpenCode CLI.
    async fn generate_with_opencode(
        &self,
        prompt: &str,
        context: &AgentContext,
    ) -> Result<String, Error> {
        // OpenCode: opencode run -m <model> (stdin)
        let model = self
            .config
            .default_model
            .as_deref()
            .unwrap_or("qwen/qwen-2.5-coder-32b-instruct");

        // Build full prompt with context
        let full_prompt = if let Some(extra) = context.extra.get("code") {
            format!(
                "Code Context:\n```\n{}\n```\n\nTask: {}",
                extra.as_str().unwrap_or(""),
                prompt
            )
        } else {
            prompt.to_string()
        };

        let args = vec!["run", "-m", model];
        let (stdout, stderr) = self.execute_command_with_stdin(&args, &full_prompt).await?;

        info!("OpenCode raw output length: {}", stdout.len());

        // Try to parse as JSON if it looks like JSON
        let output = stdout.trim();
        if output.starts_with('{') && output.ends_with('}') {
            if let Ok(data) = serde_json::from_str::<serde_json::Value>(output) {
                if let Some(code) = data.get("code").and_then(|v| v.as_str()) {
                    return Ok(code.to_string());
                }
                if let Some(response) = data.get("response").and_then(|v| v.as_str()) {
                    return Ok(response.to_string());
                }
            }
        }

        if output.is_empty() && !stderr.is_empty() {
            return Ok(format!("Error: {}", stderr));
        }

        Ok(output.to_string())
    }

    /// Generate code using Crush CLI.
    async fn generate_with_crush(&self, prompt: &str) -> Result<String, Error> {
        // Crush: crush run -q <prompt>
        let args = vec!["run", "-q", prompt];
        let (stdout, _stderr) = self.execute_command(&args).await?;

        Ok(stdout.trim().to_string())
    }

    /// Generate code using Codex CLI.
    async fn generate_with_codex(
        &self,
        prompt: &str,
        context: &AgentContext,
    ) -> Result<String, Error> {
        // Codex: codex exec --sandbox workspace-write --full-auto --json -- <prompt>

        // Build full prompt with context
        let mode = context.mode.as_deref().unwrap_or("quick");

        let mode_prefix = match mode {
            "generate" => "Generate code for the following requirement:",
            "complete" => "Complete the following code:",
            "refactor" => "Refactor the following code for better quality:",
            "explain" => "Explain the following code:",
            "review" => "Review the following code and provide feedback:",
            "analysis" => "Analyze the following codebase and identify issues:",
            _ => "Code task:",
        };

        let mut full_prompt = format!("{}\n\n{}", mode_prefix, prompt);

        // Add code context if provided
        if let Some(code) = context.extra.get("code").and_then(|v| v.as_str()) {
            full_prompt = format!("{}\n\nCode context:\n```\n{}\n```", full_prompt, code);
        }

        // Model and reasoning effort configuration
        let model = self
            .config
            .default_model
            .as_deref()
            .unwrap_or("gpt-5.3-codex");
        let reasoning_effort_cfg = format!(
            "reasoning_effort={}",
            env::var("CODEX_REASONING_EFFORT").unwrap_or_else(|_| "xhigh".to_string())
        );

        // Check for bypass sandbox mode (only for already-sandboxed environments)
        let bypass_sandbox = env::var("CODEX_BYPASS_SANDBOX")
            .map(|v| v == "true")
            .unwrap_or(false);

        let args: Vec<&str> = if bypass_sandbox {
            warn!("Using Codex with sandbox bypass - ensure environment is isolated");
            vec![
                "exec",
                "--model",
                model,
                "-c",
                &reasoning_effort_cfg,
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "--",
                &full_prompt,
            ]
        } else {
            vec![
                "exec",
                "--model",
                model,
                "-c",
                &reasoning_effort_cfg,
                "--sandbox",
                "workspace-write",
                "--full-auto",
                "--json",
                "--",
                &full_prompt,
            ]
        };

        let (stdout, _stderr) = self.execute_command(&args).await?;

        // Parse JSONL output
        self.parse_codex_output(&stdout)
    }

    /// Parse Codex JSONL output.
    fn parse_codex_output(&self, output: &str) -> Result<String, Error> {
        let mut messages: Vec<String> = Vec::new();
        let mut command_outputs: Vec<String> = Vec::new();

        for line in output.lines() {
            if line.trim().is_empty() {
                continue;
            }

            if let Ok(event) = serde_json::from_str::<serde_json::Value>(line) {
                self.parse_codex_event(&event, &mut messages, &mut command_outputs);
            } else if !line.starts_with('[') {
                // Not JSON, might be direct output
                debug!("Non-JSON line from Codex: {}", &line[..line.len().min(100)]);
                messages.push(line.to_string());
            }
        }

        let all_outputs: Vec<String> = messages.into_iter().chain(command_outputs).collect();

        if all_outputs.is_empty() {
            // Return raw output if parsing failed
            return Ok(output.trim().to_string());
        }

        Ok(all_outputs.join("\n"))
    }

    /// Parse a single Codex JSON event.
    fn parse_codex_event(
        &self,
        event: &serde_json::Value,
        messages: &mut Vec<String>,
        command_outputs: &mut Vec<String>,
    ) {
        // Handle nested message structure
        if let Some(msg) = event.get("msg") {
            if let Some(msg_type) = msg.get("type").and_then(|v| v.as_str()) {
                match msg_type {
                    "agent_message" => {
                        if let Some(message) = msg.get("message").and_then(|v| v.as_str()) {
                            messages.push(message.to_string());
                        }
                    },
                    "exec_command_end" => {
                        if let Some(stdout) = msg.get("stdout").and_then(|v| v.as_str()) {
                            command_outputs.push(stdout.trim().to_string());
                        }
                    },
                    "agent_reasoning" => {
                        if let Some(text) = msg.get("text").and_then(|v| v.as_str()) {
                            if !text.starts_with("**") {
                                messages.push(format!("[Reasoning] {}", text));
                            }
                        }
                    },
                    _ => {},
                }
            }
        }

        // Handle direct message events
        if event.get("type").and_then(|v| v.as_str()) == Some("message") {
            if let Some(message) = event.get("message").and_then(|v| v.as_str()) {
                messages.push(message.to_string());
            }
        }

        // Handle item.completed events (v0.79.0+ / v0.101.0 format)
        if event.get("type").and_then(|v| v.as_str()) == Some("item.completed") {
            if let Some(item) = event.get("item") {
                let item_type = item.get("type").and_then(|v| v.as_str()).unwrap_or("");
                match item_type {
                    "agent_message" => {
                        if let Some(text) = item.get("text").and_then(|v| v.as_str()) {
                            messages.push(text.to_string());
                        }
                    },
                    "message" => {
                        if let Some(content) = item.get("content").and_then(|v| v.as_array()) {
                            for part in content {
                                if part.get("type").and_then(|v| v.as_str()) == Some("text") {
                                    if let Some(text) = part.get("text").and_then(|v| v.as_str()) {
                                        messages.push(text.to_string());
                                    }
                                }
                            }
                        }
                    },
                    _ => {},
                }
            }
        }
    }
}

#[async_trait]
impl Agent for CliAgent {
    fn name(&self) -> &str {
        &self.config.name
    }

    fn trigger_keyword(&self) -> &str {
        &self.config.trigger_keyword
    }

    async fn is_available(&self) -> bool {
        // Use cached value if available
        if let Some(available) = self.available {
            return available;
        }

        self.check_executable().await
    }

    fn capabilities(&self) -> Vec<AgentCapability> {
        self.config.capabilities.clone()
    }

    fn priority(&self) -> u8 {
        self.config.priority
    }

    async fn generate_code(&self, prompt: &str, context: &AgentContext) -> Result<String, Error> {
        info!(
            "Agent {} generating code (prompt length: {} chars)",
            self.config.name,
            prompt.len()
        );

        // Dispatch to agent-specific implementation
        match self.config.name.as_str() {
            "claude" => self.generate_with_claude(prompt).await,
            "gemini" => self.generate_with_gemini(prompt).await,
            "opencode" => self.generate_with_opencode(prompt, context).await,
            "crush" => self.generate_with_crush(prompt).await,
            "codex" => self.generate_with_codex(prompt, context).await,
            _ => {
                // Generic fallback
                let (stdout, stderr) = self.execute_command(&[prompt]).await?;
                if !stderr.is_empty() && stdout.is_empty() {
                    error!("Agent {} stderr: {}", self.config.name, stderr);
                }
                Ok(stdout)
            },
        }
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
        assert_eq!(agent.priority(), 100); // Claude has highest priority
    }

    #[test]
    fn test_cli_agent_capabilities() {
        let agent = CliAgent::claude(300);
        let caps = agent.capabilities();
        assert!(caps.contains(&AgentCapability::CodeGeneration));
        assert!(caps.contains(&AgentCapability::CodeReview));
    }

    #[test]
    fn test_default_config() {
        let config = CliAgentConfig::default();
        assert_eq!(config.timeout_secs, 300);
        assert_eq!(config.priority, 50);
    }
}

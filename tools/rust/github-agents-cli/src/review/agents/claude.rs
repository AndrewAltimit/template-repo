//! Claude Code CLI agent for PR reviews.
//!
//! Uses Claude Code (claude-code CLI) for code reviews, enabling access to
//! local tools, MCP servers, and the full Claude Code agent capabilities.

use async_trait::async_trait;
use std::process::Stdio;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;

use super::ReviewAgent;
use crate::error::{Error, Result};

/// Claude Code CLI agent for PR reviews
///
/// Uses the Claude Code CLI instead of direct API calls, which provides:
/// - Access to local tools and MCP servers
/// - File system access for code exploration
/// - Full Claude Code agent capabilities (Task agents, LSP, etc.)
pub struct ClaudeAgent {
    claude_path: Option<String>,
    model: String,
}

impl ClaudeAgent {
    /// Create a new Claude agent
    pub fn new() -> Self {
        // Find claude CLI binary
        let claude_path = find_claude_binary();

        if claude_path.is_some() {
            tracing::info!("Claude Code CLI found, using CLI-based agent");
        } else {
            tracing::warn!("Claude Code CLI not found in PATH");
        }

        Self {
            claude_path,
            model: "sonnet".to_string(), // Default to sonnet for reviews
        }
    }

    /// Create with custom model
    pub fn with_model(model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!("Using Claude model: {}", model);
        agent.model = model;
        agent
    }

    /// Get the model name
    pub fn model(&self) -> &str {
        &self.model
    }

    /// Call the Claude Code CLI with a prompt
    async fn call_cli(&self, prompt: &str) -> Result<String> {
        let claude_path = self
            .claude_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("Claude Code CLI not found in PATH".to_string()))?;

        tracing::info!("Calling Claude Code CLI with model: {}", self.model);

        // Build command with appropriate flags:
        // --print: Non-interactive mode, output response and exit
        // --dangerously-skip-permissions: Auto-approve all tool uses
        // --model: Specify the model to use
        // Prompt is passed via stdin to handle large prompts safely
        let mut child = Command::new(claude_path)
            .arg("--print")
            .arg("--dangerously-skip-permissions")
            .arg("--model")
            .arg(&self.model)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| Error::Config(format!("Failed to spawn Claude Code CLI: {}", e)))?;

        // Write prompt to stdin
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(prompt.as_bytes())
                .await
                .map_err(|e| Error::Config(format!("Failed to write to Claude stdin: {}", e)))?;
            // Close stdin to signal end of input
            drop(stdin);
        }

        // Wait for completion with timeout
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(900), // 15 minute timeout (Claude can be thorough)
            child.wait_with_output(),
        )
        .await
        .map_err(|_| Error::Config("Claude Code CLI timed out after 15 minutes".to_string()))?
        .map_err(|e| Error::Config(format!("Claude Code CLI failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            tracing::error!("Claude Code CLI failed with stderr: {}", stderr);
            return Err(Error::Config(format!(
                "Claude Code CLI exited with status {}: {}",
                output.status, stderr
            )));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();

        // Filter out any ANSI escape codes and control characters
        let cleaned = strip_ansi_codes(&stdout);

        Ok(cleaned)
    }
}

/// Find the claude binary by trying to execute it directly
/// (avoids `which` command which may not be available in Docker)
fn find_claude_binary() -> Option<String> {
    let home = std::env::var("HOME").unwrap_or_default();

    // Candidates to try - will verify by executing --version
    let candidates = [
        "claude".to_string(),
        format!("{}/.nvm/versions/node/v22.16.0/bin/claude", home),
        format!("{}/.nvm/versions/node/v20.18.0/bin/claude", home),
        "/usr/local/bin/claude".to_string(),
        "/usr/bin/claude".to_string(),
    ];

    // Try each candidate by executing --version
    for candidate in &candidates {
        if let Ok(output) = std::process::Command::new(candidate).arg("--version").output() {
            if output.status.success() {
                return Some(candidate.clone());
            }
        }
    }

    None
}

/// Strip ANSI escape codes from output
fn strip_ansi_codes(s: &str) -> String {
    // Simple regex-free ANSI stripping
    let mut result = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();

    while let Some(c) = chars.next() {
        if c == '\x1b' {
            // Skip escape sequence
            if chars.peek() == Some(&'[') {
                chars.next(); // consume '['
                // Skip until we hit a letter (end of escape sequence)
                while let Some(&next) = chars.peek() {
                    chars.next();
                    if next.is_ascii_alphabetic() {
                        break;
                    }
                }
            }
        } else {
            result.push(c);
        }
    }

    result
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

    async fn is_available(&self) -> bool {
        self.claude_path.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        self.call_cli(prompt).await
    }

    async fn condense(&self, review: &str, max_words: usize) -> Result<String> {
        let condense_prompt = format!(
            r#"Condense this code review to under {} words while keeping ALL actionable issues.

Rules:
- Keep ONLY actionable issues (bugs, security, required fixes)
- Remove generic praise and filler
- Remove duplicates
- Keep exactly ONE reaction image at the end
- Use bullet points

Review to condense:

{}
"#,
            max_words, review
        );

        self.call_cli(&condense_prompt).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_claude_binary() {
        // This test just verifies the function runs without panicking
        let _ = find_claude_binary();
    }

    #[test]
    fn test_strip_ansi_codes() {
        let input = "\x1b[32mGreen text\x1b[0m and normal";
        let output = strip_ansi_codes(input);
        assert_eq!(output, "Green text and normal");
    }
}

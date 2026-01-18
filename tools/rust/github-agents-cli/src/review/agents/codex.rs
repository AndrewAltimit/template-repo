//! Codex CLI agent for PR reviews.
//!
//! Uses the Codex CLI for code reviews, enabling access to
//! local tools, sandboxed execution, and AI-powered code analysis.

use async_trait::async_trait;
use std::process::Stdio;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;

use super::ReviewAgent;
use crate::error::{Error, Result};

/// Codex CLI agent for PR reviews
///
/// Uses the Codex CLI instead of direct API calls, which provides:
/// - Sandboxed execution environment
/// - File system access for code exploration
/// - MCP server integration
pub struct CodexAgent {
    codex_path: Option<String>,
    model: String,
}

impl CodexAgent {
    /// Create a new Codex agent
    pub fn new() -> Self {
        // Find codex CLI binary
        let codex_path = find_codex_binary();

        if codex_path.is_some() {
            tracing::info!("Codex CLI found, using CLI-based agent");
        } else {
            tracing::warn!("Codex CLI not found in PATH");
        }

        Self {
            codex_path,
            model: String::new(), // Use Codex's default model (varies by account type)
        }
    }

    /// Create with custom model
    pub fn with_model(model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!("Using Codex model: {}", model);
        agent.model = model;
        agent
    }

    /// Get the model name
    pub fn model(&self) -> &str {
        &self.model
    }

    /// Call the Codex CLI with a prompt
    async fn call_cli(&self, prompt: &str) -> Result<String> {
        let codex_path = self
            .codex_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("Codex CLI not found in PATH".to_string()))?;

        if self.model.is_empty() {
            tracing::info!("Calling Codex CLI with default model");
        } else {
            tracing::info!("Calling Codex CLI with model: {}", self.model);
        }

        // Build command with appropriate flags:
        // exec: Non-interactive execution mode
        // --full-auto: Auto-approve with workspace-write sandbox
        // --model: Specify the model to use (optional)
        // -: Read prompt from stdin
        let mut cmd = Command::new(codex_path);
        cmd.arg("exec").arg("--full-auto");

        // Only add --model if explicitly specified
        if !self.model.is_empty() {
            cmd.arg("--model").arg(&self.model);
        }

        let mut child = cmd
            .arg("-") // Read prompt from stdin
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| Error::Config(format!("Failed to spawn Codex CLI: {}", e)))?;

        // Write prompt to stdin
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(prompt.as_bytes())
                .await
                .map_err(|e| Error::Config(format!("Failed to write to Codex stdin: {}", e)))?;
            // Close stdin to signal end of input
            drop(stdin);
        }

        // Wait for completion with timeout
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(600), // 10 minute timeout
            child.wait_with_output(),
        )
        .await
        .map_err(|_| Error::Config("Codex CLI timed out after 10 minutes".to_string()))?
        .map_err(|e| Error::Config(format!("Codex CLI failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            tracing::error!("Codex CLI failed with stderr: {}", stderr);
            return Err(Error::Config(format!(
                "Codex CLI exited with status {}: {}",
                output.status, stderr
            )));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();

        // Filter out any ANSI escape codes and control characters
        let cleaned = strip_ansi_codes(&stdout);

        Ok(cleaned)
    }
}

/// Find the codex binary in common locations
fn find_codex_binary() -> Option<String> {
    // Check PATH first using which
    if let Ok(output) = std::process::Command::new("which").arg("codex").output() {
        if output.status.success() {
            let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !path.is_empty() && std::path::Path::new(&path).exists() {
                return Some(path);
            }
        }
    }

    // Check common NVM paths
    let home = std::env::var("HOME").unwrap_or_default();
    let common_paths = [
        format!("{}/.nvm/versions/node/v22.16.0/bin/codex", home),
        format!("{}/.nvm/versions/node/v20.18.0/bin/codex", home),
        "/usr/local/bin/codex".to_string(),
        "/usr/bin/codex".to_string(),
    ];

    for path in common_paths {
        if std::path::Path::new(&path).exists() {
            return Some(path);
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

impl Default for CodexAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for CodexAgent {
    fn name(&self) -> &str {
        "codex"
    }

    async fn is_available(&self) -> bool {
        self.codex_path.is_some()
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
    fn test_find_codex_binary() {
        // This test just verifies the function runs without panicking
        let _ = find_codex_binary();
    }

    #[test]
    fn test_strip_ansi_codes() {
        let input = "\x1b[32mGreen text\x1b[0m and normal";
        let output = strip_ansi_codes(input);
        assert_eq!(output, "Green text and normal");
    }
}

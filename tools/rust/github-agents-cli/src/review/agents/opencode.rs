//! OpenCode CLI agent for PR reviews.
//!
//! Uses the OpenCode CLI for code reviews via OpenRouter models.

use async_trait::async_trait;
use std::process::Stdio;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;

use super::ReviewAgent;
use crate::error::{Error, Result};

/// Default model for OpenCode reviews
const DEFAULT_MODEL: &str = "opencode/gpt-5-nano";

/// OpenCode CLI agent for PR reviews
///
/// Uses the OpenCode CLI for code reviews.
pub struct OpenCodeAgent {
    opencode_path: Option<String>,
    model: String,
}

impl OpenCodeAgent {
    /// Create a new OpenCode agent
    pub fn new() -> Self {
        // Find opencode CLI binary
        let opencode_path = find_opencode_binary();

        if opencode_path.is_some() {
            tracing::info!("OpenCode CLI found, using CLI-based agent");
        } else {
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

    /// Get the model name
    pub fn model(&self) -> &str {
        &self.model
    }

    /// Call the OpenCode CLI with a prompt
    async fn call_cli(&self, prompt: &str) -> Result<String> {
        let opencode_path = self
            .opencode_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("OpenCode CLI not found in PATH".to_string()))?;

        tracing::info!("Calling OpenCode CLI with model: {}", self.model);

        // Build command with appropriate flags:
        // run: Non-interactive execution mode
        // --model: Specify the model to use
        // Prompt is passed via stdin
        let mut child = Command::new(opencode_path)
            .arg("run")
            .arg("--model")
            .arg(&self.model)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| Error::Config(format!("Failed to spawn OpenCode CLI: {}", e)))?;

        // Write prompt to stdin
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(prompt.as_bytes())
                .await
                .map_err(|e| Error::Config(format!("Failed to write to OpenCode stdin: {}", e)))?;
            // Close stdin to signal end of input
            drop(stdin);
        }

        // Wait for completion with timeout
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(600), // 10 minute timeout
            child.wait_with_output(),
        )
        .await
        .map_err(|_| Error::Config("OpenCode CLI timed out after 10 minutes".to_string()))?
        .map_err(|e| Error::Config(format!("OpenCode CLI failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            tracing::error!("OpenCode CLI failed with stderr: {}", stderr);
            return Err(Error::Config(format!(
                "OpenCode CLI exited with status {}: {}",
                output.status, stderr
            )));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();

        // Filter out any ANSI escape codes and control characters
        let cleaned = strip_ansi_codes(&stdout);

        Ok(cleaned)
    }
}

/// Find the opencode binary by trying to execute it directly
/// (avoids `which` command which may not be available in Docker)
fn find_opencode_binary() -> Option<String> {
    let home = std::env::var("HOME").unwrap_or_default();

    // Candidates to try - will verify by executing --version
    let candidates = [
        "opencode".to_string(),
        format!("{}/.nvm/versions/node/v22.16.0/bin/opencode", home),
        format!("{}/.nvm/versions/node/v20.18.0/bin/opencode", home),
        "/usr/local/bin/opencode".to_string(),
        "/usr/bin/opencode".to_string(),
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

    async fn is_available(&self) -> bool {
        self.opencode_path.is_some()
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
    fn test_find_opencode_binary() {
        let _ = find_opencode_binary();
    }

    #[test]
    fn test_strip_ansi_codes() {
        let input = "\x1b[32mGreen text\x1b[0m and normal";
        let output = strip_ansi_codes(input);
        assert_eq!(output, "Green text and normal");
    }
}

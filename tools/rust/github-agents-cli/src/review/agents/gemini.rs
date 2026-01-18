//! Gemini CLI agent for PR reviews.
//!
//! Uses the Gemini CLI (via subprocess) for code reviews, enabling access to
//! local tools, MCP servers, and the full Gemini agent capabilities.

use async_trait::async_trait;
use std::process::Stdio;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;

use super::ReviewAgent;
use crate::error::{Error, Result};

/// Default model for reviews
const DEFAULT_REVIEW_MODEL: &str = "gemini-2.0-flash";

/// Default model for condensation (faster)
const DEFAULT_CONDENSER_MODEL: &str = "gemini-2.0-flash";

/// Gemini CLI agent for PR reviews
///
/// Uses the Gemini CLI instead of direct API calls, which provides:
/// - Access to local tools and MCP servers
/// - File system access for code exploration
/// - Full Gemini agent capabilities
pub struct GeminiAgent {
    gemini_path: Option<String>,
    review_model: String,
    condenser_model: String,
}

impl GeminiAgent {
    /// Create a new Gemini agent
    pub fn new() -> Self {
        // Find gemini CLI binary
        let gemini_path = find_gemini_binary();

        if gemini_path.is_some() {
            tracing::info!("Gemini CLI found, using CLI-based agent");
        } else {
            tracing::warn!("Gemini CLI not found in PATH");
        }

        Self {
            gemini_path,
            review_model: DEFAULT_REVIEW_MODEL.to_string(),
            condenser_model: DEFAULT_CONDENSER_MODEL.to_string(),
        }
    }

    /// Create with custom models
    pub fn with_models(review_model: String, condenser_model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!(
            "Using Gemini models - review: {}, condenser: {}",
            review_model,
            condenser_model
        );
        agent.review_model = review_model;
        agent.condenser_model = condenser_model;
        agent
    }

    /// Get the review model name
    pub fn review_model(&self) -> &str {
        &self.review_model
    }

    /// Call the Gemini CLI with a prompt
    async fn call_cli(&self, model: &str, prompt: &str) -> Result<String> {
        let gemini_path = self
            .gemini_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("Gemini CLI not found in PATH".to_string()))?;

        tracing::info!("Calling Gemini CLI with model: {}", model);

        // Build command with appropriate flags:
        // --yolo: Auto-approve all tool uses (needed for non-interactive mode)
        // --model: Specify the model to use
        // Prompt is passed via stdin to handle large prompts safely
        let mut cmd = Command::new(gemini_path);
        cmd.arg("--yolo")
            .arg("--model")
            .arg(model)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        // Pass GEMINI_API_KEY to subprocess, falling back to GOOGLE_API_KEY if needed
        // (GitHub workflows often use GOOGLE_API_KEY, but Gemini CLI expects GEMINI_API_KEY)
        // Check for non-empty values since workflows may set empty defaults
        let api_key = std::env::var("GEMINI_API_KEY")
            .ok()
            .filter(|k| !k.is_empty())
            .or_else(|| std::env::var("GOOGLE_API_KEY").ok().filter(|k| !k.is_empty()));

        if let Some(key) = api_key {
            cmd.env("GEMINI_API_KEY", key);
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| Error::Config(format!("Failed to spawn Gemini CLI: {}", e)))?;

        // Write prompt to stdin
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(prompt.as_bytes())
                .await
                .map_err(|e| Error::Config(format!("Failed to write to Gemini stdin: {}", e)))?;
            // Close stdin to signal end of input
            drop(stdin);
        }

        // Wait for completion with timeout
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(600), // 10 minute timeout
            child.wait_with_output(),
        )
        .await
        .map_err(|_| Error::Config("Gemini CLI timed out after 10 minutes".to_string()))?
        .map_err(|e| Error::Config(format!("Gemini CLI failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            tracing::error!("Gemini CLI failed with stderr: {}", stderr);
            return Err(Error::Config(format!(
                "Gemini CLI exited with status {}: {}",
                output.status, stderr
            )));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();

        // Filter out any ANSI escape codes and control characters
        let cleaned = strip_ansi_codes(&stdout);

        Ok(cleaned)
    }
}

/// Find the gemini binary in common locations
fn find_gemini_binary() -> Option<String> {
    // Check PATH first using which
    if let Ok(output) = std::process::Command::new("which").arg("gemini").output() {
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
        format!("{}/.nvm/versions/node/v22.16.0/bin/gemini", home),
        format!("{}/.nvm/versions/node/v20.18.0/bin/gemini", home),
        "/usr/local/bin/gemini".to_string(),
        "/usr/bin/gemini".to_string(),
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

impl Default for GeminiAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for GeminiAgent {
    fn name(&self) -> &str {
        "gemini"
    }

    async fn is_available(&self) -> bool {
        self.gemini_path.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        self.call_cli(&self.review_model, prompt).await
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

        self.call_cli(&self.condenser_model, &condense_prompt).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_gemini_binary() {
        // This test just verifies the function runs without panicking
        let _ = find_gemini_binary();
    }

    #[test]
    fn test_strip_ansi_codes() {
        let input = "\x1b[32mGreen text\x1b[0m and normal";
        let output = strip_ansi_codes(input);
        assert_eq!(output, "Green text and normal");
    }

    #[test]
    fn test_strip_ansi_codes_empty() {
        let input = "no escape codes here";
        let output = strip_ansi_codes(input);
        assert_eq!(output, input);
    }
}

//! Crush CLI agent for PR reviews.
//!
//! Uses the Crush CLI for fast code reviews via OpenRouter models.

use async_trait::async_trait;
use std::process::Stdio;
use tokio::process::Command;

use super::ReviewAgent;
use crate::error::{Error, Result};

/// Crush CLI agent for PR reviews
///
/// Uses the Crush CLI (Charmbracelet) with OpenRouter for fast code reviews.
/// Crush is optimized for concise, fast responses.
pub struct CrushAgent {
    crush_path: Option<String>,
}

impl CrushAgent {
    /// Create a new Crush agent
    pub fn new() -> Self {
        // Find crush CLI binary
        let crush_path = find_crush_binary();

        if crush_path.is_some() {
            tracing::info!("Crush CLI found, using CLI-based agent");
        } else {
            tracing::warn!("Crush CLI not found in PATH");
        }

        Self { crush_path }
    }

    /// Call the Crush CLI with a prompt
    async fn call_cli(&self, prompt: &str) -> Result<String> {
        let crush_path = self
            .crush_path
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("Crush CLI not found in PATH".to_string()))?;

        tracing::info!("Calling Crush CLI");

        // Build command with appropriate flags:
        // run: Non-interactive execution mode
        // Prompt is passed as positional argument
        let child = Command::new(crush_path)
            .arg("run")
            .arg(prompt)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| Error::Config(format!("Failed to spawn Crush CLI: {}", e)))?;

        // Wait for completion with timeout
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(300), // 5 minute timeout (Crush is fast)
            child.wait_with_output(),
        )
        .await
        .map_err(|_| Error::Config("Crush CLI timed out after 5 minutes".to_string()))?
        .map_err(|e| Error::Config(format!("Crush CLI failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let stdout = String::from_utf8_lossy(&output.stdout);
            tracing::error!("Crush CLI failed with stderr: {}", stderr);
            // Check combined stderr+stdout for transient errors since some CLIs
            // report errors on stdout instead of stderr
            let combined = if stdout.is_empty() {
                stderr.to_string()
            } else {
                format!("{}\n{}", stderr, stdout)
            };

            if super::is_transient_error(&combined) {
                tracing::warn!("Transient network error detected from Crush CLI");
                return Err(Error::AgentExecutionFailed {
                    name: "crush".to_string(),
                    exit_code: output.status.code().unwrap_or(1),
                    stdout: stdout.to_string(),
                    stderr: format!("service unavailable (transient): {}", combined),
                });
            }

            return Err(Error::Config(format!(
                "Crush CLI exited with status {}: {}",
                output.status, combined
            )));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();

        // Filter out any ANSI escape codes and control characters
        let cleaned = strip_ansi_codes(&stdout);

        Ok(cleaned)
    }
}

/// Find the crush binary by trying to execute it directly
/// (avoids `which` command which may not be available in Docker)
fn find_crush_binary() -> Option<String> {
    // 1. Check CRUSH_PATH environment variable first (allows explicit override)
    if let Ok(path) = std::env::var("CRUSH_PATH") {
        if !path.is_empty() && verify_binary(&path, "--version") {
            tracing::info!("Using crush from CRUSH_PATH: {}", path);
            return Some(path);
        }
    }

    let home = std::env::var("HOME").unwrap_or_default();

    // 2. Build candidates list - PATH lookup first, then common locations
    let mut candidates = vec![
        "crush".to_string(), // PATH lookup
        "/usr/local/bin/crush".to_string(),
        "/usr/bin/crush".to_string(),
    ];

    // 3. Add Go binary location (Crush is a Charmbracelet Go tool)
    if !home.is_empty() {
        candidates.push(format!("{}/go/bin/crush", home));

        // 4. Dynamically discover NVM node versions (in case installed via npm)
        let nvm_versions_dir = format!("{}/.nvm/versions/node", home);
        if let Ok(entries) = std::fs::read_dir(&nvm_versions_dir) {
            let mut node_versions: Vec<_> = entries
                .filter_map(|e| e.ok())
                .filter(|e| e.path().is_dir())
                .map(|e| e.file_name().to_string_lossy().to_string())
                .collect();
            // Sort descending to prefer newer versions
            node_versions.sort_by(|a, b| b.cmp(a));
            for version in node_versions {
                candidates.push(format!("{}/{}/bin/crush", nvm_versions_dir, version));
            }
        }
    }

    // Try each candidate by executing --version
    for candidate in &candidates {
        if verify_binary(candidate, "--version") {
            return Some(candidate.clone());
        }
    }

    None
}

/// Verify a binary exists and runs successfully with given arg
fn verify_binary(path: &str, arg: &str) -> bool {
    std::process::Command::new(path)
        .arg(arg)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
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
    fn test_find_crush_binary() {
        let _ = find_crush_binary();
    }

    #[test]
    fn test_strip_ansi_codes() {
        let input = "\x1b[32mGreen text\x1b[0m and normal";
        let output = strip_ansi_codes(input);
        assert_eq!(output, "Green text and normal");
    }
}

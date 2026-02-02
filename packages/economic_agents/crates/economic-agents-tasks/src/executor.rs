//! Task executor using Claude CLI.
//!
//! Executes coding tasks by sending them to Claude and parsing the generated solutions.

use std::env;
use std::process::Stdio;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use tracing::{debug, error, info, warn};

use crate::catalog::CodingChallenge;

/// Result of task execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    /// Whether execution succeeded.
    pub success: bool,
    /// Generated solution code.
    pub solution: Option<String>,
    /// Error message if failed.
    pub error: Option<String>,
    /// Execution time in milliseconds.
    pub execution_time_ms: u64,
    /// Model used for generation.
    pub model: String,
}

/// Configuration for the task executor.
#[derive(Debug, Clone)]
pub struct ExecutorConfig {
    /// Model to use (e.g., "sonnet", "opus", "haiku").
    pub model: String,
    /// Timeout for execution.
    pub timeout: Duration,
    /// Path to claude binary (auto-detected if None).
    pub claude_path: Option<String>,
}

impl Default for ExecutorConfig {
    fn default() -> Self {
        Self {
            model: "sonnet".to_string(),
            timeout: Duration::from_secs(300), // 5 minutes for code generation
            claude_path: None,
        }
    }
}

/// Executes coding tasks using Claude CLI.
pub struct TaskExecutor {
    config: ExecutorConfig,
    claude_path: Option<String>,
}

impl TaskExecutor {
    /// Create a new task executor with the given configuration.
    pub fn new(config: ExecutorConfig) -> Self {
        let claude_path = config.claude_path.clone().or_else(find_claude_binary);

        if claude_path.is_some() {
            info!("Task Executor initialized with Claude CLI");
        } else {
            warn!("Claude CLI not found, task execution will fail");
        }

        Self {
            config,
            claude_path,
        }
    }

    /// Create with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(ExecutorConfig::default())
    }

    /// Check if Claude CLI is available.
    pub fn is_available(&self) -> bool {
        self.claude_path.is_some()
    }

    /// Execute a coding challenge and generate a solution.
    pub async fn execute(&self, challenge: &CodingChallenge) -> ExecutionResult {
        let start = std::time::Instant::now();

        if !self.is_available() {
            return ExecutionResult {
                success: false,
                solution: None,
                error: Some("Claude CLI not available".to_string()),
                execution_time_ms: start.elapsed().as_millis() as u64,
                model: self.config.model.clone(),
            };
        }

        let prompt = self.build_prompt(challenge);

        match self.call_claude(&prompt).await {
            Ok(response) => {
                let solution = self.extract_code(&response, &challenge.language);
                ExecutionResult {
                    success: solution.is_some(),
                    solution,
                    error: None,
                    execution_time_ms: start.elapsed().as_millis() as u64,
                    model: self.config.model.clone(),
                }
            },
            Err(e) => ExecutionResult {
                success: false,
                solution: None,
                error: Some(e),
                execution_time_ms: start.elapsed().as_millis() as u64,
                model: self.config.model.clone(),
            },
        }
    }

    /// Build the prompt for Claude.
    fn build_prompt(&self, challenge: &CodingChallenge) -> String {
        // Only show non-hidden test cases
        let visible_tests: Vec<_> = challenge
            .test_cases
            .iter()
            .filter(|tc| !tc.hidden)
            .collect();

        let test_examples = visible_tests
            .iter()
            .map(|tc| {
                format!(
                    "- {}: inputs={:?}, expected={}",
                    tc.name, tc.inputs, tc.expected_output
                )
            })
            .collect::<Vec<_>>()
            .join("\n");

        format!(
            r#"You are a coding assistant. Solve the following coding challenge.

## Challenge: {}

{}

## Language: {}

## Function Template:
```{}
{}
```

## Test Cases:
{}

## Instructions:
1. Implement ONLY the function(s) specified in the template
2. Your solution must pass all test cases
3. Write clean, efficient code
4. Do NOT include any test code or main function
5. Do NOT include any explanations - ONLY the code

## Response Format:
Return ONLY the complete function implementation in a code block:
```{}
<your solution here>
```"#,
            challenge.name,
            challenge.description,
            challenge.language,
            challenge.language,
            challenge.function_template,
            test_examples,
            challenge.language
        )
    }

    /// Extract code from Claude's response.
    fn extract_code(&self, response: &str, language: &str) -> Option<String> {
        // Try to find code block with specific language
        let lang_pattern = format!("```{}", language);
        if let Some(start) = response.find(&lang_pattern) {
            let code_start = start + lang_pattern.len();
            if let Some(end) = response[code_start..].find("```") {
                let code = response[code_start..code_start + end].trim();
                return Some(code.to_string());
            }
        }

        // Try generic code block
        if let Some(start) = response.find("```") {
            let after_backticks = start + 3;
            // Skip language identifier if present
            let code_start = if let Some(newline) = response[after_backticks..].find('\n') {
                after_backticks + newline + 1
            } else {
                after_backticks
            };

            if let Some(end) = response[code_start..].find("```") {
                let code = response[code_start..code_start + end].trim();
                return Some(code.to_string());
            }
        }

        // If no code block, try to extract the whole response as code
        // (only if it looks like code)
        let trimmed = response.trim();
        if trimmed.contains("def ") || trimmed.contains("class ") || trimmed.contains("fn ") {
            return Some(trimmed.to_string());
        }

        None
    }

    /// Call Claude CLI with a prompt.
    async fn call_claude(&self, prompt: &str) -> Result<String, String> {
        let claude_path = self.claude_path.as_ref().ok_or("Claude CLI not found")?;

        debug!("Calling Claude CLI for task execution");

        let mut cmd = Command::new(claude_path);
        cmd.arg("--print")
            .arg("--dangerously-skip-permissions")
            .arg("--model")
            .arg(&self.config.model)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Claude CLI: {}", e))?;

        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(prompt.as_bytes())
                .await
                .map_err(|e| format!("Failed to write to stdin: {}", e))?;
            drop(stdin);
        }

        let output = tokio::time::timeout(self.config.timeout, child.wait_with_output())
            .await
            .map_err(|_| format!("Claude CLI timed out after {:?}", self.config.timeout))?
            .map_err(|e| format!("Claude CLI failed: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("Claude CLI failed: {}", stderr);
            return Err(format!("Claude CLI failed: {}", stderr));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        Ok(strip_ansi_codes(&stdout))
    }
}

impl Default for TaskExecutor {
    fn default() -> Self {
        Self::with_defaults()
    }
}

/// Find the claude binary by checking common locations.
fn find_claude_binary() -> Option<String> {
    if let Ok(path) = env::var("CLAUDE_PATH")
        && !path.is_empty()
        && verify_binary(&path)
    {
        return Some(path);
    }

    let home = env::var("HOME").unwrap_or_default();
    let mut candidates = vec![
        "claude".to_string(),
        "/usr/local/bin/claude".to_string(),
        "/usr/bin/claude".to_string(),
    ];

    if !home.is_empty() {
        let nvm_versions_dir = format!("{}/.nvm/versions/node", home);
        if let Ok(entries) = std::fs::read_dir(&nvm_versions_dir) {
            let mut node_versions: Vec<_> = entries
                .filter_map(|e| e.ok())
                .filter(|e| e.path().is_dir())
                .map(|e| e.file_name().to_string_lossy().to_string())
                .collect();
            node_versions.sort_by(|a, b| b.cmp(a));
            for version in node_versions {
                candidates.push(format!("{}/{}/bin/claude", nvm_versions_dir, version));
            }
        }
        candidates.push(format!("{}/.npm-global/bin/claude", home));
    }

    for candidate in &candidates {
        if verify_binary(candidate) {
            return Some(candidate.clone());
        }
    }

    None
}

fn verify_binary(path: &str) -> bool {
    std::process::Command::new(path)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok_and(|s| s.success())
}

fn strip_ansi_codes(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();

    while let Some(c) = chars.next() {
        if c == '\x1b' {
            if chars.peek() == Some(&'[') {
                chars.next();
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::catalog::TaskCatalog;

    #[test]
    fn test_executor_creation() {
        let executor = TaskExecutor::with_defaults();
        assert_eq!(executor.config.model, "sonnet");
    }

    #[test]
    fn test_build_prompt() {
        let executor = TaskExecutor::with_defaults();
        let catalog = TaskCatalog::new();
        let challenge = catalog.get("fizzbuzz").unwrap();

        let prompt = executor.build_prompt(challenge);
        assert!(prompt.contains("FizzBuzz"));
        assert!(prompt.contains("def fizzbuzz"));
        assert!(prompt.contains("Fizz"));
    }

    #[test]
    fn test_extract_code_with_language() {
        let executor = TaskExecutor::with_defaults();
        let response = r#"Here is the solution:
```python
def fizzbuzz(n):
    if n % 15 == 0:
        return "FizzBuzz"
    elif n % 3 == 0:
        return "Fizz"
    elif n % 5 == 0:
        return "Buzz"
    return str(n)
```
"#;

        let code = executor.extract_code(response, "python");
        assert!(code.is_some());
        let code = code.unwrap();
        assert!(code.contains("def fizzbuzz"));
        assert!(code.contains("FizzBuzz"));
    }

    #[test]
    fn test_extract_code_generic_block() {
        let executor = TaskExecutor::with_defaults();
        let response = r#"```
def hello():
    return "world"
```"#;

        let code = executor.extract_code(response, "python");
        assert!(code.is_some());
        assert!(code.unwrap().contains("def hello"));
    }

    #[test]
    fn test_strip_ansi() {
        let input = "\x1b[32mgreen\x1b[0m normal";
        assert_eq!(strip_ansi_codes(input), "green normal");
    }
}

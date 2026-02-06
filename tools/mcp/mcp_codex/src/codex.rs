//! Codex CLI integration module.

use chrono::Utc;
use serde_json::Value;
use std::process::Stdio;
use tokio::process::Command;
use tokio::time::{Duration, timeout};
use tracing::{debug, info, warn};

use crate::types::{
    CodexConfig, CodexStats, ConsultMode, ConsultResult, ConsultStatus, HistoryEntry,
};

/// Codex CLI integration
pub struct CodexIntegration {
    config: CodexConfig,
    history: Vec<HistoryEntry>,
    stats: CodexStats,
}

impl CodexIntegration {
    /// Create a new Codex integration
    pub fn new(config: CodexConfig) -> Self {
        Self {
            config,
            history: Vec::new(),
            stats: CodexStats::default(),
        }
    }

    /// Consult Codex for code generation or assistance (internal implementation).
    async fn consult_impl(
        &mut self,
        query: &str,
        context: &str,
        mode: ConsultMode,
        _comparison_mode: bool,
        force: bool,
    ) -> ConsultResult {
        // Check if enabled
        if !self.config.enabled && !force {
            return ConsultResult::disabled("Codex integration is disabled");
        }

        self.stats.consultations += 1;
        self.stats.last_consultation = Some(Utc::now());

        // Check if Codex CLI is available
        if !self.check_codex_available().await {
            self.stats.errors += 1;
            return ConsultResult::error(
                "Codex CLI not available. Please install with: npm install -g @openai/codex",
                mode,
            );
        }

        // Check if Codex authentication exists
        if !self.check_auth_exists() {
            self.stats.errors += 1;
            return ConsultResult::error(
                format!(
                    "Codex authentication not configured. Auth file not found at: {}. \
                     Please run 'codex' interactively to complete authentication.",
                    self.config.auth_path
                ),
                mode,
            );
        }

        // Build the prompt
        let prompt = self.build_prompt(query, context, mode);

        // Execute Codex
        match self.execute_codex(&prompt, mode).await {
            Ok(output) => {
                // Add to history
                if self.config.include_history {
                    self.add_to_history(query, mode, true, Some(&output));
                }

                if self.config.log_consultations {
                    info!(
                        "Codex consultation: mode={:?}, query_length={}",
                        mode,
                        query.len()
                    );
                }

                ConsultResult::success(output, mode)
            },
            Err(e) => {
                self.stats.errors += 1;

                if self.config.include_history {
                    self.add_to_history(query, mode, false, None);
                }

                ConsultResult::error(e, mode)
            },
        }
    }

    /// Execute the Codex CLI command
    async fn execute_codex(&self, prompt: &str, mode: ConsultMode) -> Result<String, String> {
        let mut args = vec!["exec".to_string()];

        if self.config.bypass_sandbox {
            // WARNING: Only use this in already-sandboxed environments (VMs, containers)
            args.extend([
                "--json".to_string(),
                "--dangerously-bypass-approvals-and-sandbox".to_string(),
                prompt.to_string(),
            ]);
        } else {
            // Default: Use safe sandboxed mode with workspace-write restrictions
            args.extend([
                "--sandbox".to_string(),
                "workspace-write".to_string(),
                "--full-auto".to_string(),
                "--json".to_string(),
                prompt.to_string(),
            ]);
        }

        debug!("Executing codex with args: {:?}", args);

        let mut cmd = Command::new("codex");
        cmd.args(&args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Codex process: {}", e))?;

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(|e| format!("Codex execution failed: {}", e))?;

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    return Err(if stderr.is_empty() {
                        "Codex execution failed".to_string()
                    } else {
                        stderr.to_string()
                    });
                }

                let stdout = String::from_utf8_lossy(&output.stdout);
                if stdout.is_empty() {
                    return Err("No output from Codex".to_string());
                }

                Ok(self.parse_codex_output(&stdout, mode))
            },
            Err(_) => Err(format!(
                "Codex execution timed out after {} seconds",
                self.config.timeout_secs
            )),
        }
    }

    /// Parse JSONL output from codex exec --json
    fn parse_codex_output(&self, output: &str, _mode: ConsultMode) -> String {
        let mut messages = Vec::new();
        let mut command_outputs = Vec::new();
        let mut reasoning_texts = Vec::new();

        for line in output.lines() {
            if line.trim().is_empty() {
                continue;
            }

            match serde_json::from_str::<Value>(line) {
                Ok(event) => {
                    self.parse_codex_event(
                        &event,
                        &mut messages,
                        &mut command_outputs,
                        &mut reasoning_texts,
                    );
                },
                Err(_) => {
                    // If not JSON, treat as plain text
                    if !line.starts_with('[') && !line.starts_with('{') {
                        messages.push(line.to_string());
                    } else {
                        warn!("Could not parse JSON line from Codex output: {}", line);
                    }
                },
            }
        }

        // Prefer messages, fall back to reasoning if no messages
        if !messages.is_empty() {
            let mut combined = messages.join("\n");
            if !command_outputs.is_empty() {
                combined.push_str("\n\n**Command Outputs:**\n");
                combined.push_str(&command_outputs.join("\n"));
            }
            combined
        } else if !reasoning_texts.is_empty() {
            // Filter out process descriptions, keep substantive reasoning
            let filtered: Vec<_> = reasoning_texts
                .into_iter()
                .filter(|r| !r.starts_with("**") || r.len() > 50)
                .collect();
            if !filtered.is_empty() {
                return filtered.join("\n");
            }
            if !command_outputs.is_empty() {
                return command_outputs.join("\n");
            }
            output.to_string()
        } else if !command_outputs.is_empty() {
            command_outputs.join("\n")
        } else {
            output.to_string()
        }
    }

    /// Parse a single Codex event
    fn parse_codex_event(
        &self,
        event: &Value,
        messages: &mut Vec<String>,
        command_outputs: &mut Vec<String>,
        reasoning_texts: &mut Vec<String>,
    ) {
        let event_type = event.get("type").and_then(|v| v.as_str()).unwrap_or("");

        // Handle Codex v0.79.0+ JSONL format
        if event_type == "item.completed" {
            if let Some(item) = event.get("item") {
                let item_type = item.get("type").and_then(|v| v.as_str()).unwrap_or("");

                match item_type {
                    "message" => {
                        // Extract agent messages (final response)
                        if let Some(content) = item.get("content").and_then(|v| v.as_array()) {
                            for part in content {
                                if part.get("type").and_then(|v| v.as_str()) == Some("text") {
                                    if let Some(text) = part.get("text").and_then(|v| v.as_str()) {
                                        if !text.is_empty() {
                                            messages.push(text.to_string());
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "reasoning" => {
                        // Extract reasoning for context
                        if let Some(text) = item.get("text").and_then(|v| v.as_str()) {
                            if !text.is_empty() {
                                reasoning_texts.push(text.to_string());
                            }
                        }
                    },
                    "command_execution" => {
                        // Extract command outputs
                        if item.get("status").and_then(|v| v.as_str()) == Some("completed") {
                            if let Some(stdout) =
                                item.get("aggregated_output").and_then(|v| v.as_str())
                            {
                                let trimmed = stdout.trim();
                                if !trimmed.is_empty() {
                                    command_outputs.push(trimmed.to_string());
                                }
                            }
                        }
                    },
                    _ => {},
                }
            }
        }
        // Handle legacy format (older Codex versions)
        else if let Some(msg) = event.get("msg") {
            let msg_type = msg.get("type").and_then(|v| v.as_str()).unwrap_or("");

            match msg_type {
                "agent_message" => {
                    if let Some(message) = msg.get("message").and_then(|v| v.as_str()) {
                        messages.push(message.to_string());
                    }
                },
                "exec_command_end" => {
                    if let Some(stdout) = msg.get("stdout").and_then(|v| v.as_str()) {
                        let trimmed = stdout.trim();
                        if !trimmed.is_empty() {
                            command_outputs.push(trimmed.to_string());
                        }
                    }
                },
                "agent_reasoning" => {
                    if let Some(text) = msg.get("text").and_then(|v| v.as_str()) {
                        if !text.is_empty() {
                            reasoning_texts.push(text.to_string());
                        }
                    }
                },
                _ => {},
            }
        }
        // Handle direct message events
        else if event_type == "message" {
            if let Some(message) = event.get("message").and_then(|v| v.as_str()) {
                messages.push(message.to_string());
            }
        }
    }

    /// Build a prompt for Codex based on mode and context
    fn build_prompt(&self, query: &str, context: &str, mode: ConsultMode) -> String {
        let mut parts = Vec::new();

        // Add history if enabled and available
        if self.config.include_history && !self.history.is_empty() {
            if let Some(history_text) = self.format_history() {
                parts.push(format!("Previous context:\n{}\n---\n", history_text));
            }
        }

        // Add mode-specific prefix
        parts.push(mode.prompt_prefix().to_string());

        // Add context if provided
        if !context.is_empty() {
            parts.push(format!("\nContext:\n{}\n", context));
        }

        // Add the main query
        parts.push(format!("\n{}", query));

        parts.join("")
    }

    /// Format conversation history for context
    fn format_history(&self) -> Option<String> {
        if self.history.is_empty() {
            return None;
        }

        let mut parts = Vec::new();
        let start = self
            .history
            .len()
            .saturating_sub(self.config.max_history_entries);

        for entry in &self.history[start..] {
            let query_preview: String = entry.query.chars().take(200).collect();
            parts.push(format!("Q: {}...", query_preview));

            if entry.success {
                if let Some(ref output) = entry.output_summary {
                    let output_preview: String = output.chars().take(200).collect();
                    parts.push(format!("A: {}...", output_preview));
                } else {
                    parts.push("A: Done".to_string());
                }
            }
        }

        Some(parts.join("\n"))
    }

    /// Add an interaction to the history
    fn add_to_history(
        &mut self,
        query: &str,
        mode: ConsultMode,
        success: bool,
        output: Option<&str>,
    ) {
        self.history.push(HistoryEntry {
            timestamp: Utc::now(),
            query: query.to_string(),
            mode,
            success,
            output_summary: output.map(|s| s.chars().take(500).collect()),
        });

        // Trim history if it exceeds max size (keep double for some buffer)
        let max = self.config.max_history_entries * 2;
        if self.history.len() > max {
            self.history = self
                .history
                .split_off(self.history.len() - self.config.max_history_entries);
        }
    }

    /// Check if Codex CLI is available
    pub async fn check_codex_available(&self) -> bool {
        match Command::new("which").arg("codex").output().await {
            Ok(output) => output.status.success(),
            Err(_) => false,
        }
    }

    /// Check if Codex authentication file exists
    fn check_auth_exists(&self) -> bool {
        let path = std::path::Path::new(&self.config.auth_path);
        path.exists()
    }

    /// Toggle auto consultation
    pub fn toggle_auto_consult(&mut self, enable: Option<bool>) -> bool {
        match enable {
            Some(val) => self.config.auto_consult = val,
            None => self.config.auto_consult = !self.config.auto_consult,
        }
        self.config.auto_consult
    }
}

// Bridge to the shared AiIntegration trait
#[async_trait::async_trait]
impl mcp_ai_consult::AiIntegration for CodexIntegration {
    fn name(&self) -> &str {
        "Codex"
    }

    fn enabled(&self) -> bool {
        self.config.enabled
    }

    fn auto_consult(&self) -> bool {
        self.config.auto_consult
    }

    fn toggle_auto_consult(&mut self, enable: Option<bool>) -> bool {
        CodexIntegration::toggle_auto_consult(self, enable)
    }

    async fn consult(
        &mut self,
        params: mcp_ai_consult::ConsultParams,
    ) -> mcp_ai_consult::ConsultResult {
        let mode = params
            .mode
            .as_deref()
            .map(ConsultMode::from_str)
            .unwrap_or_default();
        let local = self
            .consult_impl(
                &params.query,
                &params.context,
                mode,
                params.comparison_mode,
                params.force,
            )
            .await;
        match local.status {
            ConsultStatus::Success => {
                mcp_ai_consult::ConsultResult::success(local.output.unwrap_or_default(), 0.0)
            },
            ConsultStatus::Error => {
                mcp_ai_consult::ConsultResult::error(local.error.unwrap_or_default(), 0.0)
            },
            ConsultStatus::Disabled => mcp_ai_consult::ConsultResult::disabled(),
        }
    }

    fn clear_history(&mut self) -> usize {
        let count = self.history.len();
        self.history.clear();
        count
    }

    fn history_len(&self) -> usize {
        self.history.len()
    }

    fn snapshot_stats(&self) -> mcp_ai_consult::IntegrationStats {
        mcp_ai_consult::IntegrationStats {
            consultations: self.stats.consultations,
            completed: 0,
            errors: self.stats.errors,
            total_execution_time: 0.0,
            last_consultation: self.stats.last_consultation,
        }
    }
}

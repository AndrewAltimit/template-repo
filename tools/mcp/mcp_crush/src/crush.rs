// Allow collapsible_if - clippy suggests let-chains which require nightly
#![allow(clippy::collapsible_if)]

//! Crush CLI integration module.

use chrono::Utc;
use std::path::Path;
use std::process::Stdio;
use std::time::Instant;
use tokio::process::Command;
use tokio::time::{timeout, Duration};
use tracing::{debug, info};

use crate::types::{ConsultResult, CrushConfig, CrushStats, HistoryEntry};

/// Crush CLI integration
pub struct CrushIntegration {
    config: CrushConfig,
    history: Vec<HistoryEntry>,
    stats: CrushStats,
    consultation_counter: u64,
}

impl CrushIntegration {
    /// Create a new Crush integration
    pub fn new(config: CrushConfig) -> Self {
        Self {
            config,
            history: Vec::new(),
            stats: CrushStats::default(),
            consultation_counter: 0,
        }
    }

    /// Consult Crush for code generation
    pub async fn consult(&mut self, query: &str, force: bool) -> ConsultResult {
        self.consultation_counter += 1;
        let consultation_id = format!(
            "crush_{}_{}_{}",
            Utc::now().timestamp(),
            self.consultation_counter,
            self.stats.consultations
        );

        self.stats.consultations += 1;
        self.stats.last_consultation = Some(Utc::now());

        // Check if enabled
        if !self.config.enabled && !force {
            return ConsultResult::disabled(consultation_id);
        }

        // Check if API key is configured
        if self.config.api_key.is_empty() {
            return ConsultResult::error(
                "OPENROUTER_API_KEY not configured. Please set it in environment variables.",
                consultation_id,
            );
        }

        // Prepare full query with history
        let full_query = self.prepare_query(query);

        // Execute Crush CLI
        let result = self.execute_crush(&full_query).await;

        match result {
            Ok((output, execution_time)) => {
                self.stats.completed += 1;
                self.stats.total_execution_time += execution_time;

                // Add to history
                if self.config.include_history {
                    self.add_to_history(query, &output);
                }

                if self.config.log_consultations {
                    info!(
                        "Crush consultation completed: id={}, time={:.2}s",
                        consultation_id, execution_time
                    );
                }

                ConsultResult::success(output, execution_time, consultation_id)
            }
            Err(e) => {
                self.stats.errors += 1;

                if e.contains("timed out") {
                    ConsultResult::timeout(self.config.timeout_secs, consultation_id)
                } else {
                    ConsultResult::error(e, consultation_id)
                }
            }
        }
    }

    /// Execute Crush CLI command
    async fn execute_crush(&self, query: &str) -> Result<(String, f64), String> {
        let start = Instant::now();

        // Check if we're running in a container
        if self.is_running_in_container() {
            debug!("Running in container, using direct crush execution");
            return self.execute_crush_direct(query, start).await;
        }

        // Check if crush is available locally
        if self.is_crush_available().await {
            debug!("Crush found locally, using local execution");
            return self.execute_crush_local(query, start).await;
        }

        // Fall back to Docker execution
        debug!("Using Docker execution");
        self.execute_crush_docker(query, start).await
    }

    /// Execute Crush directly (when in container)
    async fn execute_crush_direct(
        &self,
        query: &str,
        start: Instant,
    ) -> Result<(String, f64), String> {
        let mut args = vec!["run".to_string()];

        if self.config.quiet_mode {
            args.push("-q".to_string());
        }

        args.push(query.to_string());

        debug!("Executing crush with args: {:?}", args);

        let mut cmd = Command::new("crush");
        cmd.args(&args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        // Set environment
        cmd.env("OPENROUTER_API_KEY", &self.config.api_key);
        cmd.env("OPENAI_API_KEY", &self.config.api_key);
        cmd.env("HOME", "/home/node");
        cmd.env("TERM", "dumb");
        cmd.env("NO_COLOR", "1");

        // Run from workspace directory
        cmd.current_dir("/home/node/workspace");

        let child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Crush process: {}", e))?;

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(|e| format!("Crush execution failed: {}", e))?;
                let execution_time = start.elapsed().as_secs_f64();

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    let error_msg = if stderr.is_empty() {
                        format!("Crush failed with exit code {:?}", output.status.code())
                    } else {
                        stderr.to_string()
                    };
                    return Err(error_msg);
                }

                let stdout = String::from_utf8_lossy(&output.stdout);
                Ok((stdout.trim().to_string(), execution_time))
            }
            Err(_) => Err(format!(
                "Crush timed out after {} seconds",
                self.config.timeout_secs
            )),
        }
    }

    /// Execute Crush locally (when not in container)
    async fn execute_crush_local(
        &self,
        query: &str,
        start: Instant,
    ) -> Result<(String, f64), String> {
        let mut args = vec!["run".to_string()];

        if self.config.quiet_mode {
            args.push("-q".to_string());
        }

        args.push(query.to_string());

        debug!("Executing crush locally with args: {:?}", args);

        let mut cmd = Command::new("crush");
        cmd.args(&args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        // Set environment
        cmd.env("OPENROUTER_API_KEY", &self.config.api_key);
        cmd.env("OPENAI_API_KEY", &self.config.api_key);
        cmd.env("TERM", "dumb");
        cmd.env("NO_COLOR", "1");

        let child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Crush process: {}", e))?;

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(|e| format!("Crush execution failed: {}", e))?;
                let execution_time = start.elapsed().as_secs_f64();

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    let error_msg = if stderr.is_empty() {
                        format!("Crush failed with exit code {:?}", output.status.code())
                    } else {
                        stderr.to_string()
                    };
                    return Err(error_msg);
                }

                let stdout = String::from_utf8_lossy(&output.stdout);
                Ok((stdout.trim().to_string(), execution_time))
            }
            Err(_) => Err(format!(
                "Crush timed out after {} seconds",
                self.config.timeout_secs
            )),
        }
    }

    /// Execute Crush via Docker
    async fn execute_crush_docker(
        &self,
        query: &str,
        start: Instant,
    ) -> Result<(String, f64), String> {
        let mut args = vec![
            "run".to_string(),
            "--rm".to_string(),
            "-e".to_string(),
            format!("OPENROUTER_API_KEY={}", self.config.api_key),
            "-e".to_string(),
            format!("OPENAI_API_KEY={}", self.config.api_key),
            self.config.docker_service.clone(),
            "crush".to_string(),
            "run".to_string(),
        ];

        if self.config.quiet_mode {
            args.push("-q".to_string());
        }

        args.push(query.to_string());

        debug!("Executing docker compose with args: {:?}", args);

        // Use docker compose (V2) instead of docker-compose (V1)
        let mut cmd = Command::new("docker");
        cmd.arg("compose").args(&args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Docker process: {}", e))?;

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(|e| format!("Docker execution failed: {}", e))?;
                let execution_time = start.elapsed().as_secs_f64();

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    let error_msg = if stderr.is_empty() {
                        format!(
                            "Crush container failed with exit code {:?}",
                            output.status.code()
                        )
                    } else {
                        stderr.to_string()
                    };
                    return Err(error_msg);
                }

                let stdout = String::from_utf8_lossy(&output.stdout);
                Ok((stdout.trim().to_string(), execution_time))
            }
            Err(_) => Err(format!(
                "Crush timed out after {} seconds",
                self.config.timeout_secs
            )),
        }
    }

    /// Check if running in a Docker container
    fn is_running_in_container(&self) -> bool {
        // Check for .dockerenv file
        if Path::new("/.dockerenv").exists() {
            return true;
        }

        // Check for Docker in cgroup
        if let Ok(content) = std::fs::read_to_string("/proc/1/cgroup") {
            if content.contains("docker") {
                return true;
            }
        }

        false
    }

    /// Check if crush CLI is available locally
    async fn is_crush_available(&self) -> bool {
        match Command::new("which").arg("crush").output().await {
            Ok(output) => output.status.success(),
            Err(_) => false,
        }
    }

    /// Prepare the full query for Crush
    fn prepare_query(&self, query: &str) -> String {
        // If no history or history disabled, just return the query (possibly truncated)
        if !self.config.include_history || self.history.is_empty() {
            if query.len() > self.config.max_prompt_length {
                return format!("{}... [truncated]", &query[..self.config.max_prompt_length]);
            }
            return query.to_string();
        }

        // Build prompt with history
        let mut parts = Vec::new();

        parts.push("Previous context:".to_string());

        // Add last 3 exchanges
        let start = self.history.len().saturating_sub(3);
        for entry in &self.history[start..] {
            let q = if entry.query.len() > 100 {
                format!("{}...", &entry.query[..100])
            } else {
                entry.query.clone()
            };
            parts.push(format!("Q: {}", q));

            let a = if entry.response.len() > 200 {
                format!("{}...", &entry.response[..200])
            } else {
                entry.response.clone()
            };
            parts.push(format!("A: {}", a));
            parts.push(String::new());
        }

        parts.push("Current question:".to_string());
        parts.push(query.to_string());

        let full_prompt = parts.join("\n");

        // Truncate if too long
        if full_prompt.len() > self.config.max_prompt_length {
            if query.len() > self.config.max_prompt_length {
                return format!("{}... [truncated]", &query[..self.config.max_prompt_length]);
            }
            return query.to_string();
        }

        full_prompt
    }

    /// Add an interaction to history
    fn add_to_history(&mut self, query: &str, response: &str) {
        self.history.push(HistoryEntry {
            query: query.to_string(),
            response: response.to_string(),
        });

        // Trim history if it exceeds max size
        let max = self.config.max_history_entries;
        if self.history.len() > max {
            self.history = self.history.split_off(self.history.len() - max);
        }
    }

    /// Clear conversation history
    pub fn clear_history(&mut self) -> usize {
        let count = self.history.len();
        self.history.clear();
        count
    }

    /// Get current statistics
    pub fn stats(&self) -> &CrushStats {
        &self.stats
    }

    /// Get history size
    pub fn history_size(&self) -> usize {
        self.history.len()
    }

    /// Get the configuration
    pub fn config(&self) -> &CrushConfig {
        &self.config
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

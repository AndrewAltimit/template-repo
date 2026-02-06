//! Gemini CLI integration module.

use chrono::Utc;
use std::process::Stdio;
use std::time::Instant;
use tokio::process::Command;
use tokio::time::{Duration, timeout};
use tracing::{debug, info};

use crate::types::{ConsultResult, ConsultStatus, GeminiConfig, GeminiStats, HistoryEntry};

/// Gemini CLI integration
pub struct GeminiIntegration {
    config: GeminiConfig,
    history: Vec<HistoryEntry>,
    stats: GeminiStats,
    last_consultation_time: Option<Instant>,
    consultation_counter: u64,
}

impl GeminiIntegration {
    /// Create a new Gemini integration
    pub fn new(config: GeminiConfig) -> Self {
        Self {
            config,
            history: Vec::new(),
            stats: GeminiStats::default(),
            last_consultation_time: None,
            consultation_counter: 0,
        }
    }

    /// Consult Gemini for a second opinion (internal implementation).
    async fn consult_impl(
        &mut self,
        query: &str,
        context: &str,
        comparison_mode: bool,
        force: bool,
    ) -> ConsultResult {
        self.consultation_counter += 1;
        let consultation_id = format!(
            "consult_{}_{}_{}",
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

        // Rate limiting
        if !force {
            self.enforce_rate_limit().await;
        }

        // Prepare full query
        let full_query = self.prepare_query(query, context, comparison_mode);

        // Execute Gemini CLI
        let result = self.execute_gemini(&full_query).await;

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
                        "Gemini consultation completed: id={}, time={:.2}s",
                        consultation_id, execution_time
                    );
                }

                ConsultResult::success(output, execution_time, consultation_id)
            },
            Err(e) => {
                self.stats.errors += 1;

                if e.contains("timed out") {
                    ConsultResult::timeout(self.config.timeout_secs, consultation_id)
                } else {
                    ConsultResult::error(e, consultation_id)
                }
            },
        }
    }

    /// Execute Gemini CLI command
    async fn execute_gemini(&self, query: &str) -> Result<(String, f64), String> {
        let start = Instant::now();

        if self.config.use_container {
            self.execute_gemini_container(query, start).await
        } else {
            self.execute_gemini_direct(query, start).await
        }
    }

    /// Execute Gemini CLI directly on the host
    async fn execute_gemini_direct(
        &self,
        query: &str,
        start: Instant,
    ) -> Result<(String, f64), String> {
        let mut args = vec!["prompt".to_string()];

        // Add model if specified
        if let Some(ref model) = self.config.model {
            args.extend(["--model".to_string(), model.clone()]);
        }

        args.extend(["--output-format".to_string(), "text".to_string()]);

        debug!("Executing gemini with args: {:?}", args);

        let mut cmd = Command::new(&self.config.cli_command);
        cmd.args(&args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        // Add API key to environment if available
        if let Ok(api_key) = std::env::var("GOOGLE_API_KEY") {
            cmd.env("GOOGLE_API_KEY", api_key);
        } else if let Ok(api_key) = std::env::var("GEMINI_API_KEY") {
            cmd.env("GOOGLE_API_KEY", api_key);
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Gemini process: {}", e))?;

        // Write query to stdin
        if let Some(mut stdin) = child.stdin.take() {
            use tokio::io::AsyncWriteExt;
            stdin
                .write_all(query.as_bytes())
                .await
                .map_err(|e| format!("Failed to write to stdin: {}", e))?;
            stdin
                .shutdown()
                .await
                .map_err(|e| format!("Failed to close stdin: {}", e))?;
        }

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(|e| format!("Gemini execution failed: {}", e))?;
                let execution_time = start.elapsed().as_secs_f64();

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    let error_msg = if stderr.is_empty() {
                        "Gemini CLI failed".to_string()
                    } else if stderr.to_lowercase().contains("authentication")
                        || stderr.to_lowercase().contains("login required")
                    {
                        "Gemini authentication required. Please run 'gemini' interactively to complete authentication.".to_string()
                    } else {
                        stderr.to_string()
                    };
                    return Err(error_msg);
                }

                let stdout = String::from_utf8_lossy(&output.stdout);
                let stdout_str = stdout.trim();

                // Check for authentication messages in stdout
                if stdout_str.to_lowercase().contains("login required")
                    || stdout_str
                        .to_lowercase()
                        .contains("waiting for authentication")
                {
                    return Err("Gemini authentication required. Please run 'gemini' interactively to complete authentication.".to_string());
                }

                Ok((stdout_str.to_string(), execution_time))
            },
            Err(_) => Err(format!(
                "Gemini CLI timed out after {} seconds",
                self.config.timeout_secs
            )),
        }
    }

    /// Execute Gemini through Docker container
    async fn execute_gemini_container(
        &self,
        query: &str,
        start: Instant,
    ) -> Result<(String, f64), String> {
        // Prepare temporary .gemini directory
        let temp_gemini_dir = self.prepare_gemini_temp_dir()?;

        // Build docker command
        let args = self.build_docker_command(&temp_gemini_dir);

        debug!("Executing docker with args: {:?}", args);

        let mut cmd = Command::new("docker");
        cmd.args(&args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Docker process: {}", e))?;

        // Write query to stdin
        if let Some(mut stdin) = child.stdin.take() {
            use tokio::io::AsyncWriteExt;
            stdin
                .write_all(query.as_bytes())
                .await
                .map_err(|e| format!("Failed to write to stdin: {}", e))?;
            stdin
                .shutdown()
                .await
                .map_err(|e| format!("Failed to close stdin: {}", e))?;
        }

        let timeout_duration = Duration::from_secs(self.config.timeout_secs);

        let result = match timeout(timeout_duration, child.wait_with_output()).await {
            Ok(result) => {
                let output = result.map_err(|e| format!("Container execution failed: {}", e))?;
                let execution_time = start.elapsed().as_secs_f64();

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    let error_msg = self.handle_container_error(&stderr);
                    return Err(error_msg);
                }

                let stdout = String::from_utf8_lossy(&output.stdout);
                let stdout_str = stdout.trim();

                // Check for authentication messages
                if stdout_str.to_lowercase().contains("login required")
                    || stdout_str
                        .to_lowercase()
                        .contains("waiting for authentication")
                {
                    return Err("Gemini authentication required. Please ensure ~/.gemini exists on the host with valid authentication.".to_string());
                }

                Ok((stdout_str.to_string(), execution_time))
            },
            Err(_) => Err(format!(
                "Gemini container execution timed out after {} seconds",
                self.config.timeout_secs
            )),
        };

        // Clean up temp directory
        let _ = std::fs::remove_dir_all(&temp_gemini_dir);

        result
    }

    /// Prepare temporary .gemini directory for container
    fn prepare_gemini_temp_dir(&self) -> Result<String, String> {
        let temp_dir = std::env::temp_dir()
            .join(format!("gemini_{}", std::process::id()))
            .to_string_lossy()
            .to_string();

        std::fs::create_dir_all(&temp_dir)
            .map_err(|e| format!("Failed to create temp dir: {}", e))?;

        // Copy ~/.gemini contents if it exists
        if let Some(home) = dirs::home_dir() {
            let src_gemini = home.join(".gemini");
            if src_gemini.exists() {
                self.copy_dir_contents(&src_gemini, std::path::Path::new(&temp_dir))
                    .map_err(|e| format!("Failed to copy .gemini: {}", e))?;
            }
        }

        Ok(temp_dir)
    }

    /// Copy directory contents recursively
    fn copy_dir_contents(
        &self,
        src: &std::path::Path,
        dst: &std::path::Path,
    ) -> std::io::Result<()> {
        for entry in std::fs::read_dir(src)? {
            let entry = entry?;
            let src_path = entry.path();
            let dst_path = dst.join(entry.file_name());

            if src_path.is_dir() {
                std::fs::create_dir_all(&dst_path)?;
                self.copy_dir_contents(&src_path, &dst_path)?;
            } else {
                std::fs::copy(&src_path, &dst_path)?;
            }
        }
        Ok(())
    }

    /// Build Docker command for container execution
    fn build_docker_command(&self, temp_gemini_dir: &str) -> Vec<String> {
        let uid = unsafe { libc::getuid() };
        let gid = unsafe { libc::getgid() };

        let mut args = vec![
            "run".to_string(),
            "--rm".to_string(),
            "-i".to_string(),
            "-u".to_string(),
            format!("{}:{}", uid, gid),
            "-v".to_string(),
            format!("{}:/home/node/.gemini", temp_gemini_dir),
            "-v".to_string(),
            format!(
                "{}:/workspace",
                std::env::current_dir().unwrap_or_default().display()
            ),
        ];

        if self.config.yolo_mode {
            args.extend(["-e".to_string(), "GEMINI_APPROVAL_MODE=yolo".to_string()]);
        }

        args.push(self.config.container_image.clone());
        args.push("prompt".to_string());

        if let Some(ref model) = self.config.model {
            args.extend(["--model".to_string(), model.clone()]);
        }

        args.extend(["--output-format".to_string(), "text".to_string()]);

        args
    }

    /// Handle container error and return user-friendly message
    fn handle_container_error(&self, stderr: &str) -> String {
        let stderr_lower = stderr.to_lowercase();

        if stderr_lower.contains("authentication") || stderr_lower.contains("login required") {
            "Gemini authentication required. Please ensure ~/.gemini exists on the host with valid authentication.".to_string()
        } else if stderr_lower.contains("docker") && stderr_lower.contains("not found") {
            "Docker is not installed or not in PATH. Container mode requires Docker.".to_string()
        } else if stderr_lower.contains("no such image") {
            format!(
                "Container image '{}' not found. Please build or pull it first.",
                self.config.container_image
            )
        } else if stderr.is_empty() {
            "Gemini container execution failed".to_string()
        } else {
            stderr.to_string()
        }
    }

    /// Prepare the full query for Gemini
    fn prepare_query(&self, query: &str, context: &str, comparison_mode: bool) -> String {
        let mut parts = Vec::new();

        if comparison_mode {
            parts.push("Please analyze the following:".to_string());
            parts.push(String::new());
        }

        // Include conversation history if enabled
        if self.config.include_history && !self.history.is_empty() {
            parts.push("Previous conversation:".to_string());
            parts.push("-".repeat(40));

            let start = self
                .history
                .len()
                .saturating_sub(self.config.max_history_entries);

            for (i, entry) in self.history[start..].iter().enumerate() {
                parts.push(format!("Q{}: {}", i + 1, entry.query));

                // Truncate long responses
                let response = if entry.response.len() > 500 {
                    format!("{}... [truncated]", &entry.response[..500])
                } else {
                    entry.response.clone()
                };
                parts.push(format!("A{}: {}", i + 1, response));
                parts.push(String::new());
            }

            parts.push("-".repeat(40));
            parts.push(String::new());
        }

        // Add context if provided (truncate if too long)
        let context_to_add = if context.len() > self.config.max_context_length {
            format!(
                "{}\n[Context truncated...]",
                &context[..self.config.max_context_length]
            )
        } else {
            context.to_string()
        };

        if !context_to_add.is_empty() {
            parts.push("Context:".to_string());
            parts.push(context_to_add);
            parts.push(String::new());
        }

        parts.push(query.to_string());

        if comparison_mode {
            parts.push(String::new());
            parts.push("Please include analysis, recommendations, and any concerns.".to_string());
        }

        parts.join("\n")
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

    /// Enforce rate limiting between consultations
    async fn enforce_rate_limit(&mut self) {
        if let Some(last_time) = self.last_consultation_time {
            let elapsed = last_time.elapsed().as_secs_f64();
            if elapsed < self.config.rate_limit_delay {
                let sleep_time = self.config.rate_limit_delay - elapsed;
                tokio::time::sleep(Duration::from_secs_f64(sleep_time)).await;
            }
        }
        self.last_consultation_time = Some(Instant::now());
    }

    /// Clear conversation history
    pub fn clear_history(&mut self) -> usize {
        let count = self.history.len();
        self.history.clear();
        count
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
impl mcp_ai_consult::AiIntegration for GeminiIntegration {
    fn name(&self) -> &str {
        "Gemini"
    }

    fn enabled(&self) -> bool {
        self.config.enabled
    }

    fn auto_consult(&self) -> bool {
        self.config.auto_consult
    }

    fn toggle_auto_consult(&mut self, enable: Option<bool>) -> bool {
        GeminiIntegration::toggle_auto_consult(self, enable)
    }

    async fn consult(
        &mut self,
        params: mcp_ai_consult::ConsultParams,
    ) -> mcp_ai_consult::ConsultResult {
        let local = self
            .consult_impl(
                &params.query,
                &params.context,
                params.comparison_mode,
                params.force,
            )
            .await;
        match local.status {
            ConsultStatus::Success => mcp_ai_consult::ConsultResult::success(
                local.response.unwrap_or_default(),
                local.execution_time,
            ),
            ConsultStatus::Error => mcp_ai_consult::ConsultResult::error(
                local.error.unwrap_or_default(),
                local.execution_time,
            ),
            ConsultStatus::Disabled => mcp_ai_consult::ConsultResult::disabled(),
            ConsultStatus::Timeout => mcp_ai_consult::ConsultResult::timeout(local.execution_time),
        }
    }

    fn clear_history(&mut self) -> usize {
        GeminiIntegration::clear_history(self)
    }

    fn history_len(&self) -> usize {
        self.history.len()
    }

    fn snapshot_stats(&self) -> mcp_ai_consult::IntegrationStats {
        let s = &self.stats;
        mcp_ai_consult::IntegrationStats {
            consultations: s.consultations,
            completed: s.completed,
            errors: s.errors,
            total_execution_time: s.total_execution_time,
            last_consultation: s.last_consultation,
        }
    }
}

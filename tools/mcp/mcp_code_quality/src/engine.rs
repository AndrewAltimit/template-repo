//! Code quality engine for running external tools.

use crate::types::{
    AuditEntry, Language, Linter, RateLimitConfig, Severity, ToolResult, ToolStatus,
};
use chrono::Utc;
use dashmap::DashMap;
use serde_json::json;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::process::Command;
use tracing::{debug, error, info};

/// Default timeout for subprocess operations (10 minutes)
pub const DEFAULT_TIMEOUT_SECS: u64 = 600;

/// Code quality engine
pub struct CodeQualityEngine {
    timeout: Duration,
    allowed_paths: Vec<PathBuf>,
    audit_log_path: PathBuf,
    rate_limiting_enabled: bool,
    rate_limit_tracker: Arc<DashMap<String, Vec<Instant>>>,
    rate_limits: HashMap<String, RateLimitConfig>,
}

impl CodeQualityEngine {
    /// Create a new code quality engine
    pub fn new(
        timeout_secs: u64,
        allowed_paths: Vec<String>,
        audit_log_path: PathBuf,
        rate_limiting_enabled: bool,
    ) -> Self {
        let allowed_paths: Vec<PathBuf> = allowed_paths.into_iter().map(PathBuf::from).collect();

        // Initialize rate limits
        let mut rate_limits = HashMap::new();
        rate_limits.insert(
            "format_check".to_string(),
            RateLimitConfig {
                calls: 100,
                period_secs: 60,
            },
        );
        rate_limits.insert(
            "lint".to_string(),
            RateLimitConfig {
                calls: 50,
                period_secs: 60,
            },
        );
        rate_limits.insert(
            "autoformat".to_string(),
            RateLimitConfig {
                calls: 50,
                period_secs: 60,
            },
        );
        rate_limits.insert(
            "run_tests".to_string(),
            RateLimitConfig {
                calls: 20,
                period_secs: 60,
            },
        );
        rate_limits.insert(
            "type_check".to_string(),
            RateLimitConfig {
                calls: 30,
                period_secs: 60,
            },
        );
        rate_limits.insert(
            "security_scan".to_string(),
            RateLimitConfig {
                calls: 20,
                period_secs: 60,
            },
        );
        rate_limits.insert(
            "audit_dependencies".to_string(),
            RateLimitConfig {
                calls: 10,
                period_secs: 60,
            },
        );
        rate_limits.insert(
            "check_markdown_links".to_string(),
            RateLimitConfig {
                calls: 30,
                period_secs: 60,
            },
        );

        // Ensure audit log directory exists
        if let Some(parent) = audit_log_path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }

        Self {
            timeout: Duration::from_secs(timeout_secs),
            allowed_paths,
            audit_log_path,
            rate_limiting_enabled,
            rate_limit_tracker: Arc::new(DashMap::new()),
            rate_limits,
        }
    }

    /// Validate that a path is within allowed directories
    fn validate_path(&self, path: &str) -> bool {
        let path = match Path::new(path).canonicalize() {
            Ok(p) => p,
            Err(_) => {
                // Path doesn't exist, try to canonicalize parent
                let p = Path::new(path);
                if let Some(parent) = p.parent() {
                    if let Ok(canonical_parent) = parent.canonicalize() {
                        if let Some(file_name) = p.file_name() {
                            canonical_parent.join(file_name)
                        } else {
                            return false;
                        }
                    } else {
                        return false;
                    }
                } else {
                    return false;
                }
            },
        };

        for allowed in &self.allowed_paths {
            if let Ok(allowed_canonical) = allowed.canonicalize()
                && path.starts_with(&allowed_canonical)
            {
                return true;
            }
            // Also check non-canonical paths
            if path.starts_with(allowed) {
                return true;
            }
        }
        false
    }

    /// Check rate limiting for an operation
    fn check_rate_limit(&self, operation: &str) -> bool {
        if !self.rate_limiting_enabled {
            return true;
        }

        let config = self.rate_limits.get(operation).copied().unwrap_or_default();

        let now = Instant::now();
        let window = Duration::from_secs(config.period_secs);

        let mut entry = self
            .rate_limit_tracker
            .entry(operation.to_string())
            .or_default();
        let timestamps = entry.value_mut();

        // Clean old entries
        timestamps.retain(|t| now.duration_since(*t) < window);

        // Check limit
        if timestamps.len() >= config.calls {
            return false;
        }

        // Record this call
        timestamps.push(now);
        true
    }

    /// Write an audit log entry
    fn audit_log(&self, operation: &str, path: &str, success: bool, details: serde_json::Value) {
        let entry = AuditEntry {
            timestamp: Utc::now().to_rfc3339(),
            operation: operation.to_string(),
            path: path.to_string(),
            success,
            details,
        };

        if let Ok(line) = serde_json::to_string(&entry)
            && let Ok(mut file) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.audit_log_path)
        {
            use std::io::Write;
            let _ = writeln!(file, "{}", line);
        }
    }

    /// Run a subprocess with timeout
    async fn run_subprocess(
        &self,
        args: &[&str],
        cwd: Option<&str>,
    ) -> Result<(i32, String, String), String> {
        if args.is_empty() {
            return Err("Empty command".to_string());
        }

        let program = args[0];
        let cmd_args = &args[1..];

        debug!("Running: {} {:?}", program, cmd_args);

        let mut cmd = Command::new(program);
        cmd.args(cmd_args);

        if let Some(dir) = cwd {
            cmd.current_dir(dir);
        }

        let output = tokio::time::timeout(self.timeout, cmd.output())
            .await
            .map_err(|_| format!("Command timed out after {}s", self.timeout.as_secs()))?
            .map_err(|e| format!("Failed to run command: {}", e))?;

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();

        Ok((output.status.code().unwrap_or(-1), stdout, stderr))
    }

    /// Check code formatting
    pub async fn format_check(&self, path: &str, language: Language) -> ToolResult {
        if !self.check_rate_limit("format_check") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(path) {
            self.audit_log(
                "format_check",
                path,
                false,
                json!({"reason": "path_not_allowed"}),
            );
            let mut result =
                ToolResult::error(format!("Path not allowed: {}", path), "path_validation");
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        let cmd: Vec<&str> = match language {
            Language::Python => vec!["black", "--check", path],
            Language::Javascript | Language::Typescript => vec!["prettier", "--check", path],
            Language::Go => vec!["gofmt", "-l", path],
            Language::Rust => vec!["rustfmt", "--check", path],
        };

        info!("Checking {} formatting for: {}", language.as_str(), path);

        match self.run_subprocess(&cmd, None).await {
            Ok((code, stdout, stderr)) => {
                let formatted = code == 0;
                self.audit_log(
                    "format_check",
                    path,
                    true,
                    json!({"language": language.as_str(), "formatted": formatted}),
                );

                let mut result = ToolResult::success();
                result.formatted = Some(formatted);
                result.output = Some(if stdout.is_empty() { stderr } else { stdout });
                result.command = Some(cmd.join(" "));
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log("format_check", path, false, json!({"reason": "timeout"}));
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "format_check",
                        path,
                        false,
                        json!({"reason": "tool_not_found", "tool": cmd[0]}),
                    );
                    ToolResult::error(
                        format!("{} not found. Please install it first.", cmd[0]),
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "format_check",
                        path,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Run code linting
    pub async fn lint(&self, path: &str, config: Option<&str>, linter: Linter) -> ToolResult {
        if !self.check_rate_limit("lint") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(path) {
            self.audit_log("lint", path, false, json!({"reason": "path_not_allowed"}));
            let mut result =
                ToolResult::error(format!("Path not allowed: {}", path), "path_validation");
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        if let Some(cfg) = config
            && !self.validate_path(cfg)
        {
            return ToolResult::error(
                format!("Config path not allowed: {}", cfg),
                "path_validation",
            );
        }

        let (cmd, cwd): (Vec<String>, Option<&str>) = match linter {
            Linter::Flake8 => (vec!["flake8".to_string(), path.to_string()], None),
            Linter::Ruff => (
                vec!["ruff".to_string(), "check".to_string(), path.to_string()],
                None,
            ),
            Linter::Eslint => (vec!["eslint".to_string(), path.to_string()], None),
            Linter::Golint => (vec!["golint".to_string(), path.to_string()], None),
            // Clippy needs to run in the target directory where Cargo.toml is located
            Linter::Clippy => (vec!["cargo".to_string(), "clippy".to_string()], Some(path)),
        };

        let mut cmd = cmd;

        // Add config file if provided
        if let Some(cfg) = config {
            match linter {
                Linter::Flake8 | Linter::Ruff | Linter::Eslint => {
                    cmd.push("--config".to_string());
                    cmd.push(cfg.to_string());
                },
                _ => {},
            }
        }

        info!("Running {} on: {}", linter.as_str(), path);

        let cmd_refs: Vec<&str> = cmd.iter().map(|s| s.as_str()).collect();

        match self.run_subprocess(&cmd_refs, cwd).await {
            Ok((code, stdout, _stderr)) => {
                let issues: Vec<String> = stdout.lines().map(|s| s.to_string()).collect();
                let passed = code == 0;

                self.audit_log(
                    "lint",
                    path,
                    passed,
                    json!({"linter": linter.as_str(), "issue_count": issues.len()}),
                );

                let mut result = ToolResult::success();
                result.passed = Some(passed);
                result.issue_count = Some(issues.len());
                result.issues = Some(issues);
                result.command = Some(cmd.join(" "));
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log("lint", path, false, json!({"reason": "timeout"}));
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "lint",
                        path,
                        false,
                        json!({"reason": "tool_not_found", "tool": linter.as_str()}),
                    );
                    ToolResult::error(
                        format!("{} not found. Please install it first.", linter.as_str()),
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "lint",
                        path,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Auto-format code
    pub async fn autoformat(&self, path: &str, language: Language) -> ToolResult {
        if !self.check_rate_limit("autoformat") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(path) {
            self.audit_log(
                "autoformat",
                path,
                false,
                json!({"reason": "path_not_allowed"}),
            );
            let mut result =
                ToolResult::error(format!("Path not allowed: {}", path), "path_validation");
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        let cmd: Vec<&str> = match language {
            Language::Python => vec!["black", path],
            Language::Javascript | Language::Typescript => vec!["prettier", "--write", path],
            Language::Go => vec!["gofmt", "-w", path],
            Language::Rust => vec!["rustfmt", path],
        };

        info!("Auto-formatting {} code in: {}", language.as_str(), path);

        match self.run_subprocess(&cmd, None).await {
            Ok((code, stdout, stderr)) => {
                let success = code == 0;
                self.audit_log(
                    "autoformat",
                    path,
                    success,
                    json!({"language": language.as_str()}),
                );

                let mut result = ToolResult::success();
                result.success = success;
                result.formatted = Some(true);
                result.output = Some(if stdout.is_empty() { stderr } else { stdout });
                result.command = Some(cmd.join(" "));
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log("autoformat", path, false, json!({"reason": "timeout"}));
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "autoformat",
                        path,
                        false,
                        json!({"reason": "tool_not_found", "tool": cmd[0]}),
                    );
                    ToolResult::error(
                        format!("{} not found. Please install it first.", cmd[0]),
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "autoformat",
                        path,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Run pytest tests
    #[allow(clippy::too_many_arguments)]
    pub async fn run_tests(
        &self,
        path: &str,
        pattern: Option<&str>,
        verbose: bool,
        coverage: bool,
        fail_fast: bool,
        markers: Option<&str>,
    ) -> ToolResult {
        if !self.check_rate_limit("run_tests") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(path) {
            self.audit_log(
                "run_tests",
                path,
                false,
                json!({"reason": "path_not_allowed"}),
            );
            let mut result =
                ToolResult::error(format!("Path not allowed: {}", path), "path_validation");
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        let mut cmd: Vec<String> = vec!["pytest".to_string(), path.to_string()];

        if verbose {
            cmd.push("-v".to_string());
        }
        if fail_fast {
            cmd.push("-x".to_string());
        }
        if coverage {
            cmd.push("--cov=.".to_string());
            cmd.push("--cov-report=term-missing".to_string());
        }
        if let Some(p) = pattern {
            cmd.push("-k".to_string());
            cmd.push(p.to_string());
        }
        if let Some(m) = markers {
            cmd.push("-m".to_string());
            cmd.push(m.to_string());
        }

        info!("Running tests: {}", cmd.join(" "));

        let cmd_refs: Vec<&str> = cmd.iter().map(|s| s.as_str()).collect();

        match self.run_subprocess(&cmd_refs, None).await {
            Ok((code, stdout, stderr)) => {
                let passed = code == 0;
                self.audit_log("run_tests", path, passed, json!({"returncode": code}));

                let mut result = ToolResult::success();
                result.passed = Some(passed);
                result.returncode = Some(code);
                result.output = Some(format!("{}{}", stdout, stderr));
                result.command = Some(cmd.join(" "));
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log("run_tests", path, false, json!({"reason": "timeout"}));
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "run_tests",
                        path,
                        false,
                        json!({"reason": "tool_not_found", "tool": "pytest"}),
                    );
                    ToolResult::error(
                        "pytest not found. Please install it first.",
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "run_tests",
                        path,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Run type checking with ty
    pub async fn type_check(&self, path: &str, config: Option<&str>) -> ToolResult {
        if !self.check_rate_limit("type_check") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(path) {
            self.audit_log(
                "type_check",
                path,
                false,
                json!({"reason": "path_not_allowed"}),
            );
            let mut result =
                ToolResult::error(format!("Path not allowed: {}", path), "path_validation");
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        if let Some(cfg) = config
            && !self.validate_path(cfg)
        {
            return ToolResult::error(
                format!("Config path not allowed: {}", cfg),
                "path_validation",
            );
        }

        let mut cmd: Vec<String> = vec!["ty".to_string(), "check".to_string(), path.to_string()];

        if let Some(cfg) = config {
            cmd.push("--config".to_string());
            cmd.push(cfg.to_string());
        }

        info!("Running ty on: {}", path);

        let cmd_refs: Vec<&str> = cmd.iter().map(|s| s.as_str()).collect();

        match self.run_subprocess(&cmd_refs, None).await {
            Ok((code, stdout, _stderr)) => {
                let issues: Vec<String> = stdout.lines().map(|s| s.to_string()).collect();
                let passed = code == 0;

                self.audit_log(
                    "type_check",
                    path,
                    passed,
                    json!({"issue_count": issues.len()}),
                );

                let mut result = ToolResult::success();
                result.passed = Some(passed);
                result.issue_count = Some(issues.len());
                result.issues = Some(issues);
                result.command = Some(cmd.join(" "));
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log("type_check", path, false, json!({"reason": "timeout"}));
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "type_check",
                        path,
                        false,
                        json!({"reason": "tool_not_found", "tool": "ty"}),
                    );
                    ToolResult::error(
                        "ty not found. Install with: pip install ty",
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "type_check",
                        path,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Run security scanning with bandit
    pub async fn security_scan(
        &self,
        path: &str,
        severity: Severity,
        confidence: Severity,
    ) -> ToolResult {
        if !self.check_rate_limit("security_scan") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(path) {
            self.audit_log(
                "security_scan",
                path,
                false,
                json!({"reason": "path_not_allowed"}),
            );
            let mut result =
                ToolResult::error(format!("Path not allowed: {}", path), "path_validation");
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        let severity_arg = format!("--severity-level={}", severity.as_str());
        let confidence_arg = format!("--confidence-level={}", confidence.as_str());
        let cmd = vec![
            "bandit",
            "-r",
            path,
            &severity_arg,
            &confidence_arg,
            "-f",
            "json",
        ];

        info!("Running security scan on: {}", path);

        match self.run_subprocess(&cmd, None).await {
            Ok((code, stdout, _stderr)) => {
                let findings: Vec<serde_json::Value> =
                    if let Ok(data) = serde_json::from_str::<serde_json::Value>(&stdout) {
                        data.get("results")
                            .and_then(|r| r.as_array())
                            .cloned()
                            .unwrap_or_default()
                    } else {
                        Vec::new()
                    };

                let passed = code == 0;
                self.audit_log(
                    "security_scan",
                    path,
                    passed,
                    json!({"finding_count": findings.len()}),
                );

                let mut result = ToolResult::success();
                result.passed = Some(passed);
                result.finding_count = Some(findings.len());
                result.findings = Some(findings);
                result.command = Some(cmd.join(" "));
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log("security_scan", path, false, json!({"reason": "timeout"}));
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "security_scan",
                        path,
                        false,
                        json!({"reason": "tool_not_found", "tool": "bandit"}),
                    );
                    ToolResult::error(
                        "bandit not found. Please install it first.",
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "security_scan",
                        path,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Audit dependencies for vulnerabilities
    pub async fn audit_dependencies(&self, requirements_file: &str) -> ToolResult {
        if !self.check_rate_limit("audit_dependencies") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(requirements_file) {
            self.audit_log(
                "audit_dependencies",
                requirements_file,
                false,
                json!({"reason": "path_not_allowed"}),
            );
            let mut result = ToolResult::error(
                format!("Path not allowed: {}", requirements_file),
                "path_validation",
            );
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        let cmd = vec!["pip-audit", "-r", requirements_file, "--format", "json"];

        info!("Auditing dependencies: {}", requirements_file);

        match self.run_subprocess(&cmd, None).await {
            Ok((code, stdout, _stderr)) => {
                let vulnerabilities: Vec<serde_json::Value> =
                    serde_json::from_str(&stdout).unwrap_or_default();

                let passed = code == 0;
                self.audit_log(
                    "audit_dependencies",
                    requirements_file,
                    passed,
                    json!({"vulnerability_count": vulnerabilities.len()}),
                );

                let mut result = ToolResult::success();
                result.passed = Some(passed);
                result.vulnerability_count = Some(vulnerabilities.len());
                result.vulnerabilities = Some(vulnerabilities);
                result.command = Some(cmd.join(" "));
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log(
                        "audit_dependencies",
                        requirements_file,
                        false,
                        json!({"reason": "timeout"}),
                    );
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "audit_dependencies",
                        requirements_file,
                        false,
                        json!({"reason": "tool_not_found", "tool": "pip-audit"}),
                    );
                    ToolResult::error(
                        "pip-audit not found. Please install it first.",
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "audit_dependencies",
                        requirements_file,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Check markdown links using md-link-checker
    #[allow(clippy::too_many_arguments)]
    pub async fn check_markdown_links(
        &self,
        path: &str,
        check_external: bool,
        link_timeout: u32,
        concurrent: u32,
        ignore_patterns: &[String],
    ) -> ToolResult {
        if !self.check_rate_limit("check_markdown_links") {
            return ToolResult::error("Rate limit exceeded", "rate_limit");
        }

        if !self.validate_path(path) {
            self.audit_log(
                "check_markdown_links",
                path,
                false,
                json!({"reason": "path_not_allowed"}),
            );
            let mut result =
                ToolResult::error(format!("Path not allowed: {}", path), "path_validation");
            result.allowed_paths = Some(
                self.allowed_paths
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect(),
            );
            return result;
        }

        let timeout_str = link_timeout.to_string();
        let concurrent_str = concurrent.to_string();

        let mut cmd: Vec<String> = vec![
            "md-link-checker".to_string(),
            path.to_string(),
            "--json".to_string(),
            "--timeout".to_string(),
            timeout_str,
            "--concurrent".to_string(),
            concurrent_str,
        ];

        if !check_external {
            cmd.push("--internal-only".to_string());
        }

        for pattern in ignore_patterns {
            cmd.push(format!("--ignore={}", pattern));
        }

        info!("Checking markdown links in: {}", path);

        let cmd_refs: Vec<&str> = cmd.iter().map(|s| s.as_str()).collect();

        match self.run_subprocess(&cmd_refs, None).await {
            Ok((code, stdout, _stderr)) => {
                // Try to parse JSON output
                let (files_checked, total_links, broken_links, all_valid) =
                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(&stdout) {
                        let files = json
                            .get("files_checked")
                            .and_then(|v| v.as_u64())
                            .map(|v| v as usize);
                        let total = json
                            .get("total_links")
                            .and_then(|v| v.as_u64())
                            .map(|v| v as usize);
                        let broken = json
                            .get("broken_links")
                            .and_then(|v| v.as_u64())
                            .map(|v| v as usize);
                        let valid = json
                            .get("all_valid")
                            .and_then(|v| v.as_bool())
                            .unwrap_or(code == 0);
                        (files, total, broken, valid)
                    } else {
                        (None, None, None, code == 0)
                    };

                self.audit_log(
                    "check_markdown_links",
                    path,
                    all_valid,
                    json!({
                        "files_checked": files_checked,
                        "total_links": total_links,
                        "broken_links": broken_links
                    }),
                );

                let mut result = ToolResult::success();
                result.passed = Some(all_valid);
                result.output = Some(stdout);
                result.command = Some(cmd.join(" "));
                result.files_checked = files_checked;
                result.total_links = total_links;
                result.broken_links = broken_links;
                result
            },
            Err(e) => {
                if e.contains("timed out") {
                    self.audit_log(
                        "check_markdown_links",
                        path,
                        false,
                        json!({"reason": "timeout"}),
                    );
                    ToolResult::error(e, "timeout")
                } else if e.contains("No such file") || e.contains("not found") {
                    self.audit_log(
                        "check_markdown_links",
                        path,
                        false,
                        json!({"reason": "tool_not_found", "tool": "md-link-checker"}),
                    );
                    ToolResult::error(
                        "md-link-checker not found. Install from tools/rust/markdown-link-checker/",
                        "tool_not_found",
                    )
                } else {
                    self.audit_log(
                        "check_markdown_links",
                        path,
                        false,
                        json!({"reason": "exception", "error": &e}),
                    );
                    ToolResult::error(e, "exception")
                }
            },
        }
    }

    /// Get server status with tool availability
    pub async fn get_status(&self) -> serde_json::Value {
        let mut tools = HashMap::new();

        let tool_checks = [
            ("black", vec!["black", "--version"]),
            ("flake8", vec!["flake8", "--version"]),
            ("ruff", vec!["ruff", "--version"]),
            ("ty", vec!["ty", "--version"]),
            ("pytest", vec!["pytest", "--version"]),
            ("bandit", vec!["bandit", "--version"]),
            ("pip-audit", vec!["pip-audit", "--version"]),
            ("prettier", vec!["prettier", "--version"]),
            ("eslint", vec!["eslint", "--version"]),
            ("md-link-checker", vec!["md-link-checker", "--version"]),
        ];

        for (name, cmd) in tool_checks {
            let status = match tokio::time::timeout(Duration::from_secs(10), async {
                self.run_subprocess(&cmd, None).await
            })
            .await
            {
                Ok(Ok((code, stdout, _))) => {
                    let version = stdout.lines().next().unwrap_or("unknown").to_string();
                    ToolStatus {
                        available: code == 0,
                        version: Some(version),
                        reason: None,
                    }
                },
                Ok(Err(e)) => {
                    if e.contains("not found") || e.contains("No such file") {
                        ToolStatus {
                            available: false,
                            version: None,
                            reason: Some("Not installed".to_string()),
                        }
                    } else {
                        ToolStatus {
                            available: false,
                            version: None,
                            reason: Some(e),
                        }
                    }
                },
                Err(_) => ToolStatus {
                    available: false,
                    version: None,
                    reason: Some("Version check timed out".to_string()),
                },
            };
            tools.insert(name.to_string(), status);
        }

        json!({
            "server": "Code Quality MCP Server",
            "version": "2.0.0",
            "timeout_seconds": self.timeout.as_secs(),
            "allowed_paths": self.allowed_paths.iter().map(|p| p.display().to_string()).collect::<Vec<_>>(),
            "rate_limiting_enabled": self.rate_limiting_enabled,
            "audit_log_path": self.audit_log_path.display().to_string(),
            "tools": tools
        })
    }

    /// Get recent audit log entries
    pub async fn get_audit_log(&self, limit: usize, operation: Option<&str>) -> serde_json::Value {
        let entries: Vec<AuditEntry> = if self.audit_log_path.exists() {
            match std::fs::read_to_string(&self.audit_log_path) {
                Ok(content) => content
                    .lines()
                    .filter_map(|line| serde_json::from_str::<AuditEntry>(line).ok())
                    .filter(|e| operation.is_none() || Some(e.operation.as_str()) == operation)
                    .collect::<Vec<_>>()
                    .into_iter()
                    .rev()
                    .take(limit)
                    .collect::<Vec<_>>()
                    .into_iter()
                    .rev()
                    .collect(),
                Err(e) => {
                    error!("Failed to read audit log: {}", e);
                    Vec::new()
                },
            }
        } else {
            Vec::new()
        };

        json!({
            "success": true,
            "entries": entries,
            "count": entries.len(),
            "log_path": self.audit_log_path.display().to_string()
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_path_validation() {
        let engine = CodeQualityEngine::new(
            60,
            vec!["/tmp".to_string(), "/app".to_string()],
            PathBuf::from("/tmp/test-audit.log"),
            false,
        );

        // Note: These paths need to exist for canonicalize to work
        // In real tests, you'd create temp directories
        assert!(engine.validate_path("/tmp"));
    }

    #[test]
    fn test_rate_limiting() {
        let engine = CodeQualityEngine::new(
            60,
            vec!["/tmp".to_string()],
            PathBuf::from("/tmp/test-audit.log"),
            true,
        );

        // First call should succeed
        assert!(engine.check_rate_limit("format_check"));
    }
}

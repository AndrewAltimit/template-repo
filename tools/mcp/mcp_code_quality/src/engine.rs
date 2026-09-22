//! Code quality engine: validates requests, runs external tools, interprets
//! their output, and records every call in the audit log.
//!
//! Every operation follows the same pipeline:
//!
//! 1. rate-limit check,
//! 2. argument validation (paths via [`PathPolicy`], ranges, free text),
//! 3. command construction ([`crate::commands`], pure),
//! 4. bounded execution ([`crate::process::run`]) under a global concurrency
//!    semaphore,
//! 5. output parsing ([`crate::parsers`], pure) into a [`CheckResult`],
//! 6. an audit log entry.
//!
//! Operations never return `Err`: failures are reported as a [`CheckResult`]
//! with `success: false` and an `error_type` (see [`error_type`]).

use crate::audit::AuditLog;
use crate::commands::{self, FormatMode, FormatRequest, LinkCheckRequest, PytestRequest};
use crate::parsers;
use crate::paths::{PathError, PathPolicy, validate_text};
use crate::process::{self, CommandSpec, ProcessError, ProcessOutput};
use crate::ratelimit::{self, RateLimiter};
use crate::types::{
    CheckResult, Language, Linter, PythonFormatter, Severity, ToolStatus, error_type,
};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Semaphore;
use tracing::info;

/// Default timeout for subprocess operations (10 minutes).
pub const DEFAULT_TIMEOUT_SECS: u64 = 600;
/// Default per-stream output capture limit.
pub const DEFAULT_MAX_OUTPUT_BYTES: usize = 100_000;
/// Default number of tool processes allowed to run at once.
pub const DEFAULT_MAX_CONCURRENT: usize = 4;
/// Maximum number of issues / findings / vulnerabilities returned in a list.
pub const MAX_LIST_ITEMS: usize = 500;
/// Timeout for the version probes in `get_status`.
const PROBE_TIMEOUT: Duration = Duration::from_secs(10);

/// Server version reported by `get_status`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Engine configuration.
#[derive(Debug, Clone)]
pub struct EngineConfig {
    pub timeout: Duration,
    pub allowed_paths: Vec<String>,
    pub audit_log_path: PathBuf,
    pub audit_log_max_bytes: u64,
    pub rate_limiting: bool,
    pub max_output_bytes: usize,
    pub max_concurrent: usize,
}

impl Default for EngineConfig {
    fn default() -> Self {
        Self {
            timeout: Duration::from_secs(DEFAULT_TIMEOUT_SECS),
            allowed_paths: vec!["/workspace".into(), "/app".into(), "/home".into()],
            audit_log_path: PathBuf::from("/var/log/mcp-code-quality/audit.log"),
            audit_log_max_bytes: crate::audit::DEFAULT_MAX_BYTES,
            rate_limiting: true,
            max_output_bytes: DEFAULT_MAX_OUTPUT_BYTES,
            max_concurrent: DEFAULT_MAX_CONCURRENT,
        }
    }
}

/// Arguments for [`CodeQualityEngine::run_tests`].
#[derive(Debug, Clone, Default)]
pub struct RunTestsArgs {
    pub path: String,
    pub working_dir: Option<String>,
    pub pattern: Option<String>,
    pub markers: Option<String>,
    pub verbose: bool,
    pub coverage: bool,
    pub fail_fast: bool,
}

/// Arguments for [`CodeQualityEngine::check_markdown_links`].
#[derive(Debug, Clone)]
pub struct LinkCheckArgs {
    pub path: String,
    pub check_external: bool,
    pub timeout: u64,
    pub concurrent: u64,
    pub ignore_patterns: Vec<String>,
    pub exclude: Vec<String>,
    pub skip_anchors: bool,
}

/// Early-exit type used inside operations: the `Err` side is already the
/// final (failed) result (boxed: `CheckResult` is large).
type Step<T> = Result<T, Box<CheckResult>>;

/// Code quality engine (shared by all tools via `Arc`).
pub struct CodeQualityEngine {
    config: EngineConfig,
    paths: PathPolicy,
    limiter: RateLimiter,
    audit: AuditLog,
    slots: Arc<Semaphore>,
}

impl CodeQualityEngine {
    /// Build the engine; canonicalizes the allowlist once up front.
    pub fn new(config: EngineConfig) -> Self {
        let paths = PathPolicy::new(&config.allowed_paths);
        let limiter = RateLimiter::new(config.rate_limiting);
        let audit = AuditLog::new(config.audit_log_path.clone(), config.audit_log_max_bytes);
        let slots = Arc::new(Semaphore::new(config.max_concurrent.max(1)));
        Self {
            config,
            paths,
            limiter,
            audit,
            slots,
        }
    }

    // ------------------------------------------------------------------
    // Shared pipeline helpers
    // ------------------------------------------------------------------

    fn rate_limit(&self, op: &str) -> Step<()> {
        self.limiter.check(op).map_err(|wait| {
            self.audit
                .record(op, "", false, json!({"reason": "rate_limit"}));
            Box::new(CheckResult::error(
                format!(
                    "Rate limit exceeded for {op}; retry in {}s",
                    wait.as_secs().max(1)
                ),
                error_type::RATE_LIMIT,
            ))
        })
    }

    fn path_failure(&self, op: &str, input: &str, err: PathError) -> Box<CheckResult> {
        let reason = match err {
            PathError::NotAllowed(_) => "path_not_allowed",
            PathError::NotFound(_) => "path_not_found",
            PathError::Invalid(_) => "path_invalid",
            PathError::WrongKind(_) => "path_wrong_kind",
        };
        self.audit
            .record(op, input, false, json!({"reason": reason}));
        let mut r = CheckResult::error(err.to_string(), error_type::PATH_VALIDATION);
        r.allowed_paths = Some(self.paths.configured().to_vec());
        Box::new(r)
    }

    fn resolve(&self, op: &str, input: &str, base: Option<&Path>) -> Step<PathBuf> {
        self.paths
            .resolve(input, base)
            .map_err(|e| self.path_failure(op, input, e))
    }

    fn resolve_dir(&self, op: &str, input: &str, base: Option<&Path>) -> Step<PathBuf> {
        self.paths
            .resolve_dir(input, base)
            .map_err(|e| self.path_failure(op, input, e))
    }

    fn resolve_file(&self, op: &str, input: &str, base: Option<&Path>) -> Step<PathBuf> {
        self.paths
            .resolve_file(input, base)
            .map_err(|e| self.path_failure(op, input, e))
    }

    fn invalid(&self, op: &str, path: &str, msg: impl Into<String>) -> Box<CheckResult> {
        let msg = msg.into();
        self.audit.record(
            op,
            path,
            false,
            json!({"reason": "invalid_input", "error": &msg}),
        );
        Box::new(CheckResult::error(msg, error_type::INVALID_INPUT))
    }

    /// Run a command under the concurrency limit, mapping spawn failures to
    /// results (and audit entries).
    async fn exec(&self, op: &str, path: &str, spec: &CommandSpec) -> Step<ProcessOutput> {
        let _permit = self.slots.acquire().await.map_err(|_| {
            Box::new(CheckResult::error(
                "Server is shutting down",
                error_type::EXCEPTION,
            ))
        })?;
        info!("{op}: {}", spec.display());
        process::run(spec, self.config.timeout, self.config.max_output_bytes)
            .await
            .map_err(|e| {
                let (kind, reason) = match &e {
                    ProcessError::NotFound(_) => (error_type::TOOL_NOT_FOUND, "tool_not_found"),
                    ProcessError::Timeout { .. } => (error_type::TIMEOUT, "timeout"),
                    ProcessError::Io(_) => (error_type::EXCEPTION, "exception"),
                };
                self.audit.record(
                    op,
                    path,
                    false,
                    json!({"reason": reason, "tool": spec.program, "error": e.to_string()}),
                );
                let mut r = CheckResult::error(e.to_string(), kind);
                r.command = Some(spec.display());
                Box::new(r)
            })
    }

    /// A result for a tool that ran but could not do its job.
    fn tool_failure(
        &self,
        op: &str,
        path: &str,
        spec: &CommandSpec,
        out: &ProcessOutput,
    ) -> Box<CheckResult> {
        self.audit.record(
            op,
            path,
            false,
            json!({"reason": "tool_error", "tool": spec.program, "returncode": out.code}),
        );
        let mut r = CheckResult::error(
            format!(
                "{} exited with code {} without producing a usable result",
                spec.program, out.code
            ),
            error_type::TOOL_ERROR,
        );
        fill_run_info(&mut r, spec, out);
        r.output = Some(out.combined());
        Box::new(r)
    }

    fn optional_text(&self, op: &str, path: &str, name: &str, v: Option<&str>) -> Step<()> {
        match v {
            Some(s) => validate_text(s, name).map_err(|e| self.invalid(op, path, e)),
            None => Ok(()),
        }
    }

    // ------------------------------------------------------------------
    // Formatting
    // ------------------------------------------------------------------

    /// Check formatting without modifying files.
    pub async fn format_check(
        &self,
        path: &str,
        language: Language,
        formatter: PythonFormatter,
        diff: bool,
    ) -> CheckResult {
        self.format(path, language, formatter, FormatMode::Check { diff })
            .await
            .unwrap_or_else(|e| *e)
    }

    /// Rewrite files in place with the language's formatter.
    pub async fn autoformat(
        &self,
        path: &str,
        language: Language,
        formatter: PythonFormatter,
    ) -> CheckResult {
        self.format(path, language, formatter, FormatMode::Write)
            .await
            .unwrap_or_else(|e| *e)
    }

    async fn format(
        &self,
        path: &str,
        language: Language,
        formatter: PythonFormatter,
        mode: FormatMode,
    ) -> Step<CheckResult> {
        let op = match mode {
            FormatMode::Check { .. } => "format_check",
            FormatMode::Write => "autoformat",
        };
        self.rate_limit(op)?;
        let target = self.resolve(op, path, None)?;
        let is_dir = target.is_dir();
        let edition = rust_edition_for(&target);
        let cmd = commands::format_command(&FormatRequest {
            language,
            python_formatter: formatter,
            target: &target,
            target_is_dir: is_dir,
            has_cargo_toml: is_dir && target.join("Cargo.toml").is_file(),
            rust_edition: &edition,
            mode,
        })
        .map_err(|e| self.invalid(op, path, e))?;

        let out = self.exec(op, path, &cmd.spec).await?;
        let unformatted = parsers::unformatted_files(cmd.kind, &out.stdout, &out.stderr);

        // rustfmt uses exit 1 for both "diff" and "error"; with no Diff lines
        // it was an error (e.g. a syntax error).
        let rust_error = cmd.kind == parsers::FormatterKind::Rustfmt
            && out.code == 1
            && unformatted.is_empty()
            && matches!(mode, FormatMode::Check { .. });
        let write_failed = matches!(mode, FormatMode::Write) && out.code != 0;
        if commands::format_exit_is_error(cmd.kind, out.code) || rust_error || write_failed {
            return Err(self.tool_failure(op, path, &cmd.spec, &out));
        }

        let formatted = match mode {
            FormatMode::Check { .. } => {
                // gofmt exits 0 even when files differ; its stdout lists them.
                out.code == 0
                    && (cmd.kind != parsers::FormatterKind::Gofmt || out.stdout.trim().is_empty())
            },
            FormatMode::Write => true,
        };
        self.audit.record(
            op,
            path,
            true,
            json!({"language": language.as_str(), "formatted": formatted, "unformatted_count": unformatted.len()}),
        );

        let mut r = CheckResult::success();
        r.formatted = Some(formatted);
        if matches!(mode, FormatMode::Check { .. }) {
            r.unformatted_files = Some(unformatted);
        }
        r.output = Some(out.combined());
        fill_run_info(&mut r, &cmd.spec, &out);
        for n in cmd.notes {
            r.note(n);
        }
        Ok(r)
    }

    // ------------------------------------------------------------------
    // Linting / type checking
    // ------------------------------------------------------------------

    /// Run a linter.
    pub async fn lint(&self, path: &str, config: Option<&str>, linter: Linter) -> CheckResult {
        self.lint_inner(path, config, linter)
            .await
            .unwrap_or_else(|e| *e)
    }

    async fn lint_inner(
        &self,
        path: &str,
        config: Option<&str>,
        linter: Linter,
    ) -> Step<CheckResult> {
        const OP: &str = "lint";
        self.rate_limit(OP)?;
        let target = self.resolve(OP, path, None)?;
        let cfg = match config {
            Some(c) => Some(self.resolve_file(OP, c, None)?),
            None => None,
        };
        let is_dir = target.is_dir();
        let cmd = commands::lint_command(
            linter,
            &target,
            is_dir,
            is_dir && target.join("Cargo.toml").is_file(),
            cfg.as_deref(),
        )
        .map_err(|e| self.invalid(OP, path, e))?;

        let out = self.exec(OP, path, &cmd.spec).await?;
        let issues = if cmd.eslint_json {
            match parsers::eslint_issues(&out.stdout) {
                Some(i) => i,
                None => return Err(self.tool_failure(OP, path, &cmd.spec, &out)),
            }
        } else if cmd.diagnostics_on_stderr {
            parsers::diagnostic_lines(&out.stderr)
        } else {
            parsers::diagnostic_lines(&out.stdout)
        };

        // Non-zero exit with nothing parsed means the linter itself failed
        // (bad config, compile error for clippy, crash) -- do not report that
        // as a clean "0 issues".
        if out.code != 0 && issues.is_empty() {
            return Err(self.tool_failure(OP, path, &cmd.spec, &out));
        }
        let passed = out.code == 0 && issues.is_empty();
        self.audit.record(
            OP,
            path,
            passed,
            json!({"linter": linter.as_str(), "issue_count": issues.len()}),
        );

        let mut r = CheckResult::success();
        r.passed = Some(passed);
        set_issues(&mut r, issues);
        fill_run_info(&mut r, &cmd.spec, &out);
        for n in cmd.notes {
            r.note(n);
        }
        Ok(r)
    }

    /// Run `ty check`.
    pub async fn type_check(&self, path: &str, config: Option<&str>, strict: bool) -> CheckResult {
        self.type_check_inner(path, config, strict)
            .await
            .unwrap_or_else(|e| *e)
    }

    async fn type_check_inner(
        &self,
        path: &str,
        config: Option<&str>,
        strict: bool,
    ) -> Step<CheckResult> {
        const OP: &str = "type_check";
        self.rate_limit(OP)?;
        let target = self.resolve(OP, path, None)?;
        let cfg = match config {
            Some(c) => Some(self.resolve_file(OP, c, None)?),
            None => None,
        };
        let spec = commands::type_check_command(&target, cfg.as_deref(), strict);
        let out = self.exec(OP, path, &spec).await?;
        let issues = parsers::diagnostic_lines(&out.stdout);
        // ty: 0 = clean, 1 = diagnostics found, 2 = usage/config error.
        if out.code >= 2 || (out.code != 0 && issues.is_empty()) {
            return Err(self.tool_failure(OP, path, &spec, &out));
        }
        let passed = out.code == 0;
        self.audit.record(
            OP,
            path,
            passed,
            json!({"issue_count": issues.len(), "strict": strict}),
        );

        let mut r = CheckResult::success();
        r.passed = Some(passed);
        set_issues(&mut r, issues);
        fill_run_info(&mut r, &spec, &out);
        Ok(r)
    }

    // ------------------------------------------------------------------
    // Tests
    // ------------------------------------------------------------------

    /// Run pytest.
    pub async fn run_tests(&self, args: &RunTestsArgs) -> CheckResult {
        self.run_tests_inner(args).await.unwrap_or_else(|e| *e)
    }

    async fn run_tests_inner(&self, a: &RunTestsArgs) -> Step<CheckResult> {
        const OP: &str = "run_tests";
        self.rate_limit(OP)?;
        let wd = match &a.working_dir {
            Some(d) => Some(self.resolve_dir(OP, d, None)?),
            None => None,
        };
        let target = self.resolve(OP, &a.path, wd.as_deref())?;
        self.optional_text(OP, &a.path, "pattern", a.pattern.as_deref())?;
        self.optional_text(OP, &a.path, "markers", a.markers.as_deref())?;

        let spec = commands::pytest_command(&PytestRequest {
            target,
            working_dir: wd.as_deref(),
            pattern: a.pattern.as_deref(),
            markers: a.markers.as_deref(),
            verbose: a.verbose,
            coverage: a.coverage,
            fail_fast: a.fail_fast,
        });
        let out = self.exec(OP, &a.path, &spec).await?;
        let summary = parsers::pytest_summary(&out.stdout);
        // pytest exit codes: 0 ok, 1 failures, 2 interrupted, 3 internal
        // error, 4 usage error, 5 no tests collected.
        if matches!(out.code, 3 | 4) || (out.code == 2 && summary.is_none()) {
            return Err(self.tool_failure(OP, &a.path, &spec, &out));
        }
        let passed = out.code == 0;
        self.audit.record(
            OP,
            &a.path,
            passed,
            json!({"returncode": out.code, "summary": summary}),
        );

        let mut r = CheckResult::success();
        r.passed = Some(passed);
        r.summary = summary;
        r.output = Some(out.combined());
        if out.code == 5 {
            r.note("pytest collected no tests (exit code 5)");
        }
        fill_run_info(&mut r, &spec, &out);
        Ok(r)
    }

    // ------------------------------------------------------------------
    // Security
    // ------------------------------------------------------------------

    /// Run bandit.
    pub async fn security_scan(
        &self,
        path: &str,
        severity: Severity,
        confidence: Severity,
    ) -> CheckResult {
        self.security_scan_inner(path, severity, confidence)
            .await
            .unwrap_or_else(|e| *e)
    }

    async fn security_scan_inner(
        &self,
        path: &str,
        severity: Severity,
        confidence: Severity,
    ) -> Step<CheckResult> {
        const OP: &str = "security_scan";
        self.rate_limit(OP)?;
        let target = self.resolve(OP, path, None)?;
        let spec = commands::bandit_command(&target, severity, confidence);
        let out = self.exec(OP, path, &spec).await?;
        // bandit exits 1 when it found issues; anything else without a JSON
        // report is a failure.
        let Some(report) = parsers::bandit(&out.stdout) else {
            return Err(self.tool_failure(OP, path, &spec, &out));
        };
        let passed = report.findings.is_empty();
        self.audit.record(
            OP,
            path,
            passed,
            json!({"finding_count": report.findings.len()}),
        );

        let mut r = CheckResult::success();
        r.passed = Some(passed);
        r.finding_count = Some(report.findings.len());
        let (findings, cut) = cap_list(report.findings);
        r.findings = Some(findings);
        r.summary = Some(report.summary);
        if !report.errors.is_empty() {
            r.note(format!(
                "bandit could not scan {} file(s): {}",
                report.errors.len(),
                Value::Array(report.errors)
            ));
        }
        fill_run_info(&mut r, &spec, &out);
        if cut {
            r.truncated = Some(true);
        }
        Ok(r)
    }

    /// Run pip-audit on a requirements file.
    pub async fn audit_dependencies(&self, requirements_file: &str) -> CheckResult {
        self.audit_dependencies_inner(requirements_file)
            .await
            .unwrap_or_else(|e| *e)
    }

    async fn audit_dependencies_inner(&self, requirements_file: &str) -> Step<CheckResult> {
        const OP: &str = "audit_dependencies";
        self.rate_limit(OP)?;
        let file = self.resolve_file(OP, requirements_file, None)?;
        let spec = commands::pip_audit_command(&file);
        let out = self.exec(OP, requirements_file, &spec).await?;
        let Some(vulns) = parsers::pip_audit(&out.stdout) else {
            return Err(self.tool_failure(OP, requirements_file, &spec, &out));
        };
        let passed = vulns.is_empty();
        self.audit.record(
            OP,
            requirements_file,
            passed,
            json!({"vulnerability_count": vulns.len()}),
        );

        let mut r = CheckResult::success();
        r.passed = Some(passed);
        r.vulnerability_count = Some(vulns.len());
        let (vulns, cut) = cap_list(vulns);
        r.vulnerabilities = Some(vulns);
        fill_run_info(&mut r, &spec, &out);
        if cut {
            r.truncated = Some(true);
        }
        Ok(r)
    }

    // ------------------------------------------------------------------
    // Markdown links
    // ------------------------------------------------------------------

    /// Run md-link-checker.
    pub async fn check_markdown_links(&self, args: &LinkCheckArgs) -> CheckResult {
        self.check_links_inner(args).await.unwrap_or_else(|e| *e)
    }

    async fn check_links_inner(&self, a: &LinkCheckArgs) -> Step<CheckResult> {
        const OP: &str = "check_markdown_links";
        self.rate_limit(OP)?;
        if !(1..=120).contains(&a.timeout) {
            return Err(self.invalid(OP, &a.path, "timeout must be between 1 and 120 seconds"));
        }
        if !(1..=64).contains(&a.concurrent) {
            return Err(self.invalid(OP, &a.path, "concurrent must be between 1 and 64"));
        }
        if a.ignore_patterns.len() > 100 || a.exclude.len() > 100 {
            return Err(self.invalid(OP, &a.path, "at most 100 ignore_patterns / exclude entries"));
        }
        for p in a.ignore_patterns.iter().chain(&a.exclude) {
            validate_text(p, "pattern").map_err(|e| self.invalid(OP, &a.path, e))?;
        }
        let target = self.resolve(OP, &a.path, None)?;
        let spec = commands::link_check_command(&LinkCheckRequest {
            target: &target,
            check_external: a.check_external,
            timeout: a.timeout as u32,
            concurrent: a.concurrent as u32,
            ignore_patterns: &a.ignore_patterns,
            exclude: &a.exclude,
            skip_anchors: a.skip_anchors,
        });
        let out = self.exec(OP, &a.path, &spec).await?;
        let Some(report) = parsers::md_links(&out.stdout) else {
            return Err(self.tool_failure(OP, &a.path, &spec, &out));
        };
        self.audit.record(
            OP,
            &a.path,
            report.all_valid,
            json!({
                "files_checked": report.files_checked,
                "total_links": report.total_links,
                "broken_links": report.broken_links
            }),
        );

        let mut r = CheckResult::success();
        r.passed = Some(report.all_valid);
        r.files_checked = Some(report.files_checked);
        r.total_links = Some(report.total_links);
        r.broken_links = Some(report.broken_links);
        let (broken, cut) = cap_list(report.broken);
        r.broken = Some(broken);
        fill_run_info(&mut r, &spec, &out);
        if cut {
            r.truncated = Some(true);
        }
        Ok(r)
    }

    // ------------------------------------------------------------------
    // Introspection
    // ------------------------------------------------------------------

    /// Server configuration plus availability/version of every external tool.
    /// Probes run concurrently, each with its own short timeout.
    pub async fn get_status(&self) -> Value {
        // (name, program, version args). Tools without a version flag are
        // probed for existence only.
        const PROBES: &[(&str, &str, &[&str])] = &[
            ("ruff", "ruff", &["--version"]),
            ("black", "black", &["--version"]),
            ("flake8", "flake8", &["--version"]),
            ("ty", "ty", &["--version"]),
            ("pytest", "pytest", &["--version"]),
            ("bandit", "bandit", &["--version"]),
            ("pip-audit", "pip-audit", &["--version"]),
            ("prettier", "prettier", &["--version"]),
            ("eslint", "eslint", &["--version"]),
            ("md-link-checker", "md-link-checker", &["--version"]),
            ("cargo", "cargo", &["--version"]),
            ("rustfmt", "rustfmt", &["--version"]),
            ("clippy", "cargo", &["clippy", "--version"]),
            ("gofmt", "gofmt", &["-l", "/dev/null"]),
            ("golint", "golint", &["-help"]),
        ];

        let mut set = tokio::task::JoinSet::new();
        for (name, program, args) in PROBES {
            let spec = CommandSpec::new(*program).args(args.iter().copied());
            set.spawn(async move { (*name, probe(&spec).await) });
        }
        let mut tools = BTreeMap::new();
        while let Some(res) = set.join_next().await {
            if let Ok((name, status)) = res {
                tools.insert(name.to_string(), status);
            }
        }

        let rate_limits: BTreeMap<&str, Value> = ratelimit::LIMITED_OPERATIONS
            .iter()
            .map(|op| {
                let c = ratelimit::limit_for(op);
                (
                    *op,
                    json!({"calls": c.calls, "period_seconds": c.period.as_secs()}),
                )
            })
            .collect();

        json!({
            "server": "Code Quality MCP Server",
            "version": VERSION,
            "timeout_seconds": self.config.timeout.as_secs(),
            "max_output_bytes": self.config.max_output_bytes,
            "max_concurrent": self.config.max_concurrent,
            "allowed_paths": self.paths.configured(),
            "effective_allowed_paths": self.paths.effective_roots(),
            "rate_limiting_enabled": self.limiter.enabled(),
            "rate_limits": rate_limits,
            "audit_log_path": self.audit.path().display().to_string(),
            "tools": tools
        })
    }

    /// Most recent audit entries (oldest first).
    pub async fn get_audit_log(self: &Arc<Self>, limit: usize, operation: Option<String>) -> Value {
        let this = Arc::clone(self);
        let result =
            tokio::task::spawn_blocking(move || this.audit.read(limit, operation.as_deref()))
                .await
                .map_err(|e| e.to_string())
                .and_then(|r| r);
        match result {
            Ok(entries) => json!({
                "success": true,
                "count": entries.len(),
                "entries": entries,
                "log_path": self.audit.path().display().to_string()
            }),
            Err(e) => json!({
                "success": false,
                "error": e,
                "error_type": error_type::EXCEPTION,
                "log_path": self.audit.path().display().to_string()
            }),
        }
    }
}

/// Probe one tool for availability and version.
async fn probe(spec: &CommandSpec) -> ToolStatus {
    match process::run(spec, PROBE_TIMEOUT, 4096).await {
        Ok(out) => {
            let first = out
                .stdout
                .lines()
                .chain(out.stderr.lines())
                .map(str::trim)
                .find(|l| !l.is_empty())
                .map(str::to_string);
            // A tool that exists but rejects our probe args (e.g. clippy not
            // installed as a cargo subcommand) is reported as unavailable.
            if out.code == 0 || spec.program == "gofmt" || spec.program == "golint" {
                ToolStatus {
                    available: true,
                    version: if out.code == 0 { first } else { None },
                    reason: None,
                }
            } else {
                ToolStatus {
                    available: false,
                    version: None,
                    reason: Some(first.unwrap_or_else(|| format!("exit code {}", out.code))),
                }
            }
        },
        Err(ProcessError::NotFound(_)) => ToolStatus {
            available: false,
            version: None,
            reason: Some("Not installed".to_string()),
        },
        Err(e) => ToolStatus {
            available: false,
            version: None,
            reason: Some(e.to_string()),
        },
    }
}

/// Copy command line, exit code, duration and truncation into a result.
fn fill_run_info(r: &mut CheckResult, spec: &CommandSpec, out: &ProcessOutput) {
    r.command = Some(spec.display());
    r.returncode = Some(out.code);
    r.duration_ms = Some(out.duration.as_millis() as u64);
    if out.truncated {
        r.truncated = Some(true);
    }
}

/// Store an issue list, capped at [`MAX_LIST_ITEMS`]; `issue_count` is the
/// full count.
fn set_issues(r: &mut CheckResult, issues: Vec<String>) {
    r.issue_count = Some(issues.len());
    let (issues, cut) = cap_list(issues);
    r.issues = Some(issues);
    if cut {
        r.truncated = Some(true);
    }
}

fn cap_list<T>(mut v: Vec<T>) -> (Vec<T>, bool) {
    let cut = v.len() > MAX_LIST_ITEMS;
    v.truncate(MAX_LIST_ITEMS);
    (v, cut)
}

/// Rust edition for single-file rustfmt: read from the nearest Cargo.toml
/// above the file; default 2021.
fn rust_edition_for(target: &Path) -> String {
    let start = if target.is_dir() {
        Some(target)
    } else {
        target.parent()
    };
    for dir in start.into_iter().flat_map(Path::ancestors) {
        let manifest = dir.join("Cargo.toml");
        // A manifest without a literal edition (e.g. workspace-inherited)
        // keeps searching upward for the workspace root.
        if let Ok(text) = std::fs::read_to_string(&manifest)
            && let Some(ed) = parsers::cargo_edition(&text)
        {
            return ed;
        }
    }
    "2021".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    struct Fixture {
        root: PathBuf,
        engine: Arc<CodeQualityEngine>,
    }

    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    fn fixture(name: &str, rate_limiting: bool) -> Fixture {
        let root = std::env::temp_dir().join(format!(
            "mcp-cq-engine-{}-{}-{}",
            name,
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let work = root.join("work");
        fs::create_dir_all(&work).unwrap();
        let root = crate::paths::canonicalize(&root).unwrap();
        let engine = CodeQualityEngine::new(EngineConfig {
            timeout: Duration::from_secs(120),
            allowed_paths: vec![root.join("work").display().to_string()],
            audit_log_path: root.join("logs/audit.log"),
            rate_limiting,
            ..EngineConfig::default()
        });
        Fixture {
            root,
            engine: Arc::new(engine),
        }
    }

    impl Fixture {
        fn work(&self) -> PathBuf {
            self.root.join("work")
        }
    }

    #[tokio::test]
    async fn rejects_paths_outside_allowlist_and_audits() {
        let f = fixture("outside", false);
        let outside = f.root.join("logs");
        fs::create_dir_all(&outside).unwrap();
        let r = f
            .engine
            .lint(&outside.display().to_string(), None, Linter::Ruff)
            .await;
        assert!(!r.success);
        assert_eq!(r.error_type.as_deref(), Some(error_type::PATH_VALIDATION));
        assert!(r.allowed_paths.is_some());

        let log = f.engine.get_audit_log(10, Some("lint".into())).await;
        assert_eq!(log["count"], 1);
        assert_eq!(log["entries"][0]["details"]["reason"], "path_not_allowed");
    }

    #[tokio::test]
    async fn rejects_missing_path_and_bad_config() {
        let f = fixture("missing", false);
        let r = f
            .engine
            .format_check(
                &f.work().join("nope.py").display().to_string(),
                Language::Python,
                PythonFormatter::Ruff,
                false,
            )
            .await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::PATH_VALIDATION));
        assert!(r.error.unwrap().contains("does not exist"));

        // config must be an existing file inside the allowlist
        let r = f
            .engine
            .lint(
                &f.work().display().to_string(),
                Some("/etc/passwd"),
                Linter::Ruff,
            )
            .await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::PATH_VALIDATION));
    }

    #[tokio::test]
    async fn rate_limit_is_enforced() {
        let f = fixture("rate", true);
        let dir = f.work().display().to_string();
        let mut limited = 0;
        for _ in 0..12 {
            let r = f.engine.audit_dependencies(&dir).await;
            if r.error_type.as_deref() == Some(error_type::RATE_LIMIT) {
                limited += 1;
                assert!(r.error.unwrap().contains("retry in"));
            }
        }
        // audit_dependencies allows 10/minute
        assert_eq!(limited, 2);
    }

    #[tokio::test]
    async fn invalid_inputs_are_rejected_before_spawning() {
        let f = fixture("invalid", false);
        let dir = f.work().display().to_string();

        // clippy on a directory without Cargo.toml
        let r = f.engine.lint(&dir, None, Linter::Clippy).await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::INVALID_INPUT));

        // requirements file must be a file
        let r = f.engine.audit_dependencies(&dir).await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::PATH_VALIDATION));

        // link checker ranges
        let args = LinkCheckArgs {
            path: dir.clone(),
            check_external: false,
            timeout: 0,
            concurrent: 10,
            ignore_patterns: vec![],
            exclude: vec![],
            skip_anchors: false,
        };
        let r = f.engine.check_markdown_links(&args).await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::INVALID_INPUT));
        let r = f
            .engine
            .check_markdown_links(&LinkCheckArgs {
                timeout: 10,
                concurrent: 1000,
                ..args.clone()
            })
            .await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::INVALID_INPUT));
        let r = f
            .engine
            .check_markdown_links(&LinkCheckArgs {
                timeout: 10,
                ignore_patterns: vec!["a\nb".into()],
                ..args
            })
            .await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::INVALID_INPUT));

        // run_tests markers with control characters
        let r = f
            .engine
            .run_tests(&RunTestsArgs {
                path: dir.clone(),
                markers: Some("slow\0".into()),
                ..Default::default()
            })
            .await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::INVALID_INPUT));

        // run_tests relative path resolved against working_dir
        let r = f
            .engine
            .run_tests(&RunTestsArgs {
                path: "does-not-exist".into(),
                working_dir: Some(dir),
                ..Default::default()
            })
            .await;
        assert_eq!(r.error_type.as_deref(), Some(error_type::PATH_VALIDATION));
    }

    /// End-to-end through a real formatter. rustfmt ships with every Rust
    /// toolchain that can run these tests; skip gracefully if it is absent.
    #[tokio::test]
    async fn rustfmt_check_and_autoformat_roundtrip() {
        let f = fixture("rustfmt", false);
        let file = f.work().join("ugly.rs");
        fs::write(&file, "fn main(){let x=1;println!(\"{}\",x);}\n").unwrap();
        let p = file.display().to_string();

        let r = f
            .engine
            .format_check(&p, Language::Rust, PythonFormatter::Ruff, false)
            .await;
        if r.error_type.as_deref() == Some(error_type::TOOL_NOT_FOUND) {
            eprintln!("rustfmt not installed; skipping");
            return;
        }
        assert!(r.success, "{r:?}");
        assert_eq!(r.formatted, Some(false));
        let unformatted = r.unformatted_files.unwrap();
        assert_eq!(unformatted.len(), 1, "{unformatted:?}");
        assert!(unformatted[0].ends_with("ugly.rs"));

        let r = f
            .engine
            .autoformat(&p, Language::Rust, PythonFormatter::Ruff)
            .await;
        assert!(r.success, "{r:?}");

        let r = f
            .engine
            .format_check(&p, Language::Rust, PythonFormatter::Ruff, false)
            .await;
        assert_eq!(r.formatted, Some(true), "{r:?}");
        assert_eq!(r.unformatted_files.as_deref(), Some(&[][..]));

        // A syntax error is a tool failure, not "unformatted".
        fs::write(&file, "fn main( {\n").unwrap();
        let r = f
            .engine
            .format_check(&p, Language::Rust, PythonFormatter::Ruff, false)
            .await;
        assert!(!r.success);
        assert_eq!(r.error_type.as_deref(), Some(error_type::TOOL_ERROR));
    }

    #[tokio::test]
    async fn status_reports_config_and_tools() {
        let f = fixture("status", true);
        let s = f.engine.get_status().await;
        assert_eq!(s["version"], VERSION);
        assert_eq!(s["rate_limiting_enabled"], true);
        assert_eq!(s["rate_limits"]["audit_dependencies"]["calls"], 10);
        assert_eq!(s["effective_allowed_paths"].as_array().unwrap().len(), 1);
        // cargo is always present under `cargo test`.
        assert_eq!(s["tools"]["cargo"]["available"], true);
        assert!(s["tools"].as_object().unwrap().len() >= 15);
    }

    #[test]
    fn edition_lookup() {
        let root = std::env::temp_dir().join(format!("mcp-cq-edition-{}", std::process::id()));
        let src = root.join("src");
        fs::create_dir_all(&src).unwrap();
        fs::write(
            root.join("Cargo.toml"),
            "[package]\nname=\"x\"\nedition = \"2024\"\n",
        )
        .unwrap();
        fs::write(src.join("main.rs"), "").unwrap();
        assert_eq!(rust_edition_for(&src.join("main.rs")), "2024");
        fs::remove_dir_all(&root).ok();
    }

    #[test]
    fn list_capping() {
        let (v, cut) = cap_list((0..MAX_LIST_ITEMS + 5).collect::<Vec<_>>());
        assert!(cut);
        assert_eq!(v.len(), MAX_LIST_ITEMS);
        let (v, cut) = cap_list(vec![1, 2]);
        assert!(!cut);
        assert_eq!(v.len(), 2);
    }
}

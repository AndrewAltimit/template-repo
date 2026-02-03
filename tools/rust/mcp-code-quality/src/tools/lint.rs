//! Linting and static analysis tools

use std::path::Path;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::json;

use super::Linter;
use crate::error::Result;
use crate::subprocess::run_command;

/// Request for lint operation
#[derive(Debug, Deserialize)]
pub struct LintRequest {
    pub path: String,
    #[serde(default = "default_linter")]
    pub linter: String,
    #[serde(default)]
    pub config: Option<String>,
}

fn default_linter() -> String {
    "ruff".to_string()
}

/// Response for lint operation
#[derive(Debug, Serialize)]
pub struct LintResponse {
    pub success: bool,
    pub clean: bool,
    pub linter: String,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issues: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Run linting on code
pub async fn lint(
    path: &Path,
    linter: Linter,
    config: Option<&str>,
    timeout: Duration,
) -> Result<LintResponse> {
    let (cmd, args) = get_lint_command(linter, path, config)?;

    let result = run_command(cmd, &args, None, timeout).await?;

    // Count issues from output (rough heuristic)
    let issue_count = if result.stdout.is_empty() {
        0
    } else {
        result.stdout.lines().count()
    };

    Ok(LintResponse {
        success: true,
        clean: result.success && issue_count == 0,
        linter: format!("{:?}", linter).to_lowercase(),
        path: path.display().to_string(),
        issues: if result.stdout.is_empty() {
            None
        } else {
            Some(result.stdout)
        },
        issue_count: Some(issue_count),
        message: if result.success && issue_count == 0 {
            Some("No linting issues found".to_string())
        } else {
            Some(format!("Found {} linting issues", issue_count))
        },
    })
}

/// Get lint command and args
/// Note: For Python, we use ruff check (10-100x faster than flake8/pylint)
fn get_lint_command(
    linter: Linter,
    path: &Path,
    config: Option<&str>,
) -> Result<(&'static str, Vec<String>)> {
    let path_str = path.display().to_string();
    let mut args = Vec::new();

    match linter {
        // Map flake8 to ruff check (compatible, much faster)
        Linter::Flake8 => {
            args.push("check".to_string());
            if let Some(cfg) = config {
                args.push(format!("--config={}", cfg));
            }
            args.push(path_str);
            Ok(("ruff", args))
        },
        // Native ruff linting
        Linter::Ruff => {
            args.push("check".to_string());
            if let Some(cfg) = config {
                args.push(format!("--config={}", cfg));
            }
            args.push(path_str);
            Ok(("ruff", args))
        },
        Linter::Eslint => {
            if let Some(cfg) = config {
                args.push("-c".to_string());
                args.push(cfg.to_string());
            }
            args.push(path_str);
            Ok(("eslint", args))
        },
        Linter::Golint => {
            args.push(path_str);
            Ok(("golint", args))
        },
        Linter::Clippy => {
            args.push("clippy".to_string());
            args.push("--".to_string());
            args.push("-D".to_string());
            args.push("warnings".to_string());
            Ok(("cargo", args))
        },
    }
}

/// Request for type_check operation
#[derive(Debug, Deserialize)]
pub struct TypeCheckRequest {
    pub path: String,
    #[serde(default)]
    pub strict: bool,
    #[serde(default)]
    pub config: Option<String>,
}

/// Response for type_check operation
#[derive(Debug, Serialize)]
pub struct TypeCheckResponse {
    pub success: bool,
    pub passed: bool,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub errors: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Run ty type checking (Astral's fast type checker, 10-60x faster than mypy)
pub async fn type_check(
    path: &Path,
    _strict: bool, // Currently unused, ty uses pyproject.toml config
    config: Option<&str>,
    timeout: Duration,
) -> Result<TypeCheckResponse> {
    let mut args = vec!["check".to_string()];

    if let Some(cfg) = config {
        args.push("--config".to_string());
        args.push(cfg.to_string());
    }

    args.push(path.display().to_string());

    let args_refs: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    let result = run_command("ty", &args_refs, None, timeout).await?;

    // Count errors from output (ty format: "error[rule-name]: message")
    let error_count = result
        .stdout
        .lines()
        .filter(|line| line.starts_with("error["))
        .count();

    Ok(TypeCheckResponse {
        success: true,
        passed: result.success,
        path: path.display().to_string(),
        errors: if result.stdout.is_empty() {
            None
        } else {
            Some(result.stdout)
        },
        error_count: Some(error_count),
        message: if result.success {
            Some("Type checking passed".to_string())
        } else {
            Some(format!("Found {} type errors", error_count))
        },
    })
}

/// Request for security_scan operation
#[derive(Debug, Deserialize)]
pub struct SecurityScanRequest {
    pub path: String,
    #[serde(default = "default_severity")]
    pub severity: String,
    #[serde(default = "default_confidence")]
    pub confidence: String,
}

fn default_severity() -> String {
    "low".to_string()
}

fn default_confidence() -> String {
    "low".to_string()
}

/// Response for security_scan operation
#[derive(Debug, Serialize)]
pub struct SecurityScanResponse {
    pub success: bool,
    pub clean: bool,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issues: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Run security scan using ruff (10-100x faster than bandit, same rules)
/// Uses the S rule set which implements bandit security rules in Rust
pub async fn security_scan(
    path: &Path,
    _severity: &str, // ruff doesn't have severity filtering, we check all
    _confidence: &str,
    timeout: Duration,
) -> Result<SecurityScanResponse> {
    let path_str = path.display().to_string();

    // Use ruff check with security rules (S = bandit rules implemented in Rust)
    let args = vec![
        "check".to_string(),
        "--select=S".to_string(), // Security rules (bandit compatible)
        path_str,
    ];

    let result = run_command("ruff", &args, None, timeout).await?;

    // Count issues from ruff output
    let issue_count = result
        .stdout
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with("Found"))
        .count();

    Ok(SecurityScanResponse {
        success: true,
        clean: result.success && issue_count == 0,
        path: path.display().to_string(),
        issues: if result.stdout.is_empty() {
            None
        } else {
            Some(result.stdout)
        },
        issue_count: Some(issue_count),
        message: if issue_count == 0 {
            Some("No security issues found".to_string())
        } else {
            Some(format!("Found {} security issues", issue_count))
        },
    })
}

impl LintResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "clean": self.clean,
            "linter": self.linter,
            "path": self.path,
            "issues": self.issues,
            "issue_count": self.issue_count,
            "message": self.message,
        })
    }
}

impl TypeCheckResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "passed": self.passed,
            "path": self.path,
            "errors": self.errors,
            "error_count": self.error_count,
            "message": self.message,
        })
    }
}

impl SecurityScanResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "clean": self.clean,
            "path": self.path,
            "issues": self.issues,
            "issue_count": self.issue_count,
            "message": self.message,
        })
    }
}

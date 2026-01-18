//! Testing and dependency audit tools

use std::path::Path;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::error::Result;
use crate::subprocess::run_command;

/// Request for run_tests operation
#[derive(Debug, Deserialize)]
pub struct RunTestsRequest {
    #[serde(default = "default_test_path")]
    pub path: String,
    #[serde(default)]
    pub verbose: bool,
    #[serde(default)]
    pub coverage: bool,
    #[serde(default)]
    pub fail_fast: bool,
    #[serde(default)]
    pub pattern: Option<String>,
    #[serde(default)]
    pub markers: Option<String>,
}

fn default_test_path() -> String {
    "tests/".to_string()
}

/// Response for run_tests operation
#[derive(Debug, Serialize)]
pub struct RunTestsResponse {
    pub success: bool,
    pub passed: bool,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub test_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failed_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Run pytest tests
pub async fn run_tests(
    path: &Path,
    verbose: bool,
    coverage: bool,
    fail_fast: bool,
    pattern: Option<&str>,
    markers: Option<&str>,
    timeout: Duration,
) -> Result<RunTestsResponse> {
    let mut args = vec![];
    let path_str = path.display().to_string();

    args.push(path_str.as_str());

    if verbose {
        args.push("-v");
    }

    if coverage {
        args.push("--cov=.");
        args.push("--cov-report=term-missing");
    }

    if fail_fast {
        args.push("-x");
    }

    let pattern_arg;
    if let Some(p) = pattern {
        args.push("-k");
        pattern_arg = p.to_string();
        args.push(&pattern_arg);
    }

    let markers_arg;
    if let Some(m) = markers {
        args.push("-m");
        markers_arg = m.to_string();
        args.push(&markers_arg);
    }

    let result = run_command("pytest", &args, None, timeout).await?;

    // Parse test results from output
    let (test_count, failed_count) = parse_pytest_output(&result.stdout);

    Ok(RunTestsResponse {
        success: true,
        passed: result.success,
        path: path.display().to_string(),
        output: Some(format!("{}\n{}", result.stdout, result.stderr)),
        test_count,
        failed_count,
        message: if result.success {
            Some("All tests passed".to_string())
        } else {
            Some(format!(
                "{} tests failed",
                failed_count.unwrap_or(0)
            ))
        },
    })
}

fn parse_pytest_output(output: &str) -> (Option<usize>, Option<usize>) {
    // Look for pytest summary line like "5 passed, 2 failed"
    for line in output.lines().rev() {
        if line.contains("passed") || line.contains("failed") {
            let mut total = 0;
            let mut failed = 0;

            // Parse "X passed"
            if let Some(idx) = line.find("passed")
                && let Some(num_str) = line[..idx].split_whitespace().last()
                && let Ok(n) = num_str.parse::<usize>()
            {
                total += n;
            }

            // Parse "X failed"
            if let Some(idx) = line.find("failed")
                && let Some(num_str) = line[..idx].split_whitespace().last()
                && let Ok(n) = num_str.parse::<usize>()
            {
                failed = n;
                total += n;
            }

            if total > 0 {
                return (Some(total), Some(failed));
            }
        }
    }

    (None, None)
}

/// Request for audit_dependencies operation
#[derive(Debug, Deserialize)]
pub struct AuditDependenciesRequest {
    #[serde(default = "default_requirements_file")]
    pub requirements_file: String,
}

fn default_requirements_file() -> String {
    "requirements.txt".to_string()
}

/// Response for audit_dependencies operation
#[derive(Debug, Serialize)]
pub struct AuditDependenciesResponse {
    pub success: bool,
    pub clean: bool,
    pub requirements_file: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vulnerabilities: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vulnerability_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Run pip-audit on dependencies
pub async fn audit_dependencies(
    requirements_file: &Path,
    timeout: Duration,
) -> Result<AuditDependenciesResponse> {
    let path_str = requirements_file.display().to_string();
    let args = ["-r", &path_str, "--format", "columns"];

    let result = run_command("pip-audit", &args, None, timeout).await?;

    // Count vulnerabilities
    let vuln_count = result
        .stdout
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with("Name"))
        .count()
        .saturating_sub(1); // Subtract header line

    Ok(AuditDependenciesResponse {
        success: true,
        clean: result.success && vuln_count == 0,
        requirements_file: path_str,
        vulnerabilities: if result.stdout.is_empty() {
            None
        } else {
            Some(result.stdout)
        },
        vulnerability_count: Some(vuln_count),
        message: if vuln_count == 0 {
            Some("No vulnerabilities found".to_string())
        } else {
            Some(format!("Found {} vulnerabilities", vuln_count))
        },
    })
}

/// Request for check_markdown_links operation
#[derive(Debug, Deserialize)]
pub struct CheckMarkdownLinksRequest {
    pub path: String,
    #[serde(default = "default_check_external")]
    pub check_external: bool,
    #[serde(default = "default_timeout")]
    pub timeout: u32,
    #[serde(default = "default_concurrent")]
    pub concurrent_checks: u32,
    #[serde(default)]
    pub ignore_patterns: Vec<String>,
}

fn default_check_external() -> bool {
    true
}

fn default_timeout() -> u32 {
    10
}

fn default_concurrent() -> u32 {
    10
}

/// Response for check_markdown_links operation
#[derive(Debug, Serialize)]
pub struct CheckMarkdownLinksResponse {
    pub success: bool,
    pub all_valid: bool,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub files_checked: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_links: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub broken_links: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Check markdown links using md-link-checker
pub async fn check_markdown_links(
    path: &Path,
    check_external: bool,
    link_timeout: u32,
    concurrent: u32,
    ignore_patterns: &[String],
    timeout: Duration,
) -> Result<CheckMarkdownLinksResponse> {
    let path_str = path.display().to_string();
    let timeout_str = link_timeout.to_string();
    let concurrent_str = concurrent.to_string();

    let mut args = vec![&path_str, "--json", "--timeout", &timeout_str, "--concurrent", &concurrent_str];

    if !check_external {
        args.push("--internal-only");
    }

    let ignore_args: Vec<String> = ignore_patterns.iter().map(|p| format!("--ignore={}", p)).collect();
    for arg in &ignore_args {
        args.push(arg);
    }

    // Try our Rust md-link-checker first
    let result = run_command("md-link-checker", &args, None, timeout).await;

    match result {
        Ok(output) => {
            // Parse JSON output
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&output.stdout) {
                let files_checked = json.get("files_checked").and_then(|v| v.as_u64()).map(|v| v as usize);
                let total_links = json.get("total_links").and_then(|v| v.as_u64()).map(|v| v as usize);
                let broken_links = json.get("broken_links").and_then(|v| v.as_u64()).map(|v| v as usize);
                let all_valid = json.get("all_valid").and_then(|v| v.as_bool()).unwrap_or(false);

                return Ok(CheckMarkdownLinksResponse {
                    success: true,
                    all_valid,
                    path: path_str,
                    files_checked,
                    total_links,
                    broken_links,
                    output: Some(output.stdout),
                    message: if all_valid {
                        Some("All links are valid".to_string())
                    } else {
                        Some(format!("Found {} broken links", broken_links.unwrap_or(0)))
                    },
                });
            }

            // Non-JSON output
            Ok(CheckMarkdownLinksResponse {
                success: true,
                all_valid: output.success,
                path: path_str,
                files_checked: None,
                total_links: None,
                broken_links: None,
                output: Some(output.stdout),
                message: Some(if output.success {
                    "Link check completed".to_string()
                } else {
                    "Link check found issues".to_string()
                }),
            })
        }
        Err(_) => {
            // Fallback message if tool not available
            Ok(CheckMarkdownLinksResponse {
                success: false,
                all_valid: false,
                path: path_str,
                files_checked: None,
                total_links: None,
                broken_links: None,
                output: None,
                message: Some("md-link-checker not available".to_string()),
            })
        }
    }
}

impl RunTestsResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "passed": self.passed,
            "path": self.path,
            "output": self.output,
            "test_count": self.test_count,
            "failed_count": self.failed_count,
            "message": self.message,
        })
    }
}

impl AuditDependenciesResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "clean": self.clean,
            "requirements_file": self.requirements_file,
            "vulnerabilities": self.vulnerabilities,
            "vulnerability_count": self.vulnerability_count,
            "message": self.message,
        })
    }
}

impl CheckMarkdownLinksResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "all_valid": self.all_valid,
            "path": self.path,
            "files_checked": self.files_checked,
            "total_links": self.total_links,
            "broken_links": self.broken_links,
            "output": self.output,
            "message": self.message,
        })
    }
}

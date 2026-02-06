//! MCP server implementation for code quality.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::engine::CodeQualityEngine;
use crate::types::{Language, Linter, Severity};

/// Code quality MCP server
pub struct CodeQualityServer {
    engine: Arc<RwLock<Option<CodeQualityEngine>>>,
    timeout_secs: u64,
    allowed_paths: Vec<String>,
    audit_log_path: PathBuf,
    rate_limiting_enabled: bool,
}

impl CodeQualityServer {
    /// Create a new code quality server
    pub fn new(
        timeout_secs: u64,
        allowed_paths: Vec<String>,
        audit_log_path: PathBuf,
        rate_limiting_enabled: bool,
    ) -> Self {
        Self {
            engine: Arc::new(RwLock::new(None)),
            timeout_secs,
            allowed_paths,
            audit_log_path,
            rate_limiting_enabled,
        }
    }

    /// Ensure engine is initialized
    #[allow(dead_code)]
    async fn ensure_initialized(&self) -> Result<()> {
        let mut guard = self.engine.write().await;
        if guard.is_none() {
            info!("Initializing code quality engine...");
            let engine = CodeQualityEngine::new(
                self.timeout_secs,
                self.allowed_paths.clone(),
                self.audit_log_path.clone(),
                self.rate_limiting_enabled,
            );
            *guard = Some(engine);
        }
        Ok(())
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(FormatCheckTool {
                server: self.clone_refs(),
            }),
            Arc::new(LintTool {
                server: self.clone_refs(),
            }),
            Arc::new(AutoformatTool {
                server: self.clone_refs(),
            }),
            Arc::new(RunTestsTool {
                server: self.clone_refs(),
            }),
            Arc::new(TypeCheckTool {
                server: self.clone_refs(),
            }),
            Arc::new(SecurityScanTool {
                server: self.clone_refs(),
            }),
            Arc::new(AuditDependenciesTool {
                server: self.clone_refs(),
            }),
            Arc::new(CheckMarkdownLinksTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetStatusTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetAuditLogTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            engine: self.engine.clone(),
            timeout_secs: self.timeout_secs,
            allowed_paths: self.allowed_paths.clone(),
            audit_log_path: self.audit_log_path.clone(),
            rate_limiting_enabled: self.rate_limiting_enabled,
        }
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    engine: Arc<RwLock<Option<CodeQualityEngine>>>,
    timeout_secs: u64,
    allowed_paths: Vec<String>,
    audit_log_path: PathBuf,
    rate_limiting_enabled: bool,
}

impl ServerRefs {
    async fn ensure_initialized(&self) -> Result<()> {
        let mut guard = self.engine.write().await;
        if guard.is_none() {
            info!("Initializing code quality engine...");
            let engine = CodeQualityEngine::new(
                self.timeout_secs,
                self.allowed_paths.clone(),
                self.audit_log_path.clone(),
                self.rate_limiting_enabled,
            );
            *guard = Some(engine);
        }
        Ok(())
    }
}

// ============================================================================
// Tool: format_check
// ============================================================================

struct FormatCheckTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for FormatCheckTool {
    fn name(&self) -> &str {
        "format_check"
    }

    fn description(&self) -> &str {
        "Check code formatting for various languages (python, javascript, typescript, go, rust)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or directory to check"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "typescript", "go", "rust"],
                    "default": "python",
                    "description": "Programming language"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'path' parameter".to_string()))?;

        let language = args
            .get("language")
            .and_then(|v| v.as_str())
            .and_then(Language::from_str)
            .unwrap_or(Language::Python);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.format_check(path, language).await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: lint
// ============================================================================

struct LintTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for LintTool {
    fn name(&self) -> &str {
        "lint"
    }

    fn description(&self) -> &str {
        "Run code linting with various linters (flake8, ruff, eslint, golint, clippy)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or directory to lint"
                },
                "config": {
                    "type": "string",
                    "description": "Path to linting configuration file"
                },
                "linter": {
                    "type": "string",
                    "enum": ["flake8", "ruff", "eslint", "golint", "clippy"],
                    "default": "ruff",
                    "description": "Linter to use"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'path' parameter".to_string()))?;

        let config = args.get("config").and_then(|v| v.as_str());

        let linter = args
            .get("linter")
            .and_then(|v| v.as_str())
            .and_then(Linter::from_str)
            .unwrap_or(Linter::Ruff);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.lint(path, config, linter).await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: autoformat
// ============================================================================

struct AutoformatTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AutoformatTool {
    fn name(&self) -> &str {
        "autoformat"
    }

    fn description(&self) -> &str {
        "Automatically format code files for various languages"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or directory to format"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "typescript", "go", "rust"],
                    "default": "python",
                    "description": "Programming language"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'path' parameter".to_string()))?;

        let language = args
            .get("language")
            .and_then(|v| v.as_str())
            .and_then(Language::from_str)
            .unwrap_or(Language::Python);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.autoformat(path, language).await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: run_tests
// ============================================================================

struct RunTestsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RunTestsTool {
    fn name(&self) -> &str {
        "run_tests"
    }

    fn description(&self) -> &str {
        "Run pytest tests with controlled parameters"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": "tests/",
                    "description": "Path to test file or directory"
                },
                "pattern": {
                    "type": "string",
                    "description": "Test file pattern (e.g., test_*.py)"
                },
                "verbose": {
                    "type": "boolean",
                    "default": false,
                    "description": "Enable verbose output"
                },
                "coverage": {
                    "type": "boolean",
                    "default": false,
                    "description": "Generate coverage report"
                },
                "fail_fast": {
                    "type": "boolean",
                    "default": false,
                    "description": "Stop on first failure"
                },
                "markers": {
                    "type": "string",
                    "description": "Run tests matching marker expression (e.g., 'not slow')"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .unwrap_or("tests/");

        let pattern = args.get("pattern").and_then(|v| v.as_str());
        let verbose = args
            .get("verbose")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let coverage = args
            .get("coverage")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let fail_fast = args
            .get("fail_fast")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let markers = args.get("markers").and_then(|v| v.as_str());

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine
            .run_tests(path, pattern, verbose, coverage, fail_fast, markers)
            .await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: type_check
// ============================================================================

struct TypeCheckTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for TypeCheckTool {
    fn name(&self) -> &str {
        "type_check"
    }

    fn description(&self) -> &str {
        "Run ty type checking (Astral's fast type checker, 10-60x faster than mypy)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or directory to check"
                },
                "strict": {
                    "type": "boolean",
                    "default": false,
                    "description": "Enable strict mode (currently unused, ty uses pyproject.toml config)"
                },
                "config": {
                    "type": "string",
                    "description": "Path to pyproject.toml configuration file (optional)"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'path' parameter".to_string()))?;

        let config = args.get("config").and_then(|v| v.as_str());

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.type_check(path, config).await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: security_scan
// ============================================================================

struct SecurityScanTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SecurityScanTool {
    fn name(&self) -> &str {
        "security_scan"
    }

    fn description(&self) -> &str {
        "Run security analysis with bandit"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or directory to scan"
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "default": "low",
                    "description": "Minimum severity level to report"
                },
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "default": "low",
                    "description": "Minimum confidence level to report"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'path' parameter".to_string()))?;

        let severity = args
            .get("severity")
            .and_then(|v| v.as_str())
            .and_then(Severity::from_str)
            .unwrap_or(Severity::Low);

        let confidence = args
            .get("confidence")
            .and_then(|v| v.as_str())
            .and_then(Severity::from_str)
            .unwrap_or(Severity::Low);

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.security_scan(path, severity, confidence).await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: audit_dependencies
// ============================================================================

struct AuditDependenciesTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AuditDependenciesTool {
    fn name(&self) -> &str {
        "audit_dependencies"
    }

    fn description(&self) -> &str {
        "Check dependencies for known vulnerabilities using pip-audit"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "requirements_file": {
                    "type": "string",
                    "default": "requirements.txt",
                    "description": "Path to requirements file"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let requirements_file = args
            .get("requirements_file")
            .and_then(|v| v.as_str())
            .unwrap_or("requirements.txt");

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.audit_dependencies(requirements_file).await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: check_markdown_links
// ============================================================================

struct CheckMarkdownLinksTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CheckMarkdownLinksTool {
    fn name(&self) -> &str {
        "check_markdown_links"
    }

    fn description(&self) -> &str {
        "Check markdown files for broken links using md-link-checker"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to markdown file or directory to check"
                },
                "check_external": {
                    "type": "boolean",
                    "default": true,
                    "description": "Check external URLs (set false for internal links only)"
                },
                "timeout": {
                    "type": "integer",
                    "default": 10,
                    "description": "Timeout in seconds for each link check"
                },
                "concurrent": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of concurrent link checks"
                },
                "ignore_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "URL patterns to ignore (e.g., 'localhost', '127.0.0.1')"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'path' parameter".to_string()))?;

        let check_external = args
            .get("check_external")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let timeout = args
            .get("timeout")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32)
            .unwrap_or(10);

        let concurrent = args
            .get("concurrent")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32)
            .unwrap_or(10);

        let ignore_patterns: Vec<String> = args
            .get("ignore_patterns")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine
            .check_markdown_links(path, check_external, timeout, concurrent, &ignore_patterns)
            .await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: get_status
// ============================================================================

struct GetStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetStatusTool {
    fn name(&self) -> &str {
        "get_status"
    }

    fn description(&self) -> &str {
        "Get server status, available tools, and their versions"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.get_status().await;
        ToolResult::json(&result)
    }
}

// ============================================================================
// Tool: get_audit_log
// ============================================================================

struct GetAuditLogTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetAuditLogTool {
    fn name(&self) -> &str {
        "get_audit_log"
    }

    fn description(&self) -> &str {
        "Get recent audit log entries for compliance review"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum number of entries to return"
                },
                "operation": {
                    "type": "string",
                    "description": "Filter by operation name"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(100);

        let operation = args.get("operation").and_then(|v| v.as_str());

        let guard = self.server.engine.read().await;
        let engine = guard
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Engine not initialized".to_string()))?;

        let result = engine.get_audit_log(limit, operation).await;
        ToolResult::json(&result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = CodeQualityServer::new(
            600,
            vec!["/tmp".to_string()],
            PathBuf::from("/tmp/audit.log"),
            true,
        );
        let tools = server.tools();
        assert_eq!(tools.len(), 10);
    }

    #[test]
    fn test_tool_names() {
        let server = CodeQualityServer::new(
            600,
            vec!["/tmp".to_string()],
            PathBuf::from("/tmp/audit.log"),
            true,
        );
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"format_check"));
        assert!(names.contains(&"lint"));
        assert!(names.contains(&"autoformat"));
        assert!(names.contains(&"run_tests"));
        assert!(names.contains(&"type_check"));
        assert!(names.contains(&"security_scan"));
        assert!(names.contains(&"audit_dependencies"));
        assert!(names.contains(&"check_markdown_links"));
        assert!(names.contains(&"get_status"));
        assert!(names.contains(&"get_audit_log"));
    }
}

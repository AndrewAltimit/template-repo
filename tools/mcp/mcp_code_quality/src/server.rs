//! MCP tool definitions.
//!
//! Each tool pairs a hand-written JSON schema (kept rich: enums, defaults,
//! ranges -- things the `#[mcp_tool]` macro's derived schema cannot express)
//! with a typed `serde` argument struct. [`parse_args`] deserializes the raw
//! arguments into that struct, so a missing required field, a wrong type, or
//! an unknown enum value becomes a clean `InvalidParameters` error instead of
//! being silently replaced by a default.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::sync::Arc;

use crate::engine::{CodeQualityEngine, LinkCheckArgs, RunTestsArgs};
use crate::types::{Language, Linter, PythonFormatter, Severity};

/// Deserialize tool arguments into `T`.
///
/// `null` values are treated as absent (so `{"config": null}` falls back to
/// the default) and a missing/`null` argument object is treated as `{}`.
pub fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = match args {
        Value::Null => Value::Object(Default::default()),
        Value::Object(mut map) => {
            map.retain(|_, v| !v.is_null());
            Value::Object(map)
        },
        other => {
            return Err(MCPError::InvalidParameters(format!(
                "arguments must be a JSON object, got {other}"
            )));
        },
    };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

/// Registers every tool against one shared engine.
pub struct CodeQualityServer {
    engine: Arc<CodeQualityEngine>,
}

impl CodeQualityServer {
    /// Wrap an engine.
    pub fn new(engine: CodeQualityEngine) -> Self {
        Self {
            engine: Arc::new(engine),
        }
    }

    /// All tools as boxed trait objects.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let e = || self.engine.clone();
        vec![
            Arc::new(FormatCheckTool(e())),
            Arc::new(LintTool(e())),
            Arc::new(AutoformatTool(e())),
            Arc::new(RunTestsTool(e())),
            Arc::new(TypeCheckTool(e())),
            Arc::new(SecurityScanTool(e())),
            Arc::new(AuditDependenciesTool(e())),
            Arc::new(CheckMarkdownLinksTool(e())),
            Arc::new(GetStatusTool(e())),
            Arc::new(GetAuditLogTool(e())),
        ]
    }
}

fn enum_schema(values: Vec<&'static str>, default: &str, description: &str) -> Value {
    json!({"type": "string", "enum": values, "default": default, "description": description})
}

fn default_true() -> bool {
    true
}

// ============================================================================
// format_check / autoformat
// ============================================================================

#[derive(Debug, Deserialize)]
struct FormatArgs {
    path: String,
    #[serde(default)]
    language: Language,
    #[serde(default)]
    formatter: PythonFormatter,
    #[serde(default)]
    diff: bool,
}

fn format_schema(with_diff: bool) -> Value {
    let mut props = json!({
        "path": {
            "type": "string",
            "description": "File or directory (inside the allowed paths). For rust, a crate directory containing Cargo.toml or a single .rs file."
        },
        "language": enum_schema(Language::names(), "python", "Programming language"),
        "formatter": enum_schema(
            PythonFormatter::names(),
            "ruff",
            "Python formatter backend (ignored for other languages): 'ruff' (ruff format, the repo standard) or 'black'"
        ),
    });
    if with_diff {
        props["diff"] = json!({
            "type": "boolean",
            "default": false,
            "description": "Include a diff of the required changes in 'output' (ruff, black, gofmt, rustfmt)"
        });
    }
    json!({"type": "object", "properties": props, "required": ["path"]})
}

struct FormatCheckTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for FormatCheckTool {
    fn name(&self) -> &str {
        "format_check"
    }

    fn description(&self) -> &str {
        "Check code formatting without modifying files (python: ruff format/black, javascript/typescript: prettier, go: gofmt, rust: cargo fmt/rustfmt). Returns 'formatted' and the list of 'unformatted_files'."
    }

    fn schema(&self) -> Value {
        format_schema(true)
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: FormatArgs = parse_args(args)?;
        let r = self
            .0
            .format_check(&a.path, a.language, a.formatter, a.diff)
            .await;
        ToolResult::json(&r)
    }
}

struct AutoformatTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for AutoformatTool {
    fn name(&self) -> &str {
        "autoformat"
    }

    fn description(&self) -> &str {
        "Format code files IN PLACE (python: ruff format/black, javascript/typescript: prettier --write, go: gofmt -w, rust: cargo fmt/rustfmt). Requires a writable mount."
    }

    fn schema(&self) -> Value {
        format_schema(false)
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: FormatArgs = parse_args(args)?;
        let r = self.0.autoformat(&a.path, a.language, a.formatter).await;
        ToolResult::json(&r)
    }
}

// ============================================================================
// lint
// ============================================================================

#[derive(Debug, Deserialize)]
struct LintArgs {
    path: String,
    config: Option<String>,
    #[serde(default)]
    linter: Linter,
}

struct LintTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for LintTool {
    fn name(&self) -> &str {
        "lint"
    }

    fn description(&self) -> &str {
        "Run a linter (ruff, flake8, eslint, golint, clippy) and return one 'file:line:col: message' entry per issue. clippy needs a crate directory containing Cargo.toml."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to lint (inside the allowed paths)"
                },
                "config": {
                    "type": "string",
                    "description": "Linter config file (inside the allowed paths). ruff/flake8/eslint: passed as --config; clippy: its directory is used as CLIPPY_CONF_DIR; golint: unsupported"
                },
                "linter": enum_schema(Linter::names(), "ruff", "Linter to use")
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: LintArgs = parse_args(args)?;
        let r = self.0.lint(&a.path, a.config.as_deref(), a.linter).await;
        ToolResult::json(&r)
    }
}

// ============================================================================
// run_tests
// ============================================================================

#[derive(Debug, Deserialize)]
struct RunTestsToolArgs {
    #[serde(default = "default_tests_path")]
    path: String,
    working_dir: Option<String>,
    pattern: Option<String>,
    #[serde(default)]
    verbose: bool,
    #[serde(default)]
    coverage: bool,
    #[serde(default)]
    fail_fast: bool,
    markers: Option<String>,
}

fn default_tests_path() -> String {
    "tests/".to_string()
}

struct RunTestsTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for RunTestsTool {
    fn name(&self) -> &str {
        "run_tests"
    }

    fn description(&self) -> &str {
        "Run pytest and return pass/fail, a parsed outcome 'summary' (passed/failed/skipped/...), and the (size-capped) output. Note: running tests executes the project's Python code."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": "tests/",
                    "description": "Test file or directory. Relative paths resolve against working_dir (or the server's working directory)."
                },
                "working_dir": {
                    "type": "string",
                    "description": "Directory to run pytest in (inside the allowed paths); also the coverage source"
                },
                "pattern": {
                    "type": "string",
                    "description": "Either a test file glob such as 'test_*.py' (sets python_files) or a pytest -k keyword expression such as 'login and not slow'"
                },
                "verbose": {"type": "boolean", "default": false, "description": "Pass -v"},
                "coverage": {
                    "type": "boolean",
                    "default": false,
                    "description": "Collect coverage (--cov, needs pytest-cov) with a term-missing report"
                },
                "fail_fast": {"type": "boolean", "default": false, "description": "Stop on first failure (-x)"},
                "markers": {
                    "type": "string",
                    "description": "Marker expression passed to -m (e.g. 'not slow')"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: RunTestsToolArgs = parse_args(args)?;
        let r = self
            .0
            .run_tests(&RunTestsArgs {
                path: a.path,
                working_dir: a.working_dir,
                pattern: a.pattern,
                markers: a.markers,
                verbose: a.verbose,
                coverage: a.coverage,
                fail_fast: a.fail_fast,
            })
            .await;
        ToolResult::json(&r)
    }
}

// ============================================================================
// type_check
// ============================================================================

#[derive(Debug, Deserialize)]
struct TypeCheckArgs {
    path: String,
    #[serde(default)]
    strict: bool,
    config: Option<String>,
}

struct TypeCheckTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for TypeCheckTool {
    fn name(&self) -> &str {
        "type_check"
    }

    fn description(&self) -> &str {
        "Run the ty Python type checker (Astral) and return one entry per diagnostic"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to check (inside the allowed paths)"
                },
                "strict": {
                    "type": "boolean",
                    "default": false,
                    "description": "Fail on warnings too (ty --error-on-warning)"
                },
                "config": {
                    "type": "string",
                    "description": "A pyproject.toml (its directory becomes --project) or a ty.toml (--config-file)"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: TypeCheckArgs = parse_args(args)?;
        let r = self
            .0
            .type_check(&a.path, a.config.as_deref(), a.strict)
            .await;
        ToolResult::json(&r)
    }
}

// ============================================================================
// security_scan
// ============================================================================

#[derive(Debug, Deserialize)]
struct SecurityScanArgs {
    path: String,
    #[serde(default)]
    severity: Severity,
    #[serde(default)]
    confidence: Severity,
}

struct SecurityScanTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for SecurityScanTool {
    fn name(&self) -> &str {
        "security_scan"
    }

    fn description(&self) -> &str {
        "Run bandit (Python security linter) recursively and return its findings plus per-severity counts"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to scan (inside the allowed paths)"
                },
                "severity": enum_schema(Severity::names(), "low", "Minimum severity level to report"),
                "confidence": enum_schema(Severity::names(), "low", "Minimum confidence level to report")
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: SecurityScanArgs = parse_args(args)?;
        let r = self
            .0
            .security_scan(&a.path, a.severity, a.confidence)
            .await;
        ToolResult::json(&r)
    }
}

// ============================================================================
// audit_dependencies
// ============================================================================

#[derive(Debug, Deserialize)]
struct AuditDependenciesArgs {
    #[serde(default = "default_requirements")]
    requirements_file: String,
}

fn default_requirements() -> String {
    "requirements.txt".to_string()
}

struct AuditDependenciesTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for AuditDependenciesTool {
    fn name(&self) -> &str {
        "audit_dependencies"
    }

    fn description(&self) -> &str {
        "Check a Python requirements file for known vulnerabilities with pip-audit (needs network access to PyPI/OSV). Returns one entry per vulnerability with fix versions."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "requirements_file": {
                    "type": "string",
                    "default": "requirements.txt",
                    "description": "Path to a requirements file (inside the allowed paths; relative paths resolve against the server's working directory)"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: AuditDependenciesArgs = parse_args(args)?;
        let r = self.0.audit_dependencies(&a.requirements_file).await;
        ToolResult::json(&r)
    }
}

// ============================================================================
// check_markdown_links
// ============================================================================

#[derive(Debug, Deserialize)]
struct CheckLinksArgs {
    path: String,
    #[serde(default = "default_true")]
    check_external: bool,
    #[serde(default = "default_ten")]
    timeout: u64,
    #[serde(default = "default_ten")]
    concurrent: u64,
    #[serde(default)]
    ignore_patterns: Vec<String>,
    #[serde(default)]
    exclude: Vec<String>,
    #[serde(default)]
    skip_anchors: bool,
}

fn default_ten() -> u64 {
    10
}

struct CheckMarkdownLinksTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for CheckMarkdownLinksTool {
    fn name(&self) -> &str {
        "check_markdown_links"
    }

    fn description(&self) -> &str {
        "Check markdown files for broken links and anchors with md-link-checker. Returns counts plus a 'broken' list of {file, url, lines, error}."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Markdown file or directory to check (inside the allowed paths)"
                },
                "check_external": {
                    "type": "boolean",
                    "default": true,
                    "description": "Check external URLs (false = internal links only)"
                },
                "timeout": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 120,
                    "description": "Timeout in seconds for each HTTP link check"
                },
                "concurrent": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 64,
                    "description": "Number of concurrent HTTP link checks"
                },
                "ignore_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "Regexes matched against links to skip (e.g. 'localhost')"
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "Gitignore-style globs of files/directories to skip (e.g. 'vendor/**')"
                },
                "skip_anchors": {
                    "type": "boolean",
                    "default": false,
                    "description": "Skip anchor/heading validation (same-page and cross-file #fragment links)"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: CheckLinksArgs = parse_args(args)?;
        let r = self
            .0
            .check_markdown_links(&LinkCheckArgs {
                path: a.path,
                check_external: a.check_external,
                timeout: a.timeout,
                concurrent: a.concurrent,
                ignore_patterns: a.ignore_patterns,
                exclude: a.exclude,
                skip_anchors: a.skip_anchors,
            })
            .await;
        ToolResult::json(&r)
    }
}

// ============================================================================
// get_status / get_audit_log
// ============================================================================

struct GetStatusTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for GetStatusTool {
    fn name(&self) -> &str {
        "get_status"
    }

    fn description(&self) -> &str {
        "Get server configuration (allowed paths, limits) and the availability/version of every external tool"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        ToolResult::json(&self.0.get_status().await)
    }
}

#[derive(Debug, Deserialize)]
struct GetAuditLogArgs {
    #[serde(default = "default_audit_limit")]
    limit: usize,
    operation: Option<String>,
}

fn default_audit_limit() -> usize {
    100
}

struct GetAuditLogTool(Arc<CodeQualityEngine>);

#[async_trait]
impl Tool for GetAuditLogTool {
    fn name(&self) -> &str {
        "get_audit_log"
    }

    fn description(&self) -> &str {
        "Get the most recent audit log entries (one per tool call), oldest first"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "maximum": crate::audit::MAX_READ_ENTRIES,
                    "description": "Maximum number of entries to return (clamped to 1..=1000)"
                },
                "operation": {
                    "type": "string",
                    "description": "Only return entries for this tool name"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: GetAuditLogArgs = parse_args(args)?;
        ToolResult::json(&self.0.get_audit_log(a.limit, a.operation).await)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::EngineConfig;
    use std::path::PathBuf;

    fn server() -> CodeQualityServer {
        let log = std::env::temp_dir()
            .join(format!("mcp-cq-server-{}", std::process::id()))
            .join("audit.log");
        CodeQualityServer::new(CodeQualityEngine::new(EngineConfig {
            allowed_paths: vec![std::env::temp_dir().display().to_string()],
            audit_log_path: log,
            rate_limiting: false,
            ..EngineConfig::default()
        }))
    }

    fn tool(name: &str) -> BoxedTool {
        server()
            .tools()
            .into_iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("no tool {name}"))
    }

    fn text(r: &ToolResult) -> Value {
        match &r.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap(),
            other => panic!("unexpected content {other:?}"),
        }
    }

    #[test]
    fn all_tools_registered_with_stable_names() {
        let names: Vec<String> = server()
            .tools()
            .iter()
            .map(|t| t.name().to_string())
            .collect();
        assert_eq!(
            names,
            vec![
                "format_check",
                "lint",
                "autoformat",
                "run_tests",
                "type_check",
                "security_scan",
                "audit_dependencies",
                "check_markdown_links",
                "get_status",
                "get_audit_log"
            ]
        );
    }

    #[test]
    fn schemas_are_objects_and_required_params_unchanged() {
        let expected_required: &[(&str, &[&str])] = &[
            ("format_check", &["path"]),
            ("lint", &["path"]),
            ("autoformat", &["path"]),
            ("type_check", &["path"]),
            ("security_scan", &["path"]),
            ("check_markdown_links", &["path"]),
        ];
        for t in server().tools() {
            let s = t.schema();
            assert_eq!(s["type"], "object", "{}", t.name());
            assert!(s["properties"].is_object(), "{}", t.name());
            let req: Vec<&str> = s
                .get("required")
                .and_then(Value::as_array)
                .map(|a| a.iter().filter_map(Value::as_str).collect())
                .unwrap_or_default();
            let want = expected_required
                .iter()
                .find(|(n, _)| *n == t.name())
                .map(|(_, r)| r.to_vec())
                .unwrap_or_default();
            assert_eq!(req, want, "{}", t.name());
            // every required param is documented in properties
            for r in req {
                assert!(s["properties"].get(r).is_some());
            }
        }
    }

    #[test]
    fn enum_schemas_match_types() {
        let s = tool("lint").schema();
        assert_eq!(s["properties"]["linter"]["enum"], json!(Linter::names()));
        let s = tool("format_check").schema();
        assert_eq!(
            s["properties"]["language"]["enum"],
            json!(Language::names())
        );
        assert!(s["properties"].get("diff").is_some());
        assert!(
            tool("autoformat").schema()["properties"]
                .get("diff")
                .is_none()
        );
    }

    #[test]
    fn parse_args_rules() {
        #[derive(Deserialize, Debug)]
        struct A {
            path: String,
            #[serde(default)]
            linter: Linter,
            config: Option<String>,
        }
        let a: A = parse_args(json!({"path": "x", "config": null})).unwrap();
        assert_eq!(a.path, "x");
        assert_eq!(a.linter, Linter::Ruff);
        assert!(a.config.is_none());

        let a: A = parse_args(json!({"path": "x", "linter": null})).unwrap();
        assert_eq!(a.linter, Linter::Ruff);

        let e = parse_args::<A>(json!({})).unwrap_err().to_string();
        assert!(e.contains("path"), "{e}");
        let e = parse_args::<A>(json!({"path": 5})).unwrap_err().to_string();
        assert!(e.contains("Invalid parameters"), "{e}");
        let e = parse_args::<A>(json!({"path": "x", "linter": "pylint"}))
            .unwrap_err()
            .to_string();
        assert!(e.contains("pylint") && e.contains("clippy"), "{e}");
        assert!(parse_args::<A>(json!([1])).is_err());
        assert!(parse_args::<A>(Value::Null).is_err()); // path still required
    }

    #[tokio::test]
    async fn missing_required_param_is_invalid_parameters() {
        let err = tool("format_check").execute(json!({})).await.unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)), "{err}");
        let err = tool("security_scan")
            .execute(json!({"path": "/x", "severity": "critical"}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)), "{err}");
        let err = tool("check_markdown_links")
            .execute(json!({"path": "/x", "timeout": -1}))
            .await
            .unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)), "{err}");
    }

    #[tokio::test]
    async fn tools_return_json_results() {
        let outside = PathBuf::from("/definitely/not/allowed/xyz");
        let r = tool("lint")
            .execute(json!({"path": outside.display().to_string()}))
            .await
            .unwrap();
        let v = text(&r);
        assert_eq!(v["success"], false);
        assert_eq!(v["error_type"], "path_validation");

        // run_tests works with no arguments at all (all optional).
        let r = tool("run_tests").execute(json!({})).await.unwrap();
        assert!(text(&r).get("success").is_some());

        let r = tool("get_audit_log")
            .execute(json!({"limit": 5}))
            .await
            .unwrap();
        assert_eq!(text(&r)["success"], true);
    }
}

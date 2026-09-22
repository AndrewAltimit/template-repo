//! MCP tool layer for GitHub Projects v2 board operations.
//!
//! Every board tool is a [`BoardTool`] driven by a [`ToolSpec`] from
//! [`crate::specs`]: arguments are validated into a `board-manager`
//! invocation, executed through a [`BoardRunner`], and the result is shaped
//! into a uniform response:
//!
//! * success: `{"success": true, "result": <board-manager JSON>}`
//! * refused / failed: `isError: true` with
//!   `{"success": false, "error": "...", "result"?: ...}`
//!
//! Invalid arguments are rejected with `InvalidParameters` before any
//! process is spawned.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::sync::Arc;

use crate::runner::{BoardRunner, RunError};
use crate::specs::{self, Expect, ToolSpec};

/// Server version reported by `board_status`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Environment variables whose presence (never value) `board_status` reports.
const TOKEN_VARS: &[&str] = &["GITHUB_PROJECTS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"];

/// Server-wide options.
#[derive(Debug, Clone, Copy, Default)]
pub struct ServerOptions {
    /// Do not register tools that modify the board or issues.
    pub read_only: bool,
}

/// GitHub Board MCP server: owns the runner and produces the tool set.
pub struct GitHubBoardServer {
    runner: Arc<dyn BoardRunner>,
    options: ServerOptions,
}

impl GitHubBoardServer {
    /// Create a server backed by the given runner.
    pub fn new(runner: Arc<dyn BoardRunner>, options: ServerOptions) -> Self {
        Self { runner, options }
    }

    /// All tools to register (mutating tools are omitted in read-only mode).
    pub fn tools(&self) -> Vec<BoxedTool> {
        let mut tools: Vec<BoxedTool> = specs::SPECS
            .iter()
            .filter(|spec| !(self.options.read_only && spec.mutating))
            .map(|spec| {
                Arc::new(BoardTool {
                    spec,
                    runner: self.runner.clone(),
                }) as BoxedTool
            })
            .collect();
        let tool_names = tools.iter().map(|t| t.name().to_string()).collect();
        tools.push(Arc::new(BoardStatusTool {
            runner: self.runner.clone(),
            options: self.options,
            tool_names,
        }));
        tools
    }
}

/// Build a tool result carrying a JSON body.
fn json_result(body: &Value, is_error: bool) -> Result<ToolResult> {
    Ok(ToolResult {
        content: vec![Content::json(body)?],
        is_error,
    })
}

/// Shape a `board-manager` result according to the tool's expectation.
///
/// Returns the response body and whether it is an error.
pub fn shape_result(tool: &str, expect: &Expect, result: Value) -> (Value, bool) {
    match expect {
        Expect::Value => (json!({ "success": true, "result": result }), false),
        Expect::OnBoard(issue) if result.is_null() => (
            json!({
                "success": false,
                "error": format!(
                    "Issue {issue} is not on the project board (add it with add_to_board)"
                ),
            }),
            true,
        ),
        Expect::OnBoard(_) => (json!({ "success": true, "result": result }), false),
        Expect::Outcome => {
            let ok = result
                .get("success")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            if ok {
                return (json!({ "success": true, "result": result }), false);
            }
            let error = match (tool, result.get("claimed_by").and_then(Value::as_str)) {
                ("claim_work", Some(holder)) => format!(
                    "Issue is already claimed by {holder}; pick other work or wait for the claim \
                     to be released or to expire"
                ),
                ("claim_work", None) => "Claim was not granted".to_string(),
                ("renew_claim", _) => {
                    "No active claim by this agent to renew (it may have expired \
                                       or be held by someone else); claim the issue again with \
                                       claim_work"
                        .to_string()
                },
                _ => "Operation was refused by board-manager".to_string(),
            };
            (
                json!({ "success": false, "error": error, "result": result }),
                true,
            )
        },
    }
}

/// Response body for a runner failure.
pub fn error_body(err: &RunError) -> Value {
    let kind = match err {
        RunError::NotFound(_) => "board_manager_not_found",
        RunError::Spawn { .. } => "spawn_failed",
        RunError::Timeout(_) => "timeout",
        RunError::Failed { .. } => "board_manager_error",
        RunError::InvalidOutput(_) => "invalid_output",
    };
    json!({ "success": false, "error": err.to_string(), "error_kind": kind })
}

/// A board tool backed by a [`ToolSpec`].
struct BoardTool {
    spec: &'static ToolSpec,
    runner: Arc<dyn BoardRunner>,
}

#[async_trait]
impl Tool for BoardTool {
    fn name(&self) -> &str {
        self.spec.name
    }

    fn description(&self) -> &str {
        self.spec.description
    }

    fn schema(&self) -> Value {
        (self.spec.schema)()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let plan = (self.spec.plan)(args)?;
        match self.runner.run(&plan.argv).await {
            Ok(result) => {
                let (body, is_error) = shape_result(self.spec.name, &plan.expect, result);
                json_result(&body, is_error)
            },
            Err(e) => {
                tracing::warn!("{} failed: {}", self.spec.name, e);
                json_result(&error_body(&e), true)
            },
        }
    }
}

/// `board_status`: local diagnostics, never calls the GitHub API.
struct BoardStatusTool {
    runner: Arc<dyn BoardRunner>,
    options: ServerOptions,
    tool_names: Vec<String>,
}

#[async_trait]
impl Tool for BoardStatusTool {
    fn name(&self) -> &str {
        "board_status"
    }

    fn description(&self) -> &str {
        "Get GitHub board server status: server version, read-only mode, registered tools, \
whether the board-manager CLI is available (path and version), the per-call timeout and which \
GitHub token variables are set (names only, never values). Does not call the GitHub API."
    }

    fn schema(&self) -> Value {
        json!({ "type": "object", "properties": {} })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let diag = self.runner.diagnostics().await;
        let available = diag
            .get("board_manager_available")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let tokens: Vec<&str> = TOKEN_VARS
            .iter()
            .copied()
            .filter(|v| std::env::var(v).is_ok_and(|s| !s.trim().is_empty()))
            .collect();
        let mut body = json!({
            "server": "github-board",
            "version": VERSION,
            // Kept for backward compatibility: true once board-manager is usable.
            "initialized": available,
            "read_only": self.options.read_only,
            "tools": self.tool_names,
            "board_manager": diag,
            "token_env_vars_set": tokens,
        });
        if tokens.is_empty() {
            body["warning"] = json!(
                "No GitHub token variable is set; board operations will fail with an \
                 authentication error"
            );
        }
        ToolResult::json(&body)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    /// Records calls and replays a canned response.
    struct MockRunner {
        calls: Mutex<Vec<Vec<String>>>,
        response: Box<dyn Fn() -> std::result::Result<Value, RunError> + Send + Sync>,
    }

    impl MockRunner {
        fn ok(v: Value) -> Arc<Self> {
            Arc::new(Self {
                calls: Mutex::new(Vec::new()),
                response: Box::new(move || Ok(v.clone())),
            })
        }

        fn err(f: fn() -> RunError) -> Arc<Self> {
            Arc::new(Self {
                calls: Mutex::new(Vec::new()),
                response: Box::new(move || Err(f())),
            })
        }

        fn calls(&self) -> Vec<Vec<String>> {
            self.calls.lock().unwrap().clone()
        }
    }

    #[async_trait]
    impl BoardRunner for MockRunner {
        async fn run(&self, args: &[String]) -> std::result::Result<Value, RunError> {
            self.calls.lock().unwrap().push(args.to_vec());
            (self.response)()
        }

        async fn diagnostics(&self) -> Value {
            json!({ "board_manager_available": true, "board_manager_path": "/mock" })
        }
    }

    fn tool(runner: Arc<MockRunner>, name: &str) -> BoxedTool {
        GitHubBoardServer::new(runner, ServerOptions::default())
            .tools()
            .into_iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("no tool {name}"))
    }

    fn body(r: &ToolResult) -> Value {
        match &r.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap(),
            other => panic!("unexpected content {other:?}"),
        }
    }

    /// The original 12 tool names must keep working.
    const LEGACY_TOOLS: &[&str] = &[
        "query_ready_work",
        "claim_work",
        "renew_claim",
        "release_work",
        "update_status",
        "add_blocker",
        "mark_discovered_from",
        "get_issue_details",
        "get_dependency_graph",
        "list_agents",
        "get_board_config",
        "board_status",
    ];

    #[test]
    fn registers_all_tools_including_legacy_names() {
        let server = GitHubBoardServer::new(MockRunner::ok(json!({})), ServerOptions::default());
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        for legacy in LEGACY_TOOLS {
            assert!(names.contains(legacy), "missing {legacy}");
        }
        for new in [
            "remove_blocker",
            "add_to_board",
            "check_approval",
            "find_approved_issues",
            "release_stale_claims",
        ] {
            assert!(names.contains(&new), "missing {new}");
        }
        assert_eq!(tools.len(), specs::SPECS.len() + 1);
    }

    #[test]
    fn legacy_required_params_unchanged() {
        let server = GitHubBoardServer::new(MockRunner::ok(json!({})), ServerOptions::default());
        let expected: &[(&str, &[&str])] = &[
            ("claim_work", &["issue_number", "agent_name", "session_id"]),
            ("renew_claim", &["issue_number", "agent_name", "session_id"]),
            ("release_work", &["issue_number", "agent_name"]),
            ("update_status", &["issue_number", "status"]),
            ("add_blocker", &["issue_number", "blocker_number"]),
            ("mark_discovered_from", &["issue_number", "parent_number"]),
            ("get_issue_details", &["issue_number"]),
            ("get_dependency_graph", &["issue_number"]),
        ];
        for t in server.tools() {
            let schema = t.schema();
            let required: Vec<&str> = schema
                .get("required")
                .and_then(Value::as_array)
                .map(|a| a.iter().filter_map(Value::as_str).collect())
                .unwrap_or_default();
            if let Some((_, want)) = expected.iter().find(|(n, _)| *n == t.name()) {
                assert_eq!(&required, want, "{}", t.name());
            }
        }
    }

    #[test]
    fn read_only_mode_hides_mutating_tools() {
        let server =
            GitHubBoardServer::new(MockRunner::ok(json!({})), ServerOptions { read_only: true });
        let names: Vec<String> = server
            .tools()
            .iter()
            .map(|t| t.name().to_string())
            .collect();
        for hidden in [
            "claim_work",
            "renew_claim",
            "release_work",
            "update_status",
            "add_blocker",
            "remove_blocker",
            "mark_discovered_from",
            "add_to_board",
            "release_stale_claims",
        ] {
            assert!(!names.iter().any(|n| n == hidden), "{hidden} visible");
        }
        for shown in [
            "query_ready_work",
            "get_issue_details",
            "get_dependency_graph",
            "check_approval",
            "board_status",
        ] {
            assert!(names.iter().any(|n| n == shown), "{shown} hidden");
        }
    }

    #[tokio::test]
    async fn success_is_wrapped() {
        let runner = MockRunner::ok(json!([{"number": 1}]));
        let t = tool(runner.clone(), "query_ready_work");
        let r = t.execute(json!({"limit": 3})).await.unwrap();
        assert!(!r.is_error);
        assert_eq!(
            body(&r),
            json!({"success": true, "result": [{"number": 1}]})
        );
        assert_eq!(runner.calls(), vec![vec!["ready", "--limit=3"]]);
    }

    #[tokio::test]
    async fn invalid_args_never_reach_the_runner() {
        let runner = MockRunner::ok(json!({}));
        let t = tool(runner.clone(), "claim_work");
        let err = t.execute(json!({"issue_number": "abc"})).await.unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));
        assert!(runner.calls().is_empty());
    }

    #[tokio::test]
    async fn refused_claim_is_an_error_with_holder() {
        let runner = MockRunner::ok(json!({
            "success": false, "issue": 5, "agent": "claude", "session_id": "s",
            "reason": "already_claimed by crush", "claimed_by": "crush"
        }));
        let t = tool(runner, "claim_work");
        let r = t
            .execute(json!({"issue_number": 5, "agent_name": "claude", "session_id": "s"}))
            .await
            .unwrap();
        assert!(r.is_error);
        let b = body(&r);
        assert_eq!(b["success"], json!(false));
        assert!(b["error"].as_str().unwrap().contains("crush"));
        assert_eq!(b["result"]["claimed_by"], json!("crush"));
    }

    #[tokio::test]
    async fn granted_claim_is_success() {
        let runner = MockRunner::ok(json!({"success": true, "issue": 5, "session_id": "s"}));
        let t = tool(runner, "claim_work");
        let r = t
            .execute(json!({"issue_number": 5, "agent_name": "claude", "session_id": "s"}))
            .await
            .unwrap();
        assert!(!r.is_error);
        assert_eq!(body(&r)["result"]["session_id"], json!("s"));
    }

    #[tokio::test]
    async fn failed_renewal_is_an_error() {
        let runner = MockRunner::ok(json!({"success": false, "issue": 5, "agent": "claude"}));
        let t = tool(runner, "renew_claim");
        let r = t
            .execute(json!({"issue_number": 5, "agent_name": "claude", "session_id": "s"}))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(body(&r)["error"].as_str().unwrap().contains("claim_work"));
    }

    #[tokio::test]
    async fn issue_not_on_board_is_reported() {
        for name in ["get_issue_details", "get_dependency_graph"] {
            let t = tool(MockRunner::ok(Value::Null), name);
            let r = t.execute(json!({"issue_number": 77})).await.unwrap();
            assert!(r.is_error, "{name}");
            assert!(
                body(&r)["error"]
                    .as_str()
                    .unwrap()
                    .contains("#77 is not on the project board"),
                "{name}"
            );
        }
        let t = tool(
            MockRunner::ok(json!({"number": 77})),
            "get_dependency_graph",
        );
        let r = t.execute(json!({"issue_number": 77})).await.unwrap();
        assert!(!r.is_error);
    }

    #[tokio::test]
    async fn runner_errors_become_tool_errors() {
        let t = tool(
            MockRunner::err(|| RunError::Failed {
                status: "exit code 1".into(),
                message: "Authentication failed: bad credentials".into(),
            }),
            "list_agents",
        );
        let r = t.execute(json!({})).await.unwrap();
        assert!(r.is_error);
        let b = body(&r);
        assert_eq!(b["error_kind"], json!("board_manager_error"));
        assert!(b["error"].as_str().unwrap().contains("bad credentials"));

        let t = tool(MockRunner::err(|| RunError::Timeout(5)), "get_board_config");
        let r = t.execute(json!({})).await.unwrap();
        assert!(r.is_error);
        assert_eq!(body(&r)["error_kind"], json!("timeout"));
    }

    #[tokio::test]
    async fn board_status_reports_diagnostics_without_runner_calls() {
        let runner = MockRunner::ok(json!({}));
        let t = tool(runner.clone(), "board_status");
        let r = t.execute(json!({})).await.unwrap();
        assert!(!r.is_error);
        let b = body(&r);
        assert_eq!(b["server"], json!("github-board"));
        assert_eq!(b["version"], json!(VERSION));
        assert_eq!(b["initialized"], json!(true));
        assert_eq!(b["read_only"], json!(false));
        assert_eq!(b["board_manager"]["board_manager_path"], json!("/mock"));
        assert!(
            b["tools"]
                .as_array()
                .unwrap()
                .contains(&json!("claim_work"))
        );
        assert!(runner.calls().is_empty());
    }

    #[test]
    fn shape_outcome_without_success_field_is_refused() {
        let (b, err) = shape_result("claim_work", &Expect::Outcome, json!({}));
        assert!(err);
        assert_eq!(b["error"], json!("Claim was not granted"));
    }
}

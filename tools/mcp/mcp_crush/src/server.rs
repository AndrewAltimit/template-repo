//! MCP server assembly for the Crush integration.

use std::sync::Arc;

use mcp_core::prelude::*;
use tokio::sync::RwLock;

use crate::config::CrushConfig;
use crate::consult::{Shared, build_tools};
use crate::crush::CrushIntegration;

/// Crush MCP server: owns the shared integration and builds its tools.
pub struct CrushServer {
    integration: Shared<CrushIntegration>,
}

impl CrushServer {
    /// Create a new server from configuration.
    pub fn new(config: CrushConfig) -> Self {
        Self::from_integration(CrushIntegration::new(config))
    }

    /// Wrap an existing integration (tests inject a fake runner this way).
    pub fn from_integration(integration: CrushIntegration) -> Self {
        Self {
            integration: Arc::new(RwLock::new(integration)),
        }
    }

    /// The four tools: `consult_crush`, `clear_crush_history`,
    /// `crush_status`, `toggle_crush_auto_consult`.
    pub fn tools(&self) -> Vec<BoxedTool> {
        build_tools(Arc::clone(&self.integration))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::crush::tests::{FakeRunner, ok, test_config};
    use serde_json::{Value, json};

    fn tool(tools: &[BoxedTool], name: &str) -> BoxedTool {
        tools
            .iter()
            .find(|t| t.name() == name)
            .cloned()
            .unwrap_or_else(|| panic!("missing tool {name}"))
    }

    fn raw_text(result: &ToolResult) -> String {
        match &result.content[0] {
            Content::Text { text } => text.clone(),
            other => panic!("unexpected content {other:?}"),
        }
    }

    fn text(result: &ToolResult) -> Value {
        serde_json::from_str(&raw_text(result)).unwrap()
    }

    fn server(extra: &[(&str, &str)], runner: Arc<FakeRunner>) -> CrushServer {
        CrushServer::from_integration(CrushIntegration::with_runner(test_config(extra), runner))
    }

    #[test]
    fn exposes_backward_compatible_tools() {
        let tools = server(&[], FakeRunner::new(vec![])).tools();
        let mut names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        names.sort_unstable();
        assert_eq!(
            names,
            [
                "clear_crush_history",
                "consult_crush",
                "crush_status",
                "toggle_crush_auto_consult"
            ]
        );
        let schema = tool(&tools, "consult_crush").schema();
        assert_eq!(schema["required"], json!(["query"]));
        assert_eq!(
            schema["properties"]["mode"]["enum"],
            json!(["quick", "generate", "explain", "convert"])
        );
        for prop in ["query", "context", "comparison_mode", "force", "model"] {
            assert!(schema["properties"].get(prop).is_some(), "missing {prop}");
        }
    }

    #[tokio::test]
    async fn consult_end_to_end_through_tools() {
        let runner = FakeRunner::new(vec![ok("fn add(a: i32, b: i32) -> i32 { a + b }")]);
        let tools = server(&[], runner.clone()).tools();

        let result = tool(&tools, "consult_crush")
            .execute(json!({"query": "add two ints", "mode": "generate"}))
            .await
            .unwrap();
        assert!(!result.is_error);
        let v = text(&result);
        assert_eq!(v["status"], "success");
        assert_eq!(v["mode"], "generate");
        assert!(v["response"].as_str().unwrap().contains("a + b"));
        assert!(v["consultation_id"].is_string());

        let status = text(
            &tool(&tools, "crush_status")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(status["stats"]["completed"], 1);
        assert_eq!(status["history_entries"], 1);
        assert_eq!(status["config"]["execution"], "local");

        let cleared = text(
            &tool(&tools, "clear_crush_history")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(cleared["cleared_count"], 1);
    }

    #[tokio::test]
    async fn errors_set_is_error() {
        let tools = server(&[], FakeRunner::new(vec![])).tools();
        let result = tool(&tools, "consult_crush")
            .execute(json!({"query": "x", "mode": "convert"}))
            .await
            .unwrap();
        assert!(result.is_error);
        assert!(
            text(&result)["error"]
                .as_str()
                .unwrap()
                .contains("target language")
        );
    }

    #[tokio::test]
    async fn status_hides_api_key() {
        let tools = server(&[], FakeRunner::new(vec![])).tools();
        let raw = raw_text(
            &tool(&tools, "crush_status")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert!(!raw.contains("testkey123456"));
        let v: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(v["config"]["api_key_configured"], true);
        assert_eq!(v["config"]["model"], "qwen/qwen3.7-max");
    }
}

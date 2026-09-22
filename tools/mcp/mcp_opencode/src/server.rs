//! MCP server assembly for the OpenCode integration.

use std::sync::Arc;

use mcp_core::prelude::*;
use tokio::sync::RwLock;

use crate::config::OpenCodeConfig;
use crate::consult::{Shared, build_tools};
use crate::opencode::OpenCodeIntegration;

/// OpenCode MCP server: owns the shared integration and builds its tools.
pub struct OpenCodeServer {
    integration: Shared<OpenCodeIntegration>,
}

impl OpenCodeServer {
    /// Create a new server from configuration.
    pub fn new(config: OpenCodeConfig) -> Self {
        Self {
            integration: Arc::new(RwLock::new(OpenCodeIntegration::new(config))),
        }
    }

    /// The four tools: `consult_opencode`, `clear_opencode_history`,
    /// `opencode_status`, `toggle_opencode_auto_consult`.
    pub fn tools(&self) -> Vec<BoxedTool> {
        build_tools(Arc::clone(&self.integration))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{MockResponse, MockServer};
    use serde_json::{Value, json};
    use std::time::Duration;

    fn server_with(pairs: Vec<(&'static str, String)>) -> OpenCodeServer {
        OpenCodeServer::new(OpenCodeConfig::from_lookup(&move |k| {
            pairs
                .iter()
                .find(|(pk, _)| *pk == k)
                .map(|(_, v)| v.clone())
        }))
    }

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

    #[test]
    fn exposes_backward_compatible_tools() {
        let tools = server_with(vec![]).tools();
        let mut names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        names.sort_unstable();
        assert_eq!(
            names,
            [
                "clear_opencode_history",
                "consult_opencode",
                "opencode_status",
                "toggle_opencode_auto_consult"
            ]
        );

        let schema = tool(&tools, "consult_opencode").schema();
        assert_eq!(schema["required"], json!(["query"]));
        for prop in [
            "query",
            "context",
            "mode",
            "comparison_mode",
            "force",
            "model",
            "temperature",
            "max_tokens",
        ] {
            assert!(schema["properties"].get(prop).is_some(), "missing {prop}");
        }
        assert_eq!(
            schema["properties"]["mode"]["enum"],
            json!(["quick", "generate", "refactor", "review", "explain"])
        );
    }

    #[tokio::test]
    async fn invalid_arguments_are_tool_errors() {
        let tools = server_with(vec![]).tools();
        let consult = tool(&tools, "consult_opencode");
        let result = consult.execute(json!({"query": ""})).await.unwrap();
        assert!(result.is_error);
        assert_eq!(text(&result)["status"], "error");

        let result = consult
            .execute(json!({"query": "q", "mode": "nope"}))
            .await
            .unwrap();
        assert!(result.is_error);
        assert!(
            text(&result)["error"]
                .as_str()
                .unwrap()
                .contains("Valid modes")
        );
    }

    #[tokio::test]
    async fn status_reports_config_without_secrets() {
        let tools =
            server_with(vec![("OPENROUTER_API_KEY", "sk-or-v1-hidden-value".into())]).tools();
        let result = tool(&tools, "opencode_status")
            .execute(json!({}))
            .await
            .unwrap();
        let raw = raw_text(&result);
        assert!(!raw.contains("hidden-value"));
        let v: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(v["config"]["api_key_configured"], true);
        assert_eq!(v["config"]["model"], "qwen/qwen3.7-max");
        assert_eq!(v["enabled"], true);
    }

    #[tokio::test]
    async fn disabled_integration_reports_disabled() {
        let tools = server_with(vec![("OPENCODE_ENABLED", "false".into())]).tools();
        let result = tool(&tools, "consult_opencode")
            .execute(json!({"query": "q"}))
            .await
            .unwrap();
        assert!(!result.is_error);
        let v = text(&result);
        assert_eq!(v["status"], "disabled");
        assert!(v["message"].as_str().unwrap().contains("force=true"));
    }

    #[tokio::test]
    async fn status_is_not_blocked_by_inflight_consultation() {
        let mock = MockServer::start(vec![MockResponse::hang()]).await;
        let tools = server_with(vec![
            ("OPENROUTER_API_KEY", "sk-or-v1-testkey123456".into()),
            ("OPENROUTER_BASE_URL", mock.url.clone()),
            ("OPENCODE_TIMEOUT", "30".into()),
        ])
        .tools();

        let consult = tool(&tools, "consult_opencode");
        let inflight = tokio::spawn(async move { consult.execute(json!({"query": "slow"})).await });
        // Wait until the request reaches the mock server.
        for _ in 0..250 {
            if !mock.requests().is_empty() {
                break;
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        assert_eq!(mock.requests().len(), 1);

        let status = tokio::time::timeout(
            Duration::from_secs(2),
            tool(&tools, "opencode_status").execute(json!({})),
        )
        .await
        .expect("status must not wait for the in-flight consultation")
        .unwrap();
        assert_eq!(text(&status)["stats"]["total_consultations"], 1);

        let toggled = tokio::time::timeout(
            Duration::from_secs(2),
            tool(&tools, "toggle_opencode_auto_consult").execute(json!({"enable": false})),
        )
        .await
        .expect("toggle must not wait for the in-flight consultation")
        .unwrap();
        assert_eq!(text(&toggled)["auto_consult_enabled"], false);

        inflight.abort();
    }
}

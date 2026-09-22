//! Behaviour of the four generic AI-consultation tools.

use std::sync::Arc;

use async_trait::async_trait;
use mcp_ai_consult::{
    AiIntegration, ConsultParams, ConsultResult, ConsultStart, IntegrationStats, make_tools,
};
use mcp_core::tool::{BoxedTool, ToolResult};
use serde_json::{Value, json};
use tokio::sync::RwLock;

#[derive(Default)]
struct Fake {
    enabled: bool,
    auto: bool,
    history: Vec<String>,
    fail: bool,
    last_mode: Option<String>,
}

#[async_trait]
impl AiIntegration for Fake {
    fn name(&self) -> &str {
        "Fake"
    }
    fn enabled(&self) -> bool {
        self.enabled
    }
    fn auto_consult(&self) -> bool {
        self.auto
    }
    fn toggle_auto_consult(&mut self, enable: Option<bool>) -> bool {
        self.auto = enable.unwrap_or(!self.auto);
        self.auto
    }
    async fn consult(&mut self, params: ConsultParams) -> ConsultResult {
        self.last_mode = params.mode.clone();
        if !self.enabled && !params.force {
            return ConsultResult::disabled();
        }
        if self.fail {
            return ConsultResult::error("backend exploded".into(), 0.5);
        }
        self.history.push(params.query.clone());
        ConsultResult::success(format!("answer to {}", params.query), 1.5)
    }
    fn clear_history(&mut self) -> usize {
        std::mem::take(&mut self.history).len()
    }
    fn history_len(&self) -> usize {
        self.history.len()
    }
    fn snapshot_stats(&self) -> IntegrationStats {
        IntegrationStats {
            consultations: 2,
            completed: 2,
            total_execution_time: 3.0,
            ..IntegrationStats::default()
        }
    }
}

fn tools(fake: Fake) -> (Arc<RwLock<Fake>>, Vec<BoxedTool>) {
    let shared = Arc::new(RwLock::new(fake));
    let tools = make_tools(
        Arc::clone(&shared),
        "fake",
        "Consult the fake",
        Some(json!({"mode": {"type": "string", "enum": ["quick"]}})),
    );
    (shared, tools)
}

fn find<'a>(tools: &'a [BoxedTool], name: &str) -> &'a BoxedTool {
    tools
        .iter()
        .find(|t| t.name() == name)
        .unwrap_or_else(|| panic!("missing tool {name}"))
}

fn body(r: &ToolResult) -> Value {
    serde_json::from_str(r.first_text().unwrap()).unwrap()
}

#[test]
fn names_and_schema() {
    let (_, tools) = tools(Fake::default());
    let mut names: Vec<_> = tools.iter().map(|t| t.name().to_string()).collect();
    names.sort();
    assert_eq!(
        names,
        vec![
            "clear_fake_history",
            "consult_fake",
            "fake_status",
            "toggle_fake_auto_consult"
        ]
    );
    let schema = find(&tools, "consult_fake").schema();
    assert_eq!(schema["required"], json!(["query"]));
    assert_eq!(schema["properties"]["mode"]["enum"], json!(["quick"]));
    assert_eq!(schema["properties"]["force"]["type"], "boolean");
}

#[tokio::test]
async fn consult_success_disabled_error_and_validation() {
    let (shared, tools) = tools(Fake {
        enabled: true,
        ..Fake::default()
    });
    let consult = find(&tools, "consult_fake");

    let r = consult
        .execute(json!({"query": "why?", "mode": "quick"}))
        .await
        .unwrap();
    assert!(!r.is_error);
    assert_eq!(body(&r)["status"], "success");
    assert_eq!(body(&r)["response"], "answer to why?");
    assert_eq!(shared.read().await.last_mode.as_deref(), Some("quick"));

    // Empty query is a tool error.
    let r = consult.execute(json!({"query": ""})).await.unwrap();
    assert!(r.is_error);

    // Backend failure is flagged isError.
    shared.write().await.fail = true;
    let r = consult.execute(json!({"query": "x"})).await.unwrap();
    assert!(r.is_error);
    assert_eq!(body(&r)["error"], "backend exploded");

    // Disabled is informational, not an error; force overrides it.
    {
        let mut f = shared.write().await;
        f.fail = false;
        f.enabled = false;
    }
    let r = consult.execute(json!({"query": "x"})).await.unwrap();
    assert!(!r.is_error);
    assert_eq!(body(&r)["status"], "disabled");
    let r = consult
        .execute(json!({"query": "x", "force": true}))
        .await
        .unwrap();
    assert_eq!(body(&r)["status"], "success");
}

#[tokio::test]
async fn status_toggle_and_clear() {
    let (shared, tools) = tools(Fake {
        enabled: true,
        history: vec!["a".into(), "b".into()],
        ..Fake::default()
    });

    let r = find(&tools, "fake_status")
        .execute(json!({}))
        .await
        .unwrap();
    let b = body(&r);
    assert_eq!(b["integration"], "fake");
    assert_eq!(b["history_entries"], 2);
    assert_eq!(b["stats"]["average_execution_time"], 1.5);

    let toggle = find(&tools, "toggle_fake_auto_consult");
    let r = toggle.execute(json!({"enable": true})).await.unwrap();
    assert_eq!(body(&r)["auto_consult_enabled"], true);
    let r = toggle.execute(json!({})).await.unwrap();
    assert_eq!(body(&r)["auto_consult_enabled"], false);

    let r = find(&tools, "clear_fake_history")
        .execute(json!({}))
        .await
        .unwrap();
    assert_eq!(body(&r)["cleared_count"], 2);
    assert_eq!(shared.read().await.history_len(), 0);
}

/// An integration using the detached (lock-free) consultation path.
#[derive(Default)]
struct Detached {
    history: Vec<String>,
    release: Arc<tokio::sync::Notify>,
}

#[async_trait]
impl AiIntegration for Detached {
    fn name(&self) -> &str {
        "Detached"
    }
    fn enabled(&self) -> bool {
        true
    }
    fn auto_consult(&self) -> bool {
        false
    }
    fn toggle_auto_consult(&mut self, _enable: Option<bool>) -> bool {
        false
    }
    async fn consult(&mut self, _params: ConsultParams) -> ConsultResult {
        ConsultResult::error("locked path must not be used".into(), 0.0)
    }
    fn clear_history(&mut self) -> usize {
        std::mem::take(&mut self.history).len()
    }
    fn history_len(&self) -> usize {
        self.history.len()
    }
    fn snapshot_stats(&self) -> IntegrationStats {
        IntegrationStats::default()
    }
    fn start_consult(&mut self, params: ConsultParams) -> ConsultStart {
        if params.query == "skip" {
            return ConsultStart::Done(ConsultResult::disabled());
        }
        let release = Arc::clone(&self.release);
        ConsultStart::Detached(Box::pin(async move {
            release.notified().await;
            ConsultResult::success(format!("detached {}", params.query), 0.1)
        }))
    }
    fn finish_consult(&mut self, params: &ConsultParams, _result: &ConsultResult) {
        self.history.push(params.query.clone());
    }
}

#[tokio::test]
async fn detached_consult_releases_the_lock_while_running() {
    let release = Arc::new(tokio::sync::Notify::new());
    let shared = Arc::new(RwLock::new(Detached {
        release: Arc::clone(&release),
        ..Detached::default()
    }));
    let tools = make_tools(Arc::clone(&shared), "det", "d", None);
    let consult = Arc::clone(find(&tools, "consult_det"));
    let status = Arc::clone(find(&tools, "det_status"));

    let running = tokio::spawn(async move { consult.execute(json!({"query": "q"})).await });
    tokio::time::sleep(std::time::Duration::from_millis(20)).await;

    // While the consultation is in flight, status must not block on the lock.
    let r = tokio::time::timeout(std::time::Duration::from_secs(2), status.execute(json!({})))
        .await
        .expect("status blocked behind a running consultation")
        .unwrap();
    assert_eq!(body(&r)["history_entries"], 0);

    release.notify_one();
    let r = running.await.unwrap().unwrap();
    assert_eq!(body(&r)["response"], "detached q");
    // finish_consult ran under the lock afterwards.
    assert_eq!(shared.read().await.history_len(), 1);

    // `Done` short-circuits without finish_consult.
    let r = find(&tools, "consult_det")
        .execute(json!({"query": "skip"}))
        .await
        .unwrap();
    assert_eq!(body(&r)["status"], "disabled");
    assert_eq!(shared.read().await.history_len(), 1);
}

#[test]
fn average_execution_time_handles_zero() {
    assert_eq!(IntegrationStats::default().average_execution_time(), 0.0);
}

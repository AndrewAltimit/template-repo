//! Consultation plumbing: request validation, state bookkeeping, and the
//! `consult_*` / `*_status` MCP tools.
//!
//! NOTE: this file is intentionally kept byte-for-byte identical between
//! `mcp_opencode/src/consult.rs` and `mcp_crush/src/consult.rs`. The two
//! crates stay self-contained (no cross-crate dependency), so shared logic
//! lives in an aligned copy. Change both copies together.
//!
//! # Why not `mcp_ai_consult::make_tools` for everything?
//!
//! The shared `ConsultTool` in `mcp-ai-consult` holds the integration's write
//! lock for the entire upstream call (up to the configured timeout, 5 minutes
//! by default). In HTTP mode that blocks every concurrent consultation *and*
//! the status/clear/toggle tools. The tools here split a consultation into
//! three phases so the lock is only held briefly:
//!
//! 1. [`ConsultBackend::prepare`] (write lock): validate, count, snapshot
//!    config + history into a self-contained [`ConsultJob`].
//! 2. [`ConsultJob::run`] (no lock): perform the slow I/O.
//! 3. [`ConsultBackend::record`] (write lock): update stats and history.
//!
//! The clear-history and toggle-auto-consult tools are reused unchanged from
//! `mcp_ai_consult::make_tools`, so tool names and payloads stay compatible.

use std::collections::VecDeque;
use std::sync::Arc;
use std::time::Instant;

use async_trait::async_trait;
use chrono::Utc;
use mcp_ai_consult::{
    AiIntegration, ConsultParams, ConsultResult, ConsultStatus, HistoryEntry, IntegrationStats,
};
use mcp_core::error::Result;
use mcp_core::tool::{BoxedTool, Tool, ToolResult};
use serde_json::{Map, Value, json};
use tokio::sync::RwLock;

/// Shared handle to a backend, as used by the tools.
pub type Shared<B> = Arc<RwLock<B>>;

/// A validated consultation request.
#[derive(Debug, Clone, Default)]
pub struct ConsultRequest {
    /// The question or code to consult about (never blank).
    pub query: String,
    /// Optional additional context (may be empty).
    pub context: String,
    /// Normalized (lowercase) mode; always one of the backend's `MODES`.
    pub mode: String,
    /// Bypass the `enabled` flag.
    pub force: bool,
    /// The raw tool arguments, for backend-specific optional parameters.
    pub extra: Map<String, Value>,
}

/// Outcome of a consultation plus backend-specific metadata (model, token
/// usage, truncation flags, ...) that is merged into the tool response.
#[derive(Debug, Clone)]
pub struct ConsultOutcome {
    /// The shared result type (status, response/error, timing, id).
    pub result: ConsultResult,
    /// Extra JSON fields merged into the tool response.
    pub meta: Map<String, Value>,
}

impl ConsultOutcome {
    /// Successful consultation.
    pub fn success(response: String, execution_time: f64) -> Self {
        Self::from_result(ConsultResult::success(response, execution_time))
    }

    /// Failed consultation with a human-readable error.
    pub fn error(message: impl Into<String>, execution_time: f64) -> Self {
        Self::from_result(ConsultResult::error(message.into(), execution_time))
    }

    /// Timed-out consultation with a human-readable error.
    pub fn timeout(message: impl Into<String>, execution_time: f64) -> Self {
        let mut result = ConsultResult::timeout(execution_time);
        result.error = Some(message.into());
        Self::from_result(result)
    }

    /// Integration disabled (and `force` was not set).
    pub fn disabled(name: &str) -> Self {
        let mut result = ConsultResult::disabled();
        result.error = Some(format!("{name} integration is disabled"));
        Self::from_result(result)
    }

    fn from_result(result: ConsultResult) -> Self {
        Self {
            result,
            meta: Map::new(),
        }
    }

    /// Attach a metadata field (builder style).
    pub fn with_meta(mut self, key: &str, value: impl Into<Value>) -> Self {
        self.meta.insert(key.to_string(), value.into());
        self
    }

    /// Whether the consultation produced a response.
    #[cfg(test)]
    pub fn is_success(&self) -> bool {
        matches!(self.result.status, ConsultStatus::Success)
    }
}

/// Mutable state common to every backend: flags, bounded history, stats.
#[derive(Debug, Clone)]
pub struct ConsultState {
    /// Whether consultations run without `force`.
    pub enabled: bool,
    /// Advisory flag for clients; the server never consults on its own.
    pub auto_consult: bool,
    /// Whether history is recorded and replayed into prompts.
    pub include_history: bool,
    /// Maximum retained history entries (0 disables history).
    pub max_history: usize,
    history: VecDeque<HistoryEntry>,
    stats: IntegrationStats,
}

impl ConsultState {
    /// Create a new state container.
    pub fn new(
        enabled: bool,
        auto_consult: bool,
        include_history: bool,
        max_history: usize,
    ) -> Self {
        Self {
            enabled,
            auto_consult,
            include_history,
            max_history,
            history: VecDeque::new(),
            stats: IntegrationStats::default(),
        }
    }

    /// Count a consultation attempt.
    pub fn begin(&mut self) {
        self.stats.consultations += 1;
        self.stats.last_consultation = Some(Utc::now());
    }

    /// Record an outcome: stats always, history only on success.
    pub fn finish(&mut self, query: &str, outcome: &ConsultOutcome) {
        match outcome.result.status {
            ConsultStatus::Success => {
                self.stats.completed += 1;
                self.stats.total_execution_time += outcome.result.execution_time;
                if let Some(response) = &outcome.result.response {
                    self.push_history(query, response);
                }
            },
            ConsultStatus::Error | ConsultStatus::Timeout => self.stats.errors += 1,
            ConsultStatus::Disabled => {},
        }
    }

    fn push_history(&mut self, query: &str, response: &str) {
        if !self.include_history || self.max_history == 0 {
            return;
        }
        self.history.push_back(HistoryEntry {
            query: query.to_string(),
            response: response.to_string(),
        });
        while self.history.len() > self.max_history {
            self.history.pop_front();
        }
    }

    /// The most recent `n` history entries (oldest first) if history is on.
    pub fn recent_history(&self, n: usize) -> Vec<HistoryEntry> {
        if !self.include_history {
            return Vec::new();
        }
        let skip = self.history.len().saturating_sub(n);
        self.history.iter().skip(skip).cloned().collect()
    }

    /// Clear history, returning how many entries were removed.
    pub fn clear_history(&mut self) -> usize {
        let n = self.history.len();
        self.history.clear();
        n
    }

    /// Number of retained history entries.
    pub fn history_len(&self) -> usize {
        self.history.len()
    }

    /// Set (`Some`) or flip (`None`) the auto-consult flag; returns new value.
    pub fn toggle_auto_consult(&mut self, enable: Option<bool>) -> bool {
        self.auto_consult = enable.unwrap_or(!self.auto_consult);
        self.auto_consult
    }

    /// Snapshot of the statistics.
    pub fn stats(&self) -> IntegrationStats {
        self.stats.clone()
    }
}

/// A self-contained unit of slow work produced by [`ConsultBackend::prepare`].
#[async_trait]
pub trait ConsultJob: Send + 'static {
    /// Execute the consultation. Must never panic on bad upstream data.
    async fn run(self) -> ConsultOutcome;
}

/// Backend-specific behaviour behind the generic tools.
pub trait ConsultBackend: AiIntegration {
    /// The job type produced by [`prepare`](Self::prepare).
    type Job: ConsultJob;

    /// Accepted `mode` values (lowercase). The first entry is the default.
    const MODES: &'static [&'static str];

    /// Short name used in tool names (`consult_{TOOL_NAME}`), e.g. `opencode`.
    const TOOL_NAME: &'static str;

    /// Description for the `consult_*` tool.
    fn consult_description(&self) -> &'static str;

    /// Additional JSON-schema properties for the `consult_*` tool.
    fn extra_schema(&self) -> Map<String, Value>;

    /// Validate the request and snapshot everything the job needs. Returning
    /// `Err(outcome)` short-circuits (disabled, missing API key, bad option).
    fn prepare(
        &mut self,
        request: &ConsultRequest,
    ) -> std::result::Result<Self::Job, ConsultOutcome>;

    /// Record the outcome of a job that ran (stats + history).
    fn record(&mut self, query: &str, outcome: &ConsultOutcome);

    /// Backend-specific configuration for the status tool (no secrets!).
    fn status_details(&self) -> Value;
}

/// Parse and validate raw tool arguments into a [`ConsultRequest`].
pub fn parse_request(args: &Value, modes: &[&str]) -> std::result::Result<ConsultRequest, String> {
    let obj = match args {
        Value::Object(map) => map.clone(),
        Value::Null => Map::new(),
        _ => return Err("Arguments must be a JSON object".to_string()),
    };

    let query = match obj.get("query") {
        Some(Value::String(s)) if !s.trim().is_empty() => s.clone(),
        Some(Value::String(_)) | None | Some(Value::Null) => {
            return Err("Query parameter is required and cannot be empty".to_string());
        },
        Some(_) => return Err("'query' must be a string".to_string()),
    };

    let context = match obj.get("context") {
        None | Some(Value::Null) => String::new(),
        Some(Value::String(s)) => s.clone(),
        Some(_) => return Err("'context' must be a string".to_string()),
    };

    let mode = match obj.get("mode") {
        None | Some(Value::Null) => modes.first().copied().unwrap_or("quick").to_string(),
        Some(Value::String(s)) => {
            let m = s.trim().to_ascii_lowercase();
            if m.is_empty() {
                modes.first().copied().unwrap_or("quick").to_string()
            } else if modes.contains(&m.as_str()) {
                m
            } else {
                return Err(format!(
                    "Invalid mode '{s}'. Valid modes: {}",
                    modes.join(", ")
                ));
            }
        },
        Some(_) => return Err("'mode' must be a string".to_string()),
    };

    let force = match obj.get("force") {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(_) => return Err("'force' must be a boolean".to_string()),
    };

    if let Some(v) = obj.get("comparison_mode")
        && !(v.is_boolean() || v.is_null())
    {
        return Err("'comparison_mode' must be a boolean".to_string());
    }

    Ok(ConsultRequest {
        query,
        context,
        mode,
        force,
        extra: obj,
    })
}

/// Run a full consultation inline (prepare, run, record) on an exclusively
/// borrowed backend. Used by the [`AiIntegration::consult`] implementations.
pub async fn consult_inline<B: ConsultBackend>(
    backend: &mut B,
    params: ConsultParams,
) -> ConsultResult {
    let args = json!({
        "query": params.query,
        "context": params.context,
        "mode": params.mode,
        "force": params.force,
    });
    let request = match parse_request(&args, B::MODES) {
        Ok(r) => r,
        Err(e) => return ConsultResult::error(e, 0.0),
    };
    match backend.prepare(&request) {
        Err(outcome) => outcome.result,
        Ok(job) => {
            let outcome = job.run().await;
            backend.record(&request.query, &outcome);
            outcome.result
        },
    }
}

/// Build a JSON-schema optional string property.
pub fn string_prop(description: &str) -> Value {
    json!({ "type": "string", "description": description })
}

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

/// `consult_{name}`: runs a consultation without holding the lock across I/O.
pub struct ConsultTool<B: ConsultBackend> {
    backend: Shared<B>,
    name: String,
    description: String,
    extra_schema: Map<String, Value>,
}

#[async_trait]
impl<B: ConsultBackend> Tool for ConsultTool<B> {
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn schema(&self) -> Value {
        let mut props = Map::new();
        props.insert(
            "query".into(),
            json!({"type": "string", "description": "The question, task, or code to consult about"}),
        );
        props.insert(
            "context".into(),
            json!({"type": "string", "description": "Additional context (code, requirements, background)", "default": ""}),
        );
        props.insert(
            "mode".into(),
            json!({
                "type": "string",
                "description": "Consultation mode",
                "enum": B::MODES,
                "default": B::MODES.first().copied().unwrap_or("quick"),
            }),
        );
        props.insert(
            "comparison_mode".into(),
            json!({
                "type": "boolean",
                "description": "Accepted for backward compatibility; currently has no effect",
                "default": true
            }),
        );
        props.insert(
            "force".into(),
            json!({"type": "boolean", "description": "Consult even if the integration is disabled", "default": false}),
        );
        for (k, v) in &self.extra_schema {
            props.insert(k.clone(), v.clone());
        }
        json!({
            "type": "object",
            "properties": props,
            "required": ["query"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let started = Instant::now();
        let request = match parse_request(&args, B::MODES) {
            Ok(r) => r,
            Err(e) => {
                return error_result(&json!({"status": "error", "error": e}));
            },
        };

        // Phase 1: prepare under a short write lock.
        let prepared = {
            let mut backend = self.backend.write().await;
            backend.prepare(&request)
        };

        let outcome = match prepared {
            Err(outcome) => outcome,
            Ok(job) => {
                // Phase 2: slow I/O without any lock held.
                let outcome = job.run().await;
                // Phase 3: record under a short write lock.
                self.backend.write().await.record(&request.query, &outcome);
                outcome
            },
        };

        let mut response = Map::new();
        let result = &outcome.result;
        let is_error = match result.status {
            ConsultStatus::Success => {
                response.insert("status".into(), json!("success"));
                response.insert("response".into(), json!(result.response));
                false
            },
            ConsultStatus::Error => {
                response.insert("status".into(), json!("error"));
                response.insert("error".into(), json!(result.error));
                true
            },
            ConsultStatus::Timeout => {
                response.insert("status".into(), json!("timeout"));
                response.insert("error".into(), json!(result.error));
                true
            },
            ConsultStatus::Disabled => {
                response.insert("status".into(), json!("disabled"));
                let reason = result
                    .error
                    .clone()
                    .unwrap_or_else(|| "Integration is disabled".to_string());
                response.insert(
                    "message".into(),
                    json!(format!(
                        "{}. Use force=true to override.",
                        reason.trim_end_matches('.')
                    )),
                );
                false
            },
        };
        if !matches!(result.status, ConsultStatus::Disabled) {
            let elapsed = if result.execution_time > 0.0 {
                result.execution_time
            } else {
                started.elapsed().as_secs_f64()
            };
            response.insert("execution_time".into(), json!(elapsed));
            response.insert("consultation_id".into(), json!(result.consultation_id));
            response.insert("mode".into(), json!(request.mode));
        }
        for (k, v) in &outcome.meta {
            response.insert(k.clone(), v.clone());
        }

        let value = Value::Object(response);
        if is_error {
            error_result(&value)
        } else {
            ToolResult::json(&value)
        }
    }
}

fn error_result(value: &Value) -> Result<ToolResult> {
    let mut result = ToolResult::json(value)?;
    result.is_error = true;
    Ok(result)
}

/// `{name}_status`: the shared status payload plus backend configuration.
pub struct StatusTool<B: ConsultBackend> {
    backend: Shared<B>,
    name: String,
}

#[async_trait]
impl<B: ConsultBackend> Tool for StatusTool<B> {
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        "Get integration status, configuration (no secrets), and statistics"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let backend = self.backend.read().await;
        let stats = backend.snapshot_stats();
        ToolResult::json(&json!({
            "integration": B::TOOL_NAME,
            "enabled": backend.enabled(),
            "auto_consult": backend.auto_consult(),
            "history_entries": backend.history_len(),
            "stats": {
                "total_consultations": stats.consultations,
                "completed": stats.completed,
                "errors": stats.errors,
                "average_execution_time": stats.average_execution_time(),
                "last_consultation": stats.last_consultation,
            },
            "config": backend.status_details(),
        }))
    }
}

/// Build the four standard tools for `backend`:
/// `consult_{name}`, `clear_{name}_history`, `{name}_status`,
/// `toggle_{name}_auto_consult`.
pub fn build_tools<B: ConsultBackend>(backend: Shared<B>) -> Vec<BoxedTool> {
    let (description, extra_schema) = {
        // `try_read` cannot fail here: nothing else holds the lock during
        // construction. Fall back to empty metadata rather than panicking.
        match backend.try_read() {
            Ok(b) => (b.consult_description().to_string(), b.extra_schema()),
            Err(_) => (String::new(), Map::new()),
        }
    };
    let name = B::TOOL_NAME;
    let consult_name = format!("consult_{name}");
    let status_name = format!("{name}_status");

    let mut tools: Vec<BoxedTool> = vec![
        Arc::new(ConsultTool {
            backend: Arc::clone(&backend),
            name: consult_name.clone(),
            description,
            extra_schema,
        }),
        Arc::new(StatusTool {
            backend: Arc::clone(&backend),
            name: status_name.clone(),
        }),
    ];
    // Reuse the shared clear-history / toggle-auto-consult tools as-is.
    tools.extend(
        mcp_ai_consult::make_tools(backend, name, "", None)
            .into_iter()
            .filter(|t| t.name() != consult_name && t.name() != status_name),
    );
    tools
}

#[cfg(test)]
mod tests {
    use super::*;

    const MODES: &[&str] = &["quick", "generate", "explain"];

    #[test]
    fn parse_request_defaults_and_normalizes() {
        let r = parse_request(&json!({"query": "hi"}), MODES).unwrap();
        assert_eq!(r.mode, "quick");
        assert_eq!(r.context, "");
        assert!(!r.force);

        let r = parse_request(
            &json!({"query": "hi", "mode": " Generate ", "force": true, "context": "c"}),
            MODES,
        )
        .unwrap();
        assert_eq!(r.mode, "generate");
        assert!(r.force);
        assert_eq!(r.context, "c");
    }

    #[test]
    fn parse_request_rejects_bad_input() {
        assert!(parse_request(&json!({}), MODES).is_err());
        assert!(parse_request(&json!({"query": "   "}), MODES).is_err());
        assert!(parse_request(&json!({"query": 5}), MODES).is_err());
        assert!(parse_request(&json!({"query": "q", "context": 1}), MODES).is_err());
        assert!(parse_request(&json!({"query": "q", "force": "yes"}), MODES).is_err());
        assert!(parse_request(&json!({"query": "q", "comparison_mode": "x"}), MODES).is_err());
        assert!(parse_request(&json!("str"), MODES).is_err());
        let err = parse_request(&json!({"query": "q", "mode": "bogus"}), MODES).unwrap_err();
        assert!(err.contains("quick, generate, explain"), "{err}");
    }

    #[test]
    fn state_tracks_stats_and_bounded_history() {
        let mut state = ConsultState::new(true, true, true, 2);
        for i in 0..3 {
            state.begin();
            state.finish(
                &format!("q{i}"),
                &ConsultOutcome::success(format!("r{i}"), 1.0),
            );
        }
        let bad = ConsultOutcome::error("boom", 0.5);
        assert!(!bad.is_success());
        state.begin();
        state.finish("bad", &bad);
        state.begin();
        state.finish("slow", &ConsultOutcome::timeout("late", 9.0));

        let stats = state.stats();
        assert_eq!(stats.consultations, 5);
        assert_eq!(stats.completed, 3);
        assert_eq!(stats.errors, 2);
        assert!((stats.average_execution_time() - 1.0).abs() < f64::EPSILON);

        let hist = state.recent_history(10);
        assert_eq!(hist.len(), 2);
        assert_eq!(hist[0].query, "q1");
        assert_eq!(hist[1].query, "q2");
        assert_eq!(state.recent_history(1)[0].query, "q2");

        assert_eq!(state.clear_history(), 2);
        assert_eq!(state.history_len(), 0);
    }

    #[test]
    fn state_history_can_be_disabled() {
        let mut state = ConsultState::new(true, true, false, 5);
        state.finish("q", &ConsultOutcome::success("r".into(), 1.0));
        assert_eq!(state.history_len(), 0);
        assert!(state.recent_history(3).is_empty());
    }

    #[test]
    fn toggle_auto_consult() {
        let mut state = ConsultState::new(true, true, true, 5);
        assert!(!state.toggle_auto_consult(None));
        assert!(state.toggle_auto_consult(None));
        assert!(!state.toggle_auto_consult(Some(false)));
        assert!(!state.toggle_auto_consult(Some(false)));
    }
}

//! Per-request context available to tools while they execute.
//!
//! The [`Tool`](crate::tool::Tool) trait takes only the JSON arguments, so the
//! request metadata (request id, progress token) and the channel back to the
//! client are exposed through a task-local instead. Inside
//! [`Tool::execute`](crate::tool::Tool::execute):
//!
//! ```no_run
//! # async fn demo() {
//! // Report progress; a no-op when the client did not ask for progress or the
//! // transport cannot push notifications (plain HTTP JSON responses).
//! for step in 0..10u32 {
//!     mcp_core::context::report_progress(f64::from(step), Some(10.0), Some("rendering"));
//!     // ... do work ...
//! }
//! # }
//! ```
//!
//! The context is bound to the task running the tool. Work moved onto
//! `tokio::spawn`ed tasks does not inherit it; capture it first with
//! [`current`] and move the [`RequestContext`] into the task.

use serde_json::{Value, json};
use tokio::sync::mpsc::UnboundedSender;

use crate::jsonrpc::{JSONRPC_VERSION, ProgressParams};

tokio::task_local! {
    static CONTEXT: RequestContext;
}

/// Sink for server-to-client messages (already-serialized JSON-RPC lines).
pub(crate) type Notifier = UnboundedSender<String>;

/// Metadata and client channel for the request currently being handled.
#[derive(Debug, Clone)]
pub struct RequestContext {
    request_id: Value,
    progress_token: Option<Value>,
    notifier: Option<Notifier>,
}

impl RequestContext {
    pub(crate) fn new(request_id: Value, params: &Value, notifier: Option<Notifier>) -> Self {
        let progress_token = params
            .get("_meta")
            .and_then(|m| m.get("progressToken"))
            .filter(|t| t.is_string() || t.is_number())
            .cloned();
        Self {
            request_id,
            progress_token,
            notifier,
        }
    }

    /// Run `fut` with this context installed as the current one.
    pub(crate) async fn scope<F: Future>(self, fut: F) -> F::Output {
        CONTEXT.scope(self, fut).await
    }

    /// The JSON-RPC id of the request being served.
    pub fn request_id(&self) -> &Value {
        &self.request_id
    }

    /// The client's `_meta.progressToken`, if it asked for progress updates.
    pub fn progress_token(&self) -> Option<&Value> {
        self.progress_token.as_ref()
    }

    /// Whether this transport can push notifications to the client.
    pub fn can_notify(&self) -> bool {
        self.notifier.as_ref().is_some_and(|n| !n.is_closed())
    }

    /// Send a `notifications/progress` for this request.
    ///
    /// `progress` must increase with every call (per the MCP spec); `total`
    /// may be omitted when unknown. Returns `true` if a notification was
    /// queued, `false` when the client did not supply a progress token or the
    /// transport cannot deliver notifications.
    pub fn report_progress(
        &self,
        progress: f64,
        total: Option<f64>,
        message: Option<&str>,
    ) -> bool {
        let Some(token) = &self.progress_token else {
            return false;
        };
        let params = ProgressParams {
            progress_token: token.clone(),
            progress,
            total,
            message: message.map(str::to_string),
        };
        match serde_json::to_value(params) {
            Ok(params) => self.notify("notifications/progress", params),
            Err(_) => false,
        }
    }

    /// Send an arbitrary JSON-RPC notification to the client.
    ///
    /// Returns `false` when the transport cannot deliver notifications.
    pub fn notify(&self, method: &str, params: Value) -> bool {
        let Some(notifier) = &self.notifier else {
            return false;
        };
        let msg = json!({"jsonrpc": JSONRPC_VERSION, "method": method, "params": params});
        notifier.send(msg.to_string()).is_ok()
    }
}

/// The context of the request whose tool is currently executing on this task,
/// or `None` outside of a `tools/call`.
pub fn current() -> Option<RequestContext> {
    CONTEXT.try_with(Clone::clone).ok()
}

/// Report progress for the current request; see
/// [`RequestContext::report_progress`]. A no-op returning `false` outside a
/// tool call.
pub fn report_progress(progress: f64, total: Option<f64>, message: Option<&str>) -> bool {
    CONTEXT
        .try_with(|ctx| ctx.report_progress(progress, total, message))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn no_context_outside_scope() {
        assert!(current().is_none());
        assert!(!report_progress(1.0, None, None));
    }

    #[tokio::test]
    async fn progress_is_sent_only_with_token() {
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        let params = json!({"_meta": {"progressToken": "tok"}});
        let ctx = RequestContext::new(json!(7), &params, Some(tx.clone()));
        ctx.scope(async {
            assert_eq!(current().unwrap().request_id(), &json!(7));
            assert!(report_progress(1.0, Some(4.0), Some("step")));
        })
        .await;
        let line = rx.recv().await.unwrap();
        let v: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(v["method"], "notifications/progress");
        assert_eq!(v["params"]["progressToken"], "tok");
        assert_eq!(v["params"]["progress"], 1.0);
        assert_eq!(v["params"]["total"], 4.0);
        assert_eq!(v["params"]["message"], "step");
        assert!(v.get("id").is_none());

        let no_token = RequestContext::new(json!(8), &json!({}), Some(tx));
        assert!(!no_token.report_progress(1.0, None, None));
        assert!(no_token.can_notify());
    }

    #[tokio::test]
    async fn no_notifier_means_no_delivery() {
        let ctx = RequestContext::new(json!(1), &json!({"_meta": {"progressToken": 5}}), None);
        assert_eq!(ctx.progress_token(), Some(&json!(5)));
        assert!(!ctx.can_notify());
        assert!(!ctx.report_progress(1.0, None, None));
    }
}

//! Shared types for AI consultation servers.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::pin::Pin;
use uuid::Uuid;

/// Status of a consultation.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConsultStatus {
    /// The backend answered
    Success,
    /// The backend failed
    Error,
    /// The integration is disabled (and `force` was not set)
    Disabled,
    /// The backend did not answer in time
    Timeout,
}

/// Result of an AI consultation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsultResult {
    /// Outcome
    pub status: ConsultStatus,
    /// Backend answer (on success)
    pub response: Option<String>,
    /// Error message (on failure)
    pub error: Option<String>,
    /// Wall-clock seconds spent
    pub execution_time: f64,
    /// Unique id of this consultation
    pub consultation_id: String,
    /// When the result was produced
    pub timestamp: DateTime<Utc>,
}

impl ConsultResult {
    /// Successful consultation
    pub fn success(response: String, execution_time: f64) -> Self {
        Self {
            status: ConsultStatus::Success,
            response: Some(response),
            error: None,
            execution_time,
            consultation_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
        }
    }

    /// Failed consultation
    pub fn error(error: String, execution_time: f64) -> Self {
        Self {
            status: ConsultStatus::Error,
            response: None,
            error: Some(error),
            execution_time,
            consultation_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
        }
    }

    /// Integration disabled
    pub fn disabled() -> Self {
        Self {
            status: ConsultStatus::Disabled,
            response: None,
            error: Some("Integration is disabled".to_string()),
            execution_time: 0.0,
            consultation_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
        }
    }

    /// Timed-out consultation
    pub fn timeout(execution_time: f64) -> Self {
        Self {
            status: ConsultStatus::Timeout,
            response: None,
            error: Some("Consultation timed out".to_string()),
            execution_time,
            consultation_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
        }
    }
}

/// A conversation history entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryEntry {
    /// The question or code
    pub query: String,
    /// The backend answer
    pub response: String,
}

/// Statistics for an AI integration (returned as owned value for trait compatibility).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct IntegrationStats {
    /// Consultations attempted
    pub consultations: u64,
    /// Consultations that completed
    pub completed: u64,
    /// Consultations that failed
    pub errors: u64,
    /// Sum of execution times of completed consultations (seconds)
    pub total_execution_time: f64,
    /// Time of the most recent consultation
    pub last_consultation: Option<DateTime<Utc>>,
}

impl IntegrationStats {
    /// Mean execution time of completed consultations (0 when none)
    pub fn average_execution_time(&self) -> f64 {
        if self.completed == 0 {
            0.0
        } else {
            self.total_execution_time / self.completed as f64
        }
    }
}

/// Parameters for a consultation request.
#[derive(Debug, Clone)]
pub struct ConsultParams {
    /// The question or code
    pub query: String,
    /// Additional context
    pub context: String,
    /// Backend-specific mode, if the tool schema defines one
    pub mode: Option<String>,
    /// Compare with a previous Claude response
    pub comparison_mode: bool,
    /// Consult even when disabled
    pub force: bool,
}

/// Trait that each AI backend must implement.
///
/// The framework handles tool registration and the standard 4-tool pattern
/// (consult, clear_history, status, toggle_auto_consult) generically.
/// Each backend implements this trait to provide its specific behavior.
///
/// Methods return owned values to avoid lifetime issues with heterogeneous
/// backend types that may store stats/history in different internal formats.
#[async_trait]
pub trait AiIntegration: Send + Sync + 'static {
    /// Human-readable name of this integration (e.g., "Gemini", "Codex").
    fn name(&self) -> &str;

    /// Whether the integration is currently enabled.
    fn enabled(&self) -> bool;

    /// Whether auto-consultation is enabled.
    fn auto_consult(&self) -> bool;

    /// Toggle auto-consultation. Returns the new state.
    fn toggle_auto_consult(&mut self, enable: Option<bool>) -> bool;

    /// Execute a consultation. The implementation handles its own history
    /// and stats tracking internally.
    async fn consult(&mut self, params: ConsultParams) -> ConsultResult;

    /// Clear conversation history. Returns the number of entries cleared.
    fn clear_history(&mut self) -> usize;

    /// Get the number of history entries.
    fn history_len(&self) -> usize;

    /// Get a snapshot of current statistics.
    fn snapshot_stats(&self) -> IntegrationStats;

    /// Opt-in: begin a consultation *without* keeping the integration locked
    /// while the backend runs.
    ///
    /// The consult tool calls this under the write lock. Return
    /// [`ConsultStart::Detached`] with a `'static` future (clone whatever
    /// config/client it needs out of `self`); the lock is released while it
    /// runs, so status/clear/toggle calls and other consultations are not
    /// blocked, then [`finish_consult`](Self::finish_consult) is called under
    /// the lock again to record history and stats.
    ///
    /// The default returns [`ConsultStart::Unsupported`], which makes the tool
    /// fall back to [`consult`](Self::consult) under the write lock (the
    /// original behaviour), so existing implementations keep working.
    fn start_consult(&mut self, params: ConsultParams) -> ConsultStart {
        ConsultStart::Unsupported(params)
    }

    /// Record the outcome of a [`ConsultStart::Detached`] consultation
    /// (history, stats). Called under the write lock. Default: no-op.
    fn finish_consult(&mut self, params: &ConsultParams, result: &ConsultResult) {
        let _ = (params, result);
    }
}

/// Backend work for one consultation that runs without the integration lock.
pub type DetachedConsult = Pin<Box<dyn Future<Output = ConsultResult> + Send + 'static>>;

/// How [`AiIntegration::start_consult`] wants a consultation to proceed.
pub enum ConsultStart {
    /// Not supported: run [`AiIntegration::consult`] under the write lock.
    Unsupported(ConsultParams),
    /// Already decided without backend work (e.g. disabled, invalid input).
    /// `finish_consult` is not called.
    Done(ConsultResult),
    /// Run this future with the lock released, then call `finish_consult`.
    Detached(DetachedConsult),
}

impl std::fmt::Debug for ConsultStart {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Unsupported(p) => f.debug_tuple("Unsupported").field(p).finish(),
            Self::Done(r) => f.debug_tuple("Done").field(r).finish(),
            Self::Detached(_) => f.write_str("Detached(..)"),
        }
    }
}

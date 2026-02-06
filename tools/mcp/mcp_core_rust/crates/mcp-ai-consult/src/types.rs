//! Shared types for AI consultation servers.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Status of a consultation.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConsultStatus {
    Success,
    Error,
    Disabled,
    Timeout,
}

/// Result of an AI consultation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsultResult {
    pub status: ConsultStatus,
    pub response: Option<String>,
    pub error: Option<String>,
    pub execution_time: f64,
    pub consultation_id: String,
    pub timestamp: DateTime<Utc>,
}

impl ConsultResult {
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
    pub query: String,
    pub response: String,
}

/// Statistics for an AI integration (returned as owned value for trait compatibility).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct IntegrationStats {
    pub consultations: u64,
    pub completed: u64,
    pub errors: u64,
    pub total_execution_time: f64,
    pub last_consultation: Option<DateTime<Utc>>,
}

impl IntegrationStats {
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
    pub query: String,
    pub context: String,
    pub mode: Option<String>,
    pub comparison_mode: bool,
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
}

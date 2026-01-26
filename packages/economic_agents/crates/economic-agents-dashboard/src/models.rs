//! Request/response models for dashboard API.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

use economic_agents_core::{
    AgentConfig, AgentState, CycleResult, EngineType, OperatingMode, Personality,
    TaskSelectionStrategy,
};

// ============================================================================
// Health & Status
// ============================================================================

/// Health check response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    /// Service status.
    pub status: String,
    /// Service name.
    pub service: String,
    /// Timestamp.
    pub timestamp: DateTime<Utc>,
    /// Version.
    pub version: String,
    /// Uptime in seconds.
    pub uptime_seconds: u64,
}

impl HealthResponse {
    /// Create a healthy response.
    pub fn healthy(uptime_seconds: u64) -> Self {
        Self {
            status: "healthy".to_string(),
            service: "dashboard".to_string(),
            timestamp: Utc::now(),
            version: env!("CARGO_PKG_VERSION").to_string(),
            uptime_seconds,
        }
    }
}

/// Dashboard status response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardStatusResponse {
    /// Health information.
    pub health: HealthResponse,
    /// Number of registered agents.
    pub agent_count: usize,
    /// Number of active agents.
    pub active_agent_count: usize,
    /// Number of connected WebSocket clients.
    pub websocket_clients: usize,
    /// Total events processed.
    pub events_processed: u64,
}

// ============================================================================
// Agent Management
// ============================================================================

/// Request to create a new agent.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CreateAgentRequest {
    /// Optional custom agent ID.
    #[serde(default)]
    pub agent_id: Option<String>,
    /// Engine type.
    #[serde(default)]
    pub engine_type: Option<String>,
    /// Operating mode.
    #[serde(default)]
    pub mode: Option<String>,
    /// Personality type.
    #[serde(default)]
    pub personality: Option<String>,
    /// Task selection strategy.
    #[serde(default)]
    pub task_selection_strategy: Option<String>,
    /// Survival buffer hours.
    #[serde(default)]
    pub survival_buffer_hours: Option<f64>,
    /// Company formation threshold.
    #[serde(default)]
    pub company_threshold: Option<f64>,
    /// Maximum cycles to run.
    #[serde(default)]
    pub max_cycles: Option<u32>,
    /// Initial balance.
    #[serde(default)]
    pub initial_balance: Option<f64>,
    /// Initial compute hours.
    #[serde(default)]
    pub initial_compute_hours: Option<f64>,
}

impl CreateAgentRequest {
    /// Build an AgentConfig from this request.
    pub fn to_config(&self) -> AgentConfig {
        let mut config = AgentConfig::default();

        if let Some(engine) = &self.engine_type {
            config.engine_type = match engine.to_lowercase().as_str() {
                "llm" => EngineType::Llm,
                _ => EngineType::RuleBased,
            };
        }

        if let Some(mode) = &self.mode {
            config.mode = match mode.to_lowercase().as_str() {
                "company" => OperatingMode::Company,
                _ => OperatingMode::Survival,
            };
        }

        if let Some(personality) = &self.personality {
            config.personality = match personality.to_lowercase().as_str() {
                "aggressive" => Personality::Aggressive,
                "risk_averse" | "riskaverse" => Personality::RiskAverse,
                _ => Personality::Balanced,
            };
        }

        if let Some(strategy) = &self.task_selection_strategy {
            config.task_selection_strategy = match strategy.to_lowercase().as_str() {
                "highest_reward" | "highestreward" => TaskSelectionStrategy::HighestReward,
                "best_ratio" | "bestratio" => TaskSelectionStrategy::BestRatio,
                "balanced" => TaskSelectionStrategy::Balanced,
                _ => TaskSelectionStrategy::FirstAvailable,
            };
        }

        if let Some(hours) = self.survival_buffer_hours {
            config.survival_buffer_hours = hours;
        }

        if let Some(threshold) = self.company_threshold {
            config.company_threshold = threshold;
        }

        if let Some(cycles) = self.max_cycles {
            config.max_cycles = Some(cycles);
        }

        config
    }
}

/// Agent summary for listing.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSummary {
    /// Agent ID.
    pub id: String,
    /// Current state.
    pub state: AgentState,
    /// Configuration summary.
    pub config: AgentConfigSummary,
    /// Whether agent is currently running.
    pub is_running: bool,
    /// Current cycle number.
    pub current_cycle: u32,
    /// Last activity timestamp.
    pub last_activity: DateTime<Utc>,
}

/// Simplified agent configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfigSummary {
    pub engine_type: String,
    pub mode: String,
    pub personality: String,
    pub task_selection_strategy: String,
    pub survival_buffer_hours: f64,
    pub company_threshold: f64,
    pub max_cycles: Option<u32>,
}

impl From<&AgentConfig> for AgentConfigSummary {
    fn from(config: &AgentConfig) -> Self {
        Self {
            engine_type: format!("{:?}", config.engine_type),
            mode: format!("{:?}", config.mode),
            personality: format!("{:?}", config.personality),
            task_selection_strategy: format!("{:?}", config.task_selection_strategy),
            survival_buffer_hours: config.survival_buffer_hours,
            company_threshold: config.company_threshold,
            max_cycles: config.max_cycles,
        }
    }
}

/// Full agent details response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentDetailsResponse {
    /// Agent summary.
    pub agent: AgentSummary,
    /// Recent cycle results.
    pub recent_cycles: Vec<CycleResult>,
    /// Performance statistics.
    pub stats: AgentStats,
}

/// Agent performance statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentStats {
    /// Total tasks completed.
    pub tasks_completed: u32,
    /// Total tasks failed.
    pub tasks_failed: u32,
    /// Success rate.
    pub success_rate: f64,
    /// Total earnings.
    pub total_earnings: f64,
    /// Total expenses.
    pub total_expenses: f64,
    /// Net profit.
    pub net_profit: f64,
    /// Average cycle duration in ms.
    pub avg_cycle_duration_ms: f64,
}

/// Response for agent list.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentListResponse {
    /// List of agents.
    pub agents: Vec<AgentSummary>,
    /// Total count.
    pub total: usize,
}

/// Request to start an agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StartAgentRequest {
    /// Maximum cycles to run (optional override).
    #[serde(default)]
    pub max_cycles: Option<u32>,
}

/// Response after starting/stopping an agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentActionResponse {
    /// Agent ID.
    pub agent_id: String,
    /// Action performed.
    pub action: String,
    /// Success status.
    pub success: bool,
    /// Message.
    pub message: String,
}

// ============================================================================
// Metrics
// ============================================================================

/// Metrics snapshot response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsResponse {
    /// Counter metrics.
    pub counters: HashMap<String, u64>,
    /// Gauge metrics.
    pub gauges: HashMap<String, f64>,
    /// Timestamp.
    pub timestamp: DateTime<Utc>,
}

/// Prometheus-format metrics response.
#[derive(Debug, Clone, Serialize)]
pub struct PrometheusMetrics {
    pub content: String,
}

// ============================================================================
// Events
// ============================================================================

/// Request to list events.
#[derive(Debug, Clone, Deserialize)]
pub struct ListEventsRequest {
    /// Maximum number of events.
    #[serde(default = "default_event_limit")]
    pub limit: usize,
    /// Filter by event type.
    #[serde(default)]
    pub event_type: Option<String>,
    /// Filter by source.
    #[serde(default)]
    pub source: Option<String>,
}

fn default_event_limit() -> usize {
    100
}

/// Event list response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventListResponse {
    /// List of events.
    pub events: Vec<EventSummary>,
    /// Total count in response.
    pub count: usize,
}

/// Event summary.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventSummary {
    /// Event ID.
    pub id: Uuid,
    /// Event type.
    pub event_type: String,
    /// Source.
    pub source: String,
    /// Payload (JSON).
    pub payload: serde_json::Value,
    /// Timestamp.
    pub timestamp: DateTime<Utc>,
}

// ============================================================================
// Decision Log
// ============================================================================

/// Request to list decisions.
#[derive(Debug, Clone, Deserialize)]
pub struct ListDecisionsRequest {
    /// Maximum number of decisions.
    #[serde(default = "default_decision_limit")]
    pub limit: usize,
    /// Filter by agent ID.
    #[serde(default)]
    pub agent_id: Option<String>,
}

fn default_decision_limit() -> usize {
    100
}

/// Decision list response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionListResponse {
    /// List of decisions.
    pub decisions: Vec<DecisionSummary>,
    /// Total count in response.
    pub count: usize,
}

/// Decision summary.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionSummary {
    /// Decision ID.
    pub id: Uuid,
    /// Agent ID.
    pub agent_id: String,
    /// Decision type.
    pub decision_type: String,
    /// Reasoning.
    pub reasoning: String,
    /// Confidence.
    pub confidence: f64,
    /// Outcome (if known).
    pub outcome: Option<String>,
    /// Timestamp.
    pub timestamp: DateTime<Utc>,
}

// ============================================================================
// WebSocket Messages
// ============================================================================

/// WebSocket message types.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum WsMessage {
    /// Event notification.
    Event(EventSummary),
    /// Agent state update.
    AgentUpdate(AgentSummary),
    /// Cycle completed.
    CycleCompleted {
        agent_id: String,
        cycle: u32,
        success: bool,
    },
    /// Metrics update.
    MetricsUpdate(MetricsResponse),
    /// Error message.
    Error { message: String },
    /// Heartbeat/ping.
    Ping,
    /// Pong response.
    Pong,
}

/// WebSocket subscription request.
#[derive(Debug, Clone, Deserialize)]
pub struct WsSubscription {
    /// Subscribe to events.
    #[serde(default)]
    pub events: bool,
    /// Subscribe to agent updates.
    #[serde(default)]
    pub agent_updates: bool,
    /// Subscribe to metrics updates.
    #[serde(default)]
    pub metrics: bool,
    /// Specific agent IDs to watch.
    #[serde(default)]
    pub agent_ids: Vec<String>,
}

impl Default for WsSubscription {
    fn default() -> Self {
        Self {
            events: true,
            agent_updates: true,
            metrics: false,
            agent_ids: Vec::new(),
        }
    }
}

// ============================================================================
// Error Response
// ============================================================================

/// API error response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiErrorResponse {
    /// Error message.
    pub error: String,
    /// Error code.
    pub code: String,
    /// Optional details.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

impl ApiErrorResponse {
    /// Create a new error response.
    pub fn new(error: impl Into<String>, code: impl Into<String>) -> Self {
        Self {
            error: error.into(),
            code: code.into(),
            details: None,
        }
    }

    /// Add details to the error.
    pub fn with_details(mut self, details: serde_json::Value) -> Self {
        self.details = Some(details);
        self
    }
}

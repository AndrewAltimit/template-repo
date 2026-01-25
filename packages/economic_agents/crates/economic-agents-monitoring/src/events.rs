//! Event bus implementation.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::{RwLock, broadcast};
use uuid::Uuid;

/// Event types in the system.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    /// Agent lifecycle events.
    AgentStarted,
    AgentStopped,
    CycleCompleted,

    /// Task events.
    TaskClaimed,
    TaskSubmitted,
    TaskCompleted,
    TaskRejected,

    /// Financial events.
    PaymentReceived,
    PaymentSent,
    BalanceChanged,

    /// Company events.
    CompanyFormed,
    CompanyStageChanged,
    InvestmentReceived,

    /// System events.
    Error,
    Warning,
    MetricRecorded,
}

/// An event in the system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    /// Event ID.
    pub id: Uuid,
    /// Event type.
    pub event_type: EventType,
    /// Source agent/component.
    pub source: String,
    /// Event payload (JSON).
    pub payload: serde_json::Value,
    /// Timestamp.
    pub timestamp: DateTime<Utc>,
}

impl Event {
    /// Create a new event.
    pub fn new(
        event_type: EventType,
        source: impl Into<String>,
        payload: serde_json::Value,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            event_type,
            source: source.into(),
            payload,
            timestamp: Utc::now(),
        }
    }
}

/// Event bus for publishing and subscribing to events.
pub struct EventBus {
    sender: broadcast::Sender<Event>,
    history: Arc<RwLock<Vec<Event>>>,
    max_history: usize,
}

impl EventBus {
    /// Create a new event bus.
    pub fn new(capacity: usize) -> Self {
        let (sender, _) = broadcast::channel(capacity);
        Self {
            sender,
            history: Arc::new(RwLock::new(Vec::new())),
            max_history: 1000,
        }
    }

    /// Publish an event.
    pub async fn publish(&self, event: Event) {
        // Store in history
        let mut history = self.history.write().await;
        history.push(event.clone());
        if history.len() > self.max_history {
            history.remove(0);
        }
        drop(history);

        // Broadcast to subscribers (ignore errors if no subscribers)
        let _ = self.sender.send(event);
    }

    /// Subscribe to events.
    pub fn subscribe(&self) -> broadcast::Receiver<Event> {
        self.sender.subscribe()
    }

    /// Get recent events.
    pub async fn recent(&self, count: usize) -> Vec<Event> {
        let history = self.history.read().await;
        let start = history.len().saturating_sub(count);
        history[start..].to_vec()
    }

    /// Get events by type.
    pub async fn by_type(&self, event_type: EventType) -> Vec<Event> {
        let history = self.history.read().await;
        history
            .iter()
            .filter(|e| e.event_type == event_type)
            .cloned()
            .collect()
    }
}

impl Default for EventBus {
    fn default() -> Self {
        Self::new(1000)
    }
}

//! Decision logging.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// A logged decision.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggedDecision {
    /// Decision ID.
    pub id: Uuid,
    /// Agent that made the decision.
    pub agent_id: String,
    /// Decision type.
    pub decision_type: String,
    /// Reasoning.
    pub reasoning: String,
    /// Confidence level.
    pub confidence: f64,
    /// Context at time of decision.
    pub context: serde_json::Value,
    /// Outcome (filled in later).
    pub outcome: Option<String>,
    /// Timestamp.
    pub timestamp: DateTime<Utc>,
}

/// Logs agent decisions for analysis.
pub struct DecisionLogger {
    decisions: Arc<RwLock<VecDeque<LoggedDecision>>>,
    max_decisions: usize,
}

impl DecisionLogger {
    /// Create a new decision logger.
    pub fn new() -> Self {
        Self {
            decisions: Arc::new(RwLock::new(VecDeque::new())),
            max_decisions: 10000,
        }
    }

    /// Log a decision.
    pub async fn log(
        &self,
        agent_id: impl Into<String>,
        decision_type: impl Into<String>,
        reasoning: impl Into<String>,
        confidence: f64,
        context: serde_json::Value,
    ) -> Uuid {
        let decision = LoggedDecision {
            id: Uuid::new_v4(),
            agent_id: agent_id.into(),
            decision_type: decision_type.into(),
            reasoning: reasoning.into(),
            confidence,
            context,
            outcome: None,
            timestamp: Utc::now(),
        };

        let id = decision.id;

        let mut decisions = self.decisions.write().await;
        decisions.push_back(decision);
        if decisions.len() > self.max_decisions {
            decisions.pop_front();
        }

        id
    }

    /// Update a decision with its outcome.
    pub async fn update_outcome(&self, decision_id: Uuid, outcome: impl Into<String>) {
        let mut decisions = self.decisions.write().await;
        if let Some(d) = decisions.iter_mut().find(|d| d.id == decision_id) {
            d.outcome = Some(outcome.into());
        }
    }

    /// Get all decisions for an agent.
    pub async fn for_agent(&self, agent_id: &str) -> Vec<LoggedDecision> {
        let decisions = self.decisions.read().await;
        decisions
            .iter()
            .filter(|d| d.agent_id == agent_id)
            .cloned()
            .collect()
    }

    /// Get recent decisions.
    pub async fn recent(&self, count: usize) -> Vec<LoggedDecision> {
        let decisions = self.decisions.read().await;
        decisions.iter().rev().take(count).rev().cloned().collect()
    }
}

impl Default for DecisionLogger {
    fn default() -> Self {
        Self::new()
    }
}

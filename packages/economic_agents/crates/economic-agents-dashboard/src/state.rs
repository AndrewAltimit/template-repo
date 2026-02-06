//! Dashboard shared state.

use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use std::time::Instant;

use chrono::Utc;
use tokio::sync::{RwLock, broadcast};

use economic_agents_core::{AgentConfig, AutonomousAgent, Backends, CycleResult};
use economic_agents_monitoring::{DecisionLogger, EventBus, MetricsCollector};

use crate::models::{AgentConfigSummary, AgentStats, AgentSummary, WsMessage};

/// Managed agent entry.
pub struct ManagedAgent {
    /// The agent instance.
    pub agent: AutonomousAgent,
    /// Whether the agent is currently running.
    pub is_running: bool,
    /// Cycle history.
    pub cycle_history: VecDeque<CycleResult>,
    /// Last activity timestamp.
    pub last_activity: chrono::DateTime<Utc>,
}

impl ManagedAgent {
    /// Create a new managed agent.
    pub fn new(agent: AutonomousAgent) -> Self {
        Self {
            agent,
            is_running: false,
            cycle_history: VecDeque::new(),
            last_activity: Utc::now(),
        }
    }

    /// Get agent summary.
    pub fn summary(&self) -> AgentSummary {
        AgentSummary {
            id: self.agent.id.clone(),
            state: self.agent.state.clone(),
            config: AgentConfigSummary::from(&self.agent.config),
            is_running: self.is_running,
            current_cycle: self.agent.state.current_cycle,
            last_activity: self.last_activity,
        }
    }

    /// Calculate agent stats.
    pub fn stats(&self) -> AgentStats {
        let state = &self.agent.state;

        let avg_duration = if self.cycle_history.is_empty() {
            0.0
        } else {
            let total: u64 = self.cycle_history.iter().map(|c| c.duration_ms).sum();
            total as f64 / self.cycle_history.len() as f64
        };

        AgentStats {
            tasks_completed: state.tasks_completed,
            tasks_failed: state.tasks_failed,
            success_rate: state.success_rate(),
            total_earnings: state.total_earnings,
            total_expenses: state.total_expenses,
            net_profit: state.total_earnings - state.total_expenses,
            avg_cycle_duration_ms: avg_duration,
        }
    }

    /// Add a cycle result to history.
    pub fn add_cycle(&mut self, result: CycleResult) {
        self.cycle_history.push_back(result);
        self.last_activity = Utc::now();
        // Keep only last 1000 cycles
        if self.cycle_history.len() > 1000 {
            self.cycle_history.pop_front();
        }
    }

    /// Get recent cycles.
    pub fn recent_cycles(&self, count: usize) -> Vec<CycleResult> {
        self.cycle_history
            .iter()
            .rev()
            .take(count)
            .rev()
            .cloned()
            .collect()
    }
}

/// Dashboard shared state.
pub struct DashboardState {
    /// Registered agents.
    pub agents: RwLock<HashMap<String, ManagedAgent>>,
    /// Event bus.
    pub event_bus: Arc<EventBus>,
    /// Metrics collector.
    pub metrics: Arc<MetricsCollector>,
    /// Decision logger.
    pub decision_logger: Arc<DecisionLogger>,
    /// WebSocket broadcast sender.
    pub ws_broadcast: broadcast::Sender<WsMessage>,
    /// Server start time.
    pub start_time: Instant,
    /// Events processed counter.
    pub events_processed: RwLock<u64>,
    /// Connected WebSocket clients count.
    pub ws_client_count: RwLock<usize>,
}

impl DashboardState {
    /// Create a new dashboard state.
    pub fn new() -> Self {
        let (ws_broadcast, _) = broadcast::channel(1000);

        Self {
            agents: RwLock::new(HashMap::new()),
            event_bus: Arc::new(EventBus::default()),
            metrics: Arc::new(MetricsCollector::new()),
            decision_logger: Arc::new(DecisionLogger::new()),
            ws_broadcast,
            start_time: Instant::now(),
            events_processed: RwLock::new(0),
            ws_client_count: RwLock::new(0),
        }
    }

    /// Get uptime in seconds.
    pub fn uptime_seconds(&self) -> u64 {
        self.start_time.elapsed().as_secs()
    }

    /// Register a new agent.
    pub async fn register_agent(&self, config: AgentConfig, backends: Option<Backends>) -> String {
        let agent = if let Some(b) = backends {
            AutonomousAgent::with_backends(config, b)
        } else {
            AutonomousAgent::new(config)
        };

        let id = agent.id.clone();
        let managed = ManagedAgent::new(agent);

        let mut agents = self.agents.write().await;
        agents.insert(id.clone(), managed);

        // Update metrics
        self.metrics.increment("agents_registered").await;
        self.metrics
            .gauge("agents_total", agents.len() as f64)
            .await;

        id
    }

    /// Get an agent by ID.
    pub async fn get_agent(&self, id: &str) -> Option<AgentSummary> {
        let agents = self.agents.read().await;
        agents.get(id).map(|a| a.summary())
    }

    /// Get all agents.
    pub async fn list_agents(&self) -> Vec<AgentSummary> {
        let agents = self.agents.read().await;
        agents.values().map(|a| a.summary()).collect()
    }

    /// Remove an agent.
    pub async fn remove_agent(&self, id: &str) -> bool {
        let mut agents = self.agents.write().await;
        let removed = agents.remove(id).is_some();

        if removed {
            self.metrics
                .gauge("agents_total", agents.len() as f64)
                .await;
        }

        removed
    }

    /// Increment events processed counter.
    pub async fn increment_events(&self) {
        let mut count = self.events_processed.write().await;
        *count += 1;
    }

    /// Get events processed count.
    pub async fn events_processed(&self) -> u64 {
        *self.events_processed.read().await
    }

    /// Increment WebSocket client count.
    pub async fn add_ws_client(&self) {
        let mut count = self.ws_client_count.write().await;
        *count += 1;
        self.metrics.gauge("ws_clients", *count as f64).await;
    }

    /// Decrement WebSocket client count.
    pub async fn remove_ws_client(&self) {
        let mut count = self.ws_client_count.write().await;
        *count = count.saturating_sub(1);
        self.metrics.gauge("ws_clients", *count as f64).await;
    }

    /// Get WebSocket client count.
    pub async fn ws_client_count(&self) -> usize {
        *self.ws_client_count.read().await
    }

    /// Broadcast a message to all WebSocket clients.
    pub fn broadcast(&self, message: WsMessage) {
        // Ignore send errors (no receivers)
        let _ = self.ws_broadcast.send(message);
    }

    /// Subscribe to WebSocket broadcasts.
    pub fn subscribe(&self) -> broadcast::Receiver<WsMessage> {
        self.ws_broadcast.subscribe()
    }
}

impl Default for DashboardState {
    fn default() -> Self {
        Self::new()
    }
}

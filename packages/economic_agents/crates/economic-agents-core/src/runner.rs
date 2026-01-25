//! Background task runner for agent lifecycle management.
//!
//! This module provides tokio-based async execution of agents with
//! channel-based communication for commands and events.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::{mpsc, oneshot, RwLock};
use tokio::task::JoinHandle;
use tracing::{debug, error, info, warn};

use crate::agent::{AutonomousAgent, Backends};
use crate::config::AgentConfig;
use crate::cycle::CycleResult;

/// Commands that can be sent to a running agent.
#[derive(Debug)]
pub enum AgentCommand {
    /// Stop the agent gracefully.
    Stop,
    /// Get current agent status.
    GetStatus(oneshot::Sender<AgentStatus>),
    /// Get recent cycle results.
    GetCycles(oneshot::Sender<Vec<CycleResult>>, usize),
}

/// Events emitted by a running agent.
#[derive(Debug, Clone)]
pub enum AgentEvent {
    /// Agent started running.
    Started { agent_id: String },
    /// Agent completed a cycle.
    CycleCompleted { agent_id: String, cycle: CycleResult },
    /// Agent stopped.
    Stopped { agent_id: String, reason: String },
    /// Agent encountered an error.
    Error { agent_id: String, error: String },
}

/// Status of a running agent.
#[derive(Debug, Clone)]
pub struct AgentStatus {
    /// Agent identifier.
    pub agent_id: String,
    /// Whether the agent is currently running.
    pub is_running: bool,
    /// Current cycle number.
    pub current_cycle: u32,
    /// Tasks completed.
    pub tasks_completed: u32,
    /// Current balance.
    pub balance: f64,
    /// Total earnings.
    pub total_earnings: f64,
    /// Has company.
    pub has_company: bool,
}

/// Handle to a running agent.
pub struct AgentHandle {
    /// Agent identifier.
    pub id: String,
    /// Command sender for controlling the agent.
    command_tx: mpsc::Sender<AgentCommand>,
    /// Event receiver for monitoring the agent.
    event_rx: Arc<RwLock<mpsc::Receiver<AgentEvent>>>,
    /// Join handle for the background task.
    join_handle: JoinHandle<()>,
}

impl AgentHandle {
    /// Stop the agent gracefully.
    pub async fn stop(&self) -> Result<(), String> {
        self.command_tx
            .send(AgentCommand::Stop)
            .await
            .map_err(|e| format!("Failed to send stop command: {}", e))
    }

    /// Get the current status of the agent.
    pub async fn status(&self) -> Result<AgentStatus, String> {
        let (tx, rx) = oneshot::channel();
        self.command_tx
            .send(AgentCommand::GetStatus(tx))
            .await
            .map_err(|e| format!("Failed to send status command: {}", e))?;

        rx.await
            .map_err(|e| format!("Failed to receive status: {}", e))
    }

    /// Get recent cycle results.
    pub async fn recent_cycles(&self, count: usize) -> Result<Vec<CycleResult>, String> {
        let (tx, rx) = oneshot::channel();
        self.command_tx
            .send(AgentCommand::GetCycles(tx, count))
            .await
            .map_err(|e| format!("Failed to send cycles command: {}", e))?;

        rx.await
            .map_err(|e| format!("Failed to receive cycles: {}", e))
    }

    /// Try to receive the next event (non-blocking).
    pub async fn try_recv_event(&self) -> Option<AgentEvent> {
        self.event_rx.write().await.try_recv().ok()
    }

    /// Wait for the agent task to complete.
    pub async fn wait(self) {
        let _ = self.join_handle.await;
    }

    /// Check if the agent task is still running.
    pub fn is_finished(&self) -> bool {
        self.join_handle.is_finished()
    }
}

/// Configuration for the agent runner.
#[derive(Debug, Clone)]
pub struct RunnerConfig {
    /// Maximum cycles to run (None = unlimited).
    pub max_cycles: Option<u32>,
    /// Delay between cycles in milliseconds.
    pub cycle_delay_ms: u64,
    /// Event channel buffer size.
    pub event_buffer_size: usize,
    /// Command channel buffer size.
    pub command_buffer_size: usize,
}

impl Default for RunnerConfig {
    fn default() -> Self {
        Self {
            max_cycles: None,
            cycle_delay_ms: 100,
            event_buffer_size: 100,
            command_buffer_size: 10,
        }
    }
}

/// Background agent runner.
///
/// Manages multiple agents running in background tokio tasks.
pub struct AgentRunner {
    /// Active agents.
    agents: Arc<RwLock<HashMap<String, AgentHandle>>>,
    /// Runner configuration.
    config: RunnerConfig,
}

impl AgentRunner {
    /// Create a new agent runner with default configuration.
    pub fn new() -> Self {
        Self {
            agents: Arc::new(RwLock::new(HashMap::new())),
            config: RunnerConfig::default(),
        }
    }

    /// Create a new agent runner with custom configuration.
    pub fn with_config(config: RunnerConfig) -> Self {
        Self {
            agents: Arc::new(RwLock::new(HashMap::new())),
            config,
        }
    }

    /// Spawn an agent in a background task.
    pub async fn spawn(
        &self,
        agent_config: AgentConfig,
        backends: Backends,
    ) -> Result<String, String> {
        let (command_tx, command_rx) = mpsc::channel(self.config.command_buffer_size);
        let (event_tx, event_rx) = mpsc::channel(self.config.event_buffer_size);

        let mut agent = AutonomousAgent::with_backends(agent_config.clone(), backends);
        let agent_id = agent.id.clone();

        // Initialize agent state
        if let Err(e) = agent.initialize().await {
            warn!(agent_id = %agent_id, error = %e, "Failed to initialize agent state");
        }

        let max_cycles = self.config.max_cycles.or(agent_config.max_cycles);
        let cycle_delay = Duration::from_millis(self.config.cycle_delay_ms);
        let id_clone = agent_id.clone();

        // Spawn the agent task
        let join_handle = tokio::spawn(async move {
            run_agent_loop(agent, command_rx, event_tx, max_cycles, cycle_delay).await;
        });

        let handle = AgentHandle {
            id: id_clone.clone(),
            command_tx,
            event_rx: Arc::new(RwLock::new(event_rx)),
            join_handle,
        };

        self.agents.write().await.insert(id_clone.clone(), handle);

        info!(agent_id = %id_clone, "Agent spawned in background");

        Ok(id_clone)
    }

    /// Get all active agent IDs.
    pub async fn list_agents(&self) -> Vec<String> {
        self.agents.read().await.keys().cloned().collect()
    }

    /// Get the status of a specific agent.
    pub async fn get_status(&self, agent_id: &str) -> Result<AgentStatus, String> {
        let agents = self.agents.read().await;
        let handle = agents
            .get(agent_id)
            .ok_or_else(|| format!("Agent not found: {}", agent_id))?;

        handle.status().await
    }

    /// Stop a specific agent.
    pub async fn stop_agent(&self, agent_id: &str) -> Result<(), String> {
        let agents = self.agents.read().await;
        let handle = agents
            .get(agent_id)
            .ok_or_else(|| format!("Agent not found: {}", agent_id))?;

        handle.stop().await
    }

    /// Stop all agents.
    pub async fn stop_all(&self) {
        let agents = self.agents.read().await;
        for (id, handle) in agents.iter() {
            if let Err(e) = handle.stop().await {
                warn!(agent_id = %id, error = %e, "Failed to stop agent");
            }
        }
    }

    /// Remove a finished agent from the registry.
    pub async fn remove_agent(&self, agent_id: &str) -> Option<AgentHandle> {
        self.agents.write().await.remove(agent_id)
    }

    /// Clean up finished agents.
    pub async fn cleanup_finished(&self) -> Vec<String> {
        let mut to_remove = Vec::new();

        {
            let agents = self.agents.read().await;
            for (id, handle) in agents.iter() {
                if handle.is_finished() {
                    to_remove.push(id.clone());
                }
            }
        }

        let mut agents = self.agents.write().await;
        for id in &to_remove {
            agents.remove(id);
        }

        to_remove
    }

    /// Get the number of active agents.
    pub async fn active_count(&self) -> usize {
        self.agents.read().await.len()
    }
}

impl Default for AgentRunner {
    fn default() -> Self {
        Self::new()
    }
}

/// Internal function to run the agent loop.
async fn run_agent_loop(
    mut agent: AutonomousAgent,
    mut command_rx: mpsc::Receiver<AgentCommand>,
    event_tx: mpsc::Sender<AgentEvent>,
    max_cycles: Option<u32>,
    cycle_delay: Duration,
) {
    let agent_id = agent.id.clone();

    // Send started event
    let _ = event_tx
        .send(AgentEvent::Started {
            agent_id: agent_id.clone(),
        })
        .await;

    let max = max_cycles.unwrap_or(u32::MAX);
    let mut should_stop = false;

    for _ in 0..max {
        // Check for commands (non-blocking)
        while let Ok(command) = command_rx.try_recv() {
            match command {
                AgentCommand::Stop => {
                    should_stop = true;
                    break;
                }
                AgentCommand::GetStatus(tx) => {
                    let status = AgentStatus {
                        agent_id: agent_id.clone(),
                        is_running: agent.state.is_active,
                        current_cycle: agent.state.current_cycle,
                        tasks_completed: agent.state.tasks_completed,
                        balance: agent.state.balance,
                        total_earnings: agent.state.total_earnings,
                        has_company: agent.state.has_company,
                    };
                    let _ = tx.send(status);
                }
                AgentCommand::GetCycles(tx, count) => {
                    let cycles = agent.recent_cycles(count).to_vec();
                    let _ = tx.send(cycles);
                }
            }
        }

        if should_stop {
            info!(agent_id = %agent_id, "Agent stopping due to command");
            break;
        }

        if !agent.state.is_active {
            info!(agent_id = %agent_id, "Agent deactivated, stopping");
            break;
        }

        if !agent.state.can_survive() {
            warn!(agent_id = %agent_id, "Agent cannot survive, stopping");
            break;
        }

        // Run a cycle
        match agent.run_cycle().await {
            Ok(cycle_result) => {
                let _ = event_tx
                    .send(AgentEvent::CycleCompleted {
                        agent_id: agent_id.clone(),
                        cycle: cycle_result,
                    })
                    .await;
            }
            Err(e) => {
                let _ = event_tx
                    .send(AgentEvent::Error {
                        agent_id: agent_id.clone(),
                        error: e.to_string(),
                    })
                    .await;
                error!(agent_id = %agent_id, error = %e, "Cycle failed");
            }
        }

        // Delay between cycles
        if cycle_delay.as_millis() > 0 {
            tokio::time::sleep(cycle_delay).await;
        }
    }

    // Send stopped event
    let reason = if should_stop {
        "Stopped by command"
    } else if !agent.state.can_survive() {
        "Cannot survive"
    } else if !agent.state.is_active {
        "Deactivated"
    } else {
        "Max cycles reached"
    };

    let _ = event_tx
        .send(AgentEvent::Stopped {
            agent_id: agent_id.clone(),
            reason: reason.to_string(),
        })
        .await;

    debug!(agent_id = %agent_id, reason = %reason, "Agent loop ended");
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::AgentConfig;
    use economic_agents_mock::MockBackendFactory;

    #[tokio::test]
    async fn test_runner_spawn_agent() {
        let runner = AgentRunner::new();
        let config = AgentConfig {
            max_cycles: Some(2),
            ..Default::default()
        };

        let backends = MockBackendFactory::create().await;
        let backends = Backends::new(
            Arc::new(backends.wallet),
            Arc::new(backends.marketplace),
            Arc::new(backends.compute),
        );

        let agent_id = runner.spawn(config, backends).await.unwrap();
        assert!(!agent_id.is_empty());

        // Wait a bit for the agent to run
        tokio::time::sleep(Duration::from_millis(500)).await;

        let agents = runner.list_agents().await;
        assert!(agents.contains(&agent_id));
    }

    #[tokio::test]
    async fn test_runner_get_status() {
        let runner = AgentRunner::with_config(RunnerConfig {
            max_cycles: Some(50),
            cycle_delay_ms: 50,
            ..Default::default()
        });

        let config = AgentConfig::default();
        let backends = MockBackendFactory::create().await;
        let backends = Backends::new(
            Arc::new(backends.wallet),
            Arc::new(backends.marketplace),
            Arc::new(backends.compute),
        );

        let agent_id = runner.spawn(config, backends).await.unwrap();

        // Give it time to start (but not too long)
        tokio::time::sleep(Duration::from_millis(50)).await;

        let status = runner.get_status(&agent_id).await.unwrap();
        assert_eq!(status.agent_id, agent_id);
        assert!(status.is_running);

        // Stop the agent so it doesn't run for too long
        runner.stop_agent(&agent_id).await.unwrap();
    }

    #[tokio::test]
    async fn test_runner_stop_agent() {
        let runner = AgentRunner::with_config(RunnerConfig {
            max_cycles: Some(100),
            cycle_delay_ms: 50,
            ..Default::default()
        });

        let config = AgentConfig::default();
        let backends = MockBackendFactory::create().await;
        let backends = Backends::new(
            Arc::new(backends.wallet),
            Arc::new(backends.marketplace),
            Arc::new(backends.compute),
        );

        let agent_id = runner.spawn(config, backends).await.unwrap();

        // Give it time to start
        tokio::time::sleep(Duration::from_millis(100)).await;

        // Stop the agent
        runner.stop_agent(&agent_id).await.unwrap();

        // Wait for it to stop
        tokio::time::sleep(Duration::from_millis(200)).await;

        // Check that it's finished
        let agents = runner.agents.read().await;
        let handle = agents.get(&agent_id).unwrap();
        assert!(handle.is_finished());
    }

    #[tokio::test]
    async fn test_runner_cleanup_finished() {
        let runner = AgentRunner::with_config(RunnerConfig {
            max_cycles: Some(1),
            cycle_delay_ms: 0,
            ..Default::default()
        });

        let config = AgentConfig::default();
        let backends = MockBackendFactory::create().await;
        let backends = Backends::new(
            Arc::new(backends.wallet),
            Arc::new(backends.marketplace),
            Arc::new(backends.compute),
        );

        let _ = runner.spawn(config, backends).await.unwrap();

        // Wait for it to finish
        tokio::time::sleep(Duration::from_millis(500)).await;

        // Cleanup
        let removed = runner.cleanup_finished().await;
        assert_eq!(removed.len(), 1);

        assert_eq!(runner.active_count().await, 0);
    }

    #[test]
    fn test_runner_config_default() {
        let config = RunnerConfig::default();
        assert!(config.max_cycles.is_none());
        assert_eq!(config.cycle_delay_ms, 100);
        assert_eq!(config.event_buffer_size, 100);
        assert_eq!(config.command_buffer_size, 10);
    }
}

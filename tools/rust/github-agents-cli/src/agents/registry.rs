//! Agent registry for managing and selecting AI agents.
//!
//! Provides a registry of available agents and methods to select
//! the best agent for a given task.

use std::collections::HashMap;
use std::sync::Arc;
use tracing::{debug, info, warn};

use super::base::{Agent, AgentCapability};
use super::cli::CliAgent;

/// Registry of available AI agents.
pub struct AgentRegistry {
    /// Map of agent name to agent instance
    agents: HashMap<String, Arc<dyn Agent>>,
    /// Default timeout for agent operations
    default_timeout_secs: u64,
}

impl AgentRegistry {
    /// Create a new agent registry with default agents.
    pub fn new() -> Self {
        Self::with_timeout(600)
    }

    /// Create a new agent registry with a custom timeout.
    pub fn with_timeout(timeout_secs: u64) -> Self {
        let mut registry = Self {
            agents: HashMap::new(),
            default_timeout_secs: timeout_secs,
        };

        // Register all known agents
        registry.register_default_agents();

        registry
    }

    /// Register the default set of agents.
    fn register_default_agents(&mut self) {
        self.register(Arc::new(CliAgent::claude(self.default_timeout_secs)));
        self.register(Arc::new(CliAgent::gemini(self.default_timeout_secs)));
        self.register(Arc::new(CliAgent::codex(self.default_timeout_secs)));
        self.register(Arc::new(CliAgent::opencode(self.default_timeout_secs)));
        self.register(Arc::new(CliAgent::crush(self.default_timeout_secs)));
    }

    /// Register an agent in the registry.
    pub fn register(&mut self, agent: Arc<dyn Agent>) {
        let name = agent.name().to_lowercase();
        debug!("Registering agent: {}", name);
        self.agents.insert(name, agent);
    }

    /// Get an agent by name (case-insensitive).
    pub fn get(&self, name: &str) -> Option<Arc<dyn Agent>> {
        self.agents.get(&name.to_lowercase()).cloned()
    }

    /// Get an agent by trigger keyword (case-insensitive).
    pub fn get_by_keyword(&self, keyword: &str) -> Option<Arc<dyn Agent>> {
        let keyword_lower = keyword.to_lowercase();
        self.agents
            .values()
            .find(|a| a.trigger_keyword().to_lowercase() == keyword_lower)
            .cloned()
    }

    /// Get all registered agents.
    pub fn all(&self) -> Vec<Arc<dyn Agent>> {
        self.agents.values().cloned().collect()
    }

    /// Check availability of all agents and return available ones.
    pub async fn available_agents(&self) -> Vec<Arc<dyn Agent>> {
        let mut available = Vec::new();

        for agent in self.agents.values() {
            if agent.is_available().await {
                available.push(agent.clone());
            }
        }

        available
    }

    /// Select the best available agent for a task.
    ///
    /// If `preferred_agent` is specified and available, use it.
    /// Otherwise, select the highest-priority available agent.
    pub async fn select_agent(&self, preferred_agent: Option<&str>) -> Option<Arc<dyn Agent>> {
        // If a specific agent is requested, try to use it
        if let Some(name) = preferred_agent {
            if let Some(agent) = self.get_by_keyword(name).or_else(|| self.get(name)) {
                if agent.is_available().await {
                    info!("Selected requested agent: {}", agent.name());
                    return Some(agent);
                }
                warn!("Requested agent '{}' is not available", name);
            } else {
                warn!("Unknown agent requested: {}", name);
            }
        }

        // Otherwise, find the highest-priority available agent
        let available = self.available_agents().await;

        if available.is_empty() {
            warn!("No agents available");
            return None;
        }

        // Sort by priority (descending) and select the first
        let mut sorted = available;
        sorted.sort_by(|a, b| b.priority().cmp(&a.priority()));

        let selected = sorted.into_iter().next();
        if let Some(ref agent) = selected {
            info!(
                "Auto-selected agent: {} (priority: {})",
                agent.name(),
                agent.priority()
            );
        }

        selected
    }

    /// Select the best agent for a specific capability.
    pub async fn select_for_capability(
        &self,
        capability: AgentCapability,
        preferred_agent: Option<&str>,
    ) -> Option<Arc<dyn Agent>> {
        // If a specific agent is requested, try to use it if it has the capability
        if let Some(name) = preferred_agent {
            if let Some(agent) = self.get_by_keyword(name).or_else(|| self.get(name)) {
                if agent.is_available().await && agent.capabilities().contains(&capability) {
                    info!(
                        "Selected requested agent {} for {:?}",
                        agent.name(),
                        capability
                    );
                    return Some(agent);
                }
            }
        }

        // Find available agents with the capability
        let available = self.available_agents().await;
        let capable: Vec<_> = available
            .into_iter()
            .filter(|a| a.capabilities().contains(&capability))
            .collect();

        if capable.is_empty() {
            warn!("No agents available with capability {:?}", capability);
            return None;
        }

        // Sort by priority and return the best
        let mut sorted = capable;
        sorted.sort_by(|a, b| b.priority().cmp(&a.priority()));

        let selected = sorted.into_iter().next();
        if let Some(ref agent) = selected {
            info!(
                "Auto-selected agent {} for {:?} (priority: {})",
                agent.name(),
                capability,
                agent.priority()
            );
        }

        selected
    }

    /// Get a summary of all agents and their availability.
    pub async fn status(&self) -> Vec<AgentStatus> {
        let mut statuses = Vec::new();

        for agent in self.agents.values() {
            let available = agent.is_available().await;
            statuses.push(AgentStatus {
                name: agent.name().to_string(),
                trigger_keyword: agent.trigger_keyword().to_string(),
                available,
                priority: agent.priority(),
                capabilities: agent.capabilities(),
            });
        }

        // Sort by priority descending
        statuses.sort_by(|a, b| b.priority.cmp(&a.priority));

        statuses
    }
}

impl Default for AgentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

/// Status information for an agent.
#[derive(Debug, Clone)]
pub struct AgentStatus {
    /// Agent name
    pub name: String,
    /// Trigger keyword
    pub trigger_keyword: String,
    /// Whether the agent is available
    pub available: bool,
    /// Agent priority
    pub priority: u8,
    /// Agent capabilities
    pub capabilities: Vec<AgentCapability>,
}

impl std::fmt::Display for AgentStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let status = if self.available { "available" } else { "unavailable" };
        let caps: Vec<String> = self
            .capabilities
            .iter()
            .map(|c| format!("{:?}", c))
            .collect();

        write!(
            f,
            "{} ({}) - {} [priority: {}, caps: {}]",
            self.name,
            self.trigger_keyword,
            status,
            self.priority,
            caps.join(", ")
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_registry_creation() {
        let registry = AgentRegistry::new();
        assert!(!registry.agents.is_empty());
    }

    #[test]
    fn test_get_agent_by_name() {
        let registry = AgentRegistry::new();
        let agent = registry.get("claude");
        assert!(agent.is_some());
        assert_eq!(agent.unwrap().name(), "claude");
    }

    #[test]
    fn test_get_agent_by_keyword() {
        let registry = AgentRegistry::new();
        let agent = registry.get_by_keyword("Claude");
        assert!(agent.is_some());
        assert_eq!(agent.unwrap().name(), "claude");
    }

    #[test]
    fn test_case_insensitive_lookup() {
        let registry = AgentRegistry::new();
        assert!(registry.get("CLAUDE").is_some());
        assert!(registry.get("Claude").is_some());
        assert!(registry.get("claude").is_some());
    }
}

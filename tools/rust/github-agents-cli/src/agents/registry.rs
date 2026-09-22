//! Agent registry for managing and selecting AI agents.
//!
//! Selection is strict: when a caller names an agent (e.g. `[Approved][Claude]`)
//! only that agent is used. Silently substituting a different agent would run
//! a model the approver did not choose, so unknown, disabled or unavailable
//! agents produce an error instead.

use std::sync::Arc;
use tracing::{debug, info};

use super::api::OpenRouterApiAgent;
use super::base::{Agent, AgentCapability};
use super::cli::CliAgent;
use super::disabled_reason;
use crate::error::Error;

/// Default timeout for agent operations (matches `security.subprocess_timeout`).
pub const DEFAULT_AGENT_TIMEOUT_SECS: u64 = 600;

/// Registry of available AI agents, ordered by descending priority.
pub struct AgentRegistry {
    agents: Vec<Arc<dyn Agent>>,
}

impl AgentRegistry {
    /// Create a registry with the default agents and timeout.
    ///
    /// The timeout can be overridden with the `AGENT_TIMEOUT_SECS` environment
    /// variable.
    pub fn new() -> Self {
        let timeout = std::env::var("AGENT_TIMEOUT_SECS")
            .ok()
            .and_then(|v| v.trim().parse().ok())
            .filter(|t| *t > 0)
            .unwrap_or(DEFAULT_AGENT_TIMEOUT_SECS);
        Self::with_timeout(timeout)
    }

    /// Create a registry with a custom per-invocation timeout.
    pub fn with_timeout(timeout_secs: u64) -> Self {
        let mut registry = Self { agents: Vec::new() };
        registry.register(Arc::new(CliAgent::claude(timeout_secs)));
        registry.register(Arc::new(CliAgent::opencode(timeout_secs)));
        registry.register(Arc::new(CliAgent::crush(timeout_secs)));
        registry.register(Arc::new(OpenRouterApiAgent::new()));
        registry
    }

    /// Register an agent (replacing any agent with the same name).
    pub fn register(&mut self, agent: Arc<dyn Agent>) {
        debug!("Registering agent: {}", agent.name());
        self.agents
            .retain(|a| !a.name().eq_ignore_ascii_case(agent.name()));
        self.agents.push(agent);
        self.agents.sort_by_key(|a| std::cmp::Reverse(a.priority()));
    }

    /// Get an agent by name or trigger keyword (case-insensitive).
    pub fn get(&self, name: &str) -> Option<Arc<dyn Agent>> {
        let name = name.trim();
        self.agents
            .iter()
            .find(|a| {
                a.name().eq_ignore_ascii_case(name)
                    || a.trigger_keyword().eq_ignore_ascii_case(name)
            })
            .cloned()
    }

    /// Resolve an explicitly requested agent, with a precise error when it
    /// cannot be used.
    async fn resolve_requested(&self, name: &str) -> Result<Arc<dyn Agent>, Error> {
        if let Some(reason) = disabled_reason(name) {
            return Err(Error::AgentNotAvailable {
                name: name.to_string(),
                reason: reason.to_string(),
            });
        }
        let agent = self.get(name).ok_or_else(|| Error::AgentNotAvailable {
            name: name.to_string(),
            reason: format!("unknown agent (known agents: {})", self.names().join(", ")),
        })?;
        if !agent.is_available().await {
            return Err(Error::AgentNotAvailable {
                name: agent.name().to_string(),
                reason: "CLI not installed or required credentials missing".to_string(),
            });
        }
        Ok(agent)
    }

    /// Select an agent.
    ///
    /// With `requested`, that exact agent is used or an error is returned.
    /// Without it, the highest-priority available agent is selected.
    pub async fn select_agent(&self, requested: Option<&str>) -> Result<Arc<dyn Agent>, Error> {
        if let Some(name) = requested {
            let agent = self.resolve_requested(name).await?;
            info!("Selected requested agent: {}", agent.name());
            return Ok(agent);
        }

        for agent in &self.agents {
            if agent.is_available().await {
                info!(
                    "Auto-selected agent: {} (priority: {})",
                    agent.name(),
                    agent.priority()
                );
                return Ok(agent.clone());
            }
        }
        Err(Error::AgentNotAvailable {
            name: "auto".to_string(),
            reason: "no agents are available".to_string(),
        })
    }

    /// Select an agent with `capability`, honoring an explicit request.
    pub async fn select_for_capability(
        &self,
        capability: AgentCapability,
        requested: Option<&str>,
    ) -> Result<Arc<dyn Agent>, Error> {
        if let Some(name) = requested {
            let agent = self.resolve_requested(name).await?;
            if !agent.capabilities().contains(&capability) {
                return Err(Error::AgentNotAvailable {
                    name: agent.name().to_string(),
                    reason: format!("agent does not support {:?}", capability),
                });
            }
            return Ok(agent);
        }

        for agent in &self.agents {
            if agent.capabilities().contains(&capability) && agent.is_available().await {
                info!(
                    "Auto-selected agent {} for {:?} (priority: {})",
                    agent.name(),
                    capability,
                    agent.priority()
                );
                return Ok(agent.clone());
            }
        }
        Err(Error::AgentNotAvailable {
            name: "auto".to_string(),
            reason: format!("no available agent supports {:?}", capability),
        })
    }

    /// Names of all registered agents (priority order).
    pub fn names(&self) -> Vec<&str> {
        self.agents.iter().map(|a| a.name()).collect()
    }
}

impl Default for AgentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agents::AgentContext;
    use async_trait::async_trait;

    struct FakeAgent {
        name: &'static str,
        priority: u8,
        available: bool,
    }

    #[async_trait]
    impl Agent for FakeAgent {
        fn name(&self) -> &str {
            self.name
        }
        fn trigger_keyword(&self) -> &str {
            self.name
        }
        async fn is_available(&self) -> bool {
            self.available
        }
        fn priority(&self) -> u8 {
            self.priority
        }
        async fn generate_code(&self, _: &str, _: &AgentContext) -> Result<String, Error> {
            Ok(self.name.to_string())
        }
    }

    fn fake_registry() -> AgentRegistry {
        let mut r = AgentRegistry { agents: Vec::new() };
        r.register(Arc::new(FakeAgent {
            name: "low",
            priority: 10,
            available: true,
        }));
        r.register(Arc::new(FakeAgent {
            name: "high",
            priority: 90,
            available: false,
        }));
        r.register(Arc::new(FakeAgent {
            name: "mid",
            priority: 50,
            available: true,
        }));
        r
    }

    #[test]
    fn test_default_registry_has_no_disabled_agents() {
        let registry = AgentRegistry::with_timeout(1);
        assert!(registry.get("claude").is_some());
        assert!(registry.get("Claude").is_some());
        assert!(registry.get("OPENCODE").is_some());
        assert!(registry.get("openrouter").is_some());
        assert!(registry.get("gemini").is_none());
        assert!(registry.get("codex").is_none());
        assert_eq!(registry.names()[0], "claude");
    }

    #[tokio::test]
    async fn test_auto_selection_prefers_available_priority() {
        let r = fake_registry();
        assert_eq!(r.names(), vec!["high", "mid", "low"]);
        let a = r.select_agent(None).await.unwrap();
        assert_eq!(a.name(), "mid");
    }

    #[tokio::test]
    async fn test_explicit_request_never_falls_back() {
        let r = fake_registry();
        // Unavailable requested agent is an error, not a substitution
        let err = r.select_agent(Some("high")).await.err().unwrap();
        assert!(matches!(err, Error::AgentNotAvailable { .. }));
        // Unknown agent
        assert!(r.select_agent(Some("nope")).await.is_err());
        // Disabled agent gives the policy reason
        match r.select_agent(Some("Gemini")).await {
            Err(Error::AgentNotAvailable { reason, .. }) => assert!(reason.contains("policy")),
            _ => panic!("expected policy error"),
        }
        assert_eq!(r.select_agent(Some("LOW")).await.unwrap().name(), "low");
    }

    #[tokio::test]
    async fn test_capability_selection() {
        let r = fake_registry();
        // FakeAgent only has the default CodeGeneration capability
        assert!(
            r.select_for_capability(AgentCapability::CodeReview, None)
                .await
                .is_err()
        );
        assert_eq!(
            r.select_for_capability(AgentCapability::CodeGeneration, None)
                .await
                .unwrap()
                .name(),
            "mid"
        );
        assert!(
            r.select_for_capability(AgentCapability::CodeReview, Some("mid"))
                .await
                .is_err()
        );
    }
}

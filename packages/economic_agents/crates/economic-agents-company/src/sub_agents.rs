//! Sub-agent management for company hierarchy.

use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Role of a sub-agent in the company.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SubAgentRole {
    /// Board member.
    BoardMember,
    /// Executive officer.
    Executive,
    /// Subject matter expert.
    SubjectMatterExpert,
    /// Individual contributor.
    IndividualContributor,
}

/// A sub-agent working for a company.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubAgent {
    /// Unique ID.
    pub id: Uuid,
    /// Agent name.
    pub name: String,
    /// Role in company.
    pub role: SubAgentRole,
    /// Specialization area.
    pub specialization: Option<String>,
    /// Tasks completed.
    pub tasks_completed: u32,
    /// Performance score (0.0-1.0).
    pub performance: f64,
}

impl SubAgent {
    /// Create a new sub-agent.
    pub fn new(name: impl Into<String>, role: SubAgentRole) -> Self {
        Self {
            id: Uuid::new_v4(),
            name: name.into(),
            role,
            specialization: None,
            tasks_completed: 0,
            performance: 0.5,
        }
    }

    /// Set specialization.
    pub fn with_specialization(mut self, spec: impl Into<String>) -> Self {
        self.specialization = Some(spec.into());
        self
    }
}

/// Manages sub-agents for a company.
pub struct SubAgentManager {
    agents: Vec<SubAgent>,
}

impl SubAgentManager {
    /// Create a new manager.
    pub fn new() -> Self {
        Self { agents: Vec::new() }
    }

    /// Add a sub-agent.
    pub fn add(&mut self, agent: SubAgent) {
        self.agents.push(agent);
    }

    /// Get all agents by role.
    pub fn by_role(&self, role: SubAgentRole) -> Vec<&SubAgent> {
        self.agents.iter().filter(|a| a.role == role).collect()
    }

    /// Get total count.
    pub fn count(&self) -> usize {
        self.agents.len()
    }
}

impl Default for SubAgentManager {
    fn default() -> Self {
        Self::new()
    }
}

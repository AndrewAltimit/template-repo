//! State manager for persisting agent state and registry.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::fs;
use tracing::{debug, info};
use uuid::Uuid;

use economic_agents_company::Company;
use economic_agents_core::state::AgentState;
use economic_agents_investment::CompanyRegistry;

/// Errors that can occur during persistence operations.
#[derive(Debug, Error)]
pub enum PersistenceError {
    /// IO error during file operations.
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// JSON serialization/deserialization error.
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// Agent state not found.
    #[error("Agent state not found: {0}")]
    AgentNotFound(String),

    /// Registry not found.
    #[error("Registry not found")]
    RegistryNotFound,

    /// Invalid path.
    #[error("Invalid path: {0}")]
    InvalidPath(String),
}

/// Result type for persistence operations.
pub type Result<T> = std::result::Result<T, PersistenceError>;

/// Serialized decision record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedDecision {
    /// Decision type.
    pub decision_type: String,
    /// Decision timestamp.
    pub timestamp: DateTime<Utc>,
    /// Decision details.
    pub details: serde_json::Value,
    /// Decision outcome.
    pub outcome: Option<String>,
}

/// Serialized agent state for persistence.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedAgentState {
    /// Agent ID.
    pub agent_id: String,
    /// Current balance.
    pub balance: f64,
    /// Compute hours remaining.
    pub compute_hours: f64,
    /// Whether agent is active.
    pub is_active: bool,
    /// Whether agent has a company.
    pub has_company: bool,
    /// Company ID if any.
    pub company_id: Option<Uuid>,
    /// Tasks completed.
    pub tasks_completed: u32,
    /// Tasks failed.
    pub tasks_failed: u32,
    /// Current cycle number.
    pub current_cycle: u32,
    /// Total earnings.
    pub total_earnings: f64,
    /// Total expenses.
    pub total_expenses: f64,
    /// Reputation score.
    pub reputation: f64,
    /// Consecutive failures.
    pub consecutive_failures: u32,
    /// Current task ID.
    pub current_task_id: Option<Uuid>,
    /// Last updated timestamp.
    pub last_updated: DateTime<Utc>,
}

impl From<&AgentState> for SerializedAgentState {
    fn from(state: &AgentState) -> Self {
        Self {
            agent_id: String::new(), // Set by caller
            balance: state.balance,
            compute_hours: state.compute_hours,
            is_active: state.is_active,
            has_company: state.has_company,
            company_id: state.company_id,
            tasks_completed: state.tasks_completed,
            tasks_failed: state.tasks_failed,
            current_cycle: state.current_cycle,
            total_earnings: state.total_earnings,
            total_expenses: state.total_expenses,
            reputation: state.reputation,
            consecutive_failures: state.consecutive_failures,
            current_task_id: state.current_task_id,
            last_updated: state.last_updated,
        }
    }
}

/// Full saved state including metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedAgentState {
    /// Agent ID.
    pub agent_id: String,
    /// Serialized state.
    pub state: SerializedAgentState,
    /// Decision history.
    pub decisions: Vec<SerializedDecision>,
    /// When saved.
    pub saved_at: DateTime<Utc>,
    /// Version for future compatibility.
    pub version: u32,
}

/// Metadata about a saved agent (for listing).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedAgentMetadata {
    /// Agent ID.
    pub agent_id: String,
    /// When saved.
    pub saved_at: DateTime<Utc>,
    /// Balance at save time.
    pub balance: f64,
    /// Cycle count at save time.
    pub current_cycle: u32,
}

/// Loaded agent state.
#[derive(Debug)]
pub struct LoadedAgentState {
    /// Restored agent state.
    pub state: AgentState,
    /// Decision history.
    pub decisions: Vec<SerializedDecision>,
    /// When originally saved.
    pub saved_at: DateTime<Utc>,
}

/// Serialized company for persistence.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedCompany {
    /// Company ID.
    pub id: Uuid,
    /// Company name.
    pub name: String,
    /// Company stage.
    pub stage: String,
    /// Available capital.
    pub capital: f64,
    /// Revenue from metrics.
    pub revenue: f64,
    /// Expenses from metrics.
    pub expenses: f64,
    /// Product count.
    pub product_count: u32,
    /// Employee count.
    pub employee_count: u32,
    /// Founded timestamp.
    pub founded_at: DateTime<Utc>,
    /// Last updated timestamp.
    pub updated_at: DateTime<Utc>,
}

impl From<&Company> for SerializedCompany {
    fn from(company: &Company) -> Self {
        Self {
            id: company.id,
            name: company.name.clone(),
            stage: format!("{:?}", company.stage),
            capital: company.capital,
            revenue: company.metrics.revenue,
            expenses: company.metrics.expenses,
            product_count: company.metrics.product_count,
            employee_count: company.metrics.employee_count,
            founded_at: company.founded_at,
            updated_at: company.updated_at,
        }
    }
}

/// Saved registry state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedRegistry {
    /// Companies by ID.
    pub companies: HashMap<Uuid, SerializedCompany>,
    /// When saved.
    pub saved_at: DateTime<Utc>,
    /// Version.
    pub version: u32,
}

/// Loaded registry data.
#[derive(Debug)]
pub struct LoadedRegistry {
    /// Serialized companies (need to be reconstructed).
    pub companies: HashMap<Uuid, SerializedCompany>,
    /// When originally saved.
    pub saved_at: DateTime<Utc>,
}

/// Manages persistence of agent state and company registry.
pub struct StateManager {
    /// Base directory for persisted state.
    base_dir: PathBuf,
    /// Agent state directory.
    agent_state_dir: PathBuf,
    /// Registry directory.
    registry_dir: PathBuf,
}

impl StateManager {
    /// Create a new state manager.
    ///
    /// # Arguments
    /// * `base_dir` - Base directory for persisted state
    pub async fn new(base_dir: impl AsRef<Path>) -> Result<Self> {
        let base_dir = base_dir.as_ref().to_path_buf();
        let agent_state_dir = base_dir.join("agents");
        let registry_dir = base_dir.join("registry");

        // Create directories
        fs::create_dir_all(&base_dir).await?;
        fs::create_dir_all(&agent_state_dir).await?;
        fs::create_dir_all(&registry_dir).await?;

        info!(base_dir = %base_dir.display(), "State manager initialized");

        Ok(Self {
            base_dir,
            agent_state_dir,
            registry_dir,
        })
    }

    /// Create with default directory (.economic_agents).
    pub async fn with_default_dir() -> Result<Self> {
        Self::new(".economic_agents").await
    }

    /// Save agent state to disk.
    ///
    /// # Arguments
    /// * `agent_id` - Agent identifier
    /// * `state` - Agent state to save
    /// * `decisions` - Decision history
    ///
    /// # Returns
    /// Path to saved state file
    pub async fn save_agent_state(
        &self,
        agent_id: &str,
        state: &AgentState,
        decisions: Vec<SerializedDecision>,
    ) -> Result<PathBuf> {
        let mut serialized_state = SerializedAgentState::from(state);
        serialized_state.agent_id = agent_id.to_string();

        let saved_state = SavedAgentState {
            agent_id: agent_id.to_string(),
            state: serialized_state,
            decisions,
            saved_at: Utc::now(),
            version: 1,
        };

        let state_file = self.agent_state_dir.join(format!("{}.json", agent_id));
        let json = serde_json::to_string_pretty(&saved_state)?;
        fs::write(&state_file, json).await?;

        debug!(agent_id = %agent_id, path = %state_file.display(), "Agent state saved");

        Ok(state_file)
    }

    /// Load agent state from disk.
    ///
    /// # Arguments
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    /// Loaded agent state
    pub async fn load_agent_state(&self, agent_id: &str) -> Result<LoadedAgentState> {
        let state_file = self.agent_state_dir.join(format!("{}.json", agent_id));

        if !state_file.exists() {
            return Err(PersistenceError::AgentNotFound(agent_id.to_string()));
        }

        let json = fs::read_to_string(&state_file).await?;
        let saved: SavedAgentState = serde_json::from_str(&json)?;

        // Reconstruct AgentState
        let state = AgentState {
            balance: saved.state.balance,
            compute_hours: saved.state.compute_hours,
            is_active: saved.state.is_active,
            has_company: saved.state.has_company,
            company_id: saved.state.company_id,
            tasks_completed: saved.state.tasks_completed,
            tasks_failed: saved.state.tasks_failed,
            current_cycle: saved.state.current_cycle,
            total_earnings: saved.state.total_earnings,
            total_expenses: saved.state.total_expenses,
            reputation: saved.state.reputation,
            consecutive_failures: saved.state.consecutive_failures,
            current_task_id: saved.state.current_task_id,
            last_updated: saved.state.last_updated,
        };

        debug!(agent_id = %agent_id, "Agent state loaded");

        Ok(LoadedAgentState {
            state,
            decisions: saved.decisions,
            saved_at: saved.saved_at,
        })
    }

    /// Save company registry to disk.
    ///
    /// # Arguments
    /// * `registry` - Company registry to save
    ///
    /// # Returns
    /// Path to saved registry file
    pub async fn save_registry(&self, registry: &CompanyRegistry) -> Result<PathBuf> {
        let companies: HashMap<Uuid, SerializedCompany> = registry
            .all()
            .map(|c| (c.id, SerializedCompany::from(c)))
            .collect();

        let saved = SavedRegistry {
            companies,
            saved_at: Utc::now(),
            version: 1,
        };

        let registry_file = self.registry_dir.join("registry.json");
        let json = serde_json::to_string_pretty(&saved)?;
        fs::write(&registry_file, json).await?;

        info!(path = %registry_file.display(), "Registry saved");

        Ok(registry_file)
    }

    /// Load company registry from disk.
    ///
    /// # Returns
    /// Loaded registry data (companies need reconstruction)
    pub async fn load_registry(&self) -> Result<LoadedRegistry> {
        let registry_file = self.registry_dir.join("registry.json");

        if !registry_file.exists() {
            return Err(PersistenceError::RegistryNotFound);
        }

        let json = fs::read_to_string(&registry_file).await?;
        let saved: SavedRegistry = serde_json::from_str(&json)?;

        info!("Registry loaded");

        Ok(LoadedRegistry {
            companies: saved.companies,
            saved_at: saved.saved_at,
        })
    }

    /// List all saved agent IDs.
    pub async fn list_saved_agents(&self) -> Result<Vec<SavedAgentMetadata>> {
        let mut agents = Vec::new();

        let mut entries = fs::read_dir(&self.agent_state_dir).await?;
        while let Some(entry) = entries.next_entry().await? {
            let path = entry.path();
            if path.extension().is_some_and(|ext| ext == "json")
                && let Some(stem) = path.file_stem()
            {
                let agent_id = stem.to_string_lossy().to_string();

                // Read just the metadata we need
                if let Ok(json) = fs::read_to_string(&path).await
                    && let Ok(saved) = serde_json::from_str::<SavedAgentState>(&json)
                {
                    agents.push(SavedAgentMetadata {
                        agent_id,
                        saved_at: saved.saved_at,
                        balance: saved.state.balance,
                        current_cycle: saved.state.current_cycle,
                    });
                }
            }
        }

        Ok(agents)
    }

    /// Check if a saved registry exists.
    pub async fn registry_exists(&self) -> bool {
        self.registry_dir.join("registry.json").exists()
    }

    /// Delete saved agent state.
    pub async fn delete_agent_state(&self, agent_id: &str) -> Result<()> {
        let state_file = self.agent_state_dir.join(format!("{}.json", agent_id));
        if state_file.exists() {
            fs::remove_file(&state_file).await?;
            debug!(agent_id = %agent_id, "Agent state deleted");
        }
        Ok(())
    }

    /// Delete saved registry.
    pub async fn delete_registry(&self) -> Result<()> {
        let registry_file = self.registry_dir.join("registry.json");
        if registry_file.exists() {
            fs::remove_file(&registry_file).await?;
            info!("Registry deleted");
        }
        Ok(())
    }

    /// Get base directory.
    pub fn base_dir(&self) -> &Path {
        &self.base_dir
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    async fn test_manager() -> (StateManager, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let manager = StateManager::new(temp_dir.path()).await.unwrap();
        (manager, temp_dir)
    }

    #[tokio::test]
    async fn test_save_and_load_agent_state() {
        let (manager, _temp) = test_manager().await;

        let state = AgentState {
            balance: 100.0,
            compute_hours: 50.0,
            is_active: true,
            has_company: false,
            company_id: None,
            tasks_completed: 10,
            tasks_failed: 2,
            current_cycle: 5,
            total_earnings: 150.0,
            total_expenses: 50.0,
            reputation: 0.8,
            consecutive_failures: 0,
            current_task_id: None,
            last_updated: Utc::now(),
        };

        let decisions = vec![SerializedDecision {
            decision_type: "accept_task".to_string(),
            timestamp: Utc::now(),
            details: serde_json::json!({"task_id": "task-1"}),
            outcome: Some("success".to_string()),
        }];

        // Save
        let path = manager
            .save_agent_state("agent-1", &state, decisions)
            .await
            .unwrap();
        assert!(path.exists());

        // Load
        let loaded = manager.load_agent_state("agent-1").await.unwrap();
        assert_eq!(loaded.state.balance, 100.0);
        assert_eq!(loaded.state.tasks_completed, 10);
        assert_eq!(loaded.decisions.len(), 1);
    }

    #[tokio::test]
    async fn test_list_saved_agents() {
        let (manager, _temp) = test_manager().await;

        let state = AgentState::default();

        manager
            .save_agent_state("agent-1", &state, vec![])
            .await
            .unwrap();
        manager
            .save_agent_state("agent-2", &state, vec![])
            .await
            .unwrap();

        let agents = manager.list_saved_agents().await.unwrap();
        assert_eq!(agents.len(), 2);
    }

    #[tokio::test]
    async fn test_agent_not_found() {
        let (manager, _temp) = test_manager().await;

        let result = manager.load_agent_state("nonexistent").await;
        assert!(matches!(result, Err(PersistenceError::AgentNotFound(_))));
    }

    #[tokio::test]
    async fn test_save_and_load_registry() {
        let (manager, _temp) = test_manager().await;

        let registry = CompanyRegistry::new();

        // Save
        let path = manager.save_registry(&registry).await.unwrap();
        assert!(path.exists());
        assert!(manager.registry_exists().await);

        // Load
        let loaded = manager.load_registry().await.unwrap();
        assert!(loaded.companies.is_empty());
    }

    #[tokio::test]
    async fn test_delete_agent_state() {
        let (manager, _temp) = test_manager().await;

        let state = AgentState::default();
        manager
            .save_agent_state("agent-1", &state, vec![])
            .await
            .unwrap();

        manager.delete_agent_state("agent-1").await.unwrap();

        let result = manager.load_agent_state("agent-1").await;
        assert!(result.is_err());
    }
}

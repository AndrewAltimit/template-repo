//! Marketplace interface for task discovery and execution.

use async_trait::async_trait;

use crate::{EntityId, Result, Task, TaskCategory, TaskSubmission};

/// Filter options for listing tasks.
#[derive(Debug, Clone, Default)]
pub struct TaskFilter {
    /// Filter by category.
    pub category: Option<TaskCategory>,
    /// Minimum reward.
    pub min_reward: Option<f64>,
    /// Maximum reward.
    pub max_reward: Option<f64>,
    /// Maximum difficulty (0.0-1.0).
    pub max_difficulty: Option<f64>,
    /// Maximum estimated hours.
    pub max_hours: Option<f64>,
    /// Maximum number of results.
    pub limit: Option<usize>,
}

/// Interface for marketplace operations.
///
/// Implementations may connect to real freelance platforms (Upwork, Fiverr),
/// mock task generators, or API-based marketplaces.
#[async_trait]
pub trait Marketplace: Send + Sync {
    /// List available tasks.
    ///
    /// # Arguments
    /// * `filter` - Optional filter criteria
    ///
    /// # Returns
    /// List of available tasks matching the filter.
    async fn list_available_tasks(&self, filter: Option<TaskFilter>) -> Result<Vec<Task>>;

    /// Claim a task for work.
    ///
    /// # Arguments
    /// * `task_id` - ID of the task to claim
    /// * `agent_id` - ID of the claiming agent
    ///
    /// # Returns
    /// The claimed task on success.
    async fn claim_task(&self, task_id: EntityId, agent_id: &str) -> Result<Task>;

    /// Submit a solution for a claimed task.
    ///
    /// # Arguments
    /// * `task_id` - ID of the task
    /// * `agent_id` - ID of the submitting agent
    /// * `content` - Solution content
    ///
    /// # Returns
    /// The submission record on success.
    async fn submit_solution(
        &self,
        task_id: EntityId,
        agent_id: &str,
        content: &str,
    ) -> Result<TaskSubmission>;

    /// Check the status of a submission.
    ///
    /// # Arguments
    /// * `submission_id` - ID of the submission
    ///
    /// # Returns
    /// Current submission status and details.
    async fn check_submission_status(&self, submission_id: EntityId) -> Result<TaskSubmission>;

    /// Get a specific task by ID.
    ///
    /// # Arguments
    /// * `task_id` - ID of the task
    ///
    /// # Returns
    /// The task if found.
    async fn get_task(&self, task_id: EntityId) -> Result<Task>;

    /// Release a claimed task (give up without completing).
    ///
    /// # Arguments
    /// * `task_id` - ID of the task
    /// * `agent_id` - ID of the agent releasing
    ///
    /// # Returns
    /// Ok if successful.
    async fn release_task(&self, task_id: EntityId, agent_id: &str) -> Result<()>;
}

//! Sub-agent autonomy - enables sub-agents to act independently.
//!
//! This module provides autonomous capabilities for sub-agents:
//! - Backend access (wallet, marketplace, compute)
//! - Independent task execution
//! - Budget management
//! - Delegation protocol from parent agents

use std::sync::Arc;

use async_trait::async_trait;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;
use uuid::Uuid;

use economic_agents_interfaces::{
    Compute, EconomicAgentError, Marketplace, Result, Task, TaskFilter, Wallet,
};

use crate::sub_agents::{SubAgent, SubAgentRole};

/// Budget allocation for an autonomous sub-agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubAgentBudget {
    /// Allocated capital (cryptocurrency).
    pub allocated_capital: f64,
    /// Spent capital.
    pub spent_capital: f64,
    /// Allocated compute hours.
    pub allocated_compute_hours: f64,
    /// Used compute hours.
    pub used_compute_hours: f64,
    /// Maximum task reward the sub-agent can pursue.
    pub max_task_reward: f64,
    /// Whether the sub-agent can hire additional sub-agents.
    pub can_hire: bool,
}

impl Default for SubAgentBudget {
    fn default() -> Self {
        Self {
            allocated_capital: 0.0,
            spent_capital: 0.0,
            allocated_compute_hours: 0.0,
            used_compute_hours: 0.0,
            max_task_reward: 50.0, // Default max task reward
            can_hire: false,
        }
    }
}

impl SubAgentBudget {
    /// Create a new budget allocation.
    pub fn new(capital: f64, compute_hours: f64) -> Self {
        Self {
            allocated_capital: capital,
            spent_capital: 0.0,
            allocated_compute_hours: compute_hours,
            used_compute_hours: 0.0,
            max_task_reward: capital * 0.5, // Can pursue tasks up to 50% of budget
            can_hire: false,
        }
    }

    /// Remaining capital.
    pub fn remaining_capital(&self) -> f64 {
        self.allocated_capital - self.spent_capital
    }

    /// Remaining compute hours.
    pub fn remaining_compute_hours(&self) -> f64 {
        self.allocated_compute_hours - self.used_compute_hours
    }

    /// Check if can afford a task.
    pub fn can_afford_task(&self, estimated_hours: f64) -> bool {
        self.remaining_compute_hours() >= estimated_hours
    }

    /// Record spending.
    pub fn spend(&mut self, capital: f64, compute_hours: f64) {
        self.spent_capital += capital;
        self.used_compute_hours += compute_hours;
    }

    /// Record earnings.
    pub fn earn(&mut self, capital: f64) {
        // Earnings reduce spent (increase effective remaining)
        self.spent_capital -= capital;
    }
}

/// Task delegation from parent to sub-agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DelegatedTask {
    /// Delegation ID.
    pub id: Uuid,
    /// Task being delegated.
    pub task: Task,
    /// Sub-agent ID assigned.
    pub assigned_to: Uuid,
    /// Delegation timestamp.
    pub delegated_at: chrono::DateTime<Utc>,
    /// Deadline for completion.
    pub deadline: Option<chrono::DateTime<Utc>>,
    /// Status of delegation.
    pub status: DelegationStatus,
    /// Result when completed.
    pub result: Option<DelegationResult>,
}

/// Status of a delegated task.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DelegationStatus {
    /// Task assigned but not yet started.
    Pending,
    /// Sub-agent is working on task.
    InProgress,
    /// Task completed successfully.
    Completed,
    /// Task failed.
    Failed,
    /// Task returned to parent.
    Returned,
}

/// Result of a delegated task.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DelegationResult {
    /// Whether successful.
    pub success: bool,
    /// Reward earned (if any).
    pub reward_earned: f64,
    /// Time spent (hours).
    pub time_spent: f64,
    /// Quality score (if available).
    pub quality_score: Option<f64>,
    /// Notes/feedback.
    pub notes: String,
}

/// Autonomous sub-agent with backend access.
pub struct AutonomousSubAgent {
    /// The underlying sub-agent.
    pub agent: SubAgent,
    /// Budget allocation.
    pub budget: SubAgentBudget,
    /// Parent agent ID.
    pub parent_id: String,
    /// Wallet backend (for future payment handling).
    #[allow(dead_code)]
    wallet: Arc<dyn Wallet>,
    /// Marketplace backend.
    marketplace: Arc<dyn Marketplace>,
    /// Compute backend (for future resource allocation).
    #[allow(dead_code)]
    compute: Arc<dyn Compute>,
    /// Currently claimed task.
    current_task: Option<Task>,
    /// Delegated tasks queue.
    delegated_tasks: Vec<DelegatedTask>,
}

impl AutonomousSubAgent {
    /// Create a new autonomous sub-agent.
    pub fn new(
        agent: SubAgent,
        parent_id: String,
        budget: SubAgentBudget,
        wallet: Arc<dyn Wallet>,
        marketplace: Arc<dyn Marketplace>,
        compute: Arc<dyn Compute>,
    ) -> Self {
        Self {
            agent,
            budget,
            parent_id,
            wallet,
            marketplace,
            compute,
            current_task: None,
            delegated_tasks: Vec::new(),
        }
    }

    /// Get agent ID.
    pub fn id(&self) -> Uuid {
        self.agent.id
    }

    /// Get agent role.
    pub fn role(&self) -> SubAgentRole {
        self.agent.role
    }

    /// Find a suitable task from the marketplace.
    pub async fn find_task(&self) -> Result<Option<Task>> {
        // Create filter based on budget constraints
        let filter = TaskFilter {
            max_reward: Some(self.budget.max_task_reward),
            max_hours: Some(self.budget.remaining_compute_hours()),
            max_difficulty: Some(match self.agent.role {
                SubAgentRole::SubjectMatterExpert => 0.8,
                SubAgentRole::IndividualContributor => 0.6,
                SubAgentRole::Executive => 0.9,
                SubAgentRole::BoardMember => 0.5,
            }),
            ..Default::default()
        };

        let tasks = self.marketplace.list_available_tasks(Some(filter)).await?;

        // Find best task based on role and specialization
        let best_task = tasks.into_iter().max_by(|a, b| {
            let score_a = self.score_task(a);
            let score_b = self.score_task(b);
            score_a
                .partial_cmp(&score_b)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        Ok(best_task)
    }

    /// Score a task based on sub-agent capabilities.
    fn score_task(&self, task: &Task) -> f64 {
        let mut score = task.reward / task.estimated_hours.max(0.1);

        // Boost for matching specialization
        if let Some(spec) = &self.agent.specialization {
            let spec_lower = spec.to_lowercase();
            let title_lower = task.title.to_lowercase();
            let desc_lower = task.description.to_lowercase();

            if title_lower.contains(&spec_lower) || desc_lower.contains(&spec_lower) {
                score *= 1.5;
            }
        }

        // Penalize tasks that are too difficult
        let difficulty_fit = match self.agent.role {
            SubAgentRole::SubjectMatterExpert => 1.0 - (task.difficulty - 0.6).abs(),
            SubAgentRole::IndividualContributor => 1.0 - (task.difficulty - 0.4).abs(),
            _ => 1.0 - task.difficulty,
        };
        score *= difficulty_fit.max(0.3);

        score
    }

    /// Claim a task from the marketplace.
    pub async fn claim_task(&mut self, task_id: Uuid) -> Result<Task> {
        let agent_id = format!("subagent-{}", self.agent.id);
        let task = self.marketplace.claim_task(task_id, &agent_id).await?;
        self.current_task = Some(task.clone());
        Ok(task)
    }

    /// Execute the current task (simplified - in real implementation would use TaskExecutor).
    pub async fn execute_task(&mut self) -> Result<DelegationResult> {
        let task = self
            .current_task
            .take()
            .ok_or_else(|| EconomicAgentError::TaskNotFound {
                id: "no_current_task".to_string(),
            })?;

        // Record compute usage
        self.budget.spend(0.0, task.estimated_hours);

        // Simulate task execution (in real implementation, would use TaskExecutor)
        let quality_score = self.agent.performance * 0.8 + 0.2 * rand::random::<f64>();
        let success = quality_score > 0.5;

        // Submit solution
        let agent_id = format!("subagent-{}", self.agent.id);
        let solution = format!(
            "Task completed by {} with quality {:.2}",
            self.agent.name, quality_score
        );

        let submission = self
            .marketplace
            .submit_solution(task.id, &agent_id, &solution)
            .await?;

        // Check result
        let final_submission = self
            .marketplace
            .check_submission_status(submission.id)
            .await?;

        let reward = final_submission.final_reward.unwrap_or(0.0);
        if reward > 0.0 {
            self.budget.earn(reward);
        }

        // Update agent stats
        if success {
            self.agent.tasks_completed += 1;
            self.agent.performance = (self.agent.performance * 0.9 + quality_score * 0.1).min(1.0);
        }

        Ok(DelegationResult {
            success,
            reward_earned: reward,
            time_spent: task.estimated_hours,
            quality_score: Some(quality_score),
            notes: format!(
                "Task '{}' {} by {}",
                task.title,
                if success { "completed" } else { "failed" },
                self.agent.name
            ),
        })
    }

    /// Accept a delegated task from parent.
    pub fn accept_delegation(
        &mut self,
        task: Task,
        deadline: Option<chrono::DateTime<Utc>>,
    ) -> Uuid {
        let delegation = DelegatedTask {
            id: Uuid::new_v4(),
            task,
            assigned_to: self.agent.id,
            delegated_at: Utc::now(),
            deadline,
            status: DelegationStatus::Pending,
            result: None,
        };

        let id = delegation.id;
        self.delegated_tasks.push(delegation);
        id
    }

    /// Work on delegated tasks.
    pub async fn work_on_delegations(&mut self) -> Vec<DelegationResult> {
        let mut results = Vec::new();

        // Collect pending delegations info first to avoid borrow issues
        let pending: Vec<(Uuid, Task, f64)> = self
            .delegated_tasks
            .iter()
            .filter(|d| d.status == DelegationStatus::Pending)
            .map(|d| (d.id, d.task.clone(), d.task.estimated_hours))
            .collect();

        for (delegation_id, task, estimated_hours) in pending {
            // Update status to InProgress
            if let Some(delegation) = self
                .delegated_tasks
                .iter_mut()
                .find(|d| d.id == delegation_id)
            {
                delegation.status = DelegationStatus::InProgress;
            }

            // Check if we can afford it
            if !self.budget.can_afford_task(estimated_hours) {
                if let Some(delegation) = self
                    .delegated_tasks
                    .iter_mut()
                    .find(|d| d.id == delegation_id)
                {
                    delegation.status = DelegationStatus::Returned;
                    delegation.result = Some(DelegationResult {
                        success: false,
                        reward_earned: 0.0,
                        time_spent: 0.0,
                        quality_score: None,
                        notes: "Insufficient compute budget".to_string(),
                    });
                }
                continue;
            }

            // Execute the task
            self.current_task = Some(task);
            let exec_result = self.execute_task().await;

            // Update delegation with result
            if let Some(delegation) = self
                .delegated_tasks
                .iter_mut()
                .find(|d| d.id == delegation_id)
            {
                match exec_result {
                    Ok(result) => {
                        delegation.status = if result.success {
                            DelegationStatus::Completed
                        } else {
                            DelegationStatus::Failed
                        };
                        results.push(result.clone());
                        delegation.result = Some(result);
                    }
                    Err(e) => {
                        delegation.status = DelegationStatus::Failed;
                        delegation.result = Some(DelegationResult {
                            success: false,
                            reward_earned: 0.0,
                            time_spent: 0.0,
                            quality_score: None,
                            notes: format!("Error: {}", e),
                        });
                    }
                }
            }
        }

        results
    }

    /// Get delegation status.
    pub fn get_delegation_status(&self, delegation_id: &Uuid) -> Option<&DelegatedTask> {
        self.delegated_tasks.iter().find(|d| &d.id == delegation_id)
    }

    /// Autonomous work cycle - find and complete tasks independently.
    #[allow(clippy::collapsible_if)] // Using let chains isn't stable
    pub async fn autonomous_cycle(&mut self) -> Result<Option<DelegationResult>> {
        // First, work on any delegated tasks
        let delegation_results = self.work_on_delegations().await;
        if !delegation_results.is_empty() {
            return Ok(delegation_results.into_iter().next());
        }

        // If no delegations, find own work (if allowed by role)
        let can_find_own_work = matches!(
            self.agent.role,
            SubAgentRole::IndividualContributor | SubAgentRole::SubjectMatterExpert
        );

        if can_find_own_work {
            if let Some(task) = self.find_task().await? {
                if self.budget.can_afford_task(task.estimated_hours) {
                    self.claim_task(task.id).await?;
                    let result = self.execute_task().await?;
                    return Ok(Some(result));
                }
            }
        }

        Ok(None)
    }
}

/// Manager for autonomous sub-agents.
pub struct AutonomousSubAgentManager {
    /// Autonomous sub-agents.
    agents: Arc<RwLock<Vec<AutonomousSubAgent>>>,
    /// Wallet backend.
    wallet: Arc<dyn Wallet>,
    /// Marketplace backend.
    marketplace: Arc<dyn Marketplace>,
    /// Compute backend.
    compute: Arc<dyn Compute>,
}

impl AutonomousSubAgentManager {
    /// Create a new autonomous manager.
    pub fn new(
        wallet: Arc<dyn Wallet>,
        marketplace: Arc<dyn Marketplace>,
        compute: Arc<dyn Compute>,
    ) -> Self {
        Self {
            agents: Arc::new(RwLock::new(Vec::new())),
            wallet,
            marketplace,
            compute,
        }
    }

    /// Create an autonomous sub-agent with budget.
    pub async fn create_autonomous_agent(
        &self,
        agent: SubAgent,
        parent_id: String,
        budget: SubAgentBudget,
    ) -> Uuid {
        let autonomous = AutonomousSubAgent::new(
            agent.clone(),
            parent_id,
            budget,
            Arc::clone(&self.wallet),
            Arc::clone(&self.marketplace),
            Arc::clone(&self.compute),
        );

        let id = autonomous.id();
        self.agents.write().await.push(autonomous);
        id
    }

    /// Delegate a task to the best available sub-agent.
    pub async fn delegate_task(
        &self,
        task: Task,
        deadline: Option<chrono::DateTime<Utc>>,
    ) -> Option<Uuid> {
        let mut agents = self.agents.write().await;

        // Find best agent for this task
        let best_idx = agents.iter().enumerate().max_by(|(_, a), (_, b)| {
            let score_a = a.score_task(&task);
            let score_b = b.score_task(&task);
            score_a
                .partial_cmp(&score_b)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        if let Some((idx, _)) = best_idx {
            let delegation_id = agents[idx].accept_delegation(task, deadline);
            Some(delegation_id)
        } else {
            None
        }
    }

    /// Run autonomous work cycles for all agents.
    pub async fn run_autonomous_cycles(&self) -> Vec<DelegationResult> {
        let mut agents = self.agents.write().await;
        let mut all_results = Vec::new();

        for agent in agents.iter_mut() {
            if let Ok(Some(result)) = agent.autonomous_cycle().await {
                all_results.push(result);
            }
        }

        all_results
    }

    /// Get total budget summary.
    pub async fn get_budget_summary(&self) -> SubAgentBudget {
        let agents = self.agents.read().await;

        let mut total = SubAgentBudget::default();
        for agent in agents.iter() {
            total.allocated_capital += agent.budget.allocated_capital;
            total.spent_capital += agent.budget.spent_capital;
            total.allocated_compute_hours += agent.budget.allocated_compute_hours;
            total.used_compute_hours += agent.budget.used_compute_hours;
        }

        total
    }

    /// Get agent count.
    pub async fn count(&self) -> usize {
        self.agents.read().await.len()
    }
}

/// Trait for agents that can delegate to sub-agents.
#[async_trait]
pub trait Delegator {
    /// Delegate a task to sub-agents.
    async fn delegate(&mut self, task: Task) -> Result<Option<Uuid>>;

    /// Collect results from delegated tasks.
    async fn collect_delegated_results(&mut self) -> Vec<DelegationResult>;

    /// Allocate budget to a sub-agent.
    async fn allocate_budget(&mut self, agent_id: Uuid, budget: SubAgentBudget) -> Result<()>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_budget_creation() {
        let budget = SubAgentBudget::new(1000.0, 100.0);
        assert_eq!(budget.allocated_capital, 1000.0);
        assert_eq!(budget.remaining_capital(), 1000.0);
        assert_eq!(budget.max_task_reward, 500.0);
    }

    #[test]
    fn test_budget_spending() {
        let mut budget = SubAgentBudget::new(1000.0, 100.0);
        budget.spend(200.0, 10.0);

        assert_eq!(budget.remaining_capital(), 800.0);
        assert_eq!(budget.remaining_compute_hours(), 90.0);
    }

    #[test]
    fn test_budget_can_afford() {
        let budget = SubAgentBudget::new(1000.0, 10.0);
        assert!(budget.can_afford_task(5.0));
        assert!(!budget.can_afford_task(15.0));
    }

    #[test]
    fn test_delegation_status() {
        let status = DelegationStatus::Pending;
        assert_eq!(status, DelegationStatus::Pending);
    }
}

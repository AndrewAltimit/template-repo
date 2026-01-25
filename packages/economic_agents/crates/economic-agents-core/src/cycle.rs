//! Cycle execution results and tracking.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::decision::{Decision, ResourceAllocation};
use crate::state::AgentState;

/// Result of a single decision cycle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CycleResult {
    /// Cycle number.
    pub cycle: u32,
    /// Timestamp when cycle started.
    pub timestamp: DateTime<Utc>,
    /// Agent state snapshot at cycle start.
    pub initial_state: AgentState,
    /// Agent state snapshot at cycle end.
    pub final_state: AgentState,
    /// Decision made this cycle.
    pub decision: Option<DecisionRecord>,
    /// Resource allocation for this cycle.
    pub allocation: Option<AllocationRecord>,
    /// Task work result (if performed).
    pub task_result: Option<TaskWorkResult>,
    /// Company formation result (if attempted).
    pub company_formation: Option<CompanyFormationResult>,
    /// Company work result (if performed).
    pub company_work: Option<CompanyWorkResult>,
    /// Investment seeking result (if attempted).
    pub investment_result: Option<InvestmentResult>,
    /// Any errors encountered.
    pub errors: Vec<String>,
    /// Duration of the cycle in milliseconds.
    pub duration_ms: u64,
}

impl CycleResult {
    /// Create a new cycle result for the given cycle number.
    pub fn new(cycle: u32, initial_state: AgentState) -> Self {
        Self {
            cycle,
            timestamp: Utc::now(),
            initial_state,
            final_state: AgentState::default(),
            decision: None,
            allocation: None,
            task_result: None,
            company_formation: None,
            company_work: None,
            investment_result: None,
            errors: Vec::new(),
            duration_ms: 0,
        }
    }

    /// Check if the cycle was successful (no errors).
    pub fn is_success(&self) -> bool {
        self.errors.is_empty()
    }

    /// Add an error to the cycle result.
    pub fn add_error(&mut self, error: impl Into<String>) {
        self.errors.push(error.into());
    }
}

/// Record of a decision made.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionRecord {
    /// Type of decision.
    pub decision_type: String,
    /// Reasoning behind the decision.
    pub reasoning: String,
    /// Confidence level (0.0-1.0).
    pub confidence: f64,
}

impl From<&Decision> for DecisionRecord {
    fn from(decision: &Decision) -> Self {
        Self {
            decision_type: format!("{:?}", decision.decision_type),
            reasoning: decision.reasoning.clone(),
            confidence: decision.confidence,
        }
    }
}

/// Record of resource allocation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllocationRecord {
    /// Hours allocated to task work.
    pub task_work_hours: f64,
    /// Hours allocated to company work.
    pub company_work_hours: f64,
    /// Hours allocated to other activities.
    pub other_hours: f64,
    /// Total hours available this cycle.
    pub total_hours: f64,
}

impl AllocationRecord {
    /// Create from a ResourceAllocation and total hours.
    pub fn from_allocation(allocation: &ResourceAllocation, total_hours: f64) -> Self {
        Self {
            task_work_hours: allocation.task_work * total_hours,
            company_work_hours: allocation.company_work * total_hours,
            other_hours: allocation.other * total_hours,
            total_hours,
        }
    }
}

/// Result of task work execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskWorkResult {
    /// Whether task work was successful.
    pub success: bool,
    /// Task ID that was worked on.
    pub task_id: Option<Uuid>,
    /// Task title.
    pub task_title: Option<String>,
    /// Hours spent on the task.
    pub hours_spent: f64,
    /// Reward earned (if any).
    pub reward_earned: Option<f64>,
    /// Quality score of submission (if available).
    pub quality_score: Option<f64>,
    /// Reason for failure (if failed).
    pub failure_reason: Option<String>,
}

impl TaskWorkResult {
    /// Create a successful task work result.
    pub fn success(task_id: Uuid, task_title: String, hours: f64, reward: f64, quality: f64) -> Self {
        Self {
            success: true,
            task_id: Some(task_id),
            task_title: Some(task_title),
            hours_spent: hours,
            reward_earned: Some(reward),
            quality_score: Some(quality),
            failure_reason: None,
        }
    }

    /// Create a failed task work result.
    pub fn failure(reason: impl Into<String>, hours: f64) -> Self {
        Self {
            success: false,
            task_id: None,
            task_title: None,
            hours_spent: hours,
            reward_earned: None,
            quality_score: None,
            failure_reason: Some(reason.into()),
        }
    }

    /// Create a rejected submission result.
    pub fn rejected(task_id: Uuid, task_title: String, hours: f64, reason: impl Into<String>) -> Self {
        Self {
            success: false,
            task_id: Some(task_id),
            task_title: Some(task_title),
            hours_spent: hours,
            reward_earned: None,
            quality_score: None,
            failure_reason: Some(reason.into()),
        }
    }
}

/// Result of company formation attempt.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompanyFormationResult {
    /// Whether company was formed successfully.
    pub success: bool,
    /// Company ID (if successful).
    pub company_id: Option<Uuid>,
    /// Company name.
    pub company_name: Option<String>,
    /// Initial capital allocated.
    pub initial_capital: f64,
    /// Reason for failure (if failed).
    pub failure_reason: Option<String>,
}

impl CompanyFormationResult {
    /// Create a successful formation result.
    pub fn success(company_id: Uuid, name: String, capital: f64) -> Self {
        Self {
            success: true,
            company_id: Some(company_id),
            company_name: Some(name),
            initial_capital: capital,
            failure_reason: None,
        }
    }

    /// Create a failed formation result.
    pub fn failure(reason: impl Into<String>) -> Self {
        Self {
            success: false,
            company_id: None,
            company_name: None,
            initial_capital: 0.0,
            failure_reason: Some(reason.into()),
        }
    }
}

/// Result of company work execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompanyWorkResult {
    /// Whether company work was successful.
    pub success: bool,
    /// Hours spent on company work.
    pub hours_spent: f64,
    /// Activities performed.
    pub activities: Vec<String>,
    /// Revenue generated (if any).
    pub revenue_generated: Option<f64>,
    /// Reason for failure (if failed).
    pub failure_reason: Option<String>,
}

impl CompanyWorkResult {
    /// Create a successful company work result.
    pub fn success(hours: f64, activities: Vec<String>, revenue: Option<f64>) -> Self {
        Self {
            success: true,
            hours_spent: hours,
            activities,
            revenue_generated: revenue,
            failure_reason: None,
        }
    }

    /// Create a failed company work result.
    pub fn failure(reason: impl Into<String>, hours: f64) -> Self {
        Self {
            success: false,
            hours_spent: hours,
            activities: Vec::new(),
            revenue_generated: None,
            failure_reason: Some(reason.into()),
        }
    }
}

/// Result of investment seeking.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvestmentResult {
    /// Whether investment seeking was successful.
    pub success: bool,
    /// Proposal ID (if created).
    pub proposal_id: Option<Uuid>,
    /// Amount requested.
    pub amount_requested: f64,
    /// Amount received (if any).
    pub amount_received: Option<f64>,
    /// Investor ID (if funded).
    pub investor_id: Option<String>,
    /// Reason for failure (if failed).
    pub failure_reason: Option<String>,
}

impl InvestmentResult {
    /// Create a pending investment result (proposal submitted).
    pub fn pending(proposal_id: Uuid, amount_requested: f64) -> Self {
        Self {
            success: true,
            proposal_id: Some(proposal_id),
            amount_requested,
            amount_received: None,
            investor_id: None,
            failure_reason: None,
        }
    }

    /// Create a funded investment result.
    pub fn funded(proposal_id: Uuid, amount: f64, investor: String) -> Self {
        Self {
            success: true,
            proposal_id: Some(proposal_id),
            amount_requested: amount,
            amount_received: Some(amount),
            investor_id: Some(investor),
            failure_reason: None,
        }
    }

    /// Create a failed investment result.
    pub fn failure(reason: impl Into<String>) -> Self {
        Self {
            success: false,
            proposal_id: None,
            amount_requested: 0.0,
            amount_received: None,
            investor_id: None,
            failure_reason: Some(reason.into()),
        }
    }
}

//! Common types used across the economic agents system.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Unique identifier for entities.
pub type EntityId = Uuid;

/// Monetary amount in the simulation currency.
pub type Currency = f64;

/// Duration in hours.
pub type Hours = f64;

/// A transaction record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Unique transaction ID.
    pub id: EntityId,
    /// Source address (None for deposits).
    pub from: Option<String>,
    /// Destination address.
    pub to: String,
    /// Amount transferred.
    pub amount: Currency,
    /// Transaction timestamp.
    pub timestamp: DateTime<Utc>,
    /// Optional memo/description.
    pub memo: Option<String>,
}

impl Transaction {
    /// Create a new transaction.
    pub fn new(from: Option<String>, to: String, amount: Currency, memo: Option<String>) -> Self {
        Self {
            id: Uuid::new_v4(),
            from,
            to,
            amount,
            timestamp: Utc::now(),
            memo,
        }
    }
}

/// A task available on the marketplace.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    /// Unique task ID.
    pub id: EntityId,
    /// Task title/name.
    pub title: String,
    /// Detailed description.
    pub description: String,
    /// Task category.
    pub category: TaskCategory,
    /// Reward amount for completion.
    pub reward: Currency,
    /// Estimated hours to complete.
    pub estimated_hours: Hours,
    /// Required skill level (0.0-1.0).
    pub difficulty: f64,
    /// Skills required for this task.
    #[serde(default)]
    pub required_skills: Vec<Skill>,
    /// Deadline for completion.
    pub deadline: Option<DateTime<Utc>>,
    /// Current status.
    pub status: TaskStatus,
    /// Poster's address/ID.
    pub posted_by: String,
    /// Timestamp when posted.
    pub posted_at: DateTime<Utc>,
    /// Agent that claimed this task (if any).
    pub claimed_by: Option<String>,
    /// Timestamp when claimed.
    pub claimed_at: Option<DateTime<Utc>>,
}

/// Skills that agents can have and tasks can require.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Skill {
    // Programming Languages
    /// Python programming.
    Python,
    /// Rust programming.
    Rust,
    /// JavaScript/TypeScript programming.
    JavaScript,
    /// Go programming.
    Go,
    /// Java programming.
    Java,
    /// C/C++ programming.
    Cpp,
    /// SQL and database queries.
    Sql,

    // Technical Domains
    /// Web development (frontend/backend).
    WebDev,
    /// API design and implementation.
    ApiDesign,
    /// Database design and optimization.
    Database,
    /// DevOps and infrastructure.
    DevOps,
    /// Machine learning and AI.
    MachineLearning,
    /// Data analysis and visualization.
    DataAnalysis,
    /// Security and cryptography.
    Security,
    /// System architecture.
    Architecture,

    // Soft Skills
    /// Technical writing and documentation.
    TechnicalWriting,
    /// Code review and quality assurance.
    CodeReview,
    /// Research and analysis.
    Research,
    /// Testing and QA.
    Testing,
    /// Project management.
    ProjectManagement,
}

/// Task categories.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskCategory {
    /// Software development.
    Coding,
    /// Code review.
    CodeReview,
    /// Writing documentation.
    Documentation,
    /// Data analysis.
    DataAnalysis,
    /// Research tasks.
    Research,
    /// Design work.
    Design,
    /// Testing.
    Testing,
    /// Other/miscellaneous.
    Other,
}

/// Task status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    /// Available for claiming.
    Available,
    /// Claimed by an agent.
    Claimed,
    /// Work submitted, pending review.
    Submitted,
    /// Completed and approved.
    Completed,
    /// Rejected.
    Rejected,
    /// Expired without completion.
    Expired,
    /// Cancelled by poster.
    Cancelled,
}

/// A task submission.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskSubmission {
    /// Unique submission ID.
    pub id: EntityId,
    /// Task this submission is for.
    pub task_id: EntityId,
    /// Agent that submitted.
    pub submitted_by: String,
    /// Submission content/solution.
    pub content: String,
    /// Submission timestamp.
    pub submitted_at: DateTime<Utc>,
    /// Current status.
    pub status: SubmissionStatus,
    /// Quality score (0.0-1.0) after review.
    pub quality_score: Option<f64>,
    /// Reviewer feedback.
    pub feedback: Option<String>,
    /// Final reward amount (may differ from task reward).
    pub final_reward: Option<Currency>,
}

/// Submission review status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SubmissionStatus {
    /// Pending review.
    Pending,
    /// Under review.
    InReview,
    /// Approved with full payment.
    Approved,
    /// Approved with partial payment.
    PartialApproval,
    /// Rejected.
    Rejected,
    /// Requires revisions.
    RevisionRequired,
}

/// Compute resource status.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComputeStatus {
    /// Hours of compute remaining.
    pub hours_remaining: Hours,
    /// Cost per hour.
    pub cost_per_hour: Currency,
    /// Total hours consumed.
    pub total_consumed: Hours,
    /// Total amount spent.
    pub total_spent: Currency,
    /// Whether the account is active.
    pub is_active: bool,
}

/// Agent state snapshot.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentState {
    /// Current balance.
    pub balance: Currency,
    /// Compute hours remaining.
    pub compute_hours: Hours,
    /// Tasks completed.
    pub tasks_completed: u32,
    /// Total earnings.
    pub total_earnings: Currency,
    /// Total expenses.
    pub total_expenses: Currency,
    /// Whether agent has formed a company.
    pub has_company: bool,
    /// Last updated timestamp.
    pub last_updated: DateTime<Utc>,
}

impl Default for AgentState {
    fn default() -> Self {
        Self {
            balance: 0.0,
            compute_hours: 0.0,
            tasks_completed: 0,
            total_earnings: 0.0,
            total_expenses: 0.0,
            has_company: false,
            last_updated: Utc::now(),
        }
    }
}

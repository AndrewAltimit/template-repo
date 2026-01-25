//! Request and response models for the API.
//!
//! These types are used for JSON serialization in HTTP requests and responses.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use economic_agents_interfaces::{
    ComputeStatus, Currency, Hours, Task, TaskCategory, TaskSubmission, Transaction,
};

// ============================================================================
// Wallet API Models
// ============================================================================

/// Response for balance queries.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BalanceResponse {
    pub balance: Currency,
    pub address: String,
}

/// Request for sending a payment.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SendPaymentRequest {
    pub to: String,
    pub amount: Currency,
    #[serde(default)]
    pub memo: Option<String>,
}

/// Request for receiving a payment.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReceivePaymentRequest {
    #[serde(default)]
    pub from: Option<String>,
    pub amount: Currency,
    #[serde(default)]
    pub memo: Option<String>,
}

/// Response wrapping a transaction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionResponse {
    pub transaction: Transaction,
}

/// Response for transaction history.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionHistoryResponse {
    pub transactions: Vec<Transaction>,
    pub total: usize,
}

// ============================================================================
// Compute API Models
// ============================================================================

/// Response for compute status.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComputeStatusResponse {
    pub status: ComputeStatus,
}

/// Request for adding funds.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AddFundsRequest {
    pub amount: Currency,
}

/// Request for consuming compute time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsumeTimeRequest {
    pub hours: Hours,
}

/// Response for hours remaining.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HoursRemainingResponse {
    pub hours: Hours,
    pub cost_per_hour: Currency,
}

// ============================================================================
// Marketplace API Models
// ============================================================================

/// Request for listing tasks.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ListTasksRequest {
    #[serde(default)]
    pub category: Option<TaskCategory>,
    #[serde(default)]
    pub min_reward: Option<f64>,
    #[serde(default)]
    pub max_reward: Option<f64>,
    #[serde(default)]
    pub max_difficulty: Option<f64>,
    #[serde(default)]
    pub max_hours: Option<f64>,
    #[serde(default)]
    pub limit: Option<usize>,
}

/// Response for task listings.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskListResponse {
    pub tasks: Vec<Task>,
    pub total: usize,
}

/// Response wrapping a single task.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResponse {
    pub task: Task,
}

/// Request for claiming a task.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimTaskRequest {
    pub agent_id: String,
}

/// Request for submitting a solution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubmitSolutionRequest {
    pub agent_id: String,
    pub content: String,
}

/// Response wrapping a submission.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubmissionResponse {
    pub submission: TaskSubmission,
}

/// Request for releasing a task.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReleaseTaskRequest {
    pub agent_id: String,
}

// ============================================================================
// Error Models
// ============================================================================

/// API error response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiErrorResponse {
    pub error: String,
    pub code: String,
    #[serde(default)]
    pub details: Option<serde_json::Value>,
}

impl ApiErrorResponse {
    pub fn new(error: impl Into<String>, code: impl Into<String>) -> Self {
        Self {
            error: error.into(),
            code: code.into(),
            details: None,
        }
    }

    pub fn with_details(mut self, details: serde_json::Value) -> Self {
        self.details = Some(details);
        self
    }
}

// ============================================================================
// Health/Status Models
// ============================================================================

/// Health check response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub service: String,
    pub version: String,
    pub timestamp: DateTime<Utc>,
}

impl HealthResponse {
    pub fn healthy(service: impl Into<String>) -> Self {
        Self {
            status: "healthy".to_string(),
            service: service.into(),
            version: env!("CARGO_PKG_VERSION").to_string(),
            timestamp: Utc::now(),
        }
    }
}

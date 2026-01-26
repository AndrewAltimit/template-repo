//! Company data models.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Company lifecycle stage.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CompanyStage {
    /// Initial ideation phase.
    Ideation,
    /// Active development.
    Development,
    /// Seeking investment.
    SeekingInvestment,
    /// Fully operational.
    Operational,
    /// Company has failed/shutdown.
    Failed,
}

impl CompanyStage {
    /// Check if a transition to another stage is valid.
    pub fn can_transition_to(&self, target: CompanyStage) -> bool {
        use CompanyStage::*;
        matches!(
            (self, target),
            (Ideation, Development)
                | (Development, SeekingInvestment)
                | (Development, Operational)
                | (SeekingInvestment, Operational)
                | (SeekingInvestment, Development) // Can go back to dev if rejected
                | (_, Failed) // Any stage can fail
        )
    }
}

/// A business plan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BusinessPlan {
    /// Plan title.
    pub title: String,
    /// Executive summary.
    pub summary: String,
    /// Problem being solved.
    pub problem: String,
    /// Proposed solution.
    pub solution: String,
    /// Target market.
    pub target_market: String,
    /// Revenue model.
    pub revenue_model: String,
    /// Initial funding required.
    pub funding_required: f64,
    /// Created timestamp.
    pub created_at: DateTime<Utc>,
}

/// A product or service.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Product {
    /// Product ID.
    pub id: Uuid,
    /// Product name.
    pub name: String,
    /// Description.
    pub description: String,
    /// Development status (0.0-1.0).
    pub completion: f64,
    /// Target launch date.
    pub target_launch: Option<DateTime<Utc>>,
}

/// Company metrics.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CompanyMetrics {
    /// Total revenue.
    pub revenue: f64,
    /// Total expenses.
    pub expenses: f64,
    /// Number of products.
    pub product_count: u32,
    /// Number of employees (sub-agents).
    pub employee_count: u32,
}

/// A company entity.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Company {
    /// Unique company ID.
    pub id: Uuid,
    /// Company name.
    pub name: String,
    /// Current stage.
    pub stage: CompanyStage,
    /// Available capital.
    pub capital: f64,
    /// Business plan.
    pub business_plan: Option<BusinessPlan>,
    /// Products.
    pub products: Vec<Product>,
    /// Metrics.
    pub metrics: CompanyMetrics,
    /// Founded timestamp.
    pub founded_at: DateTime<Utc>,
    /// Last updated timestamp.
    pub updated_at: DateTime<Utc>,
}

impl Company {
    /// Create a new company.
    pub fn new(name: impl Into<String>, initial_capital: f64) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            name: name.into(),
            stage: CompanyStage::Ideation,
            capital: initial_capital,
            business_plan: None,
            products: Vec::new(),
            metrics: CompanyMetrics::default(),
            founded_at: now,
            updated_at: now,
        }
    }

    /// Check if company is bankrupt.
    pub fn is_bankrupt(&self) -> bool {
        self.capital < 0.0
    }

    /// Transition to a new stage.
    pub fn transition_to(&mut self, stage: CompanyStage) -> Result<(), String> {
        if self.stage.can_transition_to(stage) {
            self.stage = stage;
            self.updated_at = Utc::now();
            Ok(())
        } else {
            Err(format!(
                "Invalid transition from {:?} to {:?}",
                self.stage, stage
            ))
        }
    }
}

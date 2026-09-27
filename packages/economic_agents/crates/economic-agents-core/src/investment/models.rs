//! Investment data models.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// An investment proposal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvestmentProposal {
    /// Proposal ID.
    pub id: Uuid,
    /// Company ID.
    pub company_id: Uuid,
    /// Company name.
    pub company_name: String,
    /// Amount requested.
    pub amount_requested: f64,
    /// Equity offered (0.0-1.0).
    pub equity_offered: f64,
    /// Use of funds description.
    pub use_of_funds: String,
    /// Projected return (multiplier).
    pub projected_return: f64,
    /// Created timestamp.
    pub created_at: DateTime<Utc>,
}

/// Decision on an investment proposal.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum InvestmentDecision {
    /// Approved as requested.
    Approved,
    /// Approved with different terms.
    Counteroffer,
    /// Rejected.
    Rejected,
    /// Need more information.
    MoreInfoRequired,
}

/// A completed investment.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Investment {
    /// Investment ID.
    pub id: Uuid,
    /// Investor ID.
    pub investor_id: Uuid,
    /// Company ID.
    pub company_id: Uuid,
    /// Amount invested.
    pub amount: f64,
    /// Equity received.
    pub equity: f64,
    /// Investment timestamp.
    pub invested_at: DateTime<Utc>,
}

/// Investor risk tolerance.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum RiskTolerance {
    /// Conservative investor.
    Conservative,
    /// Moderate risk.
    #[default]
    Moderate,
    /// Aggressive/high risk.
    Aggressive,
}

/// An investor profile.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvestorProfile {
    /// Investor ID.
    pub id: Uuid,
    /// Investor name.
    pub name: String,
    /// Available capital.
    pub available_capital: f64,
    /// Risk tolerance.
    pub risk_tolerance: RiskTolerance,
    /// Minimum investment amount.
    pub min_investment: f64,
    /// Maximum investment amount.
    pub max_investment: f64,
    /// Preferred sectors.
    pub preferred_sectors: Vec<String>,
}

impl InvestorProfile {
    /// Create a new investor profile.
    pub fn new(name: impl Into<String>, capital: f64) -> Self {
        Self {
            id: Uuid::new_v4(),
            name: name.into(),
            available_capital: capital,
            risk_tolerance: RiskTolerance::default(),
            min_investment: 1000.0,
            max_investment: capital * 0.25, // Max 25% in one investment
            preferred_sectors: Vec::new(),
        }
    }
}

//! Investor agent implementation.

use crate::models::{InvestmentDecision, InvestmentProposal, InvestorProfile};

/// An AI investor agent that evaluates proposals.
pub struct InvestorAgent {
    profile: InvestorProfile,
}

impl InvestorAgent {
    /// Create a new investor agent.
    pub fn new(profile: InvestorProfile) -> Self {
        Self { profile }
    }

    /// Evaluate an investment proposal.
    pub async fn evaluate(&self, proposal: &InvestmentProposal) -> InvestmentDecision {
        // Simple rule-based evaluation for now
        // TODO: Add LLM-powered evaluation

        // Check if within budget
        if proposal.amount_requested > self.profile.available_capital {
            return InvestmentDecision::Rejected;
        }

        if proposal.amount_requested > self.profile.max_investment {
            return InvestmentDecision::Counteroffer;
        }

        if proposal.amount_requested < self.profile.min_investment {
            return InvestmentDecision::Rejected;
        }

        // Evaluate based on projected return and risk tolerance
        let min_return = match self.profile.risk_tolerance {
            crate::models::RiskTolerance::Conservative => 2.0,
            crate::models::RiskTolerance::Moderate => 1.5,
            crate::models::RiskTolerance::Aggressive => 1.2,
        };

        if proposal.projected_return >= min_return {
            InvestmentDecision::Approved
        } else {
            InvestmentDecision::Rejected
        }
    }

    /// Get the investor profile.
    pub fn profile(&self) -> &InvestorProfile {
        &self.profile
    }
}

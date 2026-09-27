//! Investor agent implementation.

use super::models::{InvestmentDecision, InvestmentProposal, InvestorProfile};

/// A simulated investor that evaluates proposals.
///
/// SIMULATED: despite the name, no model is consulted. Evaluation is a fixed
/// rule set (budget bounds plus a minimum projected-return multiple per
/// [`RiskTolerance`](super::models::RiskTolerance)); LLM-based evaluation is
/// not implemented.
pub struct InvestorAgent {
    profile: InvestorProfile,
}

impl InvestorAgent {
    /// Create a new investor agent.
    pub fn new(profile: InvestorProfile) -> Self {
        Self { profile }
    }

    /// Evaluate an investment proposal with the fixed rule set described on
    /// [`InvestorAgent`].
    pub async fn evaluate(&self, proposal: &InvestmentProposal) -> InvestmentDecision {
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
            super::models::RiskTolerance::Conservative => 2.0,
            super::models::RiskTolerance::Moderate => 1.5,
            super::models::RiskTolerance::Aggressive => 1.2,
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

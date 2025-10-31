"""Investor agent that evaluates and makes investment decisions."""

import uuid
from typing import Any, Dict, List, Optional

from economic_agents.investment.models import (
    Investment,
    InvestmentDecision,
    InvestmentProposal,
    InvestorProfile,
)
from economic_agents.simulation.market_dynamics import MarketDynamics
from economic_agents.simulation.reputation_system import ReputationSystem


class InvestorAgent:
    """Agent that evaluates investment proposals and makes funding decisions."""

    def __init__(
        self,
        profile: InvestorProfile,
        market_dynamics: Optional[MarketDynamics] = None,
        reputation_system: Optional[ReputationSystem] = None,
    ):
        """Initialize investor agent with profile and optional simulation systems.

        Args:
            profile: Investor profile
            market_dynamics: Optional market dynamics simulator
            reputation_system: Optional reputation system
        """
        self.profile = profile
        self.market_dynamics = market_dynamics
        self.reputation_system = reputation_system

    def evaluate_proposal(self, proposal: InvestmentProposal, agent_id: Optional[str] = None) -> InvestmentDecision:
        """
        Evaluate an investment proposal and make a decision.

        Args:
            proposal: Investment proposal to evaluate
            agent_id: Optional agent ID for reputation-based evaluation

        Returns InvestmentDecision with evaluation scores and decision.
        """
        # Update market dynamics
        if self.market_dynamics:
            self.market_dynamics.update()

        # Calculate evaluation scores for each criterion
        evaluation_scores = self._calculate_scores(proposal)

        # Add reputation score if available
        if self.reputation_system and agent_id:
            reputation_summary = self.reputation_system.get_reputation_summary(agent_id)
            # Reputation affects overall evaluation
            reputation_score = reputation_summary["trust_score"]
            evaluation_scores["reputation"] = reputation_score

        # Overall score is weighted average
        overall_score = sum(evaluation_scores.values()) / len(evaluation_scores)

        # Apply market dynamics modifiers to approval threshold
        base_approval_threshold = 0.6
        if self.market_dynamics:
            market_modifier = self.market_dynamics.get_investor_approval_probability_modifier()
            approval_threshold = base_approval_threshold - market_modifier  # Lower threshold in bull markets
        else:
            approval_threshold = base_approval_threshold

        # Decision logic based on overall score and specific criteria
        approved = self._should_approve(proposal, evaluation_scores, overall_score, approval_threshold)

        # Determine investment terms if approved
        if approved:
            # Adjust amount based on market dynamics
            base_amount = proposal.amount_requested
            if self.market_dynamics:
                funding_multiplier = self.market_dynamics.get_investor_funding_multiplier()
                amount_offered = base_amount * funding_multiplier
            else:
                amount_offered = base_amount

            # Adjust based on reputation
            if self.reputation_system and agent_id:
                interest_multiplier = self.reputation_system.get_investor_interest_multiplier(agent_id)
                amount_offered *= interest_multiplier

            equity_requested = proposal.equity_offered
            conditions = self._generate_conditions(proposal, evaluation_scores)
            reasoning = self._generate_approval_reasoning(evaluation_scores, overall_score)
        else:
            amount_offered = 0.0
            equity_requested = 0.0
            conditions = []
            reasoning = self._generate_rejection_reasoning(evaluation_scores, overall_score)

        decision = InvestmentDecision(
            id=str(uuid.uuid4()),
            investor_id=self.profile.id,
            proposal_id=proposal.id,
            approved=approved,
            amount_offered=amount_offered,
            equity_requested=equity_requested,
            reasoning=reasoning,
            evaluation_scores=evaluation_scores,
            conditions=conditions,
        )

        self.profile.decision_history.append(decision.id)

        return decision

    def _calculate_scores(self, proposal: InvestmentProposal) -> Dict[str, float]:
        """Calculate evaluation scores for each criterion (0.0 to 1.0)."""
        scores = {}

        # Market size score
        if proposal.market_size >= self.profile.criteria.min_market_size * 2:
            scores["market_size"] = 1.0
        elif proposal.market_size >= self.profile.criteria.min_market_size:
            scores["market_size"] = 0.7
        else:
            scores["market_size"] = 0.3

        # Revenue projection score (year 1)
        year1_revenue = proposal.revenue_projections[0] if proposal.revenue_projections else 0
        if year1_revenue >= self.profile.criteria.min_revenue_projection * 2:
            scores["revenue"] = 1.0
        elif year1_revenue >= self.profile.criteria.min_revenue_projection:
            scores["revenue"] = 0.7
        else:
            scores["revenue"] = 0.3

        # Team size score
        if proposal.team_size >= self.profile.criteria.required_team_size * 2:
            scores["team"] = 1.0
        elif proposal.team_size >= self.profile.criteria.required_team_size:
            scores["team"] = 0.8
        else:
            scores["team"] = 0.4

        # Stage alignment score
        if proposal.stage in self.profile.criteria.preferred_stages:
            scores["stage"] = 1.0
        else:
            scores["stage"] = 0.5

        # Valuation reasonableness (lower is better)
        # Compare requested valuation to revenue multiple
        if year1_revenue > 0:
            valuation_multiple = proposal.valuation / year1_revenue
            if valuation_multiple < 5:
                scores["valuation"] = 1.0
            elif valuation_multiple < 10:
                scores["valuation"] = 0.7
            else:
                scores["valuation"] = 0.4
        else:
            scores["valuation"] = 0.5

        # Competitive advantages score
        scores["competitive_advantage"] = min(1.0, len(proposal.competitive_advantages) * 0.25)

        # Risk assessment (fewer risks is better)
        risk_score = max(0.0, 1.0 - len(proposal.risks) * 0.15)
        # Adjust by investor's risk tolerance
        scores["risk"] = risk_score + (1.0 - risk_score) * self.profile.criteria.risk_tolerance

        return scores

    def _should_approve(
        self, proposal: InvestmentProposal, scores: Dict[str, float], overall_score: float, threshold: float = 0.6
    ) -> bool:
        """Determine if proposal should be approved.

        Args:
            proposal: Investment proposal
            scores: Evaluation scores
            overall_score: Overall evaluation score
            threshold: Approval threshold (adjusted by market conditions)
        """
        # Must pass minimum score threshold
        if overall_score < threshold:
            return False

        # Must have sufficient capital
        if not self.profile.can_invest(proposal.amount_requested):
            return False

        # Critical criteria must pass
        if scores.get("market_size", 0) < 0.3:
            return False
        if scores.get("team", 0) < 0.4:
            return False

        # Risk tolerance check
        if scores.get("risk", 0) < 0.5 and self.profile.criteria.risk_tolerance < 0.5:
            return False

        return True

    def _generate_conditions(self, proposal: InvestmentProposal, scores: Dict[str, float]) -> List[str]:
        """Generate investment conditions based on evaluation."""
        conditions = []

        if scores.get("team", 0) < 0.8:
            conditions.append("Must hire key executives within 6 months")

        if scores.get("risk", 0) < 0.7:
            conditions.append("Quarterly progress reviews required")

        if scores.get("revenue", 0) < 0.7:
            conditions.append("Must achieve 50% of year 1 revenue target")

        # Always include standard conditions
        conditions.append("Board seat and voting rights")
        conditions.append("Monthly financial reporting required")

        return conditions

    def _generate_approval_reasoning(self, scores: Dict[str, float], overall_score: float) -> str:
        """Generate reasoning for approval."""
        strengths = []
        if scores.get("market_size", 0) >= 0.7:
            strengths.append("strong market opportunity")
        if scores.get("revenue", 0) >= 0.7:
            strengths.append("solid revenue projections")
        if scores.get("team", 0) >= 0.8:
            strengths.append("capable team")
        if scores.get("competitive_advantage", 0) >= 0.75:
            strengths.append("clear competitive advantages")

        return f"Approved with overall score {overall_score:.2f}. Key strengths: {', '.join(strengths)}."

    def _generate_rejection_reasoning(self, scores: Dict[str, float], overall_score: float) -> str:
        """Generate reasoning for rejection."""
        weaknesses = []
        if scores.get("market_size", 0) < 0.5:
            weaknesses.append("insufficient market size")
        if scores.get("revenue", 0) < 0.5:
            weaknesses.append("weak revenue projections")
        if scores.get("team", 0) < 0.6:
            weaknesses.append("team too small")
        if scores.get("risk", 0) < 0.5:
            weaknesses.append("risk profile too high")
        if scores.get("valuation", 0) < 0.5:
            weaknesses.append("valuation too aggressive")

        if not weaknesses:
            weaknesses.append("does not meet investment criteria")

        return f"Rejected with overall score {overall_score:.2f}. Key concerns: {', '.join(weaknesses)}."

    def execute_investment(self, proposal: InvestmentProposal, decision: InvestmentDecision) -> Investment:
        """
        Execute an approved investment.

        Returns Investment record.
        Raises ValueError if decision was not approved or insufficient capital.
        """
        if not decision.approved:
            raise ValueError("Cannot execute rejected investment")

        if not self.profile.can_invest(decision.amount_offered):
            raise ValueError("Insufficient capital for investment")

        investment = Investment(
            id=str(uuid.uuid4()),
            investor_id=self.profile.id,
            company_id=proposal.company_id,
            proposal_id=proposal.id,
            decision_id=decision.id,
            amount=decision.amount_offered,
            equity=decision.equity_requested,
            valuation=proposal.valuation,
            stage=proposal.stage,
            terms={"conditions": decision.conditions},
        )

        # Update investor profile
        self.profile.record_investment(investment.id, investment.amount)

        return investment

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get summary of investor's portfolio."""
        return {
            "investor": self.profile.name,
            "available_capital": self.profile.available_capital,
            "total_invested": self.profile.total_invested,
            "portfolio_size": self.profile.portfolio_size,
            "investment_count": len(self.profile.investment_history),
            "decision_count": len(self.profile.decision_history),
        }

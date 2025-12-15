"""Generate investment proposals from company business plans."""

from datetime import datetime
from typing import Any, Dict
import uuid

from economic_agents.company.models import Company
from economic_agents.investment.models import (
    InvestmentProposal,
    InvestmentStage,
    ProposalStatus,
)


class ProposalGenerator:
    """Generates investment proposals for companies seeking funding."""

    def generate_proposal(self, company: Company, stage: InvestmentStage = InvestmentStage.SEED) -> InvestmentProposal:
        """
        Generate investment proposal based on company's business plan.

        Args:
            company: Company seeking investment
            stage: Investment stage (pre-seed, seed, series A, etc.)

        Returns:
            InvestmentProposal ready for submission
        """
        if not company.business_plan:
            raise ValueError("Company must have business plan to generate proposal")

        plan = company.business_plan

        # Determine valuation based on stage and projections
        valuation = self._calculate_valuation(company, stage)

        # Calculate equity offering based on funding requested and valuation
        equity_offered = (plan.funding_requested / valuation) * 100 if valuation > 0 else 5.0

        # Generate use of funds breakdown
        use_of_funds = self._generate_use_of_funds(plan.funding_requested, stage)

        # Extract competitive advantages and risks
        competitive_advantages = plan.competitive_advantages or [
            "Experienced team",
            "First-mover advantage",
            "Strong product-market fit",
        ]

        risks = self._identify_risks(company, stage)

        # Generate milestones
        milestones = self._generate_milestones(company, stage)

        proposal = InvestmentProposal(
            id=str(uuid.uuid4()),
            company_id=company.id,
            company_name=company.name,
            amount_requested=plan.funding_requested,
            valuation=valuation,
            equity_offered=equity_offered,
            stage=stage,
            use_of_funds=use_of_funds,
            revenue_projections=plan.revenue_projections,
            market_size=self._estimate_market_size(plan),
            team_size=len(company.get_all_sub_agent_ids()),
            competitive_advantages=competitive_advantages,
            risks=risks,
            milestones=milestones,
            status=ProposalStatus.DRAFT,
        )

        return proposal

    def _calculate_valuation(self, company: Company, stage: InvestmentStage) -> float:
        """Calculate company valuation based on stage and metrics."""
        if not company.business_plan:
            return 500000.0  # Default for early stage

        plan = company.business_plan

        # Base valuation on revenue projections
        year1_revenue = plan.revenue_projections[0] if plan.revenue_projections else 0

        # Stage-based revenue multiples
        multiples = {
            InvestmentStage.PRE_SEED: 5.0,
            InvestmentStage.SEED: 8.0,
            InvestmentStage.SERIES_A: 10.0,
            InvestmentStage.SERIES_B: 12.0,
            InvestmentStage.SERIES_C: 15.0,
        }

        multiple = multiples.get(stage, 8.0)

        if year1_revenue > 0:
            valuation = year1_revenue * multiple
        else:
            # Pre-revenue valuation based on funding requested
            valuation = plan.funding_requested * 5

        # Adjust based on team size and products
        team_size = len(company.get_all_sub_agent_ids())
        if team_size >= 5:
            valuation *= 1.2
        if len(company.products) >= 2:
            valuation *= 1.1

        return round(valuation, 2)

    def _generate_use_of_funds(self, total: float, stage: InvestmentStage) -> Dict[str, float]:
        """Generate use of funds breakdown."""
        # Stage-based allocation templates
        if stage in [InvestmentStage.PRE_SEED, InvestmentStage.SEED]:
            return {
                "product_development": total * 0.40,
                "team_expansion": total * 0.30,
                "marketing": total * 0.20,
                "operations": total * 0.10,
            }
        # Series A+
        return {
            "product_development": total * 0.30,
            "team_expansion": total * 0.25,
            "sales_marketing": total * 0.30,
            "operations": total * 0.10,
            "working_capital": total * 0.05,
        }

    def _estimate_market_size(self, plan: Any) -> float:
        """Estimate total addressable market size."""
        # Estimate based on target market
        market_sizes = {
            "developers": 50_000_000.0,
            "enterprises": 100_000_000.0,
            "consumers": 500_000_000.0,
            "teams": 75_000_000.0,
            "businesses": 200_000_000.0,
        }

        target = plan.target_market.lower()
        for key, size in market_sizes.items():
            if key in target:
                return size

        return 50_000_000.0  # Default estimate

    def _identify_risks(self, company: Company, stage: InvestmentStage) -> list[str]:
        """Identify investment risks."""
        risks = []

        # Team size risk
        team_size = len(company.get_all_sub_agent_ids())
        if team_size < 5:
            risks.append("Limited team size may slow execution")

        # Product risk
        if not company.products:
            risks.append("No products developed yet")
        elif all(p.status in ["ideation", "development"] for p in company.products):
            risks.append("Products not yet market-ready")

        # Stage-specific risks
        if stage == InvestmentStage.PRE_SEED:
            risks.append("Pre-revenue stage with unproven market demand")
        elif stage == InvestmentStage.SEED:
            risks.append("Early stage with limited market validation")

        # General startup risks
        risks.append("Market competition and timing risk")
        risks.append("Execution risk on product roadmap")

        return risks

    def _generate_milestones(self, company: Company, stage: InvestmentStage) -> list[Dict[str, Any]]:
        """Generate investment milestones."""
        if not company.business_plan:
            return []

        plan = company.business_plan
        milestones = []

        # Revenue milestones
        if plan.revenue_projections:
            milestones.append(
                {
                    "description": f"Achieve ${plan.revenue_projections[0]:,.0f} in year 1 revenue",
                    "timeline": "12 months",
                    "type": "revenue",
                }
            )

        # Team milestones
        milestones.append(
            {
                "description": "Expand team to 10+ members",
                "timeline": "6 months",
                "type": "team",
            }
        )

        # Product milestones
        if company.products:
            milestones.append(
                {
                    "description": "Launch product to general availability",
                    "timeline": "3 months",
                    "type": "product",
                }
            )
        else:
            milestones.append(
                {
                    "description": "Complete MVP development",
                    "timeline": "6 months",
                    "type": "product",
                }
            )

        # Customer milestones
        milestones.append(
            {
                "description": "Acquire 100+ paying customers",
                "timeline": "9 months",
                "type": "customers",
            }
        )

        # Stage-specific milestones
        if stage in [InvestmentStage.SERIES_A, InvestmentStage.SERIES_B]:
            milestones.append(
                {
                    "description": "Achieve profitability or clear path to profitability",
                    "timeline": "18 months",
                    "type": "financial",
                }
            )

        return milestones

    def submit_proposal(self, proposal: InvestmentProposal) -> InvestmentProposal:
        """Mark proposal as submitted."""
        proposal.status = ProposalStatus.SUBMITTED
        proposal.submitted_at = datetime.now()
        return proposal

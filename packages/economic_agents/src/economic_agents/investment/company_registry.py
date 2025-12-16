"""Company registry for tracking all companies in the ecosystem."""

from typing import Any, Dict, List, Optional

from economic_agents.company.models import Company
from economic_agents.investment.models import Investment, InvestmentProposal


class CompanyRegistry:
    """Central registry for all companies and their investment history."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        self.companies: Dict[str, Company] = {}
        self.proposals: Dict[str, InvestmentProposal] = {}
        self.investments: Dict[str, Investment] = {}
        self.company_investments: Dict[str, List[str]] = {}  # company_id -> investment_ids
        self.company_proposals: Dict[str, List[str]] = {}  # company_id -> proposal_ids

    def register_company(self, company: Company) -> bool:
        """
        Register a new company in the registry.

        Returns True if registered, False if already exists.
        """
        if company.id in self.companies:
            return False

        self.companies[company.id] = company
        self.company_investments[company.id] = []
        self.company_proposals[company.id] = []
        return True

    def get_company(self, company_id: str) -> Optional[Company]:
        """Get company by ID."""
        return self.companies.get(company_id)

    def submit_proposal(self, proposal: InvestmentProposal) -> bool:
        """
        Submit an investment proposal.

        Returns True if submitted, False if already exists.
        """
        if proposal.id in self.proposals:
            return False

        if proposal.company_id not in self.companies:
            raise ValueError(f"Company {proposal.company_id} not registered")

        self.proposals[proposal.id] = proposal
        self.company_proposals[proposal.company_id].append(proposal.id)
        return True

    def record_investment(self, investment: Investment) -> bool:
        """
        Record a completed investment.

        Returns True if recorded, False if already exists.
        Note: This only tracks the investment. The company must call
        company.record_investment() separately to update its capital.
        """
        if investment.id in self.investments:
            return False

        if investment.company_id not in self.companies:
            raise ValueError(f"Company {investment.company_id} not registered")

        self.investments[investment.id] = investment
        self.company_investments[investment.company_id].append(investment.id)

        return True

    def get_company_proposals(self, company_id: str) -> List[InvestmentProposal]:
        """Get all proposals for a company."""
        proposal_ids = self.company_proposals.get(company_id, [])
        return [self.proposals[pid] for pid in proposal_ids]

    def get_company_investments(self, company_id: str) -> List[Investment]:
        """Get all investments for a company."""
        investment_ids = self.company_investments.get(company_id, [])
        return [self.investments[iid] for iid in investment_ids]

    def get_total_funding(self, company_id: str) -> float:
        """Get total funding received by a company."""
        investments = self.get_company_investments(company_id)
        total: float = sum(inv.amount for inv in investments)
        return total

    def list_companies(
        self, stage: Optional[str] = None, min_capital: Optional[float] = None, seeking_investment: bool = False
    ) -> List[Company]:
        """
        List companies matching filters.

        Args:
            stage: Filter by company stage
            min_capital: Minimum capital threshold
            seeking_investment: Only companies seeking investment
        """
        results = list(self.companies.values())

        if stage:
            results = [c for c in results if c.stage == stage]

        if min_capital is not None:
            results = [c for c in results if c.capital >= min_capital]

        if seeking_investment:
            results = [c for c in results if c.stage == "seeking_investment"]

        return results

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_funding = sum(inv.amount for inv in self.investments.values())

        companies_by_stage: Dict[str, int] = {}
        for company in self.companies.values():
            companies_by_stage[company.stage] = companies_by_stage.get(company.stage, 0) + 1

        return {
            "total_companies": len(self.companies),
            "total_proposals": len(self.proposals),
            "total_investments": len(self.investments),
            "total_funding": total_funding,
            "companies_by_stage": companies_by_stage,
            "avg_funding_per_company": total_funding / len(self.companies) if self.companies else 0,
        }

    def get_company_summary(self, company_id: str) -> Dict[str, Any]:
        """Get comprehensive summary of a company."""
        company = self.get_company(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        proposals = self.get_company_proposals(company_id)
        investments = self.get_company_investments(company_id)
        total_funding = self.get_total_funding(company_id)

        return {
            "company": (
                company.to_dict()
                if hasattr(company, "to_dict")
                else {
                    "id": company.id,
                    "name": company.name,
                    "stage": company.stage,
                    "capital": company.capital,
                }
            ),
            "proposals": len(proposals),
            "investments": len(investments),
            "total_funding": total_funding,
            "team_size": len(company.get_all_sub_agent_ids()),
            "products": len(company.products),
        }

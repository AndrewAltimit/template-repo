"""Data models for investment system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class InvestorType(str, Enum):
    """Types of investors."""

    ANGEL = "angel"
    VENTURE_CAPITAL = "venture_capital"
    CORPORATE = "corporate"
    STRATEGIC = "strategic"


class InvestmentStage(str, Enum):
    """Investment stages."""

    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"


class ProposalStatus(str, Enum):
    """Status of investment proposals."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FUNDED = "funded"


@dataclass
class InvestmentCriteria:
    """Criteria for investment decisions."""

    min_market_size: float  # Minimum addressable market size
    min_revenue_projection: float  # Minimum year 1 revenue projection
    max_burn_rate: float  # Maximum acceptable monthly burn rate
    required_team_size: int  # Minimum team size
    preferred_stages: List[InvestmentStage]
    preferred_markets: List[str]
    risk_tolerance: float  # 0.0 to 1.0, higher = more risk tolerant
    min_roi_expectation: float  # Minimum expected ROI multiple


@dataclass
class InvestmentProposal:
    """Investment proposal from a company."""

    id: str
    company_id: str
    company_name: str
    amount_requested: float
    valuation: float
    equity_offered: float  # Percentage
    stage: InvestmentStage
    use_of_funds: Dict[str, float]  # Category -> amount
    revenue_projections: List[float]  # 3-year projections
    market_size: float
    team_size: int
    competitive_advantages: List[str]
    risks: List[str]
    milestones: List[Dict[str, Any]]
    status: ProposalStatus = ProposalStatus.DRAFT
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None


@dataclass
class InvestmentDecision:
    """Decision made by an investor on a proposal."""

    id: str
    investor_id: str
    proposal_id: str
    approved: bool
    amount_offered: float  # May differ from requested
    equity_requested: float  # May differ from offered
    reasoning: str
    evaluation_scores: Dict[str, float]  # Criteria -> score
    conditions: List[str]  # Investment conditions
    decided_at: datetime = field(default_factory=datetime.now)


@dataclass
class Investment:
    """Record of completed investment."""

    id: str
    investor_id: str
    company_id: str
    proposal_id: str
    decision_id: str
    amount: float
    equity: float
    valuation: float
    stage: InvestmentStage
    invested_at: datetime = field(default_factory=datetime.now)
    terms: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InvestorProfile:
    """Profile of an investor agent."""

    id: str
    name: str
    type: InvestorType
    available_capital: float
    total_invested: float
    portfolio_size: int  # Number of companies invested in
    criteria: InvestmentCriteria
    investment_history: List[str] = field(default_factory=list)  # Investment IDs
    decision_history: List[str] = field(default_factory=list)  # Decision IDs
    created_at: datetime = field(default_factory=datetime.now)

    def can_invest(self, amount: float) -> bool:
        """Check if investor has sufficient capital."""
        return self.available_capital >= amount

    def record_investment(self, investment_id: str, amount: float):
        """Record a new investment."""
        self.investment_history.append(investment_id)
        self.available_capital -= amount
        self.total_invested += amount
        self.portfolio_size += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "available_capital": self.available_capital,
            "total_invested": self.total_invested,
            "portfolio_size": self.portfolio_size,
            "investment_count": len(self.investment_history),
        }

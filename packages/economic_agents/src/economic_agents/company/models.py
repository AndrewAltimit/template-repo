"""Data models for companies, products, and business plans."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from economic_agents.exceptions import CompanyBankruptError, InvalidStageTransitionError, StageRegressionError


@dataclass
class Milestone:
    """Represents a business milestone."""

    title: str
    description: str
    target_date: str
    completed: bool = False


@dataclass
class RevenueStream:
    """Represents a source of revenue."""

    name: str
    description: str
    projected_annual: float


@dataclass
class CostStructure:
    """Represents cost breakdown."""

    compute_costs: float
    sub_agent_costs: float
    infrastructure_costs: float
    other_costs: float

    @property
    def total_annual(self) -> float:
        """Calculate total annual costs."""
        return self.compute_costs + self.sub_agent_costs + self.infrastructure_costs + self.other_costs


@dataclass
class BusinessPlan:
    """Comprehensive business plan."""

    # Executive Summary
    company_name: str
    mission: str
    vision: str
    one_liner: str

    # Problem & Solution
    problem_statement: str
    solution_description: str
    unique_value_proposition: str

    # Market
    target_market: str
    market_size: float
    competition_analysis: str
    competitive_advantages: List[str]

    # Product
    product_description: str
    features: List[str]
    development_roadmap: List[Milestone]

    # Business Model
    revenue_streams: List[RevenueStream]
    pricing_strategy: str
    cost_structure: CostStructure

    # Financial Projections
    funding_requested: float
    use_of_funds: dict
    revenue_projections: List[float]  # Year 1-3
    break_even_timeline: str

    # Team
    required_roles: List[str]

    # Milestones
    milestones: List[Milestone]


@dataclass
class ProductSpec:
    """Product specification."""

    name: str
    description: str
    category: str  # "api-service", "cli-tool", "library", "saas", "data-product"
    features: List[str]
    tech_stack: List[str]


@dataclass
class Product:
    """Represents a developed product."""

    spec: ProductSpec
    status: str  # "ideation", "development", "alpha", "beta", "released"
    completion_percentage: float
    code_artifacts: dict  # File paths to generated code
    documentation: str
    demo_url: str | None = None


@dataclass
class CompanyMetrics:
    """Tracks company performance metrics."""

    revenue: float = 0.0
    expenses: float = 0.0
    burn_rate_per_hour: float = 0.0
    tasks_completed: int = 0
    products_developed: int = 0
    sub_agents_created: int = 0

    @property
    def profit(self) -> float:
        """Calculate current profit."""
        return self.revenue - self.expenses

    @property
    def runway_hours(self) -> float:
        """Calculate hours until funds depleted."""
        if self.burn_rate_per_hour <= 0:
            return float("inf")
        available = self.revenue - self.expenses
        if available <= 0:
            return 0.0
        return available / self.burn_rate_per_hour


@dataclass
class Company:
    """Represents an agent-founded company."""

    id: str
    name: str
    mission: str
    created_at: datetime
    capital: float
    founder_agent_id: str

    # Organizational structure
    board_member_ids: List[str] = field(default_factory=list)
    executive_ids: List[str] = field(default_factory=list)
    employee_ids: List[str] = field(default_factory=list)

    # Business artifacts
    business_plan: BusinessPlan | None = None
    products: List[Product] = field(default_factory=list)

    # Status
    stage: str = "ideation"  # "ideation", "development", "seeking_investment", "operational"
    funding_status: str = "bootstrapped"  # "bootstrapped", "seeking_seed", "funded"

    # Investment tracking
    funding_rounds: List[str] = field(default_factory=list)  # Investment IDs
    total_funding_received: float = 0.0
    investor_ids: List[str] = field(default_factory=list)

    # Metrics
    metrics: CompanyMetrics = field(default_factory=CompanyMetrics)

    def get_all_sub_agent_ids(self) -> List[str]:
        """Get all sub-agent IDs in the company."""
        return self.board_member_ids + self.executive_ids + self.employee_ids

    def add_sub_agent(self, agent_id: str, role_type: str):
        """Add a sub-agent to the company.

        Args:
            agent_id: ID of the sub-agent
            role_type: Type of role ("board", "executive", "employee")
        """
        if role_type == "board":
            self.board_member_ids.append(agent_id)
        elif role_type == "executive":
            self.executive_ids.append(agent_id)
        elif role_type == "employee":
            self.employee_ids.append(agent_id)
        else:
            raise ValueError(f"Unknown role type: {role_type}")

        self.metrics.sub_agents_created += 1

    def record_investment(self, investment_id: str, investor_id: str, amount: float):
        """Record a received investment.

        Args:
            investment_id: ID of the investment
            investor_id: ID of the investor agent
            amount: Investment amount
        """
        self.funding_rounds.append(investment_id)
        self.total_funding_received += amount
        if investor_id not in self.investor_ids:
            self.investor_ids.append(investor_id)
        self.capital += amount

    def check_bankruptcy(self) -> bool:
        """Check if company has gone bankrupt.

        Returns:
            True if bankrupt

        Raises:
            CompanyBankruptError: If capital is negative
        """
        if self.capital < 0:
            raise CompanyBankruptError(company_name=self.name, deficit=abs(self.capital))
        return False

    def attempt_stage_progression(self, target_stage: str) -> bool:
        """Attempt to progress to a new stage with validation.

        Args:
            target_stage: Stage to progress to

        Returns:
            True if progression successful

        Raises:
            InvalidStageTransitionError: If transition is invalid
        """
        valid_transitions = {
            "ideation": ["development"],
            "development": ["seeking_investment", "operational"],
            "seeking_investment": ["operational", "development"],  # Can go back or forward
            "operational": [],  # Terminal stage for progression
        }

        if target_stage not in valid_transitions.get(self.stage, []):
            raise InvalidStageTransitionError(current_stage=self.stage, target_stage=target_stage)

        self.stage = target_stage
        return True

    def regress_stage(self, reason: str) -> str:
        """Regress company to previous stage due to failures.

        Args:
            reason: Reason for regression

        Returns:
            Previous stage name

        Raises:
            StageRegressionError: When regression occurs
        """
        regression_map = {
            "operational": "development",
            "seeking_investment": "development",
            "development": "ideation",
            "ideation": "ideation",  # Can't regress further
        }

        current_stage = self.stage
        previous_stage = regression_map.get(current_stage, current_stage)

        if previous_stage != current_stage:
            self.stage = previous_stage
            raise StageRegressionError(
                company_name=self.name, from_stage=current_stage, to_stage=previous_stage, reason=reason
            )

        return previous_stage

    def handle_failed_investment_round(self) -> None:
        """Handle the aftermath of a failed investment round.

        Updates company status and may trigger regression.
        """
        # Update funding status first
        if self.funding_status == "seeking_seed":
            self.funding_status = "bootstrapped"

        # Then trigger regression if in seeking_investment stage (will raise error)
        if self.stage == "seeking_investment":
            self.regress_stage("Failed to secure investment, returning to development")

    def spend_capital(self, amount: float, _description: str = "operation") -> float:
        """Spend capital and check for bankruptcy.

        Args:
            amount: Amount to spend
            _description: Description of expenditure

        Returns:
            Remaining capital

        Raises:
            CompanyBankruptError: If spending results in bankruptcy
        """
        self.capital -= amount
        self.metrics.expenses += amount

        # Check for bankruptcy after spending
        self.check_bankruptcy()

        return self.capital

    def to_dict(self) -> dict:
        """Convert company to dictionary for logging."""
        return {
            "id": self.id,
            "name": self.name,
            "mission": self.mission,
            "stage": self.stage,
            "funding_status": self.funding_status,
            "capital": self.capital,
            "board_members": len(self.board_member_ids),
            "executives": len(self.executive_ids),
            "employees": len(self.employee_ids),
            "products": len(self.products),
            "revenue": self.metrics.revenue,
            "expenses": self.metrics.expenses,
            "profit": self.metrics.profit,
        }

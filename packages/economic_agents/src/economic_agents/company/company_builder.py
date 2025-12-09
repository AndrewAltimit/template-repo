"""Company builder for autonomous company formation."""

from datetime import datetime
from typing import Dict
import uuid

from economic_agents.company.business_plan_generator import BusinessPlanGenerator
from economic_agents.company.models import Company, ProductSpec
from economic_agents.company.product_builder import ProductBuilder
from economic_agents.company.sub_agent_manager import SubAgentManager
from economic_agents.exceptions import CompanyBankruptError, InsufficientCapitalError
from economic_agents.monitoring.decision_logger import DecisionLogger

# Resource costs
HIRING_COSTS = {
    "board": 0.0,  # Advisory roles, equity-only compensation
    "executive": 5000.0,  # One-time recruiting/onboarding cost
    "employee": 2000.0,  # One-time recruiting/onboarding cost
}

MONTHLY_SALARIES = {
    "board": 0.0,  # Board members work for equity
    "executive": 15000.0,  # Executive monthly compensation
    "employee": 10000.0,  # Employee monthly compensation
}

# Product development costs
PRODUCT_DEVELOPMENT_COST = 10000.0  # Initial MVP development cost
MONTHLY_PRODUCT_COST = 2000.0  # Ongoing development/maintenance per product


class CompanyBuilder:
    """Handles company creation and management."""

    def __init__(self, config: dict | None = None, logger: DecisionLogger | None = None):
        """Initialize company builder.

        Args:
            config: Configuration for company building
            logger: Decision logger for transparency
        """
        self.config = config or {}
        self.logger = logger
        self.sub_agent_manager = SubAgentManager(config)
        self.business_plan_generator = BusinessPlanGenerator(config)
        self.product_builder = ProductBuilder(config)

    def create_company(
        self,
        founder_agent_id: str,
        opportunity: Dict[str, str],
        initial_capital: float,
    ) -> Company:
        """Create a company with initial structure.

        Args:
            founder_agent_id: ID of the founding agent
            opportunity: Market opportunity description
            initial_capital: Starting capital

        Returns:
            Newly created company
        """
        # Generate business plan
        business_plan = self.business_plan_generator.generate_plan(opportunity)

        # Create company
        company_id = str(uuid.uuid4())
        company = Company(
            id=company_id,
            name=business_plan.company_name,
            mission=business_plan.mission,
            created_at=datetime.now(),
            capital=initial_capital,
            founder_agent_id=founder_agent_id,
            business_plan=business_plan,
            stage="ideation",
            funding_status="bootstrapped",
        )

        # Create initial team
        team = self.sub_agent_manager.create_initial_team(company_id)

        # Add team members to company
        for board_member in team["board"]:
            company.add_sub_agent(board_member.id, "board")

        for executive in team["executives"]:
            company.add_sub_agent(executive.id, "executive")

        # Log company formation
        if self.logger:
            self.logger.log_decision(
                decision_type="company_formation",
                decision=f"Formed company: {company.name}",
                reasoning=f"Sufficient capital (${initial_capital:.2f}) and market opportunity identified",
                context={
                    "company_id": company.id,
                    "initial_team_size": len(company.get_all_sub_agent_ids()),
                    "business_plan": business_plan.company_name,
                },
                confidence=0.85,
            )

        return company

    def expand_team(self, company: Company, role: str, specialization: str) -> str:
        """Add a new sub-agent to the company.

        Args:
            company: Company to expand
            role: Role type ("board", "executive", "employee")
            specialization: Area of expertise

        Returns:
            ID of created sub-agent

        Raises:
            InsufficientCapitalError: If company cannot afford hiring cost
        """
        # Determine agent role type
        if role == "board":
            agent_role = "board_member"
            role_type = "board"
        elif role == "executive":
            agent_role = "executive"
            role_type = "executive"
        else:
            agent_role = "ic"  # Default to individual contributor
            role_type = "employee"

        # Check if can afford hiring cost
        hiring_cost = HIRING_COSTS.get(role_type, 2000.0)
        if company.capital < hiring_cost:
            raise InsufficientCapitalError(
                required=hiring_cost,
                available=company.capital,
                operation=f"hiring {role_type} ({specialization})",
            )

        # Deduct hiring cost
        company.capital -= hiring_cost
        company.metrics.expenses += hiring_cost

        # Create sub-agent
        agent = self.sub_agent_manager.create_sub_agent(
            role=agent_role,
            specialization=specialization,
            company_id=company.id,
            role_title=specialization if agent_role == "executive" else None,
        )

        # Add to company
        agent_id: str = agent.id
        company.add_sub_agent(agent_id, role_type)

        # Log decision
        if self.logger:
            self.logger.log_decision(
                decision_type="hire_sub_agent",
                decision=f"Hired {role}: {specialization}",
                reasoning=f"Company growth requires {specialization} expertise",
                context={"company_id": company.id, "agent_id": agent_id, "role": role},
                confidence=0.8,
            )

        return agent_id

    def develop_product(self, company: Company, product_type: str) -> None:
        """Develop a product for the company.

        Args:
            company: Company to develop product for
            product_type: Type of product to develop

        Raises:
            InsufficientCapitalError: If company cannot afford development cost
        """
        # Check if can afford product development
        if company.capital < PRODUCT_DEVELOPMENT_COST:
            raise InsufficientCapitalError(
                required=PRODUCT_DEVELOPMENT_COST,
                available=company.capital,
                operation=f"developing {product_type} product",
            )

        # Deduct development cost
        company.capital -= PRODUCT_DEVELOPMENT_COST
        company.metrics.expenses += PRODUCT_DEVELOPMENT_COST

        # Create product spec from business plan
        spec = ProductSpec(
            name=company.business_plan.product_description if company.business_plan else "Product",
            description=company.business_plan.solution_description if company.business_plan else "Solution",
            category=product_type,
            features=company.business_plan.features if company.business_plan else [],
            tech_stack=["Python", "FastAPI", "PostgreSQL"],  # Default stack
        )

        # Build MVP
        product = self.product_builder.build_mvp(spec)

        # Add to company
        company.products.append(product)
        company.metrics.products_developed += 1
        company.stage = "development"

        # Log decision
        if self.logger:
            self.logger.log_decision(
                decision_type="product_development",
                decision=f"Developed {product_type} MVP for ${PRODUCT_DEVELOPMENT_COST:,.0f}",
                reasoning="Product development aligned with business plan",
                context={
                    "company_id": company.id,
                    "product_name": spec.name,
                    "completion": product.completion_percentage,
                    "cost": PRODUCT_DEVELOPMENT_COST,
                },
                confidence=0.75,
            )

    def advance_company_stage(self, company: Company) -> None:
        """Advance company to next stage.

        Args:
            company: Company to advance
        """
        stage_progression = {
            "ideation": "development",
            "development": "seeking_investment",
            "seeking_investment": "operational",
        }

        old_stage = company.stage
        company.stage = stage_progression.get(old_stage, company.stage)

        if self.logger and company.stage != old_stage:
            self.logger.log_decision(
                decision_type="stage_advancement",
                decision=f"Advanced from {old_stage} to {company.stage}",
                reasoning=f"Completed {old_stage} milestones",
                context={"company_id": company.id, "new_stage": company.stage},
                confidence=0.8,
            )

    def calculate_monthly_burn_rate(self, company: Company) -> float:
        """Calculate company's monthly burn rate.

        Args:
            company: Company to calculate burn rate for

        Returns:
            Monthly burn rate (expenses per month)
        """
        monthly_burn = 0.0

        # Count team members by role
        board_count = len(company.board_member_ids)
        executive_count = len(company.executive_ids)
        employee_count = len(company.employee_ids)

        # Add salaries
        monthly_burn += board_count * MONTHLY_SALARIES["board"]
        monthly_burn += executive_count * MONTHLY_SALARIES["executive"]
        monthly_burn += employee_count * MONTHLY_SALARIES["employee"]

        # Add product maintenance costs
        monthly_burn += len(company.products) * MONTHLY_PRODUCT_COST

        return monthly_burn

    def simulate_monthly_operations(self, company: Company) -> Dict:
        """Simulate one month of company operations.

        Args:
            company: Company to simulate operations for

        Returns:
            Dict with operation results

        Raises:
            CompanyBankruptError: If company runs out of capital
        """
        burn_rate = self.calculate_monthly_burn_rate(company)

        # Check if company can afford operations
        if company.capital < burn_rate:
            deficit = burn_rate - company.capital
            raise CompanyBankruptError(
                company_name=company.name,
                deficit=deficit,
            )

        # Deduct monthly costs
        company.capital -= burn_rate
        company.metrics.expenses += burn_rate

        # Update metrics
        company.metrics.months_active = company.metrics.months_active + 1 if hasattr(company.metrics, "months_active") else 1

        # Log decision
        if self.logger:
            month_num = company.metrics.months_active if hasattr(company.metrics, "months_active") else 1
            self.logger.log_decision(
                decision_type="monthly_operations",
                decision=f"Completed month {month_num} operations",
                reasoning=f"Monthly burn rate: ${burn_rate:,.2f}",
                context={
                    "company_id": company.id,
                    "burn_rate": burn_rate,
                    "remaining_capital": company.capital,
                    "runway_months": company.capital / burn_rate if burn_rate > 0 else float("inf"),
                    "team_size": len(company.get_all_sub_agent_ids()),
                    "products": len(company.products),
                },
                confidence=0.95,
            )

        return {
            "success": True,
            "burn_rate": burn_rate,
            "remaining_capital": company.capital,
            "runway_months": company.capital / burn_rate if burn_rate > 0 else float("inf"),
        }

    def get_company_status(self, company: Company) -> Dict:
        """Get comprehensive company status.

        Args:
            company: Company to query

        Returns:
            Status dictionary
        """
        burn_rate = self.calculate_monthly_burn_rate(company)

        return {
            "company": company.to_dict(),
            "team": self.sub_agent_manager.get_team_summary(),
            "products": [
                {
                    "name": p.spec.name,
                    "status": p.status,
                    "completion": p.completion_percentage,
                }
                for p in company.products
            ],
            "financials": {
                "capital": company.capital,
                "monthly_burn_rate": burn_rate,
                "runway_months": company.capital / burn_rate if burn_rate > 0 else float("inf"),
                "total_expenses": company.metrics.expenses,
            },
        }

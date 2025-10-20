"""Company builder for autonomous company formation."""

import uuid
from datetime import datetime
from typing import Dict

from economic_agents.company.business_plan_generator import BusinessPlanGenerator
from economic_agents.company.models import Company, ProductSpec
from economic_agents.company.product_builder import ProductBuilder
from economic_agents.company.sub_agent_manager import SubAgentManager
from economic_agents.monitoring.decision_logger import DecisionLogger


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
        """
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
                decision=f"Developed {product_type} MVP",
                reasoning="Product development aligned with business plan",
                context={
                    "company_id": company.id,
                    "product_name": spec.name,
                    "completion": product.completion_percentage,
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

    def get_company_status(self, company: Company) -> Dict:
        """Get comprehensive company status.

        Args:
            company: Company to query

        Returns:
            Status dictionary
        """
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
        }

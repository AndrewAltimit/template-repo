"""Business plan generator for autonomous company formation."""

from typing import Dict

from economic_agents.company.models import (
    BusinessPlan,
    CostStructure,
    Milestone,
    RevenueStream,
)


class BusinessPlanGenerator:
    """Generates comprehensive business plans for agent-founded companies."""

    def __init__(self, config: dict | None = None):
        """Initialize business plan generator.

        Args:
            config: Configuration for business plan generation
        """
        self.config = config or {}

    def generate_plan(self, opportunity: Dict[str, str]) -> BusinessPlan:
        """Generate a business plan based on market opportunity.

        Args:
            opportunity: Market opportunity description

        Returns:
            Complete business plan
        """
        product_type = opportunity.get("product_type", "api-service")
        target_market = opportunity.get("target_market", "developers")

        # Generate plan based on product type
        if product_type == "api-service":
            return self._generate_api_service_plan(target_market)
        if product_type == "cli-tool":
            return self._generate_cli_tool_plan(target_market)
        if product_type == "saas":
            return self._generate_saas_plan(target_market)
        return self._generate_generic_plan(product_type, target_market)

    def _generate_api_service_plan(self, target_market: str) -> BusinessPlan:
        """Generate plan for API service."""
        return BusinessPlan(
            company_name="DataFlow API",
            mission="Provide reliable and scalable data processing APIs",
            vision="Become the go-to API service for data transformation",
            one_liner="Fast, reliable data processing APIs for modern applications",
            problem_statement="Developers waste time building and maintaining data processing infrastructure",
            solution_description="Managed API service handling data transformation, validation, and enrichment",
            unique_value_proposition="99.9% uptime, sub-100ms latency, pay-per-use pricing",
            target_market=target_market,
            market_size=5000000.0,
            competition_analysis="Competes with AWS Lambda, Azure Functions, but specialized for data",
            competitive_advantages=[
                "Specialized data processing algorithms",
                "Superior latency",
                "Transparent pricing",
                "Developer-friendly API",
            ],
            product_description="REST API for data transformation with JSON/CSV support",
            features=[
                "Data validation",
                "Format conversion",
                "Schema transformation",
                "Batch processing",
                "Real-time webhooks",
            ],
            development_roadmap=[
                Milestone("MVP Launch", "Core API with basic transformations", "Month 1", False),
                Milestone("Beta Release", "Add advanced features", "Month 2", False),
                Milestone("Production", "Full feature set with SLA", "Month 3", False),
            ],
            revenue_streams=[
                RevenueStream("API Usage", "Pay-per-request model", 50000.0),
                RevenueStream("Enterprise Plans", "Fixed monthly subscriptions", 30000.0),
            ],
            pricing_strategy="Freemium with usage-based pricing",
            cost_structure=CostStructure(
                compute_costs=15000.0,
                sub_agent_costs=20000.0,
                infrastructure_costs=10000.0,
                other_costs=5000.0,
            ),
            funding_requested=100000.0,
            use_of_funds={
                "product_development": 40000.0,
                "infrastructure": 30000.0,
                "marketing": 20000.0,
                "operations": 10000.0,
            },
            revenue_projections=[80000.0, 250000.0, 500000.0],
            break_even_timeline="Month 9",
            required_roles=["CTO", "Backend Engineer", "DevOps Engineer"],
            milestones=[
                Milestone("MVP Complete", "Core functionality ready", "Month 1", False),
                Milestone("First 100 Users", "Achieve 100 active users", "Month 3", False),
                Milestone("Break Even", "Achieve profitability", "Month 9", False),
            ],
        )

    def _generate_cli_tool_plan(self, target_market: str) -> BusinessPlan:
        """Generate plan for CLI tool."""
        return BusinessPlan(
            company_name="DevTools CLI",
            mission="Simplify developer workflows with powerful CLI tools",
            vision="The essential CLI toolkit for modern developers",
            one_liner="CLI tools that make developers 10x more productive",
            problem_statement="Developers repeat manual tasks that could be automated",
            solution_description="Suite of CLI tools for common development workflows",
            unique_value_proposition="Open source core with enterprise features",
            target_market=target_market,
            market_size=2000000.0,
            competition_analysis="Competes with existing CLI tools but more integrated",
            competitive_advantages=[
                "Unified interface",
                "Cross-platform support",
                "Plugin ecosystem",
                "Active community",
            ],
            product_description="CLI tool suite for development automation",
            features=[
                "Project scaffolding",
                "Code generation",
                "Deployment automation",
                "Testing utilities",
                "Performance profiling",
            ],
            development_roadmap=[
                Milestone("Alpha Release", "Core tools available", "Month 1", False),
                Milestone("Plugin System", "Enable community plugins", "Month 2", False),
                Milestone("Enterprise Edition", "Enterprise features", "Month 4", False),
            ],
            revenue_streams=[
                RevenueStream("Enterprise Licenses", "Team and enterprise pricing", 60000.0),
                RevenueStream("Support Contracts", "Priority support", 20000.0),
            ],
            pricing_strategy="Open core with paid enterprise features",
            cost_structure=CostStructure(
                compute_costs=5000.0,
                sub_agent_costs=25000.0,
                infrastructure_costs=5000.0,
                other_costs=5000.0,
            ),
            funding_requested=75000.0,
            use_of_funds={
                "product_development": 35000.0,
                "community_building": 20000.0,
                "marketing": 15000.0,
                "operations": 5000.0,
            },
            revenue_projections=[40000.0, 120000.0, 250000.0],
            break_even_timeline="Month 12",
            required_roles=["CTO", "Software Engineer", "Community Manager"],
            milestones=[
                Milestone("Open Source Launch", "Release core as open source", "Month 1", False),
                Milestone("1000 Stars", "Achieve GitHub popularity", "Month 4", False),
                Milestone("Enterprise Deals", "Sign first enterprise customers", "Month 8", False),
            ],
        )

    def _generate_saas_plan(self, target_market: str) -> BusinessPlan:
        """Generate plan for SaaS product."""
        return BusinessPlan(
            company_name="TeamFlow",
            mission="Streamline team collaboration and productivity",
            vision="The productivity platform teams love",
            one_liner="Team collaboration made simple",
            problem_statement="Teams struggle with fragmented tools and inefficient workflows",
            solution_description="Unified platform for team communication, project management, and automation",
            unique_value_proposition="All-in-one platform with AI-powered automation",
            target_market=target_market,
            market_size=10000000.0,
            competition_analysis="Competes with Slack, Asana but more integrated",
            competitive_advantages=[
                "Unified platform",
                "AI automation",
                "Superior UX",
                "Competitive pricing",
            ],
            product_description="SaaS platform for team productivity",
            features=[
                "Team chat",
                "Project management",
                "Task automation",
                "File sharing",
                "Analytics dashboard",
            ],
            development_roadmap=[
                Milestone("Private Beta", "Core features with select users", "Month 2", False),
                Milestone("Public Launch", "General availability", "Month 4", False),
                Milestone("Mobile Apps", "iOS and Android apps", "Month 6", False),
            ],
            revenue_streams=[
                RevenueStream("Subscriptions", "Monthly recurring revenue", 100000.0),
                RevenueStream("Enterprise Plans", "Custom enterprise pricing", 50000.0),
            ],
            pricing_strategy="Subscription tiers: Free, Pro, Enterprise",
            cost_structure=CostStructure(
                compute_costs=20000.0,
                sub_agent_costs=40000.0,
                infrastructure_costs=15000.0,
                other_costs=10000.0,
            ),
            funding_requested=150000.0,
            use_of_funds={
                "product_development": 60000.0,
                "infrastructure": 30000.0,
                "marketing": 40000.0,
                "operations": 20000.0,
            },
            revenue_projections=[150000.0, 500000.0, 1200000.0],
            break_even_timeline="Month 15",
            required_roles=["CEO", "CTO", "Product Manager", "Engineers", "Marketing"],
            milestones=[
                Milestone("Beta Launch", "Private beta with 100 teams", "Month 2", False),
                Milestone("Product-Market Fit", "Strong retention metrics", "Month 8", False),
                Milestone("Profitability", "Achieve positive cash flow", "Month 15", False),
            ],
        )

    def _generate_generic_plan(self, product_type: str, target_market: str) -> BusinessPlan:
        """Generate generic business plan."""
        return BusinessPlan(
            company_name=f"{product_type.title()} Co",
            mission=f"Deliver exceptional {product_type} solutions",
            vision=f"Lead the {product_type} market",
            one_liner=f"Innovative {product_type} for {target_market}",
            problem_statement=f"{target_market} need better {product_type} solutions",
            solution_description=f"Modern {product_type} with superior features",
            unique_value_proposition="Best-in-class quality and support",
            target_market=target_market,
            market_size=3000000.0,
            competition_analysis="Competitive landscape analysis pending",
            competitive_advantages=[
                "Innovation",
                "Quality",
                "Customer focus",
            ],
            product_description=f"{product_type} solution",
            features=[
                "Core functionality",
                "Advanced features",
                "Integrations",
            ],
            development_roadmap=[
                Milestone("MVP", "Minimum viable product", "Month 2", False),
                Milestone("Launch", "Product launch", "Month 4", False),
            ],
            revenue_streams=[
                RevenueStream("Sales", "Direct sales", 70000.0),
            ],
            pricing_strategy="Value-based pricing",
            cost_structure=CostStructure(
                compute_costs=10000.0,
                sub_agent_costs=30000.0,
                infrastructure_costs=10000.0,
                other_costs=5000.0,
            ),
            funding_requested=100000.0,
            use_of_funds={
                "product_development": 50000.0,
                "marketing": 30000.0,
                "operations": 20000.0,
            },
            revenue_projections=[70000.0, 200000.0, 400000.0],
            break_even_timeline="Month 12",
            required_roles=["CTO", "Engineer"],
            milestones=[
                Milestone("MVP", "Launch MVP", "Month 2", False),
                Milestone("Growth", "Achieve growth targets", "Month 8", False),
            ],
        )

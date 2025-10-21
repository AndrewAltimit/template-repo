"""Executive sub-agent for strategic execution."""

from typing import Any, Dict, List

from economic_agents.sub_agents.base_agent import SubAgent


class Executive(SubAgent):
    """Executive responsible for department leadership and strategy execution."""

    def __init__(self, agent_id: str, role_title: str, specialization: str):
        """Initialize executive.

        Args:
            agent_id: Unique identifier
            role_title: Executive title (e.g., "CEO", "CTO", "CFO")
            specialization: Area of expertise
        """
        super().__init__(
            id=agent_id,
            role="executive",
            specialization=specialization,
        )
        self.role_title = role_title

    def create_okrs(self, timeframe: str = "quarterly") -> Dict[str, Any]:
        """Create OKRs (Objectives and Key Results) based on role.

        Args:
            timeframe: OKR timeframe (quarterly, annual)

        Returns:
            Dict containing objectives and key results
        """
        if self.role_title == "CEO":
            return {
                "objective": "Scale company to product-market fit and profitability",
                "key_results": [
                    {"metric": "Monthly Active Users", "current": 0, "target": 10000, "unit": "users"},
                    {"metric": "Monthly Recurring Revenue", "current": 0, "target": 50000, "unit": "$"},
                    {"metric": "Customer Acquisition Cost", "current": 150, "target": 50, "unit": "$"},
                    {"metric": "Net Promoter Score", "current": 0, "target": 40, "unit": "points"},
                ],
                "timeframe": timeframe,
            }
        elif self.role_title == "CTO":
            return {
                "objective": "Build scalable, reliable technical infrastructure",
                "key_results": [
                    {"metric": "System Uptime", "current": 95.0, "target": 99.9, "unit": "%"},
                    {"metric": "API Response Time", "current": 500, "target": 100, "unit": "ms"},
                    {"metric": "Code Test Coverage", "current": 60, "target": 90, "unit": "%"},
                    {"metric": "Deployment Frequency", "current": 2, "target": 20, "unit": "per_month"},
                ],
                "timeframe": timeframe,
            }
        elif self.role_title == "CFO":
            return {
                "objective": "Optimize financial health and extend runway",
                "key_results": [
                    {"metric": "Burn Multiple", "current": 3.0, "target": 1.5, "unit": "ratio"},
                    {"metric": "Gross Margin", "current": 40, "target": 70, "unit": "%"},
                    {"metric": "Cash Runway", "current": 12, "target": 18, "unit": "months"},
                    {"metric": "CAC Payback Period", "current": 12, "target": 6, "unit": "months"},
                ],
                "timeframe": timeframe,
            }
        else:
            return {
                "objective": f"{self.role_title} departmental goals",
                "key_results": [
                    {"metric": "Team Productivity", "current": 70, "target": 90, "unit": "%"},
                    {"metric": "Project Completion Rate", "current": 60, "target": 85, "unit": "%"},
                ],
                "timeframe": timeframe,
            }

    def allocate_resources(self, budget: float, team_size: int, priorities: List[str]) -> Dict[str, Any]:
        """Create resource allocation plan based on priorities.

        Args:
            budget: Available budget
            team_size: Number of team members available
            priorities: List of priority areas

        Returns:
            Resource allocation breakdown
        """
        # Default allocation percentages by role
        if self.role_title == "CEO":
            allocation_template = {
                "product": 0.40,
                "marketing": 0.25,
                "sales": 0.20,
                "operations": 0.15,
            }
        elif self.role_title == "CTO":
            allocation_template = {
                "product_development": 0.50,
                "infrastructure": 0.25,
                "security": 0.15,
                "technical_debt": 0.10,
            }
        elif self.role_title == "CFO":
            allocation_template = {
                "personnel": 0.60,
                "infrastructure": 0.20,
                "marketing": 0.15,
                "reserve": 0.05,
            }
        else:
            allocation_template = {
                "core_operations": 0.70,
                "growth_initiatives": 0.20,
                "reserve": 0.10,
            }

        # Adjust based on priorities
        allocation = {}
        for area, percentage in allocation_template.items():
            # Boost priority areas by 20%
            if area in priorities:
                percentage *= 1.2

            allocation[area] = {
                "budget": round(budget * percentage, 2),
                "team_allocation": round(team_size * percentage, 1),
                "percentage": round(percentage * 100, 1),
            }

        # Normalize to 100%
        total_pct = sum(a["percentage"] for a in allocation.values())
        for area in allocation:
            allocation[area]["percentage"] = round(allocation[area]["percentage"] / total_pct * 100, 1)

        return {
            "total_budget": budget,
            "total_team": team_size,
            "allocation": allocation,
            "priorities": priorities,
        }

    def create_strategic_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive strategic plan with concrete actions.

        Args:
            context: Planning context (budget, team, goals)

        Returns:
            Strategic plan with milestones and metrics
        """
        budget = context.get("budget", 100000)
        team_size = context.get("team_size", 5)
        timeline_weeks = context.get("timeline_weeks", 12)

        okrs = self.create_okrs()
        resources = self.allocate_resources(budget, team_size, context.get("priorities", []))

        # Create concrete milestones
        milestones = []
        weeks_per_milestone = timeline_weeks // 4

        for i in range(4):
            week_num = (i + 1) * weeks_per_milestone
            milestone = {
                "week": week_num,
                "phase": ["Planning", "Execution", "Optimization", "Scaling"][i],
                "deliverables": self._get_phase_deliverables(i),
                "success_criteria": self._get_success_criteria(i, okrs),
            }
            milestones.append(milestone)

        return {
            "executive": self.role_title,
            "objectives": okrs,
            "resource_allocation": resources,
            "milestones": milestones,
            "timeline_weeks": timeline_weeks,
            "risk_mitigation": self._create_risk_mitigation_plan(),
        }

    def _get_phase_deliverables(self, phase_index: int) -> List[str]:
        """Get deliverables for a specific phase."""
        if self.role_title == "CEO":
            deliverables_by_phase = [
                ["Company vision doc", "OKRs defined", "Team hired", "Budget allocated"],
                ["Product launched", "First customers", "Metrics dashboard", "Feedback loop"],
                ["Revenue growing", "Processes refined", "Team scaled", "Partnerships established"],
                ["Market leader", "Profitable unit economics", "Expansion ready", "Exit strategy"],
            ]
        elif self.role_title == "CTO":
            deliverables_by_phase = [
                ["Architecture designed", "Tech stack chosen", "Dev environment", "CI/CD pipeline"],
                ["MVP deployed", "APIs functional", "Database optimized", "Security audit"],
                ["Performance tuned", "Monitoring live", "Auto-scaling", "Documentation complete"],
                ["99.9% uptime", "API <100ms", "Load tested", "Multi-region"],
            ]
        elif self.role_title == "CFO":
            deliverables_by_phase = [
                ["Financial model", "Budget approved", "Accounting setup", "Banking established"],
                ["Burn tracking", "Revenue recognized", "Expense managed", "Reports automated"],
                ["Margins improved", "Runway extended", "Investors updated", "Forecasts refined"],
                ["Profitability", "Fundraise ready", "Audit prepared", "IPO foundation"],
            ]
        else:
            deliverables_by_phase = [
                ["Team onboarded", "Goals set", "Processes defined"],
                ["Executing plan", "Hitting KPIs", "Iterating"],
                ["Optimized ops", "Scaled team", "Refined process"],
                ["Excellence achieved", "Sustained performance"],
            ]

        return deliverables_by_phase[min(phase_index, len(deliverables_by_phase) - 1)]

    def _get_success_criteria(self, phase_index: int, okrs: Dict[str, Any]) -> List[str]:
        """Get success criteria for a phase based on OKRs."""
        key_results = okrs["key_results"]
        criteria = []

        for kr in key_results[:2]:  # Use first 2 KRs
            progress_percentage = (phase_index + 1) * 25  # 25%, 50%, 75%, 100%
            target_value = kr["current"] + (kr["target"] - kr["current"]) * (progress_percentage / 100)

            criteria.append(f"{kr['metric']}: {round(target_value, 1)}{kr.get('unit', '')}")

        return criteria

    def _create_risk_mitigation_plan(self) -> List[Dict[str, str]]:
        """Create role-specific risk mitigation strategies."""
        if self.role_title == "CEO":
            return [
                {"risk": "Market changes", "mitigation": "Monthly market analysis & pivot readiness"},
                {"risk": "Team attrition", "mitigation": "Strong culture, equity, growth opportunities"},
                {"risk": "Funding gap", "mitigation": "18mo runway target, investor relationships"},
            ]
        elif self.role_title == "CTO":
            return [
                {"risk": "Technical debt", "mitigation": "20% time for refactoring & debt paydown"},
                {"risk": "Scalability issues", "mitigation": "Load testing, monitoring, auto-scaling"},
                {"risk": "Security breach", "mitigation": "Regular audits, pen testing, bug bounty"},
            ]
        elif self.role_title == "CFO":
            return [
                {"risk": "Cash shortage", "mitigation": "Weekly burn monitoring, 3mo early warning"},
                {"risk": "Revenue miss", "mitigation": "Conservative forecasting, multiple revenue streams"},
                {"risk": "Cost overrun", "mitigation": "Budget caps, approval workflows, alerts"},
            ]
        else:
            return [
                {"risk": "Execution delays", "mitigation": "Buffer time, dependency tracking"},
                {"risk": "Resource constraints", "mitigation": "Prioritization, outsourcing options"},
            ]

    def execute_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a strategic initiative with detailed planning.

        Args:
            strategy: Strategy to execute

        Returns:
            Execution plan with milestones
        """
        self.tasks_completed += 1

        strategy_type = strategy.get("type", "general")

        # Create comprehensive plan
        plan = self.create_strategic_plan(
            {
                "budget": strategy.get("budget", 100000),
                "team_size": strategy.get("team_size", 5),
                "timeline_weeks": strategy.get("timeline_weeks", 12),
                "priorities": strategy.get("priorities", []),
            }
        )

        return {
            "status": "planned",
            "strategy_type": strategy_type,
            "strategic_plan": plan,
            "next_actions": plan["milestones"][0]["deliverables"][:3],
            "estimated_completion": f"{plan['timeline_weeks']} weeks",
        }

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make operational decision with concrete reasoning.

        Args:
            context: Decision context

        Returns:
            Operational decision
        """
        self.decisions_made += 1

        current_metrics = context.get("metrics", {})

        if self.role_title == "CEO":
            # Data-driven decision based on growth metrics
            user_growth = current_metrics.get("user_growth_rate", 0)
            revenue_growth = current_metrics.get("revenue_growth_rate", 0)

            if revenue_growth > 15:  # >15% monthly growth
                decision = "scale_operations"
                reasoning = f"Strong revenue growth ({revenue_growth}%), invest in scaling"
            elif user_growth > 20:  # >20% user growth but weak revenue
                decision = "optimize_monetization"
                reasoning = f"High user growth ({user_growth}%) but need to improve monetization"
            else:
                decision = "improve_product_market_fit"
                reasoning = "Focus on product-market fit before scaling"

            return {
                "decision": decision,
                "reasoning": reasoning,
                "confidence": 0.85,
                "action_items": self._get_ceo_actions(decision),
            }

        elif self.role_title == "CTO":
            # Technical decision based on system metrics
            uptime = current_metrics.get("uptime", 99.0)
            response_time = current_metrics.get("avg_response_ms", 200)

            if uptime < 99.5 or response_time > 300:
                decision = "prioritize_reliability"
                reasoning = f"System metrics below target (uptime: {uptime}%, response: {response_time}ms)"
            else:
                decision = "build_new_features"
                reasoning = "System stable, ready for feature development"

            return {
                "decision": decision,
                "reasoning": reasoning,
                "confidence": 0.9,
                "action_items": self._get_cto_actions(decision),
            }

        elif self.role_title == "CFO":
            # Financial decision based on burn and runway
            runway_months = current_metrics.get("runway_months", 12)
            burn_multiple = current_metrics.get("burn_multiple", 2.0)

            if runway_months < 9:
                decision = "emergency_fundraise"
                reasoning = f"Critical runway ({runway_months} months), must raise capital"
            elif burn_multiple > 3.0:
                decision = "reduce_burn"
                reasoning = f"High burn multiple ({burn_multiple}x), optimize costs"
            else:
                decision = "maintain_trajectory"
                reasoning = "Financial health good, continue current strategy"

            return {
                "decision": decision,
                "reasoning": reasoning,
                "confidence": 0.85,
                "action_items": self._get_cfo_actions(decision),
            }

        else:
            return {
                "decision": "execute_departmental_plan",
                "reasoning": f"{self.role_title} executing according to strategic plan",
                "confidence": 0.75,
            }

    def _get_ceo_actions(self, decision: str) -> List[str]:
        """Get CEO action items based on decision."""
        actions = {
            "scale_operations": [
                "Hire 3-5 key roles",
                "Expand marketing budget by 2x",
                "Open new market segments",
            ],
            "optimize_monetization": [
                "A/B test pricing models",
                "Launch premium tier",
                "Improve onboarding conversion",
            ],
            "improve_product_market_fit": [
                "Conduct 20 customer interviews",
                "Analyze churn reasons",
                "Iterate on core value prop",
            ],
        }
        return actions.get(decision, ["Execute strategic plan"])

    def _get_cto_actions(self, decision: str) -> List[str]:
        """Get CTO action items based on decision."""
        actions = {
            "prioritize_reliability": [
                "Implement auto-scaling",
                "Add comprehensive monitoring",
                "Run load tests & fix bottlenecks",
            ],
            "build_new_features": [
                "Prioritize feature roadmap",
                "Allocate engineering resources",
                "Set up feature flags for testing",
            ],
        }
        return actions.get(decision, ["Continue technical execution"])

    def _get_cfo_actions(self, decision: str) -> List[str]:
        """Get CFO action items based on decision."""
        actions = {
            "emergency_fundraise": [
                "Prepare investor deck",
                "Reach out to 20 investors",
                "Negotiate bridge financing",
            ],
            "reduce_burn": [
                "Audit all expenses",
                "Renegotiate vendor contracts",
                "Optimize team structure",
            ],
            "maintain_trajectory": [
                "Continue monthly reporting",
                "Monitor key metrics",
                "Prepare for next funding round",
            ],
        }
        return actions.get(decision, ["Continue financial management"])

    def to_dict(self) -> Dict[str, Any]:
        """Convert executive to dictionary."""
        result: Dict[str, Any] = super().to_dict()
        result["role_title"] = self.role_title
        return result

"""Board member sub-agent for governance decisions."""

from typing import Any, Dict

from economic_agents.sub_agents.base_agent import SubAgent


class BoardMember(SubAgent):
    """Board member responsible for strategic oversight and governance."""

    def __init__(self, agent_id: str, specialization: str = "governance"):
        """Initialize board member.

        Args:
            agent_id: Unique identifier
            specialization: Area of expertise (e.g., "governance", "finance", "operations")
        """
        super().__init__(
            id=agent_id,
            role="board_member",
            specialization=specialization,
        )

    def calculate_roi(self, investment: float, annual_return: float, years: int = 3) -> Dict[str, Any]:
        """Calculate return on investment with detailed analysis.

        Args:
            investment: Initial investment amount
            annual_return: Expected annual return
            years: Time horizon for ROI calculation

        Returns:
            Dict containing ROI metrics
        """
        total_return = annual_return * years
        roi_percentage = ((total_return - investment) / investment) * 100
        payback_period = investment / annual_return if annual_return > 0 else float("inf")

        # Calculate NPV with 10% discount rate
        discount_rate = 0.10
        npv = -investment
        for year in range(1, years + 1):
            npv += annual_return / ((1 + discount_rate) ** year)

        return {
            "roi_percentage": round(roi_percentage, 2),
            "total_return": round(total_return, 2),
            "payback_period_years": round(payback_period, 2),
            "npv": round(npv, 2),
            "break_even": npv > 0,
            "annualized_roi": round(roi_percentage / years, 2),
        }

    def analyze_cash_flow(self, monthly_revenue: float, monthly_expenses: float, current_capital: float) -> Dict[str, Any]:
        """Analyze company cash flow and runway.

        Args:
            monthly_revenue: Monthly revenue
            monthly_expenses: Monthly expenses
            current_capital: Current capital available

        Returns:
            Dict containing cash flow analysis
        """
        monthly_burn = monthly_expenses - monthly_revenue
        runway_months = current_capital / monthly_burn if monthly_burn > 0 else float("inf")

        cash_flow_positive = monthly_revenue >= monthly_expenses

        # Projected capital in 6 months
        projected_6mo = current_capital + (monthly_revenue - monthly_expenses) * 6

        return {
            "monthly_burn_rate": round(monthly_burn, 2),
            "monthly_profit": round(monthly_revenue - monthly_expenses, 2),
            "runway_months": round(runway_months, 2),
            "cash_flow_positive": cash_flow_positive,
            "projected_capital_6mo": round(projected_6mo, 2),
            "urgent_funding_needed": runway_months < 6 if monthly_burn > 0 else False,
        }

    def assess_risk(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform quantitative risk assessment.

        Args:
            context: Context containing risk factors

        Returns:
            Risk assessment with quantitative metrics
        """
        # Extract risk factors
        market_risk = context.get("market_volatility", 0.5)  # 0-1 scale
        execution_risk = context.get("team_experience", 0.7)  # 0-1 scale (higher is better)
        financial_risk = context.get("burn_multiple", 1.0)  # Burn / Revenue

        # Calculate composite risk score (0-100, higher is more risk)
        market_weight = 0.3
        execution_weight = 0.4
        financial_weight = 0.3

        risk_score = (
            market_risk * market_weight * 100
            + (1 - execution_risk) * execution_weight * 100  # Invert execution risk
            + min(financial_risk / 3, 1.0) * financial_weight * 100
        )

        if risk_score < 30:
            risk_level = "low"
            recommendation = "approve"
        elif risk_score < 60:
            risk_level = "medium"
            recommendation = "approve_with_conditions"
        else:
            risk_level = "high"
            recommendation = "defer_or_reject"

        return {
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "recommendation": recommendation,
            "factors": {
                "market_risk": round(market_risk, 2),
                "execution_risk": round(1 - execution_risk, 2),
                "financial_risk": round(min(financial_risk / 3, 1.0), 2),
            },
        }

    def review_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Review and approve/reject a major company decision.

        Args:
            decision: Decision to review

        Returns:
            Approval result with feedback
        """
        self.decisions_made += 1

        decision_type = decision.get("type", "unknown")
        risk_level = decision.get("risk_level", "medium")

        # Perform quantitative analysis for financial decisions
        if decision_type in ["investment", "major_expense", "hire", "product_launch"]:
            investment = decision.get("cost", 0)
            annual_return = decision.get("expected_annual_return", 0)

            if investment > 0 and annual_return > 0:
                roi_analysis = self.calculate_roi(investment, annual_return)

                # Approve if ROI is positive and NPV > 0
                approved = roi_analysis["npv"] > 0 and roi_analysis["roi_percentage"] > 20

                reasoning = (
                    f"{self.specialization.title()} board member: {decision_type} analysis - "
                    f"ROI: {roi_analysis['roi_percentage']}%, "
                    f"NPV: ${roi_analysis['npv']:,.2f}, "
                    f"Payback: {roi_analysis['payback_period_years']} years"
                )

                conditions = []
                if roi_analysis["payback_period_years"] > 2:
                    conditions.append("Monitor payback timeline closely")
                if roi_analysis["roi_percentage"] < 50:
                    conditions.append("Consider alternative investments with higher ROI")

                return {
                    "approved": approved,
                    "reasoning": reasoning,
                    "conditions": conditions,
                    "confidence": 0.85,
                    "financial_metrics": roi_analysis,
                }

        # Risk-based assessment for high-risk decisions
        if risk_level == "high":
            risk_assessment = self.assess_risk(decision.get("risk_context", {}))

            approved = risk_assessment["recommendation"] == "approve"

            reasoning = (
                f"{self.specialization.title()} board member: High-risk {decision_type} "
                f"(Risk Score: {risk_assessment['risk_score']}/100) - "
                f"{risk_assessment['recommendation']}"
            )

            return {
                "approved": approved,
                "reasoning": reasoning,
                "conditions": ["Implement risk mitigation plan", "Monthly progress reviews"],
                "confidence": 0.75,
                "risk_assessment": risk_assessment,
            }

        # Default approval for low-risk operational decisions
        return {
            "approved": True,
            "reasoning": f"{self.specialization.title()} board member: Standard {decision_type} approved",
            "conditions": [],
            "confidence": 0.8,
        }

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make strategic governance decision.

        Args:
            context: Context for decision

        Returns:
            Strategic decision
        """
        self.decisions_made += 1

        decision_needed = context.get("decision_type", "general")

        # Company formation with financial analysis
        if decision_needed == "company_formation":
            initial_capital = context.get("initial_capital", 0)
            monthly_burn = context.get("estimated_monthly_burn", 0)

            if monthly_burn > 0:
                runway = initial_capital / monthly_burn
                sufficient_runway = runway >= 12  # Require 12 months minimum

                return {
                    "decision": "approve" if sufficient_runway else "defer",
                    "reasoning": (
                        f"Company formation: ${initial_capital:,.2f} capital provides "
                        f"{runway:.1f} months runway. "
                        + ("Sufficient for launch." if sufficient_runway else "Need more capital.")
                    ),
                    "confidence": 0.85,
                    "financial_analysis": {
                        "runway_months": round(runway, 1),
                        "minimum_required": 12,
                        "sufficient": sufficient_runway,
                    },
                }

            return {
                "decision": "approve",
                "reasoning": "Company formation aligns with strategic objectives",
                "confidence": 0.85,
            }

        # Executive hire with cost-benefit analysis
        elif decision_needed == "hire_executive":
            annual_cost = context.get("annual_salary", 180000)  # Default exec salary
            expected_value = context.get("expected_annual_value", 0)

            # Require 3x value-to-cost ratio for executive hires
            value_ratio = expected_value / annual_cost if annual_cost > 0 else 0
            hire_justified = value_ratio >= 2.0

            return {
                "decision": "approve" if hire_justified else "defer",
                "reasoning": (
                    f"Executive hire cost: ${annual_cost:,.0f}/year, "
                    f"Expected value: ${expected_value:,.0f}/year "
                    f"(Ratio: {value_ratio:.1f}x). "
                    + ("Hire justified." if hire_justified else "Value insufficient (need 2x minimum).")
                ),
                "confidence": 0.8,
                "cost_benefit": {
                    "annual_cost": annual_cost,
                    "expected_value": expected_value,
                    "value_ratio": round(value_ratio, 2),
                    "threshold": 2.0,
                },
            }

        # General decisions
        else:
            return {
                "decision": "defer",
                "reasoning": f"Insufficient financial data for {decision_needed} decision",
                "confidence": 0.6,
            }

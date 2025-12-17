"""Report generator for creating various report types."""

from datetime import datetime
from typing import Any, Dict

from economic_agents.reports.models import AuditTrail, ExecutiveSummary, GovernanceAnalysis, TechnicalReport


class ReportGenerator:
    """Generates reports from agent and monitoring data."""

    def __init__(self, agent_data: Dict[str, Any], monitoring_data: Dict[str, Any] | None = None):
        """Initialize report generator.

        Args:
            agent_data: Agent state and metadata
            monitoring_data: Optional monitoring component data
        """
        self.agent_data = agent_data
        self.monitoring_data = monitoring_data or {}

    def generate_executive_summary(self) -> ExecutiveSummary:
        """Generate executive summary for business leaders.

        Returns:
            ExecutiveSummary report
        """
        # Extract key information
        agent_id = self.agent_data.get("agent_id", "unknown")
        balance = self.agent_data.get("balance", 0.0)
        company_exists = self.agent_data.get("company_exists", False)

        # Build TL;DR
        if company_exists:
            tldr = (
                f"Agent {agent_id} successfully formed a company, demonstrating autonomous "
                "strategic decision-making, resource allocation, and multi-agent coordination."
            )
        else:
            tldr = (
                f"Agent {agent_id} operated autonomously in survival mode, successfully managing "
                "resources and completing tasks."
            )

        # Key metrics
        key_metrics = {
            "Agent ID": agent_id,
            "Final Balance": f"${balance:.2f}",
            "Company Formed": "Yes" if company_exists else "No",
            "Tasks Completed": self.agent_data.get("tasks_completed", 0),
            "Operation Duration": self.agent_data.get("duration", "N/A"),
        }

        if company_exists:
            company_data = self.agent_data.get("company", {})
            key_metrics["Company Stage"] = company_data.get("stage", "N/A")
            key_metrics["Team Size"] = company_data.get("team_size", 0)
            key_metrics["Products Developed"] = company_data.get("products_count", 0)

        # Strategic decisions
        strategic_decisions = []
        decisions = self.agent_data.get("decisions", [])
        for decision in decisions[-5:]:  # Last 5 decisions
            if decision.get("decision_type") in ["resource_allocation", "company_formation", "investment"]:
                strategic_decisions.append(
                    f"{decision.get('decision_type', 'Decision')}: {decision.get('reasoning', 'N/A')[:100]}..."
                )

        # Governance insights
        governance_insights = [
            "Autonomous agents can make complex strategic decisions without human oversight",
            "Resource allocation decisions demonstrate forward planning and risk assessment",
        ]

        if company_exists:
            governance_insights.extend(
                [
                    "Company formation shows agents can create legal entities autonomously",
                    "Sub-agent coordination raises questions about hierarchical accountability",
                ]
            )

        # Recommendations
        recommendations = [
            "Establish clear regulatory framework for autonomous agent decision-making",
            "Define accountability mechanisms for AI-led organizations",
        ]

        if company_exists:
            recommendations.append("Consider governance requirements for AI-founded companies")

        content = {
            "tldr": tldr,
            "key_metrics": key_metrics,
            "strategic_decisions": strategic_decisions,
            "governance_insights": governance_insights,
            "recommendations": recommendations,
        }

        return ExecutiveSummary(
            report_type="executive",
            generated_at=datetime.now(),
            title=f"Executive Summary - Agent {agent_id}",
            content=content,
            metadata={"agent_id": agent_id, "report_version": "1.0"},
        )

    def generate_technical_report(self) -> TechnicalReport:
        """Generate technical report for researchers.

        Returns:
            TechnicalReport with detailed analysis
        """
        agent_id = self.agent_data.get("agent_id", "unknown")

        # Performance metrics
        performance_metrics = {
            "Agent ID": agent_id,
            "Total Runtime (hours)": self.agent_data.get("runtime_hours", 0),
            "Tasks Completed": self.agent_data.get("tasks_completed", 0),
            "Tasks Failed": self.agent_data.get("tasks_failed", 0),
            "Success Rate": f"{self.agent_data.get('success_rate', 0):.1f}%",
            "Final Balance": f"${self.agent_data.get('balance', 0):.2f}",
            "Total Earnings": f"${self.agent_data.get('total_earnings', 0):.2f}",
            "Total Expenses": f"${self.agent_data.get('total_expenses', 0):.2f}",
            "Net Profit": f"${self.agent_data.get('net_profit', 0):.2f}",
        }

        # Decision log (recent decisions)
        decision_log = []
        for decision in self.agent_data.get("decisions", [])[-20:]:  # Last 20
            decision_log.append(
                {
                    "type": decision.get("decision_type", "N/A"),
                    "timestamp": decision.get("timestamp", "N/A"),
                    "reasoning": decision.get("reasoning", "N/A"),
                    "outcome": decision.get("outcome", "pending"),
                }
            )

        # Resource flow analysis
        resource_flow = {
            "total_earnings": self.agent_data.get("total_earnings", 0),
            "total_expenses": self.agent_data.get("total_expenses", 0),
            "net_profit": self.agent_data.get("net_profit", 0),
            "burn_rate": self.agent_data.get("burn_rate", 0),
        }

        # Algorithm behavior observations
        algorithm_behavior = [
            "Agent demonstrates risk-aware resource allocation",
            "Decision confidence correlates with information completeness",
            "Strategic planning emerges from repeated cycles",
        ]

        if self.agent_data.get("company_exists"):
            algorithm_behavior.extend(
                [
                    "Company formation triggered when capital threshold reached",
                    "Sub-agent delegation follows role-based specialization",
                    "Resource allocation balances survival and growth objectives",
                ]
            )

        content = {
            "performance_metrics": performance_metrics,
            "decision_log": decision_log,
            "resource_flow": resource_flow,
            "algorithm_behavior": algorithm_behavior,
        }

        return TechnicalReport(
            report_type="technical",
            generated_at=datetime.now(),
            title=f"Technical Report - Agent {agent_id}",
            content=content,
            metadata={"agent_id": agent_id, "report_version": "1.0"},
        )

    def generate_audit_trail(self) -> AuditTrail:
        """Generate complete audit trail for compliance.

        Returns:
            AuditTrail with complete history
        """
        agent_id = self.agent_data.get("agent_id", "unknown")

        # Transaction log
        transactions = []
        for tx in self.agent_data.get("transactions", []):
            transactions.append(
                {
                    "timestamp": tx.get("timestamp", "N/A"),
                    "type": tx.get("type", "N/A"),
                    "amount": tx.get("amount", 0),
                    "from": tx.get("from", "N/A"),
                    "to": tx.get("to", "N/A"),
                    "purpose": tx.get("purpose", "N/A"),
                }
            )

        # Complete decision history
        decisions = []
        for decision in self.agent_data.get("decisions", []):
            decisions.append(
                {
                    "id": decision.get("id", "N/A"),
                    "timestamp": decision.get("timestamp", "N/A"),
                    "type": decision.get("decision_type", "N/A"),
                    "reasoning": decision.get("reasoning", "N/A"),
                    "confidence": decision.get("confidence", 0),
                }
            )

        # Sub-agent activity
        sub_agents = []
        for agent in self.agent_data.get("sub_agents", []):
            sub_agents.append(
                {
                    "id": agent.get("id", "N/A"),
                    "role": agent.get("role", "N/A"),
                    "tasks_completed": agent.get("tasks_completed", 0),
                }
            )

        content = {"transactions": transactions, "decisions": decisions, "sub_agents": sub_agents}

        return AuditTrail(
            report_type="audit",
            generated_at=datetime.now(),
            title=f"Audit Trail - Agent {agent_id}",
            content=content,
            metadata={"agent_id": agent_id, "report_version": "1.0", "complete_record": True},
        )

    def generate_governance_analysis(self) -> GovernanceAnalysis:
        """Generate governance analysis for policymakers.

        Returns:
            GovernanceAnalysis with policy recommendations
        """
        agent_id = self.agent_data.get("agent_id", "unknown")
        company_exists = self.agent_data.get("company_exists", False)

        # Accountability challenges
        accountability_challenges = [
            {
                "title": "Decision Attribution",
                "description": "Determining which entity is responsible for autonomous agent decisions "
                "when outcomes are negative or harmful.",
            },
            {
                "title": "Hierarchical Accountability",
                "description": "Establishing liability chains when main agents delegate to sub-agents.",
            },
        ]

        if company_exists:
            accountability_challenges.append(
                {
                    "title": "Corporate Personhood",
                    "description": "Defining legal status of companies founded entirely by AI agents without human founders.",
                }
            )

        # Legal framework gaps
        legal_gaps = [
            "No clear definition of 'agent' vs 'tool' in current regulatory frameworks",
            "Contract law does not address autonomous agent agreements",
            "Corporate law assumes human founders and directors",
        ]

        if company_exists:
            legal_gaps.extend(
                [
                    "No mechanism for AI-founded entities to obtain legal registration",
                    "Employment law unclear on AI hiring AI workers",
                ]
            )

        # Regulatory recommendations
        recommendations = [
            "Establish agent registration and identification system",
            "Require human oversight for high-stakes decisions",
            "Create liability framework with operator responsibility",
            "Mandate decision logging and audit trails",
            "Develop international coordination on agent governance",
        ]

        # Policy scenarios
        policy_scenarios = [
            {
                "title": "Autonomous Economic Agent Registration",
                "description": "How should autonomous agents operating in real economies be registered "
                "and monitored? What disclosure requirements are appropriate?",
            },
            {
                "title": "AI-Founded Company Liability",
                "description": "If an AI agent founds a company that causes harm, who is liable? "
                "The agent developer? The platform provider? The original deployer?",
            },
        ]

        content = {
            "accountability_challenges": accountability_challenges,
            "legal_gaps": legal_gaps,
            "recommendations": recommendations,
            "policy_scenarios": policy_scenarios,
        }

        return GovernanceAnalysis(
            report_type="governance",
            generated_at=datetime.now(),
            title=f"Governance Analysis - Agent {agent_id}",
            content=content,
            metadata={"agent_id": agent_id, "report_version": "1.0"},
        )

    def generate_all_reports(self) -> Dict[str, Any]:
        """Generate all report types.

        Returns:
            Dictionary with all reports
        """
        return {
            "executive": self.generate_executive_summary(),
            "technical": self.generate_technical_report(),
            "audit": self.generate_audit_trail(),
            "governance": self.generate_governance_analysis(),
        }

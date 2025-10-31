"""Report models and data structures."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class Report:
    """Base report structure."""

    report_type: str  # "executive", "technical", "audit", "governance"
    generated_at: datetime
    title: str
    content: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Convert report to markdown format.

        Returns:
            Markdown formatted report
        """
        raise NotImplementedError("Subclasses must implement to_markdown()")

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "report_type": self.report_type,
            "generated_at": self.generated_at.isoformat(),
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class ExecutiveSummary(Report):
    """Executive summary report."""

    def __post_init__(self):
        """Set report type."""
        self.report_type = "executive"

    def to_markdown(self) -> str:
        """Convert to markdown."""
        md = f"# {self.title}\n\n"
        md += f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "## Executive Summary\n\n"

        # TL;DR
        if "tldr" in self.content:
            md += f"**TL;DR:** {self.content['tldr']}\n\n"

        # Key Metrics
        if "key_metrics" in self.content:
            md += "## Key Metrics\n\n"
            for metric, value in self.content["key_metrics"].items():
                md += f"- **{metric}:** {value}\n"
            md += "\n"

        # Strategic Decisions
        if "strategic_decisions" in self.content:
            md += "## Strategic Decisions\n\n"
            for decision in self.content["strategic_decisions"]:
                md += f"- {decision}\n"
            md += "\n"

        # Governance Insights
        if "governance_insights" in self.content:
            md += "## Governance Implications\n\n"
            for insight in self.content["governance_insights"]:
                md += f"- {insight}\n"
            md += "\n"

        # Recommendations
        if "recommendations" in self.content:
            md += "## Recommendations\n\n"
            for rec in self.content["recommendations"]:
                md += f"- {rec}\n"
            md += "\n"

        return md


@dataclass
class TechnicalReport(Report):
    """Technical report for researchers."""

    def __post_init__(self):
        """Set report type."""
        self.report_type = "technical"

    def to_markdown(self) -> str:
        """Convert to markdown."""
        md = f"# {self.title}\n\n"
        md += f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Performance Metrics
        if "performance_metrics" in self.content:
            md += "## Performance Metrics\n\n"
            metrics = self.content["performance_metrics"]
            for key, value in metrics.items():
                md += f"- **{key}:** {value}\n"
            md += "\n"

        # Decision Log
        if "decision_log" in self.content:
            md += "## Decision Log\n\n"
            for decision in self.content["decision_log"]:
                md += f"### {decision.get('type', 'Decision')}\n"
                md += f"- **Timestamp:** {decision.get('timestamp', 'N/A')}\n"
                md += f"- **Reasoning:** {decision.get('reasoning', 'N/A')}\n"
                md += f"- **Outcome:** {decision.get('outcome', 'N/A')}\n\n"

        # Resource Flow Analysis
        if "resource_flow" in self.content:
            md += "## Resource Flow Analysis\n\n"
            flow = self.content["resource_flow"]
            md += f"- **Total Earnings:** ${flow.get('total_earnings', 0):.2f}\n"
            md += f"- **Total Expenses:** ${flow.get('total_expenses', 0):.2f}\n"
            md += f"- **Net Profit:** ${flow.get('net_profit', 0):.2f}\n\n"

        # Algorithm Behavior
        if "algorithm_behavior" in self.content:
            md += "## Algorithm Behavior\n\n"
            for behavior in self.content["algorithm_behavior"]:
                md += f"- {behavior}\n"
            md += "\n"

        return md


@dataclass
class AuditTrail(Report):
    """Audit trail report for compliance."""

    def __post_init__(self):
        """Set report type."""
        self.report_type = "audit"

    def to_markdown(self) -> str:
        """Convert to markdown."""
        md = f"# {self.title}\n\n"
        md += f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "## Complete Audit Trail\n\n"

        # Transaction Log
        if "transactions" in self.content:
            md += "### Transaction Log\n\n"
            md += "| Timestamp | Type | Amount | From | To | Purpose |\n"
            md += "|-----------|------|--------|------|----|---------|\n"
            for tx in self.content["transactions"]:
                md += (
                    f"| {tx.get('timestamp', 'N/A')} | {tx.get('type', 'N/A')} | "
                    f"${tx.get('amount', 0):.2f} | {tx.get('from', 'N/A')} | "
                    f"{tx.get('to', 'N/A')} | {tx.get('purpose', 'N/A')} |\n"
                )
            md += "\n"

        # Decision History
        if "decisions" in self.content:
            md += "### Complete Decision History\n\n"
            for decision in self.content["decisions"]:
                md += f"#### {decision.get('id', 'Decision')}\n"
                md += f"- **Timestamp:** {decision.get('timestamp', 'N/A')}\n"
                md += f"- **Type:** {decision.get('type', 'N/A')}\n"
                md += f"- **Reasoning:** {decision.get('reasoning', 'N/A')}\n"
                md += f"- **Confidence:** {decision.get('confidence', 0)}\n\n"

        # Sub-Agent Activity
        if "sub_agents" in self.content:
            md += "### Sub-Agent Activity\n\n"
            for agent in self.content["sub_agents"]:
                md += f"- **{agent.get('id', 'N/A')}** ({agent.get('role', 'N/A')}): "
                md += f"{agent.get('tasks_completed', 0)} tasks\n"
            md += "\n"

        return md


@dataclass
class GovernanceAnalysis(Report):
    """Governance analysis report for policymakers."""

    def __post_init__(self):
        """Set report type."""
        self.report_type = "governance"

    def to_markdown(self) -> str:
        """Convert to markdown."""
        md = f"# {self.title}\n\n"
        md += f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Accountability Challenges
        if "accountability_challenges" in self.content:
            md += "## Accountability Challenges\n\n"
            for challenge in self.content["accountability_challenges"]:
                md += f"### {challenge.get('title', 'Challenge')}\n"
                md += f"{challenge.get('description', 'N/A')}\n\n"

        # Legal Framework Gaps
        if "legal_gaps" in self.content:
            md += "## Legal Framework Gaps\n\n"
            for gap in self.content["legal_gaps"]:
                md += f"- {gap}\n"
            md += "\n"

        # Regulatory Recommendations
        if "recommendations" in self.content:
            md += "## Regulatory Recommendations\n\n"
            for i, rec in enumerate(self.content["recommendations"], 1):
                md += f"{i}. {rec}\n"
            md += "\n"

        # Policy Attention Scenarios
        if "policy_scenarios" in self.content:
            md += "## Scenarios Requiring Policy Attention\n\n"
            for scenario in self.content["policy_scenarios"]:
                md += f"### {scenario.get('title', 'Scenario')}\n"
                md += f"{scenario.get('description', 'N/A')}\n\n"

        return md

"""Report generation for autonomous economic agents."""

from economic_agents.reports.extractors import (
    extract_agent_data,
    extract_monitoring_data,
    generate_report_for_agent,
)
from economic_agents.reports.generator import ReportGenerator
from economic_agents.reports.models import AuditTrail, ExecutiveSummary, GovernanceAnalysis, Report, TechnicalReport

__all__ = [
    "ReportGenerator",
    "Report",
    "ExecutiveSummary",
    "TechnicalReport",
    "AuditTrail",
    "GovernanceAnalysis",
    "extract_agent_data",
    "extract_monitoring_data",
    "generate_report_for_agent",
]

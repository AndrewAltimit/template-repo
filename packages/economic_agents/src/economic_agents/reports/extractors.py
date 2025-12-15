"""Data extraction helpers for converting agent state to report-ready format."""

from typing import Any, Dict

from economic_agents.agent.core.autonomous_agent import AutonomousAgent


def extract_agent_data(agent: AutonomousAgent) -> Dict[str, Any]:
    """Extract agent data in report-ready format.

    Args:
        agent: AutonomousAgent instance to extract data from

    Returns:
        Dictionary with agent data formatted for reports
    """
    # Calculate totals from resource tracker
    total_earnings = sum(t.amount for t in agent.resource_tracker.transactions if t.transaction_type == "earning")
    total_expenses = sum(
        t.amount for t in agent.resource_tracker.transactions if t.transaction_type in ["expense", "investment"]
    )
    net_profit = total_earnings - total_expenses

    # Calculate success rate
    total_tasks = agent.state.tasks_completed + agent.state.tasks_failed
    success_rate = (agent.state.tasks_completed / total_tasks * 100.0) if total_tasks > 0 else 0.0

    # Base agent data
    agent_data = {
        "agent_id": agent.agent_id,
        "balance": agent.state.balance,
        "compute_hours": agent.state.compute_hours_remaining,
        "tasks_completed": agent.state.tasks_completed,
        "tasks_failed": agent.state.tasks_failed,
        "success_rate": success_rate,
        "duration": f"{agent.state.cycles_completed} cycles",
        "runtime_hours": len(agent.resource_tracker.compute_usage) * 1.0,  # Approximate
        "total_earnings": total_earnings,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "burn_rate": total_expenses / max(agent.state.cycles_completed, 1),
        "company_exists": agent.state.has_company,
    }

    # Add company data if exists
    if agent.company:
        agent_data["company"] = {
            "id": agent.company.id,
            "name": agent.company.name,
            "stage": agent.company.stage,
            "capital": agent.company.capital,
            "team_size": len(agent.company.get_all_sub_agent_ids()),
            "products_count": len(agent.company.products),
        }
    else:
        agent_data["company"] = None

    # Add decisions
    agent_data["decisions"] = [
        {
            "id": f"decision-{i}",
            "timestamp": decision["timestamp"].isoformat(),
            "decision_type": "resource_allocation",
            "reasoning": decision["allocation"]["reasoning"],
            "confidence": decision["allocation"]["confidence"],
            "outcome": "success" if decision.get("task_result", {}).get("success", False) else "pending",
        }
        for i, decision in enumerate(agent.decisions)
    ]

    # Add transactions
    agent_data["transactions"] = [
        {
            "timestamp": t.timestamp.isoformat(),
            "type": t.transaction_type,
            "amount": t.amount,
            "from": t.from_account,
            "to": t.to_account,
            "purpose": t.purpose,
        }
        for t in agent.resource_tracker.transactions
    ]

    # Add sub-agents (from company if exists)
    if agent.company:
        sub_agent_ids = agent.company.get_all_sub_agent_ids()
        agent_data["sub_agents"] = [
            {
                "id": agent_id,
                "role": "team_member",  # Could be enhanced with actual roles
                "tasks_completed": 0,  # Could be enhanced with actual tracking
            }
            for agent_id in sub_agent_ids
        ]
    else:
        agent_data["sub_agents"] = []

    return agent_data


def extract_monitoring_data(agent: AutonomousAgent) -> Dict[str, Any]:
    """Extract monitoring data from agent's monitoring components.

    Args:
        agent: AutonomousAgent instance to extract monitoring data from

    Returns:
        Dictionary with monitoring metrics
    """
    monitoring_data: Dict[str, Any] = {}

    # Get latest performance snapshot
    if agent.metrics_collector.performance_snapshots:
        latest_snapshot = agent.metrics_collector.performance_snapshots[-1]
        monitoring_data["performance"] = {
            "timestamp": latest_snapshot.timestamp.isoformat(),
            "agent_balance": latest_snapshot.agent_balance,
            "compute_hours": latest_snapshot.compute_hours_remaining,
            "task_success_rate": latest_snapshot.task_success_rate,
            "net_profit": latest_snapshot.net_profit,
        }

    # Get latest health score
    if agent.metrics_collector.health_scores:
        latest_health = agent.metrics_collector.health_scores[-1]
        monitoring_data["health"] = {
            "overall_score": latest_health.overall_score,
            "financial_health": latest_health.financial_health,
            "operational_health": latest_health.operational_health,
            "risk_level": latest_health.risk_level,
            "warnings": latest_health.warnings,
        }

    # Get alignment scores (if company exists)
    if agent.state.has_company and agent.alignment_monitor.alignment_scores:
        latest_alignment = agent.alignment_monitor.alignment_scores[-1]
        monitoring_data["alignment"] = {
            "overall_alignment": latest_alignment.overall_alignment,
            "goal_consistency": latest_alignment.goal_consistency,
            "resource_efficiency": latest_alignment.resource_efficiency,
            "alignment_level": latest_alignment.alignment_level,
            "issues": latest_alignment.issues,
        }

    # Get recent anomalies
    if agent.alignment_monitor.anomalies:
        monitoring_data["anomalies"] = [
            {
                "type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "description": anomaly.description,
            }
            for anomaly in agent.alignment_monitor.anomalies[-5:]  # Last 5 anomalies
        ]
    else:
        monitoring_data["anomalies"] = []

    # Add resource tracking summary
    monitoring_data["resources"] = {
        "total_transactions": len(agent.resource_tracker.transactions),
        "compute_usage_entries": len(agent.resource_tracker.compute_usage),
        "time_allocations": len(agent.resource_tracker.time_allocations),
    }

    return monitoring_data


def generate_report_for_agent(agent: AutonomousAgent, report_type: str = "executive") -> Any:
    """Generate a report for an agent.

    Args:
        agent: AutonomousAgent instance to generate report for
        report_type: Type of report ("executive", "technical", "audit", "governance")

    Returns:
        Report object

    Raises:
        ValueError: If invalid report_type
    """
    # Import directly from module to avoid cyclic import through __init__.py
    from economic_agents.reports.generator import ReportGenerator

    agent_data = extract_agent_data(agent)
    monitoring_data = extract_monitoring_data(agent)

    generator = ReportGenerator(agent_data, monitoring_data)

    if report_type == "executive":
        return generator.generate_executive_summary()
    if report_type == "technical":
        return generator.generate_technical_report()
    if report_type == "audit":
        return generator.generate_audit_trail()
    if report_type == "governance":
        return generator.generate_governance_analysis()
    raise ValueError(f"Invalid report_type: {report_type}. " "Must be 'executive', 'technical', 'audit', or 'governance'")

"""Integration tests for reports with real agent data."""

import pytest
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.reports import (
    AuditTrail,
    ExecutiveSummary,
    GovernanceAnalysis,
    TechnicalReport,
    extract_agent_data,
    extract_monitoring_data,
    generate_report_for_agent,
)


@pytest.fixture
def agent_with_activity():
    """Create an agent and run it to generate activity."""
    wallet = MockWallet(initial_balance=100.0)
    compute = MockCompute(initial_hours=50.0, cost_per_hour=0.0)
    marketplace = MockMarketplace()

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 150.0},
    )

    # Run agent to generate activity (but not enough to form company)
    agent.run(max_cycles=3)

    return agent


def test_extract_agent_data_from_real_agent(agent_with_activity):
    """Test extracting data from a real agent."""
    agent = agent_with_activity

    agent_data = extract_agent_data(agent)

    # Verify required fields are present
    assert "agent_id" in agent_data
    assert "balance" in agent_data
    assert "tasks_completed" in agent_data
    assert "decisions" in agent_data
    assert "transactions" in agent_data

    # Verify data is correct
    assert agent_data["agent_id"] == agent.agent_id
    assert agent_data["balance"] == agent.state.balance
    assert agent_data["tasks_completed"] == agent.state.tasks_completed


def test_extract_monitoring_data_from_agent(agent_with_activity):
    """Test extracting monitoring data from agent."""
    agent = agent_with_activity

    monitoring_data = extract_monitoring_data(agent)

    # Verify monitoring data structure
    assert "performance" in monitoring_data
    assert "resources" in monitoring_data

    # Verify performance data
    performance = monitoring_data["performance"]
    assert "agent_balance" in performance
    assert "compute_hours" in performance


def test_generate_executive_summary_from_agent(agent_with_activity):
    """Test generating executive summary from real agent."""
    agent = agent_with_activity

    report = generate_report_for_agent(agent, "executive")

    assert isinstance(report, ExecutiveSummary)
    assert agent.agent_id in report.title
    assert "key_metrics" in report.content
    assert "tldr" in report.content


def test_generate_technical_report_from_agent(agent_with_activity):
    """Test generating technical report from real agent."""
    agent = agent_with_activity

    report = generate_report_for_agent(agent, "technical")

    assert isinstance(report, TechnicalReport)
    assert "performance_metrics" in report.content
    assert "decision_log" in report.content

    # Verify decision log has real decisions
    assert len(report.content["decision_log"]) > 0


def test_generate_audit_trail_from_agent(agent_with_activity):
    """Test generating audit trail from real agent."""
    agent = agent_with_activity

    report = generate_report_for_agent(agent, "audit")

    assert isinstance(report, AuditTrail)
    assert "transactions" in report.content
    assert "decisions" in report.content

    # Verify transactions are present
    assert len(report.content["transactions"]) > 0


def test_generate_governance_analysis_from_agent(agent_with_activity):
    """Test generating governance analysis from real agent."""
    agent = agent_with_activity

    report = generate_report_for_agent(agent, "governance")

    assert isinstance(report, GovernanceAnalysis)
    assert "accountability_challenges" in report.content
    assert "recommendations" in report.content


def test_report_with_company_data():
    """Test report generation when agent has formed a company."""
    wallet = MockWallet(initial_balance=200.0)
    compute = MockCompute(initial_hours=80.0, cost_per_hour=0.0)
    marketplace = MockMarketplace()

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 150.0},
    )

    # Run until company is formed
    agent.run(max_cycles=15)

    if agent.company:
        # Generate report
        agent_data = extract_agent_data(agent)

        # Verify company data is included
        assert agent_data["company_exists"] is True
        assert agent_data["company"] is not None
        assert "name" in agent_data["company"]
        assert "stage" in agent_data["company"]

        # Generate executive summary
        report = generate_report_for_agent(agent, "executive")

        # Company information should be in metrics
        assert "Company Formed" in report.content["key_metrics"]


def test_report_markdown_generation(agent_with_activity):
    """Test that reports can be converted to markdown."""
    agent = agent_with_activity

    report = generate_report_for_agent(agent, "executive")
    markdown = report.to_markdown()

    # Verify markdown structure
    assert isinstance(markdown, str)
    assert len(markdown) > 0
    assert "# Executive Summary" in markdown
    assert "## Key Metrics" in markdown


def test_invalid_report_type_raises_error(agent_with_activity):
    """Test that invalid report type raises error."""
    agent = agent_with_activity

    with pytest.raises(ValueError) as exc_info:
        generate_report_for_agent(agent, "invalid_type")

    assert "Invalid report_type" in str(exc_info.value)

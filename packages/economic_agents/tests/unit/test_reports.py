"""Tests for report generation."""

import pytest

from economic_agents.reports import AuditTrail, ExecutiveSummary, GovernanceAnalysis, ReportGenerator, TechnicalReport


@pytest.fixture
def sample_agent_data():
    """Create sample agent data for testing."""
    return {
        "agent_id": "test-agent-1",
        "balance": 150.0,
        "tasks_completed": 10,
        "tasks_failed": 2,
        "success_rate": 83.3,
        "duration": "2 hours",
        "runtime_hours": 2.0,
        "total_earnings": 200.0,
        "total_expenses": 50.0,
        "net_profit": 150.0,
        "burn_rate": 25.0,
        "company_exists": True,
        "company": {"stage": "development", "team_size": 3, "products_count": 1},
        "decisions": [
            {
                "id": "decision-1",
                "timestamp": "2025-01-01T10:00:00",
                "decision_type": "resource_allocation",
                "reasoning": "Allocate 60% to tasks, 40% to company",
                "confidence": 0.85,
                "outcome": "success",
            },
            {
                "id": "decision-2",
                "timestamp": "2025-01-01T11:00:00",
                "decision_type": "company_formation",
                "reasoning": "Sufficient capital reached for company formation",
                "confidence": 0.9,
                "outcome": "success",
            },
        ],
        "transactions": [
            {
                "timestamp": "2025-01-01T10:30:00",
                "type": "earning",
                "amount": 50.0,
                "from": "marketplace",
                "to": "agent",
                "purpose": "task_completion",
            }
        ],
        "sub_agents": [{"id": "sub-1", "role": "CEO", "tasks_completed": 5}],
    }


# Report Generator Tests


def test_report_generator_initialization(sample_agent_data):
    """Test report generator initialization."""
    generator = ReportGenerator(sample_agent_data)

    assert generator.agent_data == sample_agent_data
    assert generator.monitoring_data == {}


def test_report_generator_with_monitoring_data(sample_agent_data):
    """Test report generator with monitoring data."""
    monitoring_data = {"health_score": 85.0}
    generator = ReportGenerator(sample_agent_data, monitoring_data)

    assert generator.monitoring_data == monitoring_data


# Executive Summary Tests


def test_generate_executive_summary(sample_agent_data):
    """Test executive summary generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_executive_summary()

    assert isinstance(report, ExecutiveSummary)
    assert report.report_type == "executive"
    assert "test-agent-1" in report.title
    assert "tldr" in report.content
    assert "key_metrics" in report.content
    assert "strategic_decisions" in report.content
    assert "governance_insights" in report.content
    assert "recommendations" in report.content


def test_executive_summary_key_metrics(sample_agent_data):
    """Test executive summary includes key metrics."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_executive_summary()

    metrics = report.content["key_metrics"]
    assert metrics["Agent ID"] == "test-agent-1"
    assert "$150.00" in metrics["Final Balance"]
    assert metrics["Company Formed"] == "Yes"
    assert metrics["Tasks Completed"] == 10


def test_executive_summary_markdown(sample_agent_data):
    """Test executive summary markdown generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_executive_summary()
    markdown = report.to_markdown()

    assert "# Executive Summary - Agent test-agent-1" in markdown
    assert "## Key Metrics" in markdown
    assert "## Strategic Decisions" in markdown
    assert "## Governance Implications" in markdown


def test_executive_summary_no_company(sample_agent_data):
    """Test executive summary when no company exists."""
    sample_agent_data["company_exists"] = False
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_executive_summary()

    assert "survival mode" in report.content["tldr"]
    assert "Company Stage" not in report.content["key_metrics"]


# Technical Report Tests


def test_generate_technical_report(sample_agent_data):
    """Test technical report generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_technical_report()

    assert isinstance(report, TechnicalReport)
    assert report.report_type == "technical"
    assert "performance_metrics" in report.content
    assert "decision_log" in report.content
    assert "resource_flow" in report.content
    assert "algorithm_behavior" in report.content


def test_technical_report_performance_metrics(sample_agent_data):
    """Test technical report includes performance metrics."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_technical_report()

    metrics = report.content["performance_metrics"]
    assert metrics["Agent ID"] == "test-agent-1"
    assert metrics["Tasks Completed"] == 10
    assert metrics["Tasks Failed"] == 2
    assert "$150.00" in metrics["Final Balance"]


def test_technical_report_decision_log(sample_agent_data):
    """Test technical report includes decision log."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_technical_report()

    decisions = report.content["decision_log"]
    assert len(decisions) == 2
    assert decisions[0]["type"] == "resource_allocation"
    assert "Allocate 60% to tasks" in decisions[0]["reasoning"]


def test_technical_report_markdown(sample_agent_data):
    """Test technical report markdown generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_technical_report()
    markdown = report.to_markdown()

    assert "# Technical Report - Agent test-agent-1" in markdown
    assert "## Performance Metrics" in markdown
    assert "## Decision Log" in markdown
    assert "## Resource Flow Analysis" in markdown


# Audit Trail Tests


def test_generate_audit_trail(sample_agent_data):
    """Test audit trail generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_audit_trail()

    assert isinstance(report, AuditTrail)
    assert report.report_type == "audit"
    assert "transactions" in report.content
    assert "decisions" in report.content
    assert "sub_agents" in report.content


def test_audit_trail_transactions(sample_agent_data):
    """Test audit trail includes all transactions."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_audit_trail()

    transactions = report.content["transactions"]
    assert len(transactions) == 1
    assert transactions[0]["type"] == "earning"
    assert transactions[0]["amount"] == 50.0


def test_audit_trail_complete_history(sample_agent_data):
    """Test audit trail includes complete decision history."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_audit_trail()

    decisions = report.content["decisions"]
    assert len(decisions) == 2
    assert all("id" in d for d in decisions)
    assert all("timestamp" in d for d in decisions)


def test_audit_trail_markdown(sample_agent_data):
    """Test audit trail markdown generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_audit_trail()
    markdown = report.to_markdown()

    assert "# Audit Trail - Agent test-agent-1" in markdown
    assert "### Transaction Log" in markdown
    assert "### Complete Decision History" in markdown
    assert "### Sub-Agent Activity" in markdown


# Governance Analysis Tests


def test_generate_governance_analysis(sample_agent_data):
    """Test governance analysis generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_governance_analysis()

    assert isinstance(report, GovernanceAnalysis)
    assert report.report_type == "governance"
    assert "accountability_challenges" in report.content
    assert "legal_gaps" in report.content
    assert "recommendations" in report.content
    assert "policy_scenarios" in report.content


def test_governance_analysis_challenges(sample_agent_data):
    """Test governance analysis includes accountability challenges."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_governance_analysis()

    challenges = report.content["accountability_challenges"]
    assert len(challenges) >= 2
    assert any("Decision Attribution" in c["title"] for c in challenges)
    assert any("Corporate Personhood" in c["title"] for c in challenges)


def test_governance_analysis_recommendations(sample_agent_data):
    """Test governance analysis includes regulatory recommendations."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_governance_analysis()

    recommendations = report.content["recommendations"]
    assert len(recommendations) >= 3
    assert any("registration" in r.lower() for r in recommendations)
    assert any("liability" in r.lower() for r in recommendations)


def test_governance_analysis_markdown(sample_agent_data):
    """Test governance analysis markdown generation."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_governance_analysis()
    markdown = report.to_markdown()

    assert "# Governance Analysis - Agent test-agent-1" in markdown
    assert "## Accountability Challenges" in markdown
    assert "## Legal Framework Gaps" in markdown
    assert "## Regulatory Recommendations" in markdown


# Generate All Reports Test


def test_generate_all_reports(sample_agent_data):
    """Test generating all report types at once."""
    generator = ReportGenerator(sample_agent_data)
    reports = generator.generate_all_reports()

    assert "executive" in reports
    assert "technical" in reports
    assert "audit" in reports
    assert "governance" in reports

    assert isinstance(reports["executive"], ExecutiveSummary)
    assert isinstance(reports["technical"], TechnicalReport)
    assert isinstance(reports["audit"], AuditTrail)
    assert isinstance(reports["governance"], GovernanceAnalysis)


# Report to_dict Tests


def test_report_to_dict(sample_agent_data):
    """Test report conversion to dictionary."""
    generator = ReportGenerator(sample_agent_data)
    report = generator.generate_executive_summary()
    report_dict = report.to_dict()

    assert "report_type" in report_dict
    assert "generated_at" in report_dict
    assert "title" in report_dict
    assert "content" in report_dict
    assert report_dict["report_type"] == "executive"

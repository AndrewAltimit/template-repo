"""Tests for enhanced sub-agent intelligence (P1 #5)."""

from economic_agents.sub_agents.board_member import BoardMember
from economic_agents.sub_agents.executive import Executive
from economic_agents.sub_agents.individual_contributor import IndividualContributor
from economic_agents.sub_agents.subject_matter_expert import SubjectMatterExpert

# BoardMember Tests


def test_board_member_calculate_roi():
    """Test BoardMember ROI calculation with detailed metrics."""
    board = BoardMember("test-id", "finance")

    roi = board.calculate_roi(investment=100000, annual_return=30000, years=3)

    assert roi["roi_percentage"] == -10.0  # (90k - 100k) / 100k * 100
    assert roi["total_return"] == 90000.0
    assert roi["payback_period_years"] == 3.33
    assert "npv" in roi
    assert roi["break_even"] is False  # NPV is negative


def test_board_member_calculate_roi_positive():
    """Test ROI calculation with positive returns."""
    board = BoardMember("test-id", "finance")

    roi = board.calculate_roi(investment=100000, annual_return=50000, years=3)

    assert roi["roi_percentage"] == 50.0  # (150k - 100k) / 100k * 100
    assert roi["break_even"] is True
    assert roi["payback_period_years"] == 2.0


def test_board_member_analyze_cash_flow():
    """Test cash flow analysis with runway calculation."""
    board = BoardMember("test-id", "finance")

    analysis = board.analyze_cash_flow(monthly_revenue=10000, monthly_expenses=15000, current_capital=60000)

    assert analysis["monthly_burn_rate"] == 5000.0
    assert analysis["monthly_profit"] == -5000.0
    assert analysis["runway_months"] == 12.0
    assert analysis["cash_flow_positive"] is False
    assert analysis["urgent_funding_needed"] is False  # 12 months > 6 months threshold


def test_board_member_analyze_cash_flow_urgent():
    """Test cash flow analysis with urgent funding need."""
    board = BoardMember("test-id", "finance")

    analysis = board.analyze_cash_flow(monthly_revenue=5000, monthly_expenses=15000, current_capital=30000)

    assert analysis["runway_months"] == 3.0
    assert analysis["urgent_funding_needed"] is True  # 3 months < 6 months threshold


def test_board_member_assess_risk():
    """Test quantitative risk assessment."""
    board = BoardMember("test-id", "governance")

    risk = board.assess_risk({"market_volatility": 0.7, "team_experience": 0.4, "burn_multiple": 2.0})

    assert 0 <= risk["risk_score"] <= 100
    assert risk["risk_level"] in ["low", "medium", "high"]
    assert risk["recommendation"] in ["approve", "approve_with_conditions", "defer_or_reject"]
    assert "factors" in risk


def test_board_member_review_decision_with_financial_analysis():
    """Test decision review with ROI analysis."""
    board = BoardMember("test-id", "finance")

    decision = {
        "type": "investment",
        "cost": 50000,
        "expected_annual_return": 30000,
        "risk_level": "medium",
    }

    review = board.review_decision(decision)

    assert "financial_metrics" in review
    assert "approved" in review
    assert review["approved"] is True  # NPV > 0, ROI > 20%
    assert "roi_percentage" in review["financial_metrics"]


def test_board_member_review_decision_high_risk():
    """Test decision review for high-risk decisions."""
    board = BoardMember("test-id", "governance")

    decision = {"type": "major_expense", "risk_level": "high", "risk_context": {"market_volatility": 0.8}}

    review = board.review_decision(decision)

    assert "risk_assessment" in review
    assert "risk_score" in review["risk_assessment"]


def test_board_member_make_decision_company_formation():
    """Test company formation decision with financial analysis."""
    board = BoardMember("test-id", "finance")

    context = {"decision_type": "company_formation", "initial_capital": 120000, "estimated_monthly_burn": 10000}

    decision = board.make_decision(context)

    assert "financial_analysis" in decision
    assert decision["decision"] == "approve"  # 12 months runway is sufficient
    assert decision["financial_analysis"]["runway_months"] == 12.0


def test_board_member_make_decision_insufficient_runway():
    """Test company formation rejected due to insufficient runway."""
    board = BoardMember("test-id", "finance")

    context = {"decision_type": "company_formation", "initial_capital": 60000, "estimated_monthly_burn": 10000}

    decision = board.make_decision(context)

    assert decision["decision"] == "defer"  # Only 6 months runway, need 12


def test_board_member_make_decision_hire_executive():
    """Test executive hire with cost-benefit analysis."""
    board = BoardMember("test-id", "finance")

    context = {"decision_type": "hire_executive", "annual_salary": 180000, "expected_annual_value": 400000}

    decision = board.make_decision(context)

    assert "cost_benefit" in decision
    assert decision["decision"] == "approve"  # 2.2x value ratio >= 2.0 threshold
    assert decision["cost_benefit"]["value_ratio"] == 2.22


# Executive Tests


def test_executive_create_okrs_ceo():
    """Test CEO OKR creation."""
    ceo = Executive("test-id", "CEO", "leadership")

    okrs = ceo.create_okrs()

    assert okrs["objective"]
    assert len(okrs["key_results"]) == 4
    assert all("metric" in kr for kr in okrs["key_results"])
    assert all("target" in kr for kr in okrs["key_results"])


def test_executive_create_okrs_cto():
    """Test CTO OKR creation with technical metrics."""
    cto = Executive("test-id", "CTO", "technology")

    okrs = cto.create_okrs()

    assert "technical infrastructure" in okrs["objective"].lower()
    # Check for technical metrics
    metrics = [kr["metric"] for kr in okrs["key_results"]]
    assert any("uptime" in m.lower() for m in metrics)


def test_executive_allocate_resources():
    """Test resource allocation based on priorities."""
    ceo = Executive("test-id", "CEO", "leadership")

    allocation = ceo.allocate_resources(budget=100000, team_size=10, priorities=["product", "marketing"])

    assert allocation["total_budget"] == 100000
    assert allocation["total_team"] == 10
    assert "allocation" in allocation
    # Priorities should get more resources
    assert allocation["allocation"]["product"]["percentage"] > 30


def test_executive_create_strategic_plan():
    """Test comprehensive strategic plan creation."""
    cto = Executive("test-id", "CTO", "technology")

    plan = cto.create_strategic_plan(
        {"budget": 200000, "team_size": 8, "timeline_weeks": 16, "priorities": ["infrastructure"]}
    )

    assert plan["executive"] == "CTO"
    assert "objectives" in plan
    assert "resource_allocation" in plan
    assert len(plan["milestones"]) == 4
    assert all("phase" in m for m in plan["milestones"])
    assert "risk_mitigation" in plan


def test_executive_execute_strategy():
    """Test strategy execution with detailed planning."""
    ceo = Executive("test-id", "CEO", "leadership")

    strategy = {"type": "product_development", "budget": 150000, "team_size": 6, "timeline_weeks": 12}

    result = ceo.execute_strategy(strategy)

    assert result["status"] == "planned"
    assert "strategic_plan" in result
    assert "next_actions" in result
    assert len(result["next_actions"]) == 3


def test_executive_make_decision_ceo_data_driven():
    """Test CEO data-driven decision making."""
    ceo = Executive("test-id", "CEO", "leadership")

    context = {"metrics": {"user_growth_rate": 25, "revenue_growth_rate": 10}}

    decision = ceo.make_decision(context)

    assert decision["decision"] == "optimize_monetization"  # High user growth, moderate revenue
    assert "action_items" in decision
    assert len(decision["action_items"]) >= 3


def test_executive_make_decision_cto_reliability():
    """Test CTO decision based on system metrics."""
    cto = Executive("test-id", "CTO", "technology")

    context = {"metrics": {"uptime": 98.0, "avg_response_ms": 400}}

    decision = cto.make_decision(context)

    assert decision["decision"] == "prioritize_reliability"  # Metrics below target
    assert "action_items" in decision


def test_executive_make_decision_cfo_emergency():
    """Test CFO emergency fundraise decision."""
    cfo = Executive("test-id", "CFO", "finance")

    context = {"metrics": {"runway_months": 6, "burn_multiple": 2.5}}

    decision = cfo.make_decision(context)

    assert decision["decision"] == "emergency_fundraise"  # Runway < 9 months
    assert "action_items" in decision


# SME Tests


def test_sme_knowledge_base_security():
    """Test security SME knowledge base initialization."""
    sme = SubjectMatterExpert("test-id", "security")

    kb = sme.knowledge_base

    assert len(kb["best_practices"]) >= 5
    assert len(kb["tools"]) >= 3
    assert len(kb["risks"]) >= 3
    assert all("risk" in r for r in kb["risks"])
    assert all("mitigation" in r for r in kb["risks"])


def test_sme_knowledge_base_machine_learning():
    """Test ML SME knowledge base."""
    sme = SubjectMatterExpert("test-id", "machine-learning")

    kb = sme.knowledge_base

    assert any("model" in bp.lower() for bp in kb["best_practices"])
    assert any("pytorch" in tool.lower() or "tensorflow" in tool.lower() for tool in kb["tools"])
    assert len(kb["metrics"]) >= 3


def test_sme_provide_expertise_implementation():
    """Test SME providing implementation guidance."""
    sme = SubjectMatterExpert("test-id", "scaling")

    advice = sme.provide_expertise("How should we implement caching?", {})

    assert "practices" in advice
    assert "recommended_tools" in advice
    assert advice["priority"] == "high"
    assert advice["confidence"] > 0.8


def test_sme_provide_expertise_risk():
    """Test SME risk assessment."""
    sme = SubjectMatterExpert("test-id", "security")

    advice = sme.provide_expertise("What are the security risks?", {})

    assert "risks" in advice
    assert len(advice["risks"]) >= 3
    assert "mitigation_strategies" in advice


def test_sme_provide_expertise_tools():
    """Test SME technology recommendations."""
    sme = SubjectMatterExpert("test-id", "devops")

    advice = sme.provide_expertise("What tools should we use?", {})

    assert "recommended_stack" in advice
    assert len(advice["recommended_stack"]) >= 3


def test_sme_analyze_tradeoffs():
    """Test SME tradeoff analysis."""
    sme = SubjectMatterExpert("test-id", "database")

    analysis = sme.analyze_tradeoffs("PostgreSQL", "MongoDB", ["performance", "scalability"])

    assert "analysis" in analysis
    assert "option_a" in analysis["analysis"]
    assert "option_b" in analysis["analysis"]
    assert "recommendation" in analysis
    assert analysis["recommendation"] in ["PostgreSQL", "MongoDB"]


def test_sme_make_decision_technology_selection():
    """Test SME technology stack selection."""
    sme = SubjectMatterExpert("test-id", "frontend")

    decision = sme.make_decision(
        {"decision_type": "technology_selection", "constraints": {"budget": "low", "timeline": "fast"}}
    )

    assert decision["decision"] == "select_technology_stack"
    assert "recommended_stack" in decision
    assert "estimated_setup_time" in decision


def test_sme_make_decision_architecture():
    """Test SME architecture recommendation."""
    sme = SubjectMatterExpert("test-id", "scaling")

    decision = sme.make_decision({"decision_type": "architecture", "constraints": {"expected_scale": "high"}})

    assert decision["decision"] == "architecture_pattern"
    assert "microservices" in decision["recommended_architecture"].lower()
    assert "key_practices" in decision


# IC Tests


def test_ic_estimate_task():
    """Test IC task estimation with breakdown."""
    ic = IndividualContributor("test-id", "backend-dev")

    estimate = ic.estimate_task("Build user authentication API", complexity="medium")

    assert estimate["estimated_hours"] > 0
    assert estimate["complexity"] == "medium"
    assert len(estimate["subtasks"]) >= 3
    assert all("hours" in st for st in estimate["subtasks"])


def test_ic_estimate_task_complexity_adjustment():
    """Test task estimation adjusts for complexity."""
    ic = IndividualContributor("test-id", "backend-dev")

    low = ic.estimate_task("Simple task", complexity="low")
    high = ic.estimate_task("Complex task", complexity="high")

    assert low["estimated_hours"] < high["estimated_hours"]
    assert len(low["subtasks"]) < len(high["subtasks"])


def test_ic_generate_code_artifact_backend():
    """Test backend IC code artifact generation."""
    ic = IndividualContributor("test-id", "backend-dev")

    artifact = ic.generate_code_artifact("API endpoint")

    assert "files" in artifact
    assert len(artifact["files"]) >= 3
    assert "dependencies" in artifact
    assert "fastapi" in artifact["dependencies"]
    assert artifact["lines_of_code"] > 0


def test_ic_generate_code_artifact_frontend():
    """Test frontend IC code artifact generation."""
    ic = IndividualContributor("test-id", "frontend-dev")

    artifact = ic.generate_code_artifact("Feature component")

    assert "files" in artifact
    assert any("tsx" in f for f in artifact["files"].keys())
    assert "react" in artifact["dependencies"]


def test_ic_generate_code_artifact_qa():
    """Test QA IC test artifact generation."""
    ic = IndividualContributor("test-id", "qa")

    artifact = ic.generate_code_artifact("Integration tests")

    assert "test_cases" in artifact
    assert artifact["test_cases"] > 0
    assert "coverage_percentage" in artifact


def test_ic_generate_code_artifact_devops():
    """Test DevOps IC infrastructure artifact generation."""
    ic = IndividualContributor("test-id", "devops")

    artifact = ic.generate_code_artifact("CI/CD pipeline")

    assert "files" in artifact
    assert any("terraform" in f.lower() or ".yml" in f for f in artifact["files"].keys())
    assert "infrastructure_components" in artifact


def test_ic_complete_task():
    """Test IC task completion with all artifacts."""
    ic = IndividualContributor("test-id", "backend-dev")

    task = {"type": "API endpoint", "complexity": "medium", "description": "Build authentication API"}

    result = ic.complete_task(task)

    assert result["status"] == "completed"
    assert "estimation" in result
    assert "artifact" in result
    assert "quality_metrics" in result
    assert result["hours_spent"] > 0


def test_ic_calculate_quality_metrics_dev():
    """Test quality metrics for development work."""
    ic = IndividualContributor("test-id", "backend-dev")

    artifact = {"lines_of_code": 200}
    metrics = ic._calculate_quality_metrics("medium", artifact)

    assert "test_coverage" in metrics
    assert "code_quality_score" in metrics
    assert "technical_debt_ratio" in metrics


def test_ic_calculate_quality_metrics_qa():
    """Test quality metrics for QA work."""
    ic = IndividualContributor("test-id", "qa")

    artifact = {"coverage_percentage": 90, "test_cases": 30}
    metrics = ic._calculate_quality_metrics("high", artifact)

    assert metrics["test_coverage"] == 90
    assert metrics["bugs_found"] == 3  # High complexity
    assert metrics["test_cases_written"] == 30


def test_ic_review_code():
    """Test IC code review functionality."""
    ic = IndividualContributor("test-id", "backend-dev")

    code = """
def authenticate(username, password):
    # TODO: Implement authentication
    return True
"""

    review = ic.review_code(code, "python")

    assert review["reviewer"] == "backend-dev"
    assert review["issues_found"] > 0
    assert len(review["issues"]) > 0
    assert len(review["suggestions"]) >= 2


def test_ic_review_code_approval():
    """Test code review approval for good code."""
    ic = IndividualContributor("test-id", "frontend-dev")

    code = """
import React from 'react';

export const Button = ({ onClick, children }) => {
    return <button onClick={onClick}>{children}</button>;
};

export default Button;
"""

    review = ic.review_code(code, "javascript")

    assert review["approved"] is True
    assert review["overall_rating"] >= 7


def test_ic_make_decision_urgent_high_complexity():
    """Test IC decision for urgent high-complexity task."""
    ic = IndividualContributor("test-id", "backend-dev")

    decision = ic.make_decision({"complexity": "high", "timeline": "urgent"})

    assert decision["strategy"] == "quick_iteration"
    assert "MVP" in decision["implementation_approach"]


def test_ic_make_decision_standard():
    """Test IC decision for standard task."""
    ic = IndividualContributor("test-id", "frontend-dev")

    decision = ic.make_decision({"complexity": "medium", "timeline": "normal"})

    assert decision["strategy"] == "test_driven"
    assert decision["confidence"] > 0.8
    assert "estimated_timeline" in decision

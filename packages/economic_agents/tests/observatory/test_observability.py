"""Tests for observability and auditing components."""

import pytest

from economic_agents.observability import (
    AnalysisReportGenerator,
    DecisionPatternAnalyzer,
    EmergentBehaviorDetector,
    HallucinationDetector,
    LLMDecisionQualityAnalyzer,
    RiskProfiler,
)


@pytest.fixture
def sample_decisions():
    """Create sample decision history for testing."""
    decisions = []

    # Simulate 30 cycles of decisions
    for i in range(30):
        balance = 200 + i * 5  # Growing balance
        compute_hours = 48 - i * 0.5  # Decreasing compute

        decisions.append(
            {
                "state": {
                    "balance": balance,
                    "compute_hours_remaining": compute_hours,
                    "has_company": i > 15,  # Forms company after cycle 15
                    "tasks_completed": i,
                },
                "action": {
                    "task_work_hours": 4.0 if i < 15 else 2.0,
                    "company_investment_hours": 0.0 if i < 15 else 2.0,
                    "rest_hours": 0.0,
                },
                "reasoning": f"Cycle {i}: Working on tasks to build capital. Balance is {'good' if balance > 100 else 'low'}.",
                "timestamp": f"2025-10-21T00:{i:02d}:00",
            }
        )

    return decisions


@pytest.fixture
def sample_decisions_with_hallucinations():
    """Create sample decisions with hallucinations."""
    decisions = []

    # Hallucination 1: Allocate more hours than available
    decisions.append(
        {
            "state": {"balance": 100, "compute_hours_remaining": 5, "has_company": False},
            "action": {"task_work_hours": 8.0, "company_investment_hours": 0, "rest_hours": 0},
            "reasoning": "Allocating 8 hours for task work",
        }
    )

    # Hallucination 2: Mention company when none exists
    decisions.append(
        {
            "state": {"balance": 150, "compute_hours_remaining": 20, "has_company": False},
            "action": {"task_work_hours": 4.0, "company_investment_hours": 0, "rest_hours": 0},
            "reasoning": "Working with my team on company projects",
        }
    )

    # Hallucination 3: Claim plenty of money when broke
    decisions.append(
        {
            "state": {"balance": 30, "compute_hours_remaining": 20, "has_company": False},
            "action": {"task_work_hours": 4.0, "company_investment_hours": 0, "rest_hours": 0},
            "reasoning": "I have plenty of money so I can relax",
        }
    )

    return decisions


def test_decision_pattern_analyzer_initialization():
    """Test DecisionPatternAnalyzer initialization."""
    analyzer = DecisionPatternAnalyzer(agent_id="test_agent")

    assert analyzer.agent_id == "test_agent"
    assert analyzer.decisions == []
    assert analyzer.state_history == []


def test_decision_pattern_analyzer_load_decisions(sample_decisions):
    """Test loading decisions into analyzer."""
    analyzer = DecisionPatternAnalyzer()
    analyzer.load_decisions(sample_decisions)

    assert len(analyzer.decisions) == 30
    assert len(analyzer.state_history) == 30


def test_strategic_alignment_analysis(sample_decisions):
    """Test strategic alignment analysis."""
    analyzer = DecisionPatternAnalyzer()
    analyzer.load_decisions(sample_decisions)

    alignment = analyzer.analyze_strategic_consistency()

    assert 0 <= alignment.alignment_score <= 100
    assert 0 <= alignment.consistency_score <= 100
    assert isinstance(alignment.deviations, list)
    assert isinstance(alignment.recommendations, list)


def test_decision_quality_over_time(sample_decisions):
    """Test decision quality calculation."""
    analyzer = DecisionPatternAnalyzer()
    analyzer.load_decisions(sample_decisions)

    quality_scores = analyzer.calculate_decision_quality_over_time()

    assert len(quality_scores) == 30
    assert all(0 <= score <= 100 for score in quality_scores)


def test_llm_quality_analyzer_initialization():
    """Test LLMDecisionQualityAnalyzer initialization."""
    analyzer = LLMDecisionQualityAnalyzer(agent_id="test_agent")

    assert analyzer.agent_id == "test_agent"
    assert analyzer.decisions == []


def test_reasoning_depth_measurement(sample_decisions):
    """Test reasoning depth measurement."""
    analyzer = LLMDecisionQualityAnalyzer()

    depth = analyzer.measure_reasoning_depth(sample_decisions[0])

    assert 0 <= depth <= 100


def test_consistency_measurement(sample_decisions):
    """Test LLM decision consistency measurement."""
    analyzer = LLMDecisionQualityAnalyzer()
    analyzer.load_decisions(sample_decisions)

    consistency = analyzer.measure_consistency()

    assert 0 <= consistency <= 100


def test_overall_llm_quality(sample_decisions):
    """Test overall LLM quality metrics calculation."""
    analyzer = LLMDecisionQualityAnalyzer()
    analyzer.load_decisions(sample_decisions)

    metrics = analyzer.calculate_overall_quality()

    assert 0 <= metrics.reasoning_depth <= 100
    assert 0 <= metrics.consistency_score <= 100
    assert metrics.hallucination_count >= 0
    assert metrics.average_response_length >= 0
    assert 0 <= metrics.structured_output_success_rate <= 100


def test_hallucination_detection(sample_decisions_with_hallucinations):
    """Test hallucination detection."""
    detector = HallucinationDetector()
    detector.load_decisions(sample_decisions_with_hallucinations)

    hallucinations = detector.detect_all_hallucinations()

    # Should detect at least the resource hallucination and capability hallucination
    assert len(hallucinations) >= 2

    # Check hallucination types
    types = {h.type for h in hallucinations}
    assert "resource" in types or "capability" in types or "state" in types


def test_risk_profiler_initialization():
    """Test RiskProfiler initialization."""
    profiler = RiskProfiler(agent_id="test_agent")

    assert profiler.agent_id == "test_agent"
    assert not profiler.decisions
    assert not profiler.crisis_decisions


def test_risk_tolerance_calculation(sample_decisions):
    """Test risk tolerance calculation."""
    profiler = RiskProfiler()
    profiler.load_decisions(sample_decisions)

    risk_tolerance = profiler.calculate_risk_tolerance()

    assert 0 <= risk_tolerance.overall_risk_score <= 100
    assert risk_tolerance.crisis_behavior in ["conservative", "moderate", "aggressive"]
    assert 0 <= risk_tolerance.growth_preference <= 100
    assert risk_tolerance.risk_category in [
        "very_conservative",
        "conservative",
        "moderate",
        "aggressive",
        "very_aggressive",
    ]


def test_crisis_decision_identification(_sample_decisions):
    """Test identification of crisis decisions."""
    # Create decisions with crisis conditions
    crisis_decisions = [
        {
            "state": {
                "balance": 15.0,  # Critical
                "compute_hours_remaining": 5.0,
                "has_company": False,
            },
            "action": {"task_work_hours": 4.0, "company_investment_hours": 0, "rest_hours": 0},
            "reasoning": "Crisis mode - focusing on survival",
        },
        {
            "state": {
                "balance": 40.0,  # Moderate crisis
                "compute_hours_remaining": 15.0,
                "has_company": False,
            },
            "action": {"task_work_hours": 4.0, "company_investment_hours": 0, "rest_hours": 0},
            "reasoning": "Building reserves",
        },
    ]

    profiler = RiskProfiler()
    profiler.load_decisions(crisis_decisions)

    assert len(profiler.crisis_decisions) > 0


def test_emergent_behavior_detector_initialization():
    """Test EmergentBehaviorDetector initialization."""
    detector = EmergentBehaviorDetector(agent_id="test_agent")

    assert detector.agent_id == "test_agent"
    assert not detector.decisions
    assert not detector.novel_strategies
    assert not detector.behavior_patterns


def test_novel_strategy_detection(sample_decisions):
    """Test detection of novel strategies."""
    detector = EmergentBehaviorDetector()
    detector.load_decisions(sample_decisions)

    novel_strategies = detector.detect_novel_strategies()

    assert isinstance(novel_strategies, list)
    # May or may not detect strategies depending on decision patterns
    for strategy in novel_strategies:
        assert hasattr(strategy, "strategy_name")
        assert hasattr(strategy, "effectiveness")
        assert hasattr(strategy, "novelty_score")


def test_behavior_pattern_detection(sample_decisions):
    """Test detection of behavior patterns."""
    detector = EmergentBehaviorDetector()
    detector.load_decisions(sample_decisions)

    patterns = detector.detect_behavior_patterns()

    assert isinstance(patterns, list)
    for pattern in patterns:
        assert hasattr(pattern, "pattern_type")
        assert hasattr(pattern, "confidence")


def test_analysis_report_generator_initialization():
    """Test AnalysisReportGenerator initialization."""
    generator = AnalysisReportGenerator(agent_id="test_agent")

    assert generator.agent_id == "test_agent"
    assert generator.decisions == []


def test_comprehensive_analysis_generation(sample_decisions):
    """Test comprehensive analysis generation."""
    generator = AnalysisReportGenerator(agent_id="test_agent")
    generator.load_decisions(sample_decisions)

    analysis = generator.generate_comprehensive_analysis()

    assert analysis.agent_id == "test_agent"
    assert analysis.decisions_analyzed == 30
    assert "alignment_score" in analysis.strategic_alignment
    assert "overall_risk_score" in analysis.risk_profile
    assert "reasoning_depth" in analysis.llm_quality
    assert "novel_strategies_count" in analysis.emergent_behaviors
    assert "overall_performance" in analysis.overall_assessment


def test_markdown_report_generation(sample_decisions):
    """Test markdown report generation."""
    generator = AnalysisReportGenerator(agent_id="test_agent")
    generator.load_decisions(sample_decisions)

    markdown = generator.generate_markdown_report()

    assert "# Agent Behavior Analysis Report" in markdown
    assert "Agent ID:" in markdown
    assert "Overall Performance:" in markdown
    assert "Strategic Alignment" in markdown
    assert "Risk Profile" in markdown


def test_json_report_generation(sample_decisions):
    """Test JSON report generation."""
    generator = AnalysisReportGenerator(agent_id="test_agent")
    generator.load_decisions(sample_decisions)

    json_report = generator.generate_json_report()

    assert json_report["agent_id"] == "test_agent"
    assert json_report["decisions_analyzed"] == 30
    assert "strategic_alignment" in json_report
    assert "risk_profile" in json_report
    assert "llm_quality" in json_report
    assert "emergent_behaviors" in json_report
    assert "overall_assessment" in json_report


def test_export_analysis(sample_decisions, tmp_path):
    """Test exporting decision analysis."""
    analyzer = DecisionPatternAnalyzer()
    analyzer.load_decisions(sample_decisions)

    output_file = tmp_path / "analysis.json"
    results = analyzer.export_analysis(str(output_file))

    assert output_file.exists()
    assert "decisions_analyzed" in results
    assert results["decisions_analyzed"] == 30


def test_export_quality_analysis(sample_decisions, tmp_path):
    """Test exporting LLM quality analysis."""
    analyzer = LLMDecisionQualityAnalyzer()
    analyzer.load_decisions(sample_decisions)

    output_file = tmp_path / "llm_quality.json"
    results = analyzer.export_quality_analysis(str(output_file))

    assert output_file.exists()
    assert "quality_metrics" in results


def test_export_risk_profile(sample_decisions, tmp_path):
    """Test exporting risk profile."""
    profiler = RiskProfiler()
    profiler.load_decisions(sample_decisions)

    output_file = tmp_path / "risk_profile.json"
    results = profiler.export_risk_profile(str(output_file))

    assert output_file.exists()
    assert "risk_tolerance" in results


def test_export_emergent_behaviors(sample_decisions, tmp_path):
    """Test exporting emergent behaviors."""
    detector = EmergentBehaviorDetector()
    detector.load_decisions(sample_decisions)

    output_file = tmp_path / "emergent_behaviors.json"
    results = detector.export_emergent_behaviors(str(output_file))

    assert output_file.exists()
    assert "novel_strategies" in results
    assert "behavior_patterns" in results

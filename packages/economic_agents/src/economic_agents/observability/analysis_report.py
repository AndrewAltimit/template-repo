"""Comprehensive analysis report generation for observability metrics.

Combines all observability components into cohesive analysis reports for research and study.
"""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from economic_agents.observability.decision_analyzer import DecisionPatternAnalyzer
from economic_agents.observability.emergent_behavior import EmergentBehaviorDetector
from economic_agents.observability.llm_quality import HallucinationDetector, LLMDecisionQualityAnalyzer
from economic_agents.observability.risk_profiler import RiskProfiler


@dataclass
class ComprehensiveAnalysis:
    """Complete analysis of agent behavior."""

    agent_id: str
    timestamp: datetime
    decisions_analyzed: int
    strategic_alignment: dict[str, Any]
    risk_profile: dict[str, Any]
    llm_quality: dict[str, Any]
    emergent_behaviors: dict[str, Any]
    overall_assessment: dict[str, Any]


class AnalysisReportGenerator:
    """Generates comprehensive behavior analysis reports."""

    def __init__(self, agent_id: str, log_dir: str | None = None):
        """Initialize report generator.

        Args:
            agent_id: Agent identifier
            log_dir: Directory to save reports
        """
        self.agent_id = agent_id
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/observability/reports")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize all analyzers
        self.decision_analyzer = DecisionPatternAnalyzer(agent_id, log_dir)
        self.llm_analyzer = LLMDecisionQualityAnalyzer(agent_id, log_dir)
        self.risk_profiler = RiskProfiler(agent_id, log_dir)
        self.behavior_detector = EmergentBehaviorDetector(agent_id, log_dir)
        self.hallucination_detector = HallucinationDetector()

        self.decisions: list[dict[str, Any]] = []

    def load_decisions(self, decisions: list[dict[str, Any]]):
        """Load decision history into all analyzers.

        Args:
            decisions: List of decision records
        """
        self.decisions = decisions

        # Load into all analyzers
        self.decision_analyzer.load_decisions(decisions)
        self.llm_analyzer.load_decisions(decisions)
        self.risk_profiler.load_decisions(decisions)
        self.behavior_detector.load_decisions(decisions)
        self.hallucination_detector.load_decisions(decisions)

    def generate_comprehensive_analysis(self, stated_strategy: dict[str, Any] | None = None) -> ComprehensiveAnalysis:
        """Generate complete behavior analysis report.

        Args:
            stated_strategy: Agent's stated strategic objectives

        Returns:
            Comprehensive analysis with all metrics
        """
        # Run all analyses
        alignment = self.decision_analyzer.analyze_strategic_consistency(stated_strategy)
        risk_tolerance = self.risk_profiler.calculate_risk_tolerance()
        llm_quality = self.llm_analyzer.calculate_overall_quality()
        hallucinations = self.hallucination_detector.detect_all_hallucinations()
        novel_strategies = self.behavior_detector.detect_novel_strategies()
        behavior_patterns = self.behavior_detector.detect_behavior_patterns()

        # Calculate overall assessment
        overall = self._calculate_overall_assessment(alignment, risk_tolerance, llm_quality, hallucinations, novel_strategies)

        return ComprehensiveAnalysis(
            agent_id=self.agent_id,
            timestamp=datetime.now(),
            decisions_analyzed=len(self.decisions),
            strategic_alignment={
                "alignment_score": alignment.alignment_score,
                "consistency_score": alignment.consistency_score,
                "deviations_count": len(alignment.deviations),
                "recommendations": alignment.recommendations,
            },
            risk_profile={
                "overall_risk_score": risk_tolerance.overall_risk_score,
                "risk_category": risk_tolerance.risk_category,
                "crisis_behavior": risk_tolerance.crisis_behavior,
                "growth_preference": risk_tolerance.growth_preference,
                "risk_adjusted_returns": risk_tolerance.risk_adjusted_returns,
            },
            llm_quality={
                "reasoning_depth": llm_quality.reasoning_depth,
                "consistency_score": llm_quality.consistency_score,
                "hallucination_count": llm_quality.hallucination_count,
                "average_response_length": llm_quality.average_response_length,
                "structured_output_success_rate": llm_quality.structured_output_success_rate,
            },
            emergent_behaviors={
                "novel_strategies_count": len(novel_strategies),
                "novel_strategies": [
                    {
                        "name": s.strategy_name,
                        "description": s.description,
                        "effectiveness": s.effectiveness,
                        "novelty_score": s.novelty_score,
                    }
                    for s in novel_strategies
                ],
                "behavior_patterns_count": len(behavior_patterns),
                "behavior_patterns": [
                    {"type": p.pattern_type, "description": p.description, "confidence": p.confidence}
                    for p in behavior_patterns
                ],
            },
            overall_assessment=overall,
        )

    def _calculate_overall_assessment(
        self, alignment, risk_tolerance, llm_quality, hallucinations, novel_strategies
    ) -> dict[str, Any]:
        """Calculate overall assessment of agent performance.

        Args:
            alignment: Strategic alignment metrics
            risk_tolerance: Risk profile
            llm_quality: LLM quality metrics
            hallucinations: List of hallucinations
            novel_strategies: List of novel strategies

        Returns:
            Overall assessment dictionary
        """
        # Calculate composite scores
        decision_quality_score = (alignment.alignment_score + alignment.consistency_score) / 2

        llm_reliability_score = (
            llm_quality.reasoning_depth + llm_quality.consistency_score + llm_quality.structured_output_success_rate
        ) / 3

        # Deduct points for hallucinations
        hallucination_penalty = min(llm_quality.hallucination_count * 5, 30)
        llm_reliability_score = max(0, llm_reliability_score - hallucination_penalty)

        # Innovation score based on novel strategies
        innovation_score = min(len(novel_strategies) * 20, 100)

        # Overall performance
        overall_performance = (decision_quality_score + llm_reliability_score) / 2

        # Generate assessment
        if overall_performance >= 80:
            performance_rating = "Excellent"
            summary = "Agent demonstrates high-quality decision-making with strong strategic alignment."
        elif overall_performance >= 60:
            performance_rating = "Good"
            summary = "Agent shows solid performance with room for improvement in consistency."
        elif overall_performance >= 40:
            performance_rating = "Fair"
            summary = "Agent exhibits acceptable performance but significant improvement areas exist."
        else:
            performance_rating = "Poor"
            summary = "Agent shows substantial performance issues requiring intervention."

        # Risk assessment
        risk_category = risk_tolerance.risk_category
        if risk_category in ["very_aggressive", "aggressive"]:
            risk_assessment = "High risk tolerance - may make bold moves but vulnerable to setbacks"
        elif risk_category in ["very_conservative", "conservative"]:
            risk_assessment = "Low risk tolerance - stable but may miss growth opportunities"
        else:
            risk_assessment = "Moderate risk tolerance - balanced approach to growth and survival"

        # Key strengths and weaknesses
        strengths = []
        weaknesses = []

        if alignment.alignment_score >= 70:
            strengths.append("Strong strategic alignment")
        else:
            weaknesses.append("Inconsistent strategy execution")

        if llm_quality.reasoning_depth >= 70:
            strengths.append("Deep analytical reasoning")
        else:
            weaknesses.append("Superficial decision reasoning")

        if llm_quality.hallucination_count == 0:
            strengths.append("No hallucinations detected")
        elif llm_quality.hallucination_count > 5:
            weaknesses.append(f"High hallucination rate ({llm_quality.hallucination_count} detected)")

        if len(novel_strategies) >= 3:
            strengths.append(f"Innovative ({len(novel_strategies)} novel strategies)")

        return {
            "overall_performance": overall_performance,
            "performance_rating": performance_rating,
            "summary": summary,
            "decision_quality_score": decision_quality_score,
            "llm_reliability_score": llm_reliability_score,
            "innovation_score": innovation_score,
            "risk_assessment": risk_assessment,
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

    def generate_markdown_report(self, analysis: ComprehensiveAnalysis | None = None, output_path: str | None = None) -> str:
        """Generate human-readable markdown report.

        Args:
            analysis: Pre-computed analysis (or will compute if None)
            output_path: Path to save markdown file

        Returns:
            Markdown report text
        """
        if analysis is None:
            analysis = self.generate_comprehensive_analysis()

        report = f"""# Agent Behavior Analysis Report

**Agent ID:** {analysis.agent_id}
**Analysis Date:** {analysis.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
**Decisions Analyzed:** {analysis.decisions_analyzed}

---

## Executive Summary

{analysis.overall_assessment["summary"]}

**Overall Performance:** {analysis.overall_assessment["overall_performance"]:.1f}/100
({analysis.overall_assessment["performance_rating"]})

### Key Metrics
- **Decision Quality:** {analysis.overall_assessment["decision_quality_score"]:.1f}/100
- **LLM Reliability:** {analysis.overall_assessment["llm_reliability_score"]:.1f}/100
- **Innovation Score:** {analysis.overall_assessment["innovation_score"]:.1f}/100

### Strengths
{self._format_list(analysis.overall_assessment["strengths"])}

### Areas for Improvement
{self._format_list(analysis.overall_assessment["weaknesses"])}

---

## Strategic Alignment

**Alignment Score:** {analysis.strategic_alignment["alignment_score"]:.1f}/100
**Consistency Score:** {analysis.strategic_alignment["consistency_score"]:.1f}/100
**Strategy Deviations:** {analysis.strategic_alignment["deviations_count"]}

### Recommendations
{self._format_list(analysis.strategic_alignment["recommendations"])}

---

## Risk Profile

**Risk Category:** {analysis.risk_profile["risk_category"].replace("_", " ").title()}
**Overall Risk Score:** {analysis.risk_profile["overall_risk_score"]:.1f}/100
**Crisis Behavior:** {analysis.risk_profile["crisis_behavior"].title()}
**Growth vs Survival Preference:** {analysis.risk_profile["growth_preference"]:.1f}/100 (0=survival, 100=growth)

{analysis.overall_assessment["risk_assessment"]}

---

## LLM Decision Quality

**Reasoning Depth:** {analysis.llm_quality["reasoning_depth"]:.1f}/100
**Decision Consistency:** {analysis.llm_quality["consistency_score"]:.1f}/100
**Structured Output Success:** {analysis.llm_quality["structured_output_success_rate"]:.1f}%
**Average Response Length:** {analysis.llm_quality["average_response_length"]:.0f} characters
**Hallucinations Detected:** {analysis.llm_quality["hallucination_count"]}

---

## Emergent Behaviors

### Novel Strategies ({analysis.emergent_behaviors["novel_strategies_count"]} detected)

"""

        # Add novel strategies
        for strategy in analysis.emergent_behaviors["novel_strategies"]:
            report += f"""
**{strategy["name"]}**
{strategy["description"]}
- Effectiveness: {strategy["effectiveness"]:.1f}/100
- Novelty: {strategy["novelty_score"]:.1f}/100

"""

        # Add behavior patterns
        report += f"""
### Behavioral Patterns ({analysis.emergent_behaviors["behavior_patterns_count"]} identified)

"""

        for pattern in analysis.emergent_behaviors["behavior_patterns"]:
            report += f"""
**{pattern["type"].replace("_", " ").title()}**
{pattern["description"]}
- Confidence: {pattern["confidence"]:.1f}/100

"""

        report += "\n---\n\n## Analysis Complete\n"

        # Save to file if path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)

        return report

    def generate_json_report(
        self, analysis: ComprehensiveAnalysis | None = None, output_path: str | None = None
    ) -> dict[str, Any]:
        """Generate machine-readable JSON report.

        Args:
            analysis: Pre-computed analysis (or will compute if None)
            output_path: Path to save JSON file

        Returns:
            JSON-serializable dictionary
        """
        if analysis is None:
            analysis = self.generate_comprehensive_analysis()

        report = {
            "agent_id": analysis.agent_id,
            "timestamp": analysis.timestamp.isoformat(),
            "decisions_analyzed": analysis.decisions_analyzed,
            "strategic_alignment": analysis.strategic_alignment,
            "risk_profile": analysis.risk_profile,
            "llm_quality": analysis.llm_quality,
            "emergent_behaviors": analysis.emergent_behaviors,
            "overall_assessment": analysis.overall_assessment,
        }

        # Save to file if path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

        return report

    def _format_list(self, items: list[str]) -> str:
        """Format list items for markdown.

        Args:
            items: List of strings

        Returns:
            Markdown formatted list
        """
        if not items:
            return "- None identified\n"

        return "\n".join(f"- {item}" for item in items) + "\n"

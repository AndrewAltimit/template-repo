"""Decision pattern analysis for autonomous agents.

Analyzes long-term agent decision patterns, strategic consistency, and behavioral trends.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class StrategyAlignment:
    """Measures alignment between stated strategy and actual decisions."""

    alignment_score: float  # 0-100
    consistency_score: float  # 0-100
    deviations: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RiskProfile:
    """Agent's revealed risk tolerance and crisis behavior."""

    risk_tolerance: float  # 0-100 (0=extremely conservative, 100=extremely aggressive)
    bankruptcy_proximity_behavior: str  # "conservative", "moderate", "aggressive"
    growth_vs_survival_preference: float  # 0-100 (0=pure survival, 100=pure growth)
    crisis_decision_quality: float  # 0-100
    recovery_pattern: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DecisionTrend:
    """Trend analysis for specific decision metrics."""

    metric_name: str
    values: list[float]
    timestamps: list[datetime]
    trend_direction: str  # "increasing", "decreasing", "stable", "volatile"
    change_rate: float  # Average change per decision
    volatility: float  # Standard deviation


class DecisionPatternAnalyzer:
    """Analyzes long-term agent decision patterns and behavioral trends."""

    def __init__(self, agent_id: str | None = None, log_dir: str | None = None):
        """Initialize decision pattern analyzer.

        Args:
            agent_id: Agent identifier for analysis
            log_dir: Directory to save analysis results
        """
        self.agent_id = agent_id
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/observatory")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.decisions: list[dict[str, Any]] = []
        self.state_history: list[dict[str, Any]] = []

    def load_decisions(self, decisions: list[dict[str, Any]]):
        """Load decision history for analysis.

        Args:
            decisions: List of decision records with state, action, reasoning
        """
        self.decisions = decisions
        self.state_history = [d.get("state", {}) for d in decisions]

    def analyze_strategic_consistency(self, stated_strategy: dict[str, Any] | None = None) -> StrategyAlignment:
        """Analyze consistency between stated strategy and actual decisions.

        Args:
            stated_strategy: Agent's stated strategic objectives and preferences

        Returns:
            StrategyAlignment with consistency metrics and deviations
        """
        if not self.decisions:
            return StrategyAlignment(
                alignment_score=0.0,
                consistency_score=0.0,
                deviations=[],
                recommendations=["Load decision history first"],
            )

        # Default strategy if none provided
        if stated_strategy is None:
            stated_strategy = {
                "objective": "survive and grow",
                "risk_tolerance": "moderate",
                "priorities": ["survival", "capital_accumulation", "growth"],
            }

        # Calculate alignment metrics
        alignment_scores = []
        deviations = []

        for i, decision in enumerate(self.decisions):
            state = decision.get("state", {})
            action = decision.get("action", {})
            reasoning = decision.get("reasoning", "")

            # Check alignment with stated objectives
            alignment = self._calculate_decision_alignment(action, state, stated_strategy)
            alignment_scores.append(alignment)

            # Identify significant deviations
            if alignment < 50:  # Below threshold
                deviations.append(
                    {
                        "cycle": i,
                        "alignment_score": alignment,
                        "state": state,
                        "action": action,
                        "reasoning": reasoning[:200],  # Truncate for readability
                    }
                )

        # Calculate overall scores
        alignment_score = np.mean(alignment_scores) if alignment_scores else 0.0
        consistency_score = (100 - np.std(alignment_scores)) if len(alignment_scores) > 1 else 100.0
        consistency_score = max(0, min(100, consistency_score))  # Clamp to 0-100

        # Generate recommendations
        recommendations = []
        if alignment_score < 50:
            recommendations.append("Review decision-making process for strategic drift")
        if consistency_score < 50:
            recommendations.append("High inconsistency detected - review decision stability")
        if len(deviations) > len(self.decisions) * 0.2:
            recommendations.append("More than 20% of decisions deviate from strategy")

        return StrategyAlignment(
            alignment_score=alignment_score,
            consistency_score=consistency_score,
            deviations=deviations,
            recommendations=recommendations,
        )

    def analyze_decision_trends(self, metric: str, window: int = 20) -> DecisionTrend:
        """Analyze trends for a specific decision metric over time.

        Args:
            metric: Metric to analyze (e.g., "task_work_hours", "company_investment")
            window: Number of recent decisions to analyze

        Returns:
            DecisionTrend with trend analysis
        """
        if not self.decisions:
            return DecisionTrend(
                metric_name=metric,
                values=[],
                timestamps=[],
                trend_direction="unknown",
                change_rate=0.0,
                volatility=0.0,
            )

        # Extract metric values
        recent_decisions = self.decisions[-window:]
        values = []
        timestamps = []

        for decision in recent_decisions:
            action = decision.get("action", {})
            timestamp = decision.get("timestamp")

            # Extract metric value from action
            value = action.get(metric, 0.0)
            values.append(value)
            if timestamp:
                timestamps.append(datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp)

        # Calculate trend metrics
        if len(values) < 2:
            trend_direction = "stable"
            change_rate = 0.0
            volatility = 0.0
        else:
            # Linear regression for trend
            x = np.arange(len(values))
            slope, _ = np.polyfit(x, values, 1)

            # Determine trend direction
            if abs(slope) < 0.01:
                trend_direction = "stable"
            elif slope > 0.05:
                trend_direction = "increasing"
            elif slope < -0.05:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"

            change_rate = slope
            volatility = np.std(values)

        return DecisionTrend(
            metric_name=metric,
            values=values,
            timestamps=timestamps,
            trend_direction=trend_direction,
            change_rate=change_rate,
            volatility=volatility,
        )

    def calculate_decision_quality_over_time(self) -> list[float]:
        """Calculate decision quality scores over time.

        Returns:
            List of quality scores (0-100) for each decision
        """
        if not self.decisions:
            return []

        quality_scores = []

        for i, decision in enumerate(self.decisions):
            state = decision.get("state", {})
            action = decision.get("action", {})

            # Quality factors
            scores = []

            # 1. Resource conservation (don't overspend)
            balance = state.get("balance", 0)
            compute_hours = state.get("compute_hours_remaining", 0)
            if balance > 50 and compute_hours > 20:
                scores.append(100)
            elif balance > 20 and compute_hours > 10:
                scores.append(70)
            else:
                scores.append(30)

            # 2. Reasonable resource allocation
            task_hours = action.get("task_work_hours", 0)
            if 0 <= task_hours <= 8:  # Reasonable work hours
                scores.append(100)
            else:
                scores.append(50)

            # 3. Strategic coherence (if company exists, invest in it)
            company_exists = state.get("has_company", False)
            company_investment = action.get("company_investment_hours", 0)
            if company_exists and company_investment > 0:
                scores.append(100)
            elif not company_exists and company_investment == 0:
                scores.append(100)
            else:
                scores.append(50)

            # Overall quality
            quality = np.mean(scores) if scores else 50.0
            quality_scores.append(quality)

        return quality_scores

    def _calculate_decision_alignment(self, action: dict[str, Any], state: dict[str, Any], strategy: dict[str, Any]) -> float:
        """Calculate how well a decision aligns with stated strategy.

        Args:
            action: Decision action taken
            state: Agent state at decision time
            strategy: Stated strategic objectives

        Returns:
            Alignment score (0-100)
        """
        scores = []

        # Check survival priority alignment
        if "survival" in strategy.get("priorities", []):
            balance = state.get("balance", 0)
            if balance < 50:  # Low balance - should prioritize survival
                task_hours = action.get("task_work_hours", 0)
                if task_hours > 0:
                    scores.append(100)  # Good - working to earn money
                else:
                    scores.append(30)  # Bad - not working when broke
            else:
                scores.append(100)  # Not in survival crisis

        # Check growth priority alignment
        if "growth" in strategy.get("priorities", []):
            balance = state.get("balance", 0)
            if balance > 100:  # Sufficient capital for growth
                company_investment = action.get("company_investment_hours", 0)
                if company_investment > 0:
                    scores.append(100)  # Good - investing in growth
                else:
                    scores.append(50)  # Neutral - could invest more
            else:
                scores.append(100)  # Not yet ready for growth

        # Check risk tolerance alignment
        risk_tolerance = strategy.get("risk_tolerance", "moderate")
        balance = state.get("balance", 0)
        compute_hours = state.get("compute_hours_remaining", 0)

        if risk_tolerance == "conservative" and (balance < 50 or compute_hours < 20):
            # Conservative strategy - should be cautious when resources low
            task_hours = action.get("task_work_hours", 0)
            if task_hours > 0:
                scores.append(100)
            else:
                scores.append(30)
        elif risk_tolerance == "aggressive":
            # Aggressive strategy - can take more risks
            scores.append(100)
        else:
            # Moderate risk tolerance
            scores.append(100)

        return np.mean(scores) if scores else 50.0

    def export_analysis(self, output_path: str | None = None):
        """Export analysis results to JSON file.

        Args:
            output_path: Path to save analysis results
        """
        output_file: Path
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.log_dir / f"decision_analysis_{timestamp}.json"
        else:
            output_file = Path(output_path)

        # Run all analyses
        alignment = self.analyze_strategic_consistency()
        quality_scores = self.calculate_decision_quality_over_time()

        # Compile results
        results = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "decisions_analyzed": len(self.decisions),
            "strategic_alignment": {
                "alignment_score": alignment.alignment_score,
                "consistency_score": alignment.consistency_score,
                "deviations_count": len(alignment.deviations),
                "recommendations": alignment.recommendations,
            },
            "decision_quality": {
                "average_quality": float(np.mean(quality_scores)) if quality_scores else 0.0,
                "min_quality": float(np.min(quality_scores)) if quality_scores else 0.0,
                "max_quality": float(np.max(quality_scores)) if quality_scores else 0.0,
                "quality_trend": (
                    "improving" if len(quality_scores) > 10 and quality_scores[-5:] > quality_scores[:5] else "stable"
                ),
            },
        }

        # Save to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

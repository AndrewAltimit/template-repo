"""LLM decision quality analysis and hallucination detection.

Measures the quality of LLM-based decision-making, including reasoning depth,
consistency, and detection of hallucinations or invalid decisions.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class LLMQualityMetrics:
    """Comprehensive LLM decision quality metrics."""

    reasoning_depth: float  # 0-100
    consistency_score: float  # 0-100
    hallucination_count: int
    average_response_length: float
    structured_output_success_rate: float  # 0-100
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Hallucination:
    """Detected hallucination in LLM decision."""

    cycle: int
    type: str  # "resource", "capability", "state", "other"
    description: str
    severity: str  # "low", "medium", "high", "critical"
    decision_text: str
    state_at_time: dict[str, Any]


class LLMDecisionQualityAnalyzer:
    """Analyzes the quality of LLM-based decision-making."""

    def __init__(self, agent_id: str | None = None, log_dir: str | None = None):
        """Initialize LLM quality analyzer.

        Args:
            agent_id: Agent identifier
            log_dir: Directory to save analysis results
        """
        self.agent_id = agent_id
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/observability")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.decisions: list[dict[str, Any]] = []

    def load_decisions(self, decisions: list[dict[str, Any]]):
        """Load LLM decision history for analysis.

        Args:
            decisions: List of LLM decisions with prompts, responses, reasoning
        """
        self.decisions = decisions

    def measure_reasoning_depth(self, decision: dict[str, Any]) -> float:
        """Measure how thorough the LLM's reasoning was.

        Args:
            decision: LLM decision record

        Returns:
            Reasoning depth score (0-100)
        """
        reasoning = decision.get("reasoning", "")

        if not reasoning:
            return 0.0

        # Factors that indicate deep reasoning
        scores = []

        # 1. Length (longer reasoning suggests more thought)
        length_score = min(len(reasoning) / 500 * 100, 100)
        scores.append(length_score)

        # 2. Contains numbers/calculations
        if re.search(r"\d+\.?\d*", reasoning):
            scores.append(100)
        else:
            scores.append(50)

        # 3. Contains conditional reasoning ("if", "because", "therefore")
        reasoning_keywords = ["if", "because", "therefore", "since", "thus", "however", "although"]
        keyword_count = sum(1 for word in reasoning_keywords if word in reasoning.lower())
        keyword_score = min(keyword_count / 3 * 100, 100)
        scores.append(keyword_score)

        # 4. Contains multiple considerations
        sentences = reasoning.split(".")
        consideration_score = min(len(sentences) / 5 * 100, 100)
        scores.append(consideration_score)

        # 5. References state variables (shows awareness)
        state_keywords = [
            "balance",
            "compute",
            "hours",
            "task",
            "company",
            "revenue",
            "expense",
        ]
        state_ref_count = sum(1 for word in state_keywords if word in reasoning.lower())
        state_score = min(state_ref_count / 3 * 100, 100)
        scores.append(state_score)

        return float(np.mean(scores))

    def measure_consistency(self, window: int = 10) -> float:
        """Measure how consistent decisions are in similar states.

        Args:
            window: Number of recent decisions to analyze

        Returns:
            Consistency score (0-100)
        """
        if len(self.decisions) < 2:
            return 100.0  # Default to perfect if insufficient data

        recent_decisions = self.decisions[-window:]

        # Group similar states
        state_clusters = self._cluster_similar_states(recent_decisions)

        if not state_clusters:
            return 100.0

        # Measure decision variance within clusters
        consistency_scores = []
        for cluster in state_clusters:
            if len(cluster) < 2:
                continue

            # Extract actions from cluster
            actions = [d.get("action", {}) for d in cluster]

            # Calculate variance for each action dimension
            variances = []
            for key in ["task_work_hours", "company_investment_hours", "rest_hours"]:
                values = [a.get(key, 0.0) for a in actions]
                if len(values) > 1:
                    variance = np.std(values)
                    # Normalize variance to 0-100 scale (lower variance = higher consistency)
                    consistency = max(0, 100 - variance * 20)
                    variances.append(consistency)

            if variances:
                consistency_scores.append(np.mean(variances))

        return np.mean(consistency_scores) if consistency_scores else 100.0

    def calculate_overall_quality(self) -> LLMQualityMetrics:
        """Calculate comprehensive LLM quality metrics.

        Returns:
            LLMQualityMetrics with all quality measurements
        """
        if not self.decisions:
            return LLMQualityMetrics(
                reasoning_depth=0.0,
                consistency_score=0.0,
                hallucination_count=0,
                average_response_length=0.0,
                structured_output_success_rate=0.0,
            )

        # Measure reasoning depth for all decisions
        reasoning_depths = [self.measure_reasoning_depth(d) for d in self.decisions]
        avg_reasoning_depth = np.mean(reasoning_depths) if reasoning_depths else 0.0

        # Measure consistency
        consistency = self.measure_consistency()

        # Count hallucinations
        hallucination_detector = HallucinationDetector()
        hallucination_detector.load_decisions(self.decisions)
        hallucinations = hallucination_detector.detect_all_hallucinations()

        # Calculate response lengths
        response_lengths = [len(d.get("reasoning", "")) for d in self.decisions]
        avg_response_length = np.mean(response_lengths) if response_lengths else 0.0

        # Check structured output success rate
        successful_parses = sum(1 for d in self.decisions if d.get("action") is not None and isinstance(d.get("action"), dict))
        success_rate = (successful_parses / len(self.decisions) * 100) if self.decisions else 0.0

        return LLMQualityMetrics(
            reasoning_depth=float(avg_reasoning_depth),
            consistency_score=float(consistency),
            hallucination_count=len(hallucinations),
            average_response_length=float(avg_response_length),
            structured_output_success_rate=success_rate,
        )

    def _cluster_similar_states(
        self, decisions: list[dict[str, Any]], similarity_threshold: float = 0.2
    ) -> list[list[dict[str, Any]]]:
        """Cluster decisions with similar agent states.

        Args:
            decisions: List of decisions to cluster
            similarity_threshold: Maximum difference to be considered similar

        Returns:
            List of decision clusters
        """
        if not decisions:
            return []

        clusters: list[list[dict[str, Any]]] = []

        for decision in decisions:
            state = decision.get("state", {})

            # Find matching cluster
            matched = False
            for cluster in clusters:
                cluster_state = cluster[0].get("state", {})

                # Calculate state similarity
                if self._states_similar(state, cluster_state, similarity_threshold):
                    cluster.append(decision)
                    matched = True
                    break

            # Create new cluster if no match
            if not matched:
                clusters.append([decision])

        return clusters

    def _states_similar(self, state1: dict[str, Any], state2: dict[str, Any], threshold: float) -> bool:
        """Check if two states are similar.

        Args:
            state1: First state
            state2: Second state
            threshold: Similarity threshold (0-1)

        Returns:
            True if states are similar
        """
        # Compare key state variables
        balance1 = state1.get("balance", 0)
        balance2 = state2.get("balance", 0)

        compute1 = state1.get("compute_hours_remaining", 0)
        compute2 = state2.get("compute_hours_remaining", 0)

        # Normalize differences
        balance_diff = abs(balance1 - balance2) / max(balance1, balance2, 1)
        compute_diff = abs(compute1 - compute2) / max(compute1, compute2, 1)

        # Average difference
        avg_diff = (balance_diff + compute_diff) / 2

        return bool(avg_diff <= threshold)

    def export_quality_analysis(self, output_path: str | None = None):
        """Export quality analysis to JSON file.

        Args:
            output_path: Path to save analysis results
        """
        output_file: Path
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.log_dir / f"llm_quality_{timestamp}.json"
        else:
            output_file = Path(output_path)

        # Calculate metrics
        metrics = self.calculate_overall_quality()

        # Compile results
        results = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "decisions_analyzed": len(self.decisions),
            "quality_metrics": {
                "reasoning_depth": metrics.reasoning_depth,
                "consistency_score": metrics.consistency_score,
                "hallucination_count": metrics.hallucination_count,
                "average_response_length": metrics.average_response_length,
                "structured_output_success_rate": metrics.structured_output_success_rate,
            },
        }

        # Save to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results


class HallucinationDetector:
    """Detects hallucinations in LLM decisions."""

    def __init__(self):
        """Initialize hallucination detector."""
        self.decisions: list[dict[str, Any]] = []
        self.hallucinations: list[Hallucination] = []

    def load_decisions(self, decisions: list[dict[str, Any]]):
        """Load decision history for hallucination detection.

        Args:
            decisions: List of LLM decisions
        """
        self.decisions = decisions

    def detect_all_hallucinations(self) -> list[Hallucination]:
        """Detect all hallucinations across decision history.

        Returns:
            List of detected hallucinations
        """
        self.hallucinations = []

        for i, decision in enumerate(self.decisions):
            state = decision.get("state", {})
            action = decision.get("action", {})
            reasoning = decision.get("reasoning", "")

            # Check for resource hallucinations
            self._check_resource_hallucinations(i, state, action, reasoning)

            # Check for capability hallucinations
            self._check_capability_hallucinations(i, state, action, reasoning)

            # Check for state hallucinations
            self._check_state_hallucinations(i, state, reasoning)

        return self.hallucinations

    def _check_resource_hallucinations(self, cycle: int, state: dict[str, Any], action: dict[str, Any], reasoning: str):
        """Check for hallucinations about available resources.

        Args:
            cycle: Decision cycle number
            state: Agent state
            action: Decision action
            reasoning: LLM reasoning text
        """
        # Check compute hours
        compute_available = state.get("compute_hours_remaining", 0)
        task_hours = action.get("task_work_hours", 0)
        company_hours = action.get("company_investment_hours", 0)
        total_hours = task_hours + company_hours

        if total_hours > compute_available:
            self.hallucinations.append(
                Hallucination(
                    cycle=cycle,
                    type="resource",
                    description=f"Allocated {total_hours}h compute but only {compute_available}h available",
                    severity="critical",
                    decision_text=reasoning[:200],
                    state_at_time=state,
                )
            )

        # Check balance for investments
        balance = state.get("balance", 0)
        if "invest" in reasoning.lower() and balance < 10:
            self.hallucinations.append(
                Hallucination(
                    cycle=cycle,
                    type="resource",
                    description=f"Mentioned investment with low balance (${balance})",
                    severity="medium",
                    decision_text=reasoning[:200],
                    state_at_time=state,
                )
            )

    def _check_capability_hallucinations(self, cycle: int, state: dict[str, Any], action: dict[str, Any], reasoning: str):
        """Check for hallucinations about agent capabilities.

        Args:
            cycle: Decision cycle number
            state: Agent state
            action: Decision action
            reasoning: LLM reasoning text
        """
        # Check for company-related hallucinations
        has_company = state.get("has_company", False)

        if not has_company:
            # Keywords suggesting company operations when no company exists
            company_keywords = ["company", "team", "employees", "sub-agent", "scaling"]
            for keyword in company_keywords:
                if keyword in reasoning.lower():
                    self.hallucinations.append(
                        Hallucination(
                            cycle=cycle,
                            type="capability",
                            description=f"Mentioned '{keyword}' but no company exists",
                            severity="low",
                            decision_text=reasoning[:200],
                            state_at_time=state,
                        )
                    )
                    break  # Only record once per decision

    def _check_state_hallucinations(self, cycle: int, state: dict[str, Any], reasoning: str):
        """Check for hallucinations about current state.

        Args:
            cycle: Decision cycle number
            state: Agent state
            reasoning: LLM reasoning text
        """
        # Check for incorrect state claims
        balance = state.get("balance", 0)

        if "plenty of money" in reasoning.lower() and balance < 50:
            self.hallucinations.append(
                Hallucination(
                    cycle=cycle,
                    type="state",
                    description=f"Claimed 'plenty of money' but balance is ${balance}",
                    severity="medium",
                    decision_text=reasoning[:200],
                    state_at_time=state,
                )
            )

        if "low on funds" in reasoning.lower() and balance > 100:
            self.hallucinations.append(
                Hallucination(
                    cycle=cycle,
                    type="state",
                    description=f"Claimed 'low on funds' but balance is ${balance}",
                    severity="low",
                    decision_text=reasoning[:200],
                    state_at_time=state,
                )
            )

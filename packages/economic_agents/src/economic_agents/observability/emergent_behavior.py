"""Emergent behavior detection for autonomous agents.

Detects novel strategies, unexpected patterns, and emergent coordination behaviors
that were not explicitly programmed.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class NovelStrategy:
    """Detected novel or unexpected agent strategy."""

    strategy_name: str
    description: str
    frequency: int  # How many times observed
    effectiveness: float  # 0-100 (how well it worked)
    first_observed_cycle: int
    example_decisions: list[dict[str, Any]]
    novelty_score: float  # 0-100 (how unexpected)


@dataclass
class BehaviorPattern:
    """Identified behavioral pattern."""

    pattern_type: str  # "cyclical", "adaptive", "opportunistic", "conservative", etc.
    description: str
    occurrences: int
    confidence: float  # 0-100
    examples: list[int]  # Cycle numbers where pattern observed


class EmergentBehaviorDetector:
    """Detects unexpected and novel agent behaviors."""

    def __init__(self, agent_id: str | None = None, log_dir: str | None = None):
        """Initialize emergent behavior detector.

        Args:
            agent_id: Agent identifier
            log_dir: Directory to save detection results
        """
        self.agent_id = agent_id
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/observability")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.decisions: list[dict[str, Any]] = []
        self.novel_strategies: list[NovelStrategy] = []
        self.behavior_patterns: list[BehaviorPattern] = []

    def load_decisions(self, decisions: list[dict[str, Any]]):
        """Load decision history for analysis.

        Args:
            decisions: List of decision records
        """
        self.decisions = decisions

    def detect_novel_strategies(self) -> list[NovelStrategy]:
        """Identify strategies not explicitly programmed.

        Returns:
            List of novel strategies detected
        """
        if not self.decisions:
            return []

        self.novel_strategies = []

        # Strategy 1: Aggressive early growth (risky but potentially rewarding)
        self._detect_aggressive_early_growth()

        # Strategy 2: Resource hoarding (accumulating before action)
        self._detect_resource_hoarding()

        # Strategy 3: Cyclical investment (alternating between survival and growth)
        self._detect_cyclical_investment()

        # Strategy 4: Opportunistic spending (big investments after windfalls)
        self._detect_opportunistic_spending()

        # Strategy 5: Conservative stockpiling (maintaining large reserves)
        self._detect_conservative_stockpiling()

        return self.novel_strategies

    def detect_behavior_patterns(self) -> list[BehaviorPattern]:
        """Detect recurring behavioral patterns.

        Returns:
            List of identified patterns
        """
        if not self.decisions:
            return []

        self.behavior_patterns = []

        # Pattern 1: Cyclical behavior
        self._detect_cyclical_patterns()

        # Pattern 2: Adaptive behavior (changing strategy based on results)
        self._detect_adaptive_behavior()

        # Pattern 3: Threshold-based behavior (sudden changes at resource levels)
        self._detect_threshold_behavior()

        return self.behavior_patterns

    def _detect_aggressive_early_growth(self):
        """Detect strategy of aggressive company investment early on."""
        # Look at first 20 decisions
        early_decisions = self.decisions[:20]

        aggressive_growth_count = 0
        examples = []

        for i, decision in enumerate(early_decisions):
            state = decision.get("state", {})
            action = decision.get("action", {})

            balance = state.get("balance", 0)
            company_hours = action.get("company_investment_hours", 0)

            # Aggressive: investing in company when balance < 100
            if balance < 100 and company_hours > 0:
                aggressive_growth_count += 1
                examples.append(decision)

        if aggressive_growth_count >= 5:  # At least 5 instances
            # Calculate effectiveness
            if len(self.decisions) > 20:
                initial_balance = self.decisions[0].get("state", {}).get("balance", 0)
                later_balance = self.decisions[20].get("state", {}).get("balance", 0)
                effectiveness = min(100, max(0, (later_balance - initial_balance) / 100 * 100))
            else:
                effectiveness = 50.0

            self.novel_strategies.append(
                NovelStrategy(
                    strategy_name="Aggressive Early Growth",
                    description="Investing heavily in company formation despite limited resources in early cycles",
                    frequency=aggressive_growth_count,
                    effectiveness=effectiveness,
                    first_observed_cycle=0,
                    example_decisions=examples[:3],
                    novelty_score=70.0,  # Somewhat unexpected
                )
            )

    def _detect_resource_hoarding(self):
        """Detect strategy of accumulating resources before major actions."""
        hoarding_sequences = []
        current_sequence = {"start": None, "duration": 0, "peak_balance": 0}

        for i, decision in enumerate(self.decisions):
            state = decision.get("state", {})
            action = decision.get("action", {})

            balance = state.get("balance", 0)
            company_hours = action.get("company_investment_hours", 0)

            # Hoarding: high balance, no company investment
            if balance > 150 and company_hours == 0:
                if current_sequence["start"] is None:
                    current_sequence["start"] = i
                current_sequence["duration"] += 1
                current_sequence["peak_balance"] = max(current_sequence["peak_balance"], balance)
            else:
                # End of hoarding sequence
                if current_sequence["duration"] >= 10:  # At least 10 cycles of hoarding
                    hoarding_sequences.append(current_sequence.copy())
                current_sequence = {"start": None, "duration": 0, "peak_balance": 0}

        if hoarding_sequences:
            avg_peak = np.mean([seq["peak_balance"] for seq in hoarding_sequences])

            # Effectiveness: did hoarding lead to successful company formation?
            effectiveness = 60.0  # Default moderate effectiveness

            self.novel_strategies.append(
                NovelStrategy(
                    strategy_name="Resource Hoarding",
                    description=f"Accumulating resources before major investments (avg peak: ${avg_peak:.0f})",
                    frequency=len(hoarding_sequences),
                    effectiveness=effectiveness,
                    first_observed_cycle=hoarding_sequences[0]["start"],
                    example_decisions=[self.decisions[seq["start"]] for seq in hoarding_sequences[:2]],
                    novelty_score=80.0,  # Quite unexpected
                )
            )

    def _detect_cyclical_investment(self):
        """Detect alternating between survival and growth focus."""
        # Analyze task vs company investment over time
        task_focus_cycles = []
        company_focus_cycles = []

        for i, decision in enumerate(self.decisions):
            action = decision.get("action", {})
            task_hours = action.get("task_work_hours", 0)
            company_hours = action.get("company_investment_hours", 0)

            if task_hours > company_hours:
                task_focus_cycles.append(i)
            elif company_hours > task_hours:
                company_focus_cycles.append(i)

        # Check for alternating pattern
        if len(task_focus_cycles) > 5 and len(company_focus_cycles) > 5:
            # Analyze cycle lengths
            task_runs = self._find_runs(task_focus_cycles)
            company_runs = self._find_runs(company_focus_cycles)

            # Cyclical if multiple runs of each type
            if len(task_runs) >= 3 and len(company_runs) >= 3:
                self.novel_strategies.append(
                    NovelStrategy(
                        strategy_name="Cyclical Investment Pattern",
                        description=(
                            f"Alternating between task work ({len(task_runs)} periods) "
                            f"and company investment ({len(company_runs)} periods)"
                        ),
                        frequency=len(task_runs) + len(company_runs),
                        effectiveness=65.0,
                        first_observed_cycle=min(task_focus_cycles[0], company_focus_cycles[0]),
                        example_decisions=[
                            self.decisions[task_focus_cycles[0]],
                            self.decisions[company_focus_cycles[0]],
                        ],
                        novelty_score=75.0,
                    )
                )

    def _detect_opportunistic_spending(self):
        """Detect big investments immediately after revenue windfalls."""
        opportunistic_instances = []

        for i in range(1, len(self.decisions)):
            prev_state = self.decisions[i - 1].get("state", {})
            curr_state = self.decisions[i].get("state", {})
            curr_action = self.decisions[i].get("action", {})

            prev_balance = prev_state.get("balance", 0)
            curr_balance = curr_state.get("balance", 0)
            company_investment = curr_action.get("company_investment_hours", 0)

            # Windfall: significant balance increase
            balance_increase = curr_balance - prev_balance
            if balance_increase > 20 and company_investment > 2:
                opportunistic_instances.append(i)

        if len(opportunistic_instances) >= 3:
            self.novel_strategies.append(
                NovelStrategy(
                    strategy_name="Opportunistic Spending",
                    description="Making large investments immediately after revenue windfalls",
                    frequency=len(opportunistic_instances),
                    effectiveness=70.0,
                    first_observed_cycle=opportunistic_instances[0],
                    example_decisions=[self.decisions[i] for i in opportunistic_instances[:2]],
                    novelty_score=85.0,  # Highly unexpected
                )
            )

    def _detect_conservative_stockpiling(self):
        """Detect maintaining large resource reserves."""
        high_balance_cycles = []

        for i, decision in enumerate(self.decisions):
            state = decision.get("state", {})
            balance = state.get("balance", 0)

            if balance > 200:
                high_balance_cycles.append(i)

        # If maintains high balance for extended period
        if len(high_balance_cycles) > len(self.decisions) * 0.3:  # More than 30% of time
            self.novel_strategies.append(
                NovelStrategy(
                    strategy_name="Conservative Stockpiling",
                    description=f"Maintaining high resource reserves (>$200) for {len(high_balance_cycles)} cycles",
                    frequency=len(high_balance_cycles),
                    effectiveness=55.0,  # Conservative - moderate effectiveness
                    first_observed_cycle=high_balance_cycles[0],
                    example_decisions=[self.decisions[high_balance_cycles[0]]],
                    novelty_score=60.0,
                )
            )

    def _detect_cyclical_patterns(self):
        """Detect cyclical behavior patterns."""
        # Already handled in _detect_cyclical_investment

    def _detect_adaptive_behavior(self):
        """Detect adaptive strategy changes based on results."""
        # Look for significant strategy shifts
        strategy_shifts = []

        window_size = 10
        for i in range(window_size, len(self.decisions) - window_size):
            # Compare before and after windows
            before_window = self.decisions[i - window_size : i]
            after_window = self.decisions[i : i + window_size]

            # Calculate average company investment ratio
            before_ratio = self._calculate_avg_company_ratio(before_window)
            after_ratio = self._calculate_avg_company_ratio(after_window)

            # Significant shift
            if abs(after_ratio - before_ratio) > 0.3:
                strategy_shifts.append(i)

        if len(strategy_shifts) >= 2:
            self.behavior_patterns.append(
                BehaviorPattern(
                    pattern_type="adaptive",
                    description=f"Agent adapts strategy based on performance ({len(strategy_shifts)} shifts detected)",
                    occurrences=len(strategy_shifts),
                    confidence=min(100, len(strategy_shifts) * 20),
                    examples=strategy_shifts[:5],
                )
            )

    def _detect_threshold_behavior(self):
        """Detect sudden behavior changes at specific resource thresholds."""
        # Look for sudden changes in behavior at balance thresholds
        threshold_changes = []

        for i in range(1, len(self.decisions)):
            prev_state = self.decisions[i - 1].get("state", {})
            curr_state = self.decisions[i].get("state", {})

            prev_balance = prev_state.get("balance", 0)
            curr_balance = curr_state.get("balance", 0)

            # Check common thresholds: 50, 100, 150, 200
            for threshold in [50, 100, 150, 200]:
                if (prev_balance < threshold <= curr_balance) or (prev_balance >= threshold > curr_balance):
                    threshold_changes.append((i, threshold))

        if len(threshold_changes) >= 5:
            self.behavior_patterns.append(
                BehaviorPattern(
                    pattern_type="threshold-based",
                    description="Agent exhibits different behaviors above/below specific resource thresholds",
                    occurrences=len(threshold_changes),
                    confidence=70.0,
                    examples=[i for i, _ in threshold_changes[:5]],
                )
            )

    def _find_runs(self, cycles: list[int]) -> list[list[int]]:
        """Find consecutive runs in cycle list.

        Args:
            cycles: List of cycle numbers

        Returns:
            List of runs (each run is a list of consecutive cycles)
        """
        if not cycles:
            return []

        runs = []
        current_run = [cycles[0]]

        for i in range(1, len(cycles)):
            if cycles[i] == cycles[i - 1] + 1:
                current_run.append(cycles[i])
            else:
                if len(current_run) >= 2:
                    runs.append(current_run)
                current_run = [cycles[i]]

        if len(current_run) >= 2:
            runs.append(current_run)

        return runs

    def _calculate_avg_company_ratio(self, decisions: list[dict[str, Any]]) -> float:
        """Calculate average company investment ratio.

        Args:
            decisions: List of decisions

        Returns:
            Average ratio of company hours to total hours
        """
        ratios = []

        for decision in decisions:
            action = decision.get("action", {})
            task_hours = action.get("task_work_hours", 0)
            company_hours = action.get("company_investment_hours", 0)
            total_hours = task_hours + company_hours

            if total_hours > 0:
                ratios.append(company_hours / total_hours)

        return np.mean(ratios) if ratios else 0.0

    def export_emergent_behaviors(self, output_path: str | None = None):
        """Export detected emergent behaviors to JSON file.

        Args:
            output_path: Path to save detection results
        """
        output_file: Path
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.log_dir / f"emergent_behaviors_{timestamp}.json"
        else:
            output_file = Path(output_path)

        # Run detection
        novel_strategies = self.detect_novel_strategies()
        behavior_patterns = self.detect_behavior_patterns()

        # Compile results
        results = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "decisions_analyzed": len(self.decisions),
            "novel_strategies": [
                {
                    "name": s.strategy_name,
                    "description": s.description,
                    "frequency": s.frequency,
                    "effectiveness": s.effectiveness,
                    "novelty_score": s.novelty_score,
                    "first_observed": s.first_observed_cycle,
                }
                for s in novel_strategies
            ],
            "behavior_patterns": [
                {
                    "type": p.pattern_type,
                    "description": p.description,
                    "occurrences": p.occurrences,
                    "confidence": p.confidence,
                }
                for p in behavior_patterns
            ],
        }

        # Save to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

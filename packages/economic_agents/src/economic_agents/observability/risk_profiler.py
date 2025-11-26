"""Risk profiling for autonomous agent decision-making.

Analyzes agent risk tolerance, crisis behaviors, and growth vs survival preferences.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class RiskTolerance:
    """Comprehensive risk tolerance profile."""

    overall_risk_score: float  # 0-100 (0=extremely conservative, 100=extremely aggressive)
    crisis_behavior: str  # "conservative", "moderate", "aggressive"
    growth_preference: float  # 0-100 (0=pure survival, 100=pure growth)
    risk_adjusted_returns: float  # Sharpe-like ratio
    recovery_speed: float | None = None  # How quickly agent recovers from setbacks
    risk_category: str = "moderate"  # "very_conservative", "conservative", "moderate", "aggressive", "very_aggressive"


@dataclass
class CrisisDecision:
    """Decision made during crisis (low resources)."""

    cycle: int
    balance: float
    compute_hours: float
    action: dict[str, Any]
    reasoning: str
    crisis_severity: str  # "mild", "moderate", "severe", "critical"


class RiskProfiler:
    """Analyzes agent risk tolerance and crisis behavior patterns."""

    def __init__(self, agent_id: str | None = None, log_dir: str | None = None):
        """Initialize risk profiler.

        Args:
            agent_id: Agent identifier
            log_dir: Directory to save analysis results
        """
        self.agent_id = agent_id
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/observability")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.decisions: list[dict[str, Any]] = []
        self.crisis_decisions: list[CrisisDecision] = []

    def load_decisions(self, decisions: list[dict[str, Any]]):
        """Load decision history for risk profiling.

        Args:
            decisions: List of decision records
        """
        self.decisions = decisions
        self._identify_crisis_decisions()

    def calculate_risk_tolerance(self) -> RiskTolerance:
        """Calculate comprehensive risk tolerance profile.

        Returns:
            RiskTolerance with risk metrics and classifications
        """
        if not self.decisions:
            return RiskTolerance(
                overall_risk_score=50.0,
                crisis_behavior="moderate",
                growth_preference=50.0,
                risk_adjusted_returns=0.0,
                risk_category="moderate",
            )

        # Calculate risk components
        overall_risk = self._calculate_overall_risk_score()
        crisis_behavior = self._analyze_crisis_behavior()
        growth_pref = self._calculate_growth_preference()
        risk_adjusted_returns = self._calculate_risk_adjusted_returns()
        recovery_speed = self._calculate_recovery_speed()

        # Determine risk category
        if overall_risk < 20:
            risk_category = "very_conservative"
        elif overall_risk < 40:
            risk_category = "conservative"
        elif overall_risk < 60:
            risk_category = "moderate"
        elif overall_risk < 80:
            risk_category = "aggressive"
        else:
            risk_category = "very_aggressive"

        return RiskTolerance(
            overall_risk_score=overall_risk,
            crisis_behavior=crisis_behavior,
            growth_preference=growth_pref,
            risk_adjusted_returns=risk_adjusted_returns,
            recovery_speed=recovery_speed,
            risk_category=risk_category,
        )

    def _identify_crisis_decisions(self):
        """Identify all decisions made during resource crises."""
        self.crisis_decisions = []

        for i, decision in enumerate(self.decisions):
            state = decision.get("state", {})
            balance = state.get("balance", 0)
            compute_hours = state.get("compute_hours_remaining", 0)

            # Determine crisis severity
            crisis_severity = None

            if balance < 10 or compute_hours < 5:
                crisis_severity = "critical"
            elif balance < 20 or compute_hours < 10:
                crisis_severity = "severe"
            elif balance < 50 or compute_hours < 20:
                crisis_severity = "moderate"
            elif balance < 100 or compute_hours < 30:
                crisis_severity = "mild"

            if crisis_severity:
                self.crisis_decisions.append(
                    CrisisDecision(
                        cycle=i,
                        balance=balance,
                        compute_hours=compute_hours,
                        action=decision.get("action", {}),
                        reasoning=decision.get("reasoning", ""),
                        crisis_severity=crisis_severity,
                    )
                )

    def _calculate_overall_risk_score(self) -> float:
        """Calculate overall risk-taking score from decision history.

        Returns:
            Risk score (0-100)
        """
        risk_scores = []

        for decision in self.decisions:
            state = decision.get("state", {})
            action = decision.get("action", {})

            balance = state.get("balance", 0)
            compute_hours = state.get("compute_hours_remaining", 0)

            # Risk factors
            scores = []

            # 1. Resource allocation aggressiveness
            task_hours = action.get("task_work_hours", 0)
            company_hours = action.get("company_investment_hours", 0)
            total_hours = task_hours + company_hours

            if compute_hours > 0:
                utilization = total_hours / compute_hours
                # High utilization = higher risk
                utilization_risk = min(utilization * 100, 100)
                scores.append(utilization_risk)

            # 2. Growth vs survival priority
            if balance < 50:  # Low resources
                # Investing in company when broke = aggressive
                if company_hours > 0:
                    scores.append(90)  # Aggressive
                else:
                    scores.append(10)  # Conservative
            else:
                scores.append(50)  # Neutral when comfortable

            # 3. Spending pattern
            if balance > 100:
                # Spending aggressively when flush
                if company_hours > task_hours:
                    scores.append(80)  # Growth focus = higher risk
                else:
                    scores.append(30)  # Conservative even when able

            risk_scores.append(np.mean(scores) if scores else 50.0)

        return np.mean(risk_scores) if risk_scores else 50.0

    def _analyze_crisis_behavior(self) -> str:
        """Analyze how agent behaves during resource crises.

        Returns:
            Crisis behavior classification
        """
        if not self.crisis_decisions:
            return "moderate"  # No crisis data

        # Analyze crisis decision patterns
        crisis_risk_scores = []

        for crisis in self.crisis_decisions:
            action = crisis.action
            task_hours = action.get("task_work_hours", 0)
            company_hours = action.get("company_investment_hours", 0)

            # During crisis, working on tasks = conservative (good)
            # Investing in company during crisis = aggressive (risky)

            if crisis.crisis_severity in ["critical", "severe"]:
                if task_hours > 0 and company_hours == 0:
                    crisis_risk_scores.append(10)  # Very conservative
                elif task_hours > company_hours:
                    crisis_risk_scores.append(30)  # Conservative
                elif task_hours == company_hours:
                    crisis_risk_scores.append(50)  # Moderate
                else:
                    crisis_risk_scores.append(90)  # Aggressive
            else:
                # Mild crisis - more flexibility acceptable
                if task_hours > 0:
                    crisis_risk_scores.append(30)
                else:
                    crisis_risk_scores.append(60)

        avg_crisis_risk = np.mean(crisis_risk_scores) if crisis_risk_scores else 50.0

        if avg_crisis_risk < 30:
            return "conservative"
        elif avg_crisis_risk < 60:
            return "moderate"
        else:
            return "aggressive"

    def _calculate_growth_preference(self) -> float:
        """Calculate preference for growth vs survival.

        Returns:
            Growth preference score (0=pure survival, 100=pure growth)
        """
        if not self.decisions:
            return 50.0

        growth_scores = []

        for decision in self.decisions:
            action = decision.get("action", {})
            task_hours = action.get("task_work_hours", 0)
            company_hours = action.get("company_investment_hours", 0)

            total_hours = task_hours + company_hours

            if total_hours > 0:
                # Percentage of time invested in growth (company)
                growth_ratio = company_hours / total_hours
                growth_scores.append(growth_ratio * 100)

        return np.mean(growth_scores) if growth_scores else 0.0

    def _calculate_risk_adjusted_returns(self) -> float:
        """Calculate risk-adjusted performance (Sharpe-like ratio).

        Returns:
            Risk-adjusted return score
        """
        if len(self.decisions) < 2:
            return 0.0

        # Extract balance over time
        balances = [d.get("state", {}).get("balance", 0) for d in self.decisions]

        # Calculate returns
        returns = []
        for i in range(1, len(balances)):
            if balances[i - 1] > 0:
                ret = (balances[i] - balances[i - 1]) / balances[i - 1]
                returns.append(ret)

        if not returns:
            return 0.0

        # Sharpe-like ratio: avg return / std deviation of returns
        avg_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0  # No volatility

        return float(avg_return / std_return)

    def _calculate_recovery_speed(self) -> float | None:
        """Calculate how quickly agent recovers from setbacks.

        Returns:
            Recovery speed metric (None if no recovery periods found)
        """
        if not self.crisis_decisions:
            return None

        recovery_speeds = []

        # Find recovery periods (crisis -> comfortable)
        for crisis in self.crisis_decisions:
            crisis_cycle = crisis.cycle

            # Look for recovery in next 20 cycles
            recovery_cycle = None
            for i in range(crisis_cycle + 1, min(crisis_cycle + 21, len(self.decisions))):
                state = self.decisions[i].get("state", {})
                balance = state.get("balance", 0)
                compute_hours = state.get("compute_hours_remaining", 0)

                # Recovered if both resources are comfortable
                if balance > 100 and compute_hours > 30:
                    recovery_cycle = i
                    break

            if recovery_cycle:
                recovery_time = recovery_cycle - crisis_cycle
                recovery_speeds.append(recovery_time)

        if not recovery_speeds:
            return None

        # Lower is better - faster recovery
        avg_recovery_time = float(np.mean(recovery_speeds))
        # Convert to 0-100 score (20 cycles = 0, 1 cycle = 100)
        recovery_score = max(0, 100 - (avg_recovery_time - 1) * 5)

        return recovery_score

    def export_risk_profile(self, output_path: str | None = None):
        """Export risk profile analysis to JSON file.

        Args:
            output_path: Path to save analysis results
        """
        output_file: Path
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.log_dir / f"risk_profile_{timestamp}.json"
        else:
            output_file = Path(output_path)

        # Calculate risk tolerance
        risk_tolerance = self.calculate_risk_tolerance()

        # Compile results
        results = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "decisions_analyzed": len(self.decisions),
            "crisis_decisions_count": len(self.crisis_decisions),
            "risk_tolerance": {
                "overall_risk_score": risk_tolerance.overall_risk_score,
                "risk_category": risk_tolerance.risk_category,
                "crisis_behavior": risk_tolerance.crisis_behavior,
                "growth_preference": risk_tolerance.growth_preference,
                "risk_adjusted_returns": risk_tolerance.risk_adjusted_returns,
                "recovery_speed": risk_tolerance.recovery_speed,
            },
        }

        # Save to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

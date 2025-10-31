"""Scenario models and data structures."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class ScenarioConfig:
    """Configuration for a scenario."""

    name: str
    description: str
    duration_minutes: int
    initial_balance: float
    initial_compute_hours: float
    mode: str  # "survival", "entrepreneur", "auto"
    company_building_enabled: bool
    investment_enabled: bool
    expected_outcomes: List[str] = field(default_factory=list)
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """Result of running a scenario."""

    scenario_name: str
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    success: bool
    outcomes_achieved: List[str]
    outcomes_missed: List[str]
    agent_data: Dict[str, Any]
    metrics: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "scenario_name": self.scenario_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes,
            "success": self.success,
            "outcomes_achieved": self.outcomes_achieved,
            "outcomes_missed": self.outcomes_missed,
            "agent_data": self.agent_data,
            "metrics": self.metrics,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class Scenario:
    """Base scenario class."""

    def __init__(self, config: ScenarioConfig):
        """Initialize scenario.

        Args:
            config: Scenario configuration
        """
        self.config = config
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

    def setup(self) -> Dict[str, Any]:
        """Set up scenario environment.

        Returns:
            Initial environment configuration
        """
        return {
            "agent_id": f"agent-{self.config.name}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "initial_balance": self.config.initial_balance,
            "initial_compute_hours": self.config.initial_compute_hours,
            "mode": self.config.mode,
            "company_building_enabled": self.config.company_building_enabled,
            "investment_enabled": self.config.investment_enabled,
        }

    def validate_outcome(self, agent_data: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        """Validate scenario outcomes.

        Args:
            agent_data: Agent state data

        Returns:
            Tuple of (success, outcomes_achieved, outcomes_missed)
        """
        criteria = self.config.success_criteria
        outcomes_achieved = []
        outcomes_missed = []

        # Check minimum balance
        if "minimum_balance" in criteria:
            if agent_data.get("balance", 0) >= criteria["minimum_balance"]:
                outcomes_achieved.append(f"Maintained balance >= ${criteria['minimum_balance']}")
            else:
                outcomes_missed.append(f"Failed to maintain minimum balance of ${criteria['minimum_balance']}")

        # Check tasks completed
        if "minimum_tasks" in criteria:
            tasks = agent_data.get("tasks_completed", 0)
            if tasks >= criteria["minimum_tasks"]:
                outcomes_achieved.append(f"Completed {tasks} tasks (minimum: {criteria['minimum_tasks']})")
            else:
                outcomes_missed.append(f"Only completed {tasks} tasks (needed: {criteria['minimum_tasks']})")

        # Check company formation
        if "company_formed" in criteria and criteria["company_formed"]:
            if agent_data.get("company_exists", False):
                outcomes_achieved.append("Successfully formed company")
            else:
                outcomes_missed.append("Failed to form company")

        # Check positive balance
        if "positive_balance" in criteria and criteria["positive_balance"]:
            if agent_data.get("balance", 0) > 0:
                outcomes_achieved.append("Maintained positive balance")
            else:
                outcomes_missed.append("Balance went negative")

        success = len(outcomes_missed) == 0
        return success, outcomes_achieved, outcomes_missed

"""Task selection strategies for autonomous agents.

Provides pluggable strategies for selecting which task to work on from
available marketplace tasks.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum

from economic_agents.agent.core.state import AgentState
from economic_agents.interfaces.marketplace import Task


class TaskSelectionStrategyType(str, Enum):
    """Available task selection strategy types."""

    FIRST_AVAILABLE = "first_available"
    HIGHEST_REWARD = "highest_reward"
    LOWEST_DIFFICULTY = "lowest_difficulty"
    BEST_REWARD_PER_DIFFICULTY = "best_reward_per_difficulty"
    BALANCED = "balanced"


class TaskSelectionStrategy(ABC):
    """Abstract base class for task selection strategies.

    Implementations determine how agents prioritize and select tasks
    from available marketplace options.

    Example:
        strategy = HighestRewardStrategy()
        task = strategy.select_task(available_tasks, agent_state)
    """

    @abstractmethod
    def select_task(self, tasks: list[Task], state: AgentState) -> Task | None:
        """Select a task from available tasks.

        Args:
            tasks: List of available tasks from marketplace
            state: Current agent state for context-aware selection

        Returns:
            Selected task, or None if no suitable task found
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this strategy."""


class FirstAvailableStrategy(TaskSelectionStrategy):
    """Select the first available task (default behavior).

    Simple strategy that picks the first task in the list.
    Fast but doesn't optimize for any particular metric.
    """

    def select_task(self, tasks: list[Task], state: AgentState) -> Task | None:
        """Select the first task in the list."""
        del state  # Unused in this strategy
        return tasks[0] if tasks else None

    @property
    def name(self) -> str:
        return "First Available"


class HighestRewardStrategy(TaskSelectionStrategy):
    """Select the task with the highest reward.

    Maximizes immediate income but may select difficult tasks
    that have higher failure rates.
    """

    def select_task(self, tasks: list[Task], state: AgentState) -> Task | None:
        """Select the task with highest reward."""
        del state  # Unused in this strategy
        if not tasks:
            return None
        return max(tasks, key=lambda t: t.reward)

    @property
    def name(self) -> str:
        return "Highest Reward"


class LowestDifficultyStrategy(TaskSelectionStrategy):
    """Select the easiest task available.

    Prioritizes tasks that are more likely to succeed,
    trading off potentially lower rewards for reliability.
    """

    DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}

    def select_task(self, tasks: list[Task], state: AgentState) -> Task | None:
        """Select the task with lowest difficulty."""
        del state  # Unused in this strategy
        if not tasks:
            return None
        return min(tasks, key=lambda t: self.DIFFICULTY_ORDER.get(t.difficulty, 1))

    @property
    def name(self) -> str:
        return "Lowest Difficulty"


class BestRewardPerDifficultyStrategy(TaskSelectionStrategy):
    """Select the task with the best reward-to-difficulty ratio.

    Balances reward and difficulty by computing an efficiency score.
    Higher rewards and lower difficulties both increase the score.
    """

    DIFFICULTY_WEIGHTS = {"easy": 1.0, "medium": 2.0, "hard": 3.0}

    def select_task(self, tasks: list[Task], state: AgentState) -> Task | None:
        """Select the task with best reward/difficulty ratio."""
        del state  # Unused in this strategy
        if not tasks:
            return None

        def efficiency_score(task: Task) -> float:
            difficulty_weight: float = self.DIFFICULTY_WEIGHTS.get(task.difficulty, 2.0)
            return float(task.reward / difficulty_weight)

        return max(tasks, key=efficiency_score)

    @property
    def name(self) -> str:
        return "Best Reward Per Difficulty"


class BalancedStrategy(TaskSelectionStrategy):
    """Context-aware strategy that adapts based on agent state.

    When survival is at risk, prioritizes easy tasks for reliable income.
    When comfortable, takes on harder tasks for better rewards.
    """

    def __init__(self):
        """Initialize with component strategies."""
        self._lowest_difficulty = LowestDifficultyStrategy()
        self._best_ratio = BestRewardPerDifficultyStrategy()
        self._highest_reward = HighestRewardStrategy()

    def select_task(self, tasks: list[Task], state: AgentState) -> Task | None:
        """Select task based on current agent state."""
        if not tasks:
            return None

        # If survival at risk, prioritize reliable easy tasks
        if state.is_survival_at_risk():
            return self._lowest_difficulty.select_task(tasks, state)

        # If has surplus capital, can take on higher risk/reward tasks
        if state.has_surplus_capital(threshold=100.0):
            return self._highest_reward.select_task(tasks, state)

        # Default: optimize for efficiency
        return self._best_ratio.select_task(tasks, state)

    @property
    def name(self) -> str:
        return "Balanced"


def create_task_selection_strategy(strategy_type: TaskSelectionStrategyType | str) -> TaskSelectionStrategy:
    """Factory function to create task selection strategies.

    Args:
        strategy_type: Type of strategy to create

    Returns:
        TaskSelectionStrategy instance

    Raises:
        ValueError: If strategy type is unknown

    Example:
        strategy = create_task_selection_strategy("highest_reward")
        task = strategy.select_task(tasks, state)
    """
    if isinstance(strategy_type, str):
        try:
            strategy_type = TaskSelectionStrategyType(strategy_type)
        except ValueError as err:
            valid = [s.value for s in TaskSelectionStrategyType]
            raise ValueError(f"Unknown strategy: {strategy_type}. Valid: {valid}") from err

    strategies: dict[TaskSelectionStrategyType, Callable[[], TaskSelectionStrategy]] = {
        TaskSelectionStrategyType.FIRST_AVAILABLE: FirstAvailableStrategy,
        TaskSelectionStrategyType.HIGHEST_REWARD: HighestRewardStrategy,
        TaskSelectionStrategyType.LOWEST_DIFFICULTY: LowestDifficultyStrategy,
        TaskSelectionStrategyType.BEST_REWARD_PER_DIFFICULTY: BestRewardPerDifficultyStrategy,
        TaskSelectionStrategyType.BALANCED: BalancedStrategy,
    }

    return strategies[strategy_type]()

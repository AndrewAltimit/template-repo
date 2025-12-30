"""Tests for task selection strategies."""

from datetime import datetime, timedelta

import pytest

from economic_agents.agent.core.state import AgentState
from economic_agents.agent.core.task_selection import (
    BalancedStrategy,
    BestRewardPerDifficultyStrategy,
    FirstAvailableStrategy,
    HighestRewardStrategy,
    LowestDifficultyStrategy,
    TaskSelectionStrategyType,
    create_task_selection_strategy,
)
from economic_agents.interfaces.marketplace import Task


@pytest.fixture
def sample_tasks():
    """Create sample tasks for testing."""
    now = datetime.now()
    return [
        Task(
            id="task-1",
            title="Easy Task",
            description="Simple task",
            requirements={},
            reward=10.0,
            deadline=now + timedelta(days=1),
            difficulty="easy",
            category="coding",
        ),
        Task(
            id="task-2",
            title="Medium Task",
            description="Medium difficulty",
            requirements={},
            reward=50.0,
            deadline=now + timedelta(days=2),
            difficulty="medium",
            category="coding",
        ),
        Task(
            id="task-3",
            title="Hard Task",
            description="Difficult task",
            requirements={},
            reward=100.0,
            deadline=now + timedelta(days=3),
            difficulty="hard",
            category="coding",
        ),
    ]


@pytest.fixture
def survival_state():
    """Agent state at survival risk."""
    return AgentState(
        balance=10.0,
        compute_hours_remaining=5.0,
        survival_buffer_hours=24.0,
    )


@pytest.fixture
def comfortable_state():
    """Agent state with surplus capital."""
    return AgentState(
        balance=500.0,
        compute_hours_remaining=100.0,
        survival_buffer_hours=24.0,
    )


def test_first_available_strategy(sample_tasks, comfortable_state):
    """FirstAvailable always picks the first task."""
    strategy = FirstAvailableStrategy()
    task = strategy.select_task(sample_tasks, comfortable_state)
    assert task is not None
    assert task.id == "task-1"
    assert strategy.name == "First Available"


def test_first_available_empty_list(comfortable_state):
    """FirstAvailable returns None for empty list."""
    strategy = FirstAvailableStrategy()
    task = strategy.select_task([], comfortable_state)
    assert task is None


def test_highest_reward_strategy(sample_tasks, comfortable_state):
    """HighestReward picks the task with maximum reward."""
    strategy = HighestRewardStrategy()
    task = strategy.select_task(sample_tasks, comfortable_state)
    assert task is not None
    assert task.id == "task-3"
    assert task.reward == 100.0
    assert strategy.name == "Highest Reward"


def test_lowest_difficulty_strategy(sample_tasks, comfortable_state):
    """LowestDifficulty picks the easiest task."""
    strategy = LowestDifficultyStrategy()
    task = strategy.select_task(sample_tasks, comfortable_state)
    assert task is not None
    assert task.id == "task-1"
    assert task.difficulty == "easy"
    assert strategy.name == "Lowest Difficulty"


def test_best_reward_per_difficulty_strategy(sample_tasks, comfortable_state):
    """BestRewardPerDifficulty optimizes reward/difficulty ratio."""
    strategy = BestRewardPerDifficultyStrategy()
    task = strategy.select_task(sample_tasks, comfortable_state)
    assert task is not None
    # task-3: 100/3 = 33.3, task-2: 50/2 = 25, task-1: 10/1 = 10
    assert task.id == "task-3"
    assert strategy.name == "Best Reward Per Difficulty"


def test_balanced_strategy_survival_mode(sample_tasks, survival_state):
    """Balanced picks easy tasks when survival at risk."""
    strategy = BalancedStrategy()
    task = strategy.select_task(sample_tasks, survival_state)
    assert task is not None
    assert task.difficulty == "easy"
    assert strategy.name == "Balanced"


def test_balanced_strategy_comfortable(sample_tasks, comfortable_state):
    """Balanced picks high reward when comfortable."""
    strategy = BalancedStrategy()
    task = strategy.select_task(sample_tasks, comfortable_state)
    assert task is not None
    assert task.id == "task-3"


def test_balanced_strategy_middle_ground(sample_tasks):
    """Balanced uses efficiency ratio in middle ground."""
    state = AgentState(
        balance=50.0,
        compute_hours_remaining=50.0,
        survival_buffer_hours=24.0,
    )
    strategy = BalancedStrategy()
    task = strategy.select_task(sample_tasks, state)
    assert task is not None
    # Should pick best ratio since not at risk and not surplus
    assert task.id == "task-3"


def test_create_strategy_from_string():
    """Factory creates strategies from string names."""
    strategy = create_task_selection_strategy("highest_reward")
    assert isinstance(strategy, HighestRewardStrategy)


def test_create_strategy_from_enum():
    """Factory creates strategies from enum values."""
    strategy = create_task_selection_strategy(TaskSelectionStrategyType.LOWEST_DIFFICULTY)
    assert isinstance(strategy, LowestDifficultyStrategy)


def test_create_strategy_invalid():
    """Factory raises error for unknown strategy."""
    with pytest.raises(ValueError, match="Unknown strategy"):
        create_task_selection_strategy("nonexistent_strategy")


def test_all_strategy_types_creatable():
    """All strategy types can be created."""
    for strategy_type in TaskSelectionStrategyType:
        strategy = create_task_selection_strategy(strategy_type)
        assert isinstance(strategy, type(strategy))
        assert strategy.name  # All have names

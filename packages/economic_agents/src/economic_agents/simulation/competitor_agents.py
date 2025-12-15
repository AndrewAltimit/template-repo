"""Competitor agent simulation for realistic task competition."""

from datetime import datetime, timedelta
import random
from typing import Dict, List, Optional, Set


class CompetitorSimulator:
    """Simulates other agents competing for tasks in the marketplace.

    Creates the illusion of a living marketplace where:
    - Tasks get claimed by competitors
    - Popular tasks disappear faster
    - Race conditions occur when multiple agents claim same task
    - New tasks appear at irregular intervals
    """

    def __init__(
        self,
        num_competitors: int = 10,
        competitor_activity_rate: float = 0.3,
        popular_task_claim_rate: float = 0.5,
        seed: Optional[int] = None,
    ):
        """Initialize competitor simulator.

        Args:
            num_competitors: Number of simulated competitor agents
            competitor_activity_rate: Base probability of competitor claiming a task
            popular_task_claim_rate: Additional claim rate for high-reward tasks
            seed: Random seed for reproducibility
        """
        self.num_competitors = num_competitors
        self.competitor_activity_rate = competitor_activity_rate
        self.popular_task_claim_rate = popular_task_claim_rate
        self.rng = random.Random(seed)

        # Track which competitors claimed which tasks
        self.competitor_claims: Dict[str, str] = {}  # task_id -> competitor_name

        # Track task view counts (for "N agents viewing" social proof)
        self.task_views: Dict[str, int] = {}  # task_id -> view count

        # Track when tasks were added (for irregular appearance)
        self.task_added_times: Dict[str, datetime] = {}

    def should_competitor_claim_task(self, task_reward: float, max_reward: float = 1000.0) -> bool:
        """Determine if a competitor should claim this task.

        Higher reward tasks are more likely to be claimed by competitors.

        Args:
            task_reward: Reward amount for this task
            max_reward: Maximum expected reward for normalization

        Returns:
            True if a competitor claims the task, False otherwise
        """
        # Base claim probability
        claim_prob = self.competitor_activity_rate

        # Increase probability for high-reward tasks
        reward_factor = min(task_reward / max_reward, 1.0)
        claim_prob += reward_factor * self.popular_task_claim_rate

        return self.rng.random() < claim_prob

    def claim_task_by_competitor(self, task_id: str) -> str:
        """Record that a competitor claimed a task.

        Args:
            task_id: Task that was claimed

        Returns:
            Name of the competitor who claimed it
        """
        competitor_name = f"Agent_{self.rng.randint(1, self.num_competitors):03d}"
        self.competitor_claims[task_id] = competitor_name
        return competitor_name

    def is_claimed_by_competitor(self, task_id: str) -> bool:
        """Check if a task has been claimed by a competitor.

        Args:
            task_id: Task to check

        Returns:
            True if claimed by competitor, False otherwise
        """
        return task_id in self.competitor_claims

    def get_task_view_count(self, task_id: str) -> int:
        """Get number of agents viewing this task.

        Args:
            task_id: Task to check

        Returns:
            Number of competitors viewing the task
        """
        if task_id not in self.task_views:
            # Generate realistic view count (1-20 agents)
            self.task_views[task_id] = self.rng.randint(1, 20)

        return self.task_views[task_id]

    def simulate_race_condition(self, task_id: str, _claim_attempt_time: float = 0.0) -> bool:
        """Simulate race condition where another agent claims task simultaneously.

        Args:
            task_id: Task being claimed
            _claim_attempt_time: Time when claim was attempted (for realism)

        Returns:
            True if race condition occurred (task already claimed), False otherwise
        """
        # Small probability of race condition (5%)
        if self.rng.random() < 0.05:
            # Another agent got there first
            self.claim_task_by_competitor(task_id)
            return True

        return False

    def get_tasks_to_remove(self, available_tasks: List[str], check_interval_minutes: float = 5.0) -> Set[str]:
        """Get tasks that should be removed due to competitor claims.

        Call this periodically to simulate tasks disappearing over time.

        Args:
            available_tasks: List of currently available task IDs
            check_interval_minutes: How often this is called (affects removal rate)

        Returns:
            Set of task IDs that were claimed by competitors
        """
        removed_tasks = set()

        for task_id in available_tasks:
            # Skip if already claimed
            if task_id in self.competitor_claims:
                continue

            # Probability increases with time interval
            # Base: 30% chance per 5 minutes
            removal_prob = 0.3 * (check_interval_minutes / 5.0)

            if self.rng.random() < removal_prob:
                self.claim_task_by_competitor(task_id)
                removed_tasks.add(task_id)

        return removed_tasks

    def should_add_new_task(self, current_task_count: int, target_count: int = 10) -> bool:
        """Determine if a new task should be added to marketplace.

        Args:
            current_task_count: Current number of available tasks
            target_count: Target number of tasks to maintain

        Returns:
            True if new task should be added, False otherwise
        """
        if current_task_count >= target_count:
            return False

        # Higher probability when task count is low
        deficit = target_count - current_task_count
        add_prob = min(deficit / target_count, 0.8)

        return self.rng.random() < add_prob

    def get_task_completion_stats(self, _task_category: str) -> Dict[str, float]:
        """Get simulated completion statistics for similar tasks.

        This provides social proof like "85% completion rate on similar tasks".

        Args:
            _task_category: Category of task (e.g., "ML", "backend", "frontend")

        Returns:
            Dict with completion_rate, avg_time_hours, num_attempts
        """
        # Generate realistic statistics
        completion_rate = self.rng.uniform(0.65, 0.95)
        avg_time_hours = self.rng.uniform(2.0, 20.0)
        num_attempts = self.rng.randint(50, 500)

        return {
            "completion_rate": completion_rate,
            "avg_time_hours": avg_time_hours,
            "num_attempts": num_attempts,
        }

    def record_task_added(self, task_id: str) -> None:
        """Record when a task was added to marketplace.

        Args:
            task_id: Task that was added
        """
        self.task_added_times[task_id] = datetime.now()

    def get_time_since_added(self, task_id: str) -> Optional[timedelta]:
        """Get time since task was added.

        Args:
            task_id: Task to check

        Returns:
            Timedelta since task was added, or None if not tracked
        """
        if task_id not in self.task_added_times:
            return None

        return datetime.now() - self.task_added_times[task_id]

    def cleanup_old_tasks(self, max_age_hours: float = 168.0) -> None:
        """Clean up tracking data for old tasks.

        Args:
            max_age_hours: Maximum age in hours before cleanup (default: 7 days)
        """
        current_time = datetime.now()
        cutoff = timedelta(hours=max_age_hours)

        # Clean up task_added_times
        old_tasks = [task_id for task_id, added_time in self.task_added_times.items() if current_time - added_time > cutoff]

        for task_id in old_tasks:
            self.task_added_times.pop(task_id, None)
            self.competitor_claims.pop(task_id, None)
            self.task_views.pop(task_id, None)

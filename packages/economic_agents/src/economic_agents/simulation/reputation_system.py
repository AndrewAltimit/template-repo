"""Reputation system for tracking agent performance and unlocking opportunities."""

from dataclasses import dataclass, field
from datetime import datetime
import random
from typing import Dict, List, Optional


@dataclass
class PerformanceRecord:
    """Record of an agent's task performance."""

    task_id: str
    success: bool
    quality_score: float  # 0.0-1.0
    completion_time_hours: float
    reward_earned: float
    timestamp: datetime


@dataclass
class ReputationProfile:
    """Agent's reputation profile."""

    agent_id: str
    trust_score: float = 0.5  # 0.0-1.0, starts neutral
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_earnings: float = 0.0
    avg_quality_score: float = 0.0
    avg_completion_time_hours: float = 0.0
    performance_history: List[PerformanceRecord] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    tier: str = "beginner"  # beginner, intermediate, advanced, expert
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    @property
    def days_active(self) -> int:
        """Calculate days since account creation."""
        return (datetime.now() - self.created_at).days


class ReputationSystem:
    """Tracks agent performance and manages reputation-based access.

    Features:
    - Trust score calculation based on performance
    - Achievement unlocks for milestones
    - Tier progression (beginner -> expert)
    - Performance history tracking
    - Reputation-based opportunity access
    """

    def __init__(
        self,
        tier_thresholds: Optional[Dict[str, int]] = None,
        seed: Optional[int] = None,
    ):
        """Initialize reputation system.

        Args:
            tier_thresholds: Task count thresholds for each tier
            seed: Random seed for reproducibility
        """
        self.profiles: Dict[str, ReputationProfile] = {}
        self.rng = random.Random(seed)

        # Default tier thresholds
        self.tier_thresholds = tier_thresholds or {
            "beginner": 0,
            "intermediate": 10,
            "advanced": 50,
            "expert": 200,
        }

        # Achievement definitions
        self.achievements = {
            "first_task": "Complete your first task",
            "perfect_ten": "Complete 10 tasks with 100% success rate",
            "speed_demon": "Complete 5 tasks in under 2 hours each",
            "high_earner": "Earn $10,000+ in total",
            "quality_master": "Maintain 95%+ average quality score over 20 tasks",
            "consistent": "Complete tasks 7 days in a row",
            "specialist_ml": "Complete 10 ML tasks",
            "specialist_backend": "Complete 10 backend tasks",
            "specialist_frontend": "Complete 10 frontend tasks",
        }

    def get_or_create_profile(self, agent_id: str) -> ReputationProfile:
        """Get existing profile or create new one.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent's reputation profile
        """
        if agent_id not in self.profiles:
            self.profiles[agent_id] = ReputationProfile(agent_id=agent_id)

        return self.profiles[agent_id]

    def record_task_completion(
        self,
        agent_id: str,
        task_id: str,
        success: bool,
        quality_score: float,
        completion_time_hours: float,
        reward_earned: float,
    ) -> ReputationProfile:
        """Record a task completion and update reputation.

        Args:
            agent_id: Agent who completed task
            task_id: Task that was completed
            success: Whether task was successful
            quality_score: Quality rating (0.0-1.0)
            completion_time_hours: Time taken to complete
            reward_earned: Reward earned (0 if failed)

        Returns:
            Updated reputation profile
        """
        profile = self.get_or_create_profile(agent_id)

        # Create performance record
        record = PerformanceRecord(
            task_id=task_id,
            success=success,
            quality_score=quality_score,
            completion_time_hours=completion_time_hours,
            reward_earned=reward_earned,
            timestamp=datetime.now(),
        )

        profile.performance_history.append(record)
        profile.total_tasks += 1

        if success:
            profile.successful_tasks += 1
            profile.total_earnings += reward_earned
        else:
            profile.failed_tasks += 1

        # Update averages
        profile.avg_quality_score = sum(r.quality_score for r in profile.performance_history) / len(
            profile.performance_history
        )
        profile.avg_completion_time_hours = sum(r.completion_time_hours for r in profile.performance_history) / len(
            profile.performance_history
        )

        # Update trust score (weighted by recent performance)
        profile.trust_score = self._calculate_trust_score(profile)

        # Update tier
        profile.tier = self._calculate_tier(profile)

        # Check for achievement unlocks
        self._check_achievements(profile)

        profile.last_updated = datetime.now()

        return profile

    def _calculate_trust_score(self, profile: ReputationProfile) -> float:
        """Calculate trust score based on performance.

        Args:
            profile: Agent's reputation profile

        Returns:
            Trust score (0.0-1.0)
        """
        if profile.total_tasks == 0:
            return 0.5  # Neutral for new agents

        # Weight components
        success_weight = 0.4
        quality_weight = 0.3
        consistency_weight = 0.2
        longevity_weight = 0.1

        # Success rate component
        success_component = profile.success_rate * success_weight

        # Quality component
        quality_component = profile.avg_quality_score * quality_weight

        # Consistency component (penalize recent failures)
        recent_tasks = profile.performance_history[-10:]  # Last 10 tasks
        if recent_tasks:
            recent_success_rate = sum(1 for r in recent_tasks if r.success) / len(recent_tasks)
        else:
            recent_success_rate = 0.5

        consistency_component = recent_success_rate * consistency_weight

        # Longevity component (more experience = more trust)
        longevity_factor = min(profile.total_tasks / 100.0, 1.0)
        longevity_component = longevity_factor * longevity_weight

        trust_score = success_component + quality_component + consistency_component + longevity_component

        return max(0.0, min(1.0, trust_score))

    def _calculate_tier(self, profile: ReputationProfile) -> str:
        """Calculate agent's tier based on task count and performance.

        Args:
            profile: Agent's reputation profile

        Returns:
            Tier name
        """
        # Must maintain minimum success rate to progress
        if profile.success_rate < 0.6 and profile.total_tasks >= 10:
            return "beginner"  # Stuck at beginner if low success rate

        # Tier based on task count
        for tier in ["expert", "advanced", "intermediate", "beginner"]:
            if profile.successful_tasks >= self.tier_thresholds[tier]:
                return tier

        return "beginner"

    def _check_achievements(self, profile: ReputationProfile) -> None:
        """Check and unlock achievements.

        Args:
            profile: Agent's reputation profile
        """
        # First task
        if profile.total_tasks == 1 and "first_task" not in profile.achievements:
            profile.achievements.append("first_task")

        # Perfect ten
        if profile.total_tasks >= 10 and profile.success_rate == 1.0 and "perfect_ten" not in profile.achievements:
            profile.achievements.append("perfect_ten")

        # Speed demon
        fast_tasks = [r for r in profile.performance_history if r.completion_time_hours <= 2.0]
        if len(fast_tasks) >= 5 and "speed_demon" not in profile.achievements:
            profile.achievements.append("speed_demon")

        # High earner
        if profile.total_earnings >= 10000.0 and "high_earner" not in profile.achievements:
            profile.achievements.append("high_earner")

        # Quality master
        if profile.total_tasks >= 20 and profile.avg_quality_score >= 0.95 and "quality_master" not in profile.achievements:
            profile.achievements.append("quality_master")

    def get_access_multiplier(self, agent_id: str) -> float:
        """Get task access multiplier based on reputation.

        Higher reputation = more tasks available.

        Args:
            agent_id: Agent identifier

        Returns:
            Multiplier (0.5-2.0) for task availability
        """
        profile = self.get_or_create_profile(agent_id)

        tier_multipliers = {
            "beginner": 0.5,
            "intermediate": 1.0,
            "advanced": 1.5,
            "expert": 2.0,
        }

        base_multiplier = tier_multipliers[profile.tier]

        # Adjust by trust score
        trust_adjustment = (profile.trust_score - 0.5) * 0.5  # ±0.25

        return max(0.5, min(2.0, base_multiplier + trust_adjustment))

    def get_investor_interest_multiplier(self, agent_id: str) -> float:
        """Get investor interest multiplier based on reputation.

        Higher reputation = more investor interest.

        Args:
            agent_id: Agent identifier

        Returns:
            Multiplier (0.3-2.0) for investor approval probability
        """
        profile = self.get_or_create_profile(agent_id)

        # Trust score is main factor
        base_multiplier = 0.5 + (profile.trust_score * 1.5)

        # Boost for high earners
        if profile.total_earnings > 5000.0:
            base_multiplier *= 1.2

        # Boost for tier
        tier_boosts = {
            "beginner": 1.0,
            "intermediate": 1.1,
            "advanced": 1.3,
            "expert": 1.5,
        }

        base_multiplier *= tier_boosts[profile.tier]

        return max(0.3, min(2.0, base_multiplier))

    def should_unlock_advanced_tasks(self, agent_id: str) -> bool:
        """Check if agent should have access to advanced tasks.

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent has unlocked advanced tasks
        """
        profile = self.get_or_create_profile(agent_id)
        return profile.tier in ["advanced", "expert"]

    def get_reputation_summary(self, agent_id: str) -> Dict:
        """Get summary of agent's reputation.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict with reputation summary
        """
        profile = self.get_or_create_profile(agent_id)

        return {
            "agent_id": agent_id,
            "trust_score": round(profile.trust_score, 3),
            "tier": profile.tier,
            "total_tasks": profile.total_tasks,
            "success_rate": round(profile.success_rate, 3),
            "avg_quality": round(profile.avg_quality_score, 3),
            "total_earnings": round(profile.total_earnings, 2),
            "achievements": profile.achievements,
            "days_active": profile.days_active,
        }

    def get_recent_performance_trend(self, agent_id: str, num_tasks: int = 10) -> str:
        """Get recent performance trend description.

        Args:
            agent_id: Agent identifier
            num_tasks: Number of recent tasks to analyze

        Returns:
            Trend description ("improving", "declining", "stable")
        """
        profile = self.get_or_create_profile(agent_id)

        if len(profile.performance_history) < num_tasks:
            return "stable"

        recent = profile.performance_history[-num_tasks:]
        first_half = recent[: num_tasks // 2]
        second_half = recent[num_tasks // 2 :]

        first_half_success = sum(1 for r in first_half if r.success) / len(first_half)
        second_half_success = sum(1 for r in second_half if r.success) / len(second_half)

        diff = second_half_success - first_half_success

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"

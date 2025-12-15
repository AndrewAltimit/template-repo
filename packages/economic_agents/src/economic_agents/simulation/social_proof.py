"""Social proof signals for realistic marketplace intelligence."""

from datetime import datetime, timedelta
import random
from typing import Any, Dict, List, Optional


class SocialProofSignals:
    """Provides social proof signals to make the marketplace feel alive.

    Features:
    - Marketplace intelligence (task view counts, active agents)
    - Competition statistics (completion rates, popular categories)
    - Funding trends (recent investments, market activity)
    - Benchmark data (typical valuations, funding amounts)
    """

    def __init__(
        self,
        base_agent_count: int = 50,
        base_weekly_funding_count: int = 5,
        seed: Optional[int] = None,
    ):
        """Initialize social proof system.

        Args:
            base_agent_count: Baseline number of active agents in marketplace
            base_weekly_funding_count: Baseline funding deals per week
            seed: Random seed for reproducibility
        """
        self.base_agent_count = base_agent_count
        self.base_weekly_funding_count = base_weekly_funding_count
        self.rng = random.Random(seed)

        # Track task view counts
        self.task_views: Dict[str, int] = {}

        # Track category statistics
        self.category_completions: Dict[str, Dict[str, int]] = {}  # category -> {total, successful}

        # Track recent funding activity
        self.recent_fundings: List[Dict] = []

    def get_task_intelligence(self, task_id: str, task_reward: float) -> Dict[str, Any]:
        """Get marketplace intelligence for a specific task.

        Args:
            task_id: Task identifier
            task_reward: Task reward amount

        Returns:
            Dict with intelligence data
        """
        # Initialize view count if new task
        if task_id not in self.task_views:
            # Popular tasks (high reward) get more views
            base_views = int(self.rng.uniform(5, 15))
            reward_factor = min(task_reward / 1000.0, 2.0)  # Cap at 2x
            self.task_views[task_id] = int(base_views * reward_factor)

        # Views increase over time
        self.task_views[task_id] += self.rng.randint(0, 3)

        # Calculate active agents interested in this task
        viewing_agents = max(1, int(self.task_views[task_id] * 0.3))  # ~30% of viewers are "active"

        return {
            "total_views": self.task_views[task_id],
            "agents_viewing": viewing_agents,
            "posted_time": f"{self.rng.randint(1, 72)} hours ago",
            "interest_level": self._get_interest_level(self.task_views[task_id]),
        }

    def _get_interest_level(self, view_count: int) -> str:
        """Get human-readable interest level.

        Args:
            view_count: Number of views

        Returns:
            Interest level string
        """
        if view_count < 10:
            return "low"
        if view_count < 20:
            return "moderate"
        if view_count < 40:
            return "high"
        return "very high"

    def get_category_stats(self, category: str) -> Dict[str, Any]:
        """Get competition statistics for a task category.

        Args:
            category: Task category (e.g., "ML", "backend", "frontend")

        Returns:
            Dict with category statistics
        """
        # Initialize if new category
        if category not in self.category_completions:
            # Generate realistic historical stats
            total = self.rng.randint(100, 500)
            success_rate = self.rng.uniform(0.65, 0.90)  # 65-90% success rate
            successful = int(total * success_rate)

            self.category_completions[category] = {"total": total, "successful": successful}

        stats = self.category_completions[category]

        completion_rate = stats["successful"] / stats["total"] if stats["total"] > 0 else 0.0

        # Generate additional stats
        avg_time_hours = self.rng.uniform(4.0, 12.0)
        popular_rank = self.rng.randint(1, 10)

        return {
            "category": category,
            "completion_rate": round(completion_rate, 3),
            "total_completions": stats["successful"],
            "avg_completion_time_hours": round(avg_time_hours, 1),
            "popularity_rank": popular_rank,
            "trend": self._get_trend(),
        }

    def _get_trend(self) -> str:
        """Get random trend indicator.

        Returns:
            Trend string ("rising", "stable", "declining")
        """
        trend_weights = [("rising", 0.3), ("stable", 0.5), ("declining", 0.2)]
        trends, weights = zip(*trend_weights)
        result = self.rng.choices(trends, weights=weights)[0]
        return str(result)

    def get_funding_trends(self, market_phase: Optional[str] = None) -> Dict[str, Any]:
        """Get funding market trends.

        Args:
            market_phase: Current market phase (bull/bear/normal/crash)

        Returns:
            Dict with funding trends
        """
        # Adjust counts based on market phase
        phase_multipliers = {"bull": 1.5, "normal": 1.0, "bear": 0.6, "crash": 0.2}

        multiplier = phase_multipliers.get(market_phase, 1.0) if market_phase else 1.0

        # Weekly funding count
        weekly_count = max(0, int(self.base_weekly_funding_count * multiplier * self.rng.uniform(0.8, 1.2)))

        # Average deal size
        base_deal_size = 2000000.0  # $2M average
        avg_deal_size = base_deal_size * multiplier * self.rng.uniform(0.7, 1.3)

        # Popular sectors (with some randomness)
        sectors = ["AI/ML", "SaaS", "FinTech", "HealthTech", "Enterprise", "Consumer"]
        sector_weights = [0.25, 0.20, 0.15, 0.15, 0.15, 0.10]
        popular_sector = self.rng.choices(sectors, weights=sector_weights)[0]

        # Market sentiment
        if market_phase == "bull":
            sentiment = "optimistic"
        elif market_phase == "bear":
            sentiment = "cautious"
        elif market_phase == "crash":
            sentiment = "pessimistic"
        else:
            sentiment = "neutral"

        return {
            "weekly_deals": weekly_count,
            "avg_deal_size": round(avg_deal_size, 0),
            "total_volume_week": round(weekly_count * avg_deal_size, 0),
            "popular_sector": popular_sector,
            "market_sentiment": sentiment,
            "yoy_growth": round(self.rng.uniform(-0.3, 0.5), 3),  # -30% to +50%
        }

    def get_benchmark_data(self, company_stage: str, market_size: float, revenue: float) -> Dict[str, Any]:
        """Get benchmark data for similar companies.

        Args:
            company_stage: Investment stage (seed, series_a, etc.)
            market_size: Target market size
            revenue: Current/projected revenue

        Returns:
            Dict with benchmark data
        """
        # Typical valuation multiples by stage
        stage_multiples = {
            "pre_seed": (3.0, 8.0),  # 3-8x revenue
            "seed": (5.0, 15.0),  # 5-15x revenue
            "series_a": (8.0, 20.0),  # 8-20x revenue
            "series_b": (10.0, 25.0),  # 10-25x revenue
        }

        multiples = stage_multiples.get(company_stage, (5.0, 15.0))
        typical_multiple = self.rng.uniform(*multiples)
        typical_valuation = revenue * typical_multiple if revenue > 0 else market_size * 0.01

        # Typical funding amounts by stage
        stage_funding = {
            "pre_seed": (100000, 500000),
            "seed": (500000, 2000000),
            "series_a": (2000000, 10000000),
            "series_b": (10000000, 50000000),
        }

        funding_range = stage_funding.get(company_stage, (500000, 2000000))
        typical_funding = self.rng.uniform(*funding_range)

        # Market comparison
        percentile = self.rng.randint(15, 85)  # Where this company falls

        return {
            "typical_valuation": round(typical_valuation, 0),
            "typical_funding": round(typical_funding, 0),
            "valuation_multiple_range": f"{multiples[0]:.1f}x - {multiples[1]:.1f}x",
            "market_percentile": percentile,
            "comparable_companies": self.rng.randint(10, 50),
            "stage": company_stage,
        }

    def record_task_completion(self, category: str, success: bool) -> None:
        """Record a task completion for statistics.

        Args:
            category: Task category
            success: Whether task was successful
        """
        if category not in self.category_completions:
            self.category_completions[category] = {"total": 0, "successful": 0}

        self.category_completions[category]["total"] += 1
        if success:
            self.category_completions[category]["successful"] += 1

    def record_funding_deal(self, amount: float, stage: str, sector: str = "AI/ML") -> None:
        """Record a funding deal for trend tracking.

        Args:
            amount: Funding amount
            stage: Investment stage
            sector: Company sector
        """
        deal = {
            "amount": amount,
            "stage": stage,
            "sector": sector,
            "timestamp": datetime.now(),
        }

        self.recent_fundings.append(deal)

        # Keep only recent deals (last 30 days)
        cutoff = datetime.now() - timedelta(days=30)
        self.recent_fundings = [d for d in self.recent_fundings if d["timestamp"] > cutoff]

    def get_marketplace_summary(self) -> Dict[str, Any]:
        """Get overall marketplace summary.

        Returns:
            Dict with marketplace statistics
        """
        # Calculate active agent count with some variance
        active_agents = int(self.base_agent_count * self.rng.uniform(0.8, 1.2))

        # Total tasks available (simulated)
        total_tasks = self.rng.randint(20, 100)

        # Recent activity
        tasks_completed_today = self.rng.randint(5, 20)
        new_tasks_today = self.rng.randint(10, 30)

        return {
            "active_agents": active_agents,
            "total_available_tasks": total_tasks,
            "tasks_completed_today": tasks_completed_today,
            "new_tasks_today": new_tasks_today,
            "avg_task_reward": round(self.rng.uniform(500, 2000), 0),
            "marketplace_health": self._get_marketplace_health(active_agents, total_tasks),
        }

    def _get_marketplace_health(self, agents: int, tasks: int) -> str:
        """Calculate marketplace health indicator.

        Args:
            agents: Number of active agents
            tasks: Number of available tasks

        Returns:
            Health indicator string
        """
        ratio = tasks / agents if agents > 0 else 0

        if ratio > 1.5:
            return "high_demand"  # More tasks than agents
        if ratio > 0.8:
            return "balanced"
        if ratio > 0.3:
            return "competitive"  # More agents than tasks
        return "low_activity"

"""Market dynamics simulation for realistic economic cycles."""

from datetime import datetime
from enum import Enum
import random
from typing import Optional


class MarketPhase(Enum):
    """Market cycle phases."""

    BULL = "bull"  # High activity, many tasks, good funding
    BEAR = "bear"  # Low activity, few tasks, tight funding
    NORMAL = "normal"  # Moderate activity
    CRASH = "crash"  # Temporary extreme low (rare)


class MarketDynamics:
    """Simulates realistic market cycles and economic conditions.

    Implements:
    - Bull/bear market periods
    - Seasonal trends (weekday/weekend patterns)
    - Market crashes (rare)
    - Supply/demand-based pricing fluctuations
    """

    def __init__(
        self,
        initial_phase: MarketPhase = MarketPhase.NORMAL,
        phase_duration_hours: float = 48.0,
        crash_probability: float = 0.01,
        seed: Optional[int] = None,
    ):
        """Initialize market dynamics simulator.

        Args:
            initial_phase: Starting market phase
            phase_duration_hours: Average duration of each phase
            crash_probability: Probability of market crash (per phase transition)
            seed: Random seed for reproducibility
        """
        self.current_phase = initial_phase
        self.phase_duration_hours = phase_duration_hours
        self.crash_probability = crash_probability
        self.rng = random.Random(seed)

        # Track phase history
        self.phase_start_time = datetime.now()
        self.phase_history: list[tuple[datetime, MarketPhase]] = [(self.phase_start_time, initial_phase)]

    def get_current_phase(self) -> MarketPhase:
        """Get current market phase.

        Returns:
            Current market phase
        """
        return self.current_phase

    def get_task_availability_multiplier(self) -> float:
        """Get multiplier for number of available tasks based on market phase.

        Returns:
            Multiplier (0.1 - 2.0) to apply to base task count
        """
        multipliers = {
            MarketPhase.BULL: self.rng.uniform(1.3, 2.0),
            MarketPhase.NORMAL: self.rng.uniform(0.8, 1.2),
            MarketPhase.BEAR: self.rng.uniform(0.4, 0.7),
            MarketPhase.CRASH: self.rng.uniform(0.1, 0.3),
        }

        return multipliers[self.current_phase]

    def get_reward_multiplier(self) -> float:
        """Get multiplier for task rewards based on market phase.

        In bull markets, rewards go up (demand > supply).
        In bear markets, rewards go down (supply > demand).

        Returns:
            Multiplier (0.5 - 1.5) to apply to base reward
        """
        multipliers = {
            MarketPhase.BULL: self.rng.uniform(1.1, 1.5),
            MarketPhase.NORMAL: self.rng.uniform(0.9, 1.1),
            MarketPhase.BEAR: self.rng.uniform(0.6, 0.9),
            MarketPhase.CRASH: self.rng.uniform(0.5, 0.7),
        }

        return multipliers[self.current_phase]

    def get_investor_funding_multiplier(self) -> float:
        """Get multiplier for investor funding availability.

        Returns:
            Multiplier (0.3 - 2.0) to apply to base funding amounts
        """
        multipliers = {
            MarketPhase.BULL: self.rng.uniform(1.3, 2.0),
            MarketPhase.NORMAL: self.rng.uniform(0.8, 1.2),
            MarketPhase.BEAR: self.rng.uniform(0.5, 0.8),
            MarketPhase.CRASH: self.rng.uniform(0.3, 0.5),
        }

        return multipliers[self.current_phase]

    def get_investor_approval_probability_modifier(self) -> float:
        """Get modifier for investor approval probability.

        Returns:
            Modifier (-0.3 to +0.2) to add to base approval probability
        """
        modifiers = {
            MarketPhase.BULL: self.rng.uniform(0.05, 0.2),
            MarketPhase.NORMAL: self.rng.uniform(-0.05, 0.05),
            MarketPhase.BEAR: self.rng.uniform(-0.15, -0.05),
            MarketPhase.CRASH: self.rng.uniform(-0.3, -0.15),
        }

        return modifiers[self.current_phase]

    def is_weekend(self) -> bool:
        """Check if current time is weekend.

        Returns:
            True if Saturday or Sunday, False otherwise
        """
        return datetime.now().weekday() >= 5  # 5 = Saturday, 6 = Sunday

    def is_business_hours(self) -> bool:
        """Check if current time is during business hours (9am-5pm).

        Returns:
            True if business hours, False otherwise
        """
        current_hour = datetime.now().hour
        return 9 <= current_hour < 17

    def get_time_of_day_multiplier(self) -> float:
        """Get activity multiplier based on time of day.

        Weekdays during business hours = more activity.
        Weekends and nights = less activity.

        Returns:
            Multiplier (0.3 - 1.5) for task/funding availability
        """
        if self.is_weekend():
            # Weekend: lower activity
            return self.rng.uniform(0.3, 0.6)
        elif self.is_business_hours():
            # Weekday business hours: peak activity
            return self.rng.uniform(1.1, 1.5)
        else:
            # Weekday off-hours: moderate activity
            return self.rng.uniform(0.6, 0.9)

    def should_transition_phase(self) -> bool:
        """Check if market should transition to new phase.

        Returns:
            True if phase should change, False otherwise
        """
        hours_in_phase = (datetime.now() - self.phase_start_time).total_seconds() / 3600.0
        return hours_in_phase >= self.phase_duration_hours

    def transition_to_next_phase(self) -> MarketPhase:
        """Transition to next market phase.

        Returns:
            New market phase
        """
        # Check for crash (rare)
        if self.rng.random() < self.crash_probability:
            new_phase = MarketPhase.CRASH
        else:
            # Normal phase progression
            phase_weights = {
                MarketPhase.BULL: {
                    MarketPhase.BULL: 0.3,  # Can continue
                    MarketPhase.NORMAL: 0.5,
                    MarketPhase.BEAR: 0.2,
                },
                MarketPhase.NORMAL: {
                    MarketPhase.BULL: 0.3,
                    MarketPhase.NORMAL: 0.4,
                    MarketPhase.BEAR: 0.3,
                },
                MarketPhase.BEAR: {
                    MarketPhase.BULL: 0.2,
                    MarketPhase.NORMAL: 0.5,
                    MarketPhase.BEAR: 0.3,
                },
                MarketPhase.CRASH: {
                    MarketPhase.BULL: 0.1,
                    MarketPhase.NORMAL: 0.6,  # Usually recover to normal
                    MarketPhase.BEAR: 0.3,
                },
            }

            weights = phase_weights[self.current_phase]
            phases = list(weights.keys())
            probabilities = list(weights.values())
            new_phase = self.rng.choices(phases, weights=probabilities)[0]

        # Update phase
        self.current_phase = new_phase
        self.phase_start_time = datetime.now()
        self.phase_history.append((self.phase_start_time, new_phase))

        return new_phase

    def get_phase_description(self) -> str:
        """Get human-readable description of current market phase.

        Returns:
            Description string for current phase
        """
        descriptions = {
            MarketPhase.BULL: "Market is hot - high task availability and good funding",
            MarketPhase.NORMAL: "Market is stable - moderate activity",
            MarketPhase.BEAR: "Market is slow - fewer tasks and tight funding",
            MarketPhase.CRASH: "Market crash - minimal activity, funding dried up",
        }

        return descriptions[self.current_phase]

    def get_market_stats(self) -> dict:
        """Get current market statistics.

        Returns:
            Dict with market stats
        """
        return {
            "phase": self.current_phase.value,
            "phase_description": self.get_phase_description(),
            "task_multiplier": self.get_task_availability_multiplier(),
            "reward_multiplier": self.get_reward_multiplier(),
            "funding_multiplier": self.get_investor_funding_multiplier(),
            "is_weekend": self.is_weekend(),
            "is_business_hours": self.is_business_hours(),
            "time_multiplier": self.get_time_of_day_multiplier(),
            "hours_in_phase": (datetime.now() - self.phase_start_time).total_seconds() / 3600.0,
        }

    def update(self) -> Optional[MarketPhase]:
        """Update market state (call periodically).

        Returns:
            New phase if transition occurred, None otherwise
        """
        if self.should_transition_phase():
            return self.transition_to_next_phase()
        return None

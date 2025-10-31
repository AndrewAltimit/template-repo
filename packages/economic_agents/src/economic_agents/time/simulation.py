"""Time simulation for connecting agent cycles to calendar time."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List


class TimeUnit(str, Enum):
    """Units of time for simulation."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


@dataclass
class TimeBasedEvent:
    """Represents an event that should occur at a specific time."""

    name: str
    trigger_month: int  # Month number when event should trigger
    callback: Callable[[Any], None]
    recurring: bool = False  # If True, repeats every trigger_month months
    triggered: bool = False


@dataclass
class SimulationClock:
    """Tracks simulation time and converts between cycles and calendar time."""

    start_date: datetime = field(default_factory=datetime.now)
    hours_per_cycle: float = 24.0  # Default: 1 cycle = 1 day
    current_cycle: int = 0
    current_month: int = 0
    total_hours_elapsed: float = 0.0

    # Constants for time conversion
    HOURS_PER_DAY: float = 24.0
    HOURS_PER_WEEK: float = 168.0  # 24 * 7
    HOURS_PER_MONTH: float = 730.0  # Approximate: 24 * 30.417
    HOURS_PER_QUARTER: float = 2190.0  # 730 * 3
    HOURS_PER_YEAR: float = 8760.0  # 24 * 365

    def advance_cycle(self, hours_elapsed: float | None = None) -> Dict[str, Any]:
        """Advance the simulation by one cycle.

        Args:
            hours_elapsed: Hours that passed in this cycle (defaults to hours_per_cycle)

        Returns:
            Dict with time statistics
        """
        if hours_elapsed is None:
            hours_elapsed = self.hours_per_cycle

        self.current_cycle += 1
        self.total_hours_elapsed += hours_elapsed

        # Calculate current month from total hours
        previous_month = self.current_month
        self.current_month = int(self.total_hours_elapsed / self.HOURS_PER_MONTH)

        month_changed = self.current_month > previous_month

        return {
            "cycle": self.current_cycle,
            "month": self.current_month,
            "total_hours": self.total_hours_elapsed,
            "hours_elapsed": hours_elapsed,
            "month_changed": month_changed,
            "current_date": self.get_current_date(),
        }

    def get_current_date(self) -> datetime:
        """Get current simulation date.

        Returns:
            Datetime object representing current simulation time
        """
        return self.start_date + timedelta(hours=self.total_hours_elapsed)

    def get_time_stats(self) -> Dict[str, Any]:
        """Get comprehensive time statistics.

        Returns:
            Dict with all time-related metrics
        """
        return {
            "start_date": self.start_date.isoformat(),
            "current_date": self.get_current_date().isoformat(),
            "current_cycle": self.current_cycle,
            "current_month": self.current_month,
            "current_quarter": self.current_month // 3,
            "current_year": self.current_month // 12,
            "total_hours_elapsed": round(self.total_hours_elapsed, 2),
            "total_days_elapsed": round(self.total_hours_elapsed / self.HOURS_PER_DAY, 2),
            "total_weeks_elapsed": round(self.total_hours_elapsed / self.HOURS_PER_WEEK, 2),
        }

    def convert_to_unit(self, hours: float, unit: TimeUnit) -> float:
        """Convert hours to specified time unit.

        Args:
            hours: Number of hours to convert
            unit: Target time unit

        Returns:
            Converted value
        """
        conversions = {
            TimeUnit.HOUR: 1.0,
            TimeUnit.DAY: self.HOURS_PER_DAY,
            TimeUnit.WEEK: self.HOURS_PER_WEEK,
            TimeUnit.MONTH: self.HOURS_PER_MONTH,
            TimeUnit.QUARTER: self.HOURS_PER_QUARTER,
            TimeUnit.YEAR: self.HOURS_PER_YEAR,
        }

        return hours / conversions[unit]

    def get_elapsed_time(self, unit: TimeUnit) -> float:
        """Get elapsed time in specified unit.

        Args:
            unit: Time unit for measurement

        Returns:
            Elapsed time in specified unit
        """
        return self.convert_to_unit(self.total_hours_elapsed, unit)

    def reset(self) -> None:
        """Reset the simulation clock."""
        self.current_cycle = 0
        self.current_month = 0
        self.total_hours_elapsed = 0.0
        self.start_date = datetime.now()


@dataclass
class TimeTracker:
    """Tracks time-based events and triggers them when appropriate."""

    clock: SimulationClock
    events: List[TimeBasedEvent] = field(default_factory=list)
    event_log: List[Dict[str, Any]] = field(default_factory=list)

    def register_event(
        self, name: str, trigger_month: int, callback: Callable[[Any], None], recurring: bool = False
    ) -> TimeBasedEvent:
        """Register a new time-based event.

        Args:
            name: Event name
            trigger_month: Month when event should trigger
            callback: Function to call when event triggers
            recurring: Whether event repeats

        Returns:
            Created event
        """
        event = TimeBasedEvent(name=name, trigger_month=trigger_month, callback=callback, recurring=recurring)
        self.events.append(event)
        return event

    def check_and_trigger_events(self, context: Any = None) -> List[str]:
        """Check if any events should trigger and execute them.

        Args:
            context: Context to pass to event callbacks

        Returns:
            List of triggered event names
        """
        triggered_events = []

        for event in self.events:
            should_trigger = False

            if event.recurring:
                # Recurring events trigger every N months
                if self.clock.current_month > 0 and self.clock.current_month % event.trigger_month == 0:
                    should_trigger = True
            else:
                # One-time events trigger at specific month
                if self.clock.current_month == event.trigger_month and not event.triggered:
                    should_trigger = True

            if should_trigger:
                try:
                    event.callback(context)
                    event.triggered = True
                    triggered_events.append(event.name)

                    # Log the event
                    self.event_log.append(
                        {
                            "event_name": event.name,
                            "triggered_at_month": self.clock.current_month,
                            "triggered_at_cycle": self.clock.current_cycle,
                            "triggered_at_date": self.clock.get_current_date().isoformat(),
                        }
                    )
                except Exception as e:
                    # Log error but don't crash simulation
                    self.event_log.append(
                        {
                            "event_name": event.name,
                            "error": str(e),
                            "triggered_at_month": self.clock.current_month,
                        }
                    )

                # Reset triggered flag for recurring events
                if event.recurring:
                    event.triggered = False

        return triggered_events

    def get_upcoming_events(self, months_ahead: int = 3) -> List[Dict[str, Any]]:
        """Get list of events scheduled for the near future.

        Args:
            months_ahead: How many months to look ahead

        Returns:
            List of upcoming events
        """
        upcoming = []
        target_month = self.clock.current_month + months_ahead

        for event in self.events:
            if event.recurring:
                # Calculate next occurrence for recurring events
                if self.clock.current_month % event.trigger_month == 0:
                    next_occurrence = self.clock.current_month + event.trigger_month
                else:
                    next_occurrence = (
                        self.clock.current_month + event.trigger_month - (self.clock.current_month % event.trigger_month)
                    )

                if next_occurrence <= target_month:
                    upcoming.append(
                        {"event_name": event.name, "trigger_month": next_occurrence, "recurring": True, "status": "pending"}
                    )
            else:
                # One-time events
                if not event.triggered and event.trigger_month <= target_month:
                    upcoming.append(
                        {
                            "event_name": event.name,
                            "trigger_month": event.trigger_month,
                            "recurring": False,
                            "status": "pending",
                        }
                    )

        return sorted(upcoming, key=lambda x: x["trigger_month"])

    def get_event_summary(self) -> Dict[str, Any]:
        """Get summary of all events and their status.

        Returns:
            Event summary statistics
        """
        total_events = len(self.events)
        triggered_count = sum(1 for e in self.events if e.triggered and not e.recurring)
        recurring_count = sum(1 for e in self.events if e.recurring)
        pending_count = sum(1 for e in self.events if not e.triggered and not e.recurring)

        return {
            "total_events": total_events,
            "triggered_events": triggered_count,
            "recurring_events": recurring_count,
            "pending_events": pending_count,
            "event_log_entries": len(self.event_log),
            "current_month": self.clock.current_month,
        }

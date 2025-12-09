"""Tests for time simulation (P1 #7)."""

from datetime import datetime, timedelta

from economic_agents.time.simulation import SimulationClock, TimeBasedEvent, TimeTracker, TimeUnit

# SimulationClock Tests


def test_simulation_clock_initialization():
    """Test SimulationClock initializes with correct defaults."""
    clock = SimulationClock()

    assert clock.current_cycle == 0
    assert clock.current_month == 0
    assert clock.total_hours_elapsed == 0.0
    assert clock.hours_per_cycle == 24.0


def test_simulation_clock_advance_single_cycle():
    """Test advancing clock by one cycle."""
    clock = SimulationClock(hours_per_cycle=24.0)

    result = clock.advance_cycle()

    assert result["cycle"] == 1
    assert result["hours_elapsed"] == 24.0
    assert clock.total_hours_elapsed == 24.0
    assert clock.current_cycle == 1


def test_simulation_clock_advance_to_next_month():
    """Test clock properly increments month after enough hours."""
    clock = SimulationClock(hours_per_cycle=730.0)  # 1 cycle = 1 month

    result = clock.advance_cycle()

    assert clock.current_month == 1
    assert result["month_changed"] is True


def test_simulation_clock_multiple_cycles():
    """Test clock tracking over multiple cycles."""
    clock = SimulationClock(hours_per_cycle=100.0)

    for _ in range(10):
        clock.advance_cycle()

    assert clock.current_cycle == 10
    assert clock.total_hours_elapsed == 1000.0
    assert clock.current_month == 1  # 1000 hours ~ 1.37 months


def test_simulation_clock_custom_hours_per_cycle():
    """Test clock with custom hours per cycle."""
    clock = SimulationClock(hours_per_cycle=10.0)

    clock.advance_cycle(hours_elapsed=50.0)  # Override default

    assert clock.total_hours_elapsed == 50.0
    assert clock.current_cycle == 1


def test_simulation_clock_get_current_date():
    """Test getting current simulation date."""
    start = datetime(2024, 1, 1, 0, 0, 0)
    clock = SimulationClock(start_date=start, hours_per_cycle=24.0)

    clock.advance_cycle()  # +24 hours = +1 day

    current = clock.get_current_date()
    assert current == start + timedelta(hours=24)


def test_simulation_clock_time_stats():
    """Test comprehensive time statistics."""
    clock = SimulationClock(hours_per_cycle=730.0)  # 1 month per cycle

    clock.advance_cycle()  # Month 1
    clock.advance_cycle()  # Month 2
    clock.advance_cycle()  # Month 3

    stats = clock.get_time_stats()

    assert stats["current_cycle"] == 3
    assert stats["current_month"] == 3
    assert stats["current_quarter"] == 1
    assert stats["total_hours_elapsed"] == 2190.0


def test_simulation_clock_convert_to_unit():
    """Test time unit conversions."""
    clock = SimulationClock()

    # 730 hours should equal 1 month
    assert clock.convert_to_unit(730.0, TimeUnit.MONTH) == 1.0

    # 24 hours should equal 1 day
    assert clock.convert_to_unit(24.0, TimeUnit.DAY) == 1.0

    # 168 hours should equal 1 week
    assert clock.convert_to_unit(168.0, TimeUnit.WEEK) == 1.0


def test_simulation_clock_get_elapsed_time():
    """Test getting elapsed time in different units."""
    clock = SimulationClock(hours_per_cycle=730.0)  # 1 month per cycle

    clock.advance_cycle()
    clock.advance_cycle()

    assert clock.get_elapsed_time(TimeUnit.MONTH) == 2.0
    assert clock.get_elapsed_time(TimeUnit.HOUR) == 1460.0


def test_simulation_clock_reset():
    """Test resetting the simulation clock."""
    clock = SimulationClock()

    clock.advance_cycle()
    clock.advance_cycle()
    clock.advance_cycle()

    clock.reset()

    assert clock.current_cycle == 0
    assert clock.current_month == 0
    assert clock.total_hours_elapsed == 0.0


# TimeBasedEvent Tests


def test_time_based_event_creation():
    """Test creating a time-based event."""
    triggered = []

    def callback(ctx):
        triggered.append(ctx)

    event = TimeBasedEvent(name="test_event", trigger_month=3, callback=callback, recurring=False)

    assert event.name == "test_event"
    assert event.trigger_month == 3
    assert event.recurring is False
    assert event.triggered is False


# TimeTracker Tests


def test_time_tracker_initialization():
    """Test TimeTracker initialization."""
    clock = SimulationClock()
    tracker = TimeTracker(clock=clock)

    assert tracker.clock == clock
    assert len(tracker.events) == 0
    assert len(tracker.event_log) == 0


def test_time_tracker_register_event():
    """Test registering an event with tracker."""
    clock = SimulationClock()
    tracker = TimeTracker(clock=clock)

    def callback(ctx):
        pass

    event = tracker.register_event(name="milestone", trigger_month=6, callback=callback)

    assert len(tracker.events) == 1
    assert event.name == "milestone"
    assert event.trigger_month == 6


def test_time_tracker_trigger_one_time_event():
    """Test triggering a one-time event."""
    clock = SimulationClock(hours_per_cycle=730.0)  # 1 month per cycle
    tracker = TimeTracker(clock=clock)

    triggered_context = []

    def callback(ctx):
        triggered_context.append(ctx)

    tracker.register_event(name="milestone", trigger_month=3, callback=callback)

    # Advance to month 3
    for _ in range(3):
        clock.advance_cycle()
        triggered_events = tracker.check_and_trigger_events(context="test_context")

    assert len(triggered_context) == 1
    assert triggered_context[0] == "test_context"
    assert "milestone" in triggered_events


def test_time_tracker_one_time_event_only_triggers_once():
    """Test that one-time events don't trigger multiple times."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    trigger_count = []

    def callback(ctx):
        trigger_count.append(1)

    tracker.register_event(name="one_time", trigger_month=2, callback=callback)

    # Advance through month 2 multiple times
    for _ in range(5):
        clock.advance_cycle()
        tracker.check_and_trigger_events()

    # Should only trigger once at month 2
    assert sum(trigger_count) == 1


def test_time_tracker_recurring_event():
    """Test recurring events trigger multiple times."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    trigger_months = []

    def callback(ctx):
        trigger_months.append(clock.current_month)

    # Event that recurs every 3 months
    tracker.register_event(name="quarterly_review", trigger_month=3, callback=callback, recurring=True)

    # Advance through 12 months
    for _ in range(12):
        clock.advance_cycle()
        tracker.check_and_trigger_events()

    # Should trigger at months 3, 6, 9, 12
    assert len(trigger_months) == 4
    assert trigger_months == [3, 6, 9, 12]


def test_time_tracker_multiple_events():
    """Test tracking multiple events."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    results = {"event1": 0, "event2": 0, "event3": 0}

    def make_callback(event_name):
        def callback(ctx):
            results[event_name] += 1

        return callback

    tracker.register_event(name="event1", trigger_month=2, callback=make_callback("event1"))
    tracker.register_event(name="event2", trigger_month=5, callback=make_callback("event2"))
    tracker.register_event(name="event3", trigger_month=2, callback=make_callback("event3"))

    # Advance through 6 months
    for _ in range(6):
        clock.advance_cycle()
        tracker.check_and_trigger_events()

    assert results["event1"] == 1  # Triggered at month 2
    assert results["event2"] == 1  # Triggered at month 5
    assert results["event3"] == 1  # Triggered at month 2


def test_time_tracker_event_log():
    """Test event logging functionality."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    def callback(ctx):
        pass

    tracker.register_event(name="logged_event", trigger_month=1, callback=callback)

    clock.advance_cycle()
    tracker.check_and_trigger_events()

    assert len(tracker.event_log) == 1
    assert tracker.event_log[0]["event_name"] == "logged_event"
    assert tracker.event_log[0]["triggered_at_month"] == 1


def test_time_tracker_error_handling():
    """Test that event errors don't crash the tracker."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    def failing_callback(ctx):
        raise ValueError("Intentional error")

    def working_callback(ctx):
        pass

    tracker.register_event(name="failing", trigger_month=1, callback=failing_callback)
    tracker.register_event(name="working", trigger_month=1, callback=working_callback)

    clock.advance_cycle()
    triggered = tracker.check_and_trigger_events()

    # Both events should be attempted (working event succeeds)
    assert len(triggered) >= 1  # At least the working event triggered
    # Both events should be in log, one with error
    assert len(tracker.event_log) == 2
    assert any("error" in log for log in tracker.event_log)


def test_time_tracker_get_upcoming_events():
    """Test getting upcoming events."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    def callback(ctx):
        pass

    tracker.register_event(name="event1", trigger_month=5, callback=callback)
    tracker.register_event(name="event2", trigger_month=8, callback=callback)
    tracker.register_event(name="recurring", trigger_month=3, callback=callback, recurring=True)

    # At month 0, looking 6 months ahead
    upcoming = tracker.get_upcoming_events(months_ahead=6)

    # Should see: recurring at month 3, event1 at month 5, recurring at month 6
    assert len(upcoming) >= 2
    assert any(e["event_name"] == "event1" for e in upcoming)


def test_time_tracker_get_event_summary():
    """Test getting event summary statistics."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    def callback(ctx):
        pass

    tracker.register_event(name="one_time", trigger_month=1, callback=callback)
    tracker.register_event(name="recurring", trigger_month=2, callback=callback, recurring=True)

    # Trigger events
    for _ in range(3):
        clock.advance_cycle()
        tracker.check_and_trigger_events()

    summary = tracker.get_event_summary()

    assert summary["total_events"] == 2
    assert summary["triggered_events"] == 1  # One-time event triggered
    assert summary["recurring_events"] == 1
    assert summary["current_month"] == 3


# Integration Tests


def test_integration_monthly_operations():
    """Test simulation clock with monthly company operations."""
    clock = SimulationClock(hours_per_cycle=730.0)  # 1 month per cycle
    tracker = TimeTracker(clock=clock)

    monthly_reports = []

    def monthly_report(ctx):
        monthly_reports.append({"month": clock.current_month, "cycle": clock.current_cycle, "context": ctx})

    # Monthly recurring event
    tracker.register_event(name="monthly_burn", trigger_month=1, callback=monthly_report, recurring=True)

    # Run for 6 months
    for i in range(6):
        clock.advance_cycle()
        tracker.check_and_trigger_events(context=f"month_{i+1}")

    # Should have 6 monthly reports
    assert len(monthly_reports) == 6
    assert monthly_reports[0]["month"] == 1
    assert monthly_reports[5]["month"] == 6


def test_integration_quarterly_reviews():
    """Test quarterly review events."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    quarterly_reviews = []

    def quarterly_review(ctx):
        quarterly_reviews.append(clock.current_month)

    tracker.register_event(name="quarterly", trigger_month=3, callback=quarterly_review, recurring=True)

    # Run for 12 months
    for _ in range(12):
        clock.advance_cycle()
        tracker.check_and_trigger_events()

    # Should have 4 quarterly reviews (months 3, 6, 9, 12)
    assert len(quarterly_reviews) == 4
    assert quarterly_reviews == [3, 6, 9, 12]


def test_integration_milestone_tracking():
    """Test tracking company milestones over time."""
    clock = SimulationClock(hours_per_cycle=730.0)
    tracker = TimeTracker(clock=clock)

    milestones = []

    def milestone(ctx):
        milestones.append(ctx)

    # Set up milestones
    tracker.register_event(name="product_launch", trigger_month=3, callback=milestone)
    tracker.register_event(name="first_customer", trigger_month=4, callback=milestone)
    tracker.register_event(name="break_even", trigger_month=8, callback=milestone)

    # Run simulation
    for month in range(10):
        clock.advance_cycle()
        triggered = tracker.check_and_trigger_events(context=f"milestone_month_{month+1}")

        if triggered:
            assert len(triggered) > 0

    assert len(milestones) == 3
    assert "milestone_month_3" in milestones
    assert "milestone_month_4" in milestones
    assert "milestone_month_8" in milestones


def test_integration_time_stats_accuracy():
    """Test accuracy of time statistics over long simulation."""
    clock = SimulationClock(hours_per_cycle=24.0)  # 1 day per cycle

    # Simulate 365 days (1 year)
    for _ in range(365):
        clock.advance_cycle()

    stats = clock.get_time_stats()

    # Should be approximately 12 months and 1 year
    assert stats["current_month"] == 12
    assert stats["current_year"] == 1
    assert stats["total_days_elapsed"] == 365.0

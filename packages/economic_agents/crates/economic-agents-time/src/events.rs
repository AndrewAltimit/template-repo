//! Time-based event tracking.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tracing::debug;

use crate::clock::SimulationClock;

/// Represents an event that should occur at a specific time.
#[derive(Debug, Clone)]
pub struct TimeBasedEvent {
    /// Event name.
    pub name: String,
    /// Month number when event should trigger.
    pub trigger_month: u32,
    /// Whether event repeats every trigger_month months.
    pub recurring: bool,
    /// Whether event has been triggered.
    pub triggered: bool,
    /// Event payload/data.
    pub payload: serde_json::Value,
}

impl TimeBasedEvent {
    /// Create a new time-based event.
    pub fn new(name: impl Into<String>, trigger_month: u32) -> Self {
        Self {
            name: name.into(),
            trigger_month,
            recurring: false,
            triggered: false,
            payload: serde_json::Value::Null,
        }
    }

    /// Make the event recurring.
    pub fn recurring(mut self) -> Self {
        self.recurring = true;
        self
    }

    /// Add payload data.
    pub fn with_payload(mut self, payload: serde_json::Value) -> Self {
        self.payload = payload;
        self
    }
}

/// Log entry for a triggered event.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventLogEntry {
    /// Event name.
    pub event_name: String,
    /// Month when triggered.
    pub triggered_at_month: u32,
    /// Cycle when triggered.
    pub triggered_at_cycle: u32,
    /// Date when triggered.
    pub triggered_at_date: DateTime<Utc>,
    /// Whether successful.
    pub success: bool,
    /// Error message if failed.
    pub error: Option<String>,
}

/// Information about an upcoming event.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpcomingEvent {
    /// Event name.
    pub event_name: String,
    /// Month when it will trigger.
    pub trigger_month: u32,
    /// Whether it's recurring.
    pub recurring: bool,
    /// Event status.
    pub status: String,
}

/// Event summary statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventSummary {
    /// Total registered events.
    pub total_events: usize,
    /// Number triggered (non-recurring).
    pub triggered_events: usize,
    /// Number of recurring events.
    pub recurring_events: usize,
    /// Number pending (non-recurring).
    pub pending_events: usize,
    /// Event log entries count.
    pub event_log_entries: usize,
    /// Current month.
    pub current_month: u32,
}

/// Result of checking for triggered events.
#[derive(Debug, Clone)]
pub struct TriggeredEvent {
    /// Event name.
    pub name: String,
    /// Event payload.
    pub payload: serde_json::Value,
    /// Month triggered.
    pub triggered_month: u32,
}

/// Tracks time-based events and triggers them when appropriate.
pub struct TimeTracker {
    /// Reference to simulation clock.
    clock: SimulationClock,
    /// Registered events.
    events: Vec<TimeBasedEvent>,
    /// Event log.
    event_log: Vec<EventLogEntry>,
    /// Last checked month (for recurring events).
    last_checked_month: u32,
}

impl TimeTracker {
    /// Create a new time tracker.
    pub fn new(clock: SimulationClock) -> Self {
        Self {
            clock,
            events: Vec::new(),
            event_log: Vec::new(),
            last_checked_month: 0,
        }
    }

    /// Get reference to the clock.
    pub fn clock(&self) -> &SimulationClock {
        &self.clock
    }

    /// Get mutable reference to the clock.
    pub fn clock_mut(&mut self) -> &mut SimulationClock {
        &mut self.clock
    }

    /// Register a new time-based event.
    pub fn register_event(&mut self, event: TimeBasedEvent) {
        debug!(name = %event.name, month = event.trigger_month, "Event registered");
        self.events.push(event);
    }

    /// Register a one-time event.
    pub fn register_one_time(&mut self, name: impl Into<String>, trigger_month: u32) {
        self.register_event(TimeBasedEvent::new(name, trigger_month));
    }

    /// Register a recurring event.
    pub fn register_recurring(&mut self, name: impl Into<String>, every_n_months: u32) {
        self.register_event(TimeBasedEvent::new(name, every_n_months).recurring());
    }

    /// Check for and collect triggered events.
    ///
    /// Unlike the Python version which takes callbacks, this returns
    /// the list of triggered events for the caller to handle.
    pub fn check_events(&mut self) -> Vec<TriggeredEvent> {
        let mut triggered = Vec::new();
        let current_month = self.clock.current_month;

        for event in &mut self.events {
            let should_trigger = if event.recurring {
                // Recurring events trigger every N months
                current_month > 0
                    && current_month > self.last_checked_month
                    && current_month.is_multiple_of(event.trigger_month)
            } else {
                // One-time events trigger at specific month
                current_month == event.trigger_month && !event.triggered
            };

            if should_trigger {
                triggered.push(TriggeredEvent {
                    name: event.name.clone(),
                    payload: event.payload.clone(),
                    triggered_month: current_month,
                });

                self.event_log.push(EventLogEntry {
                    event_name: event.name.clone(),
                    triggered_at_month: current_month,
                    triggered_at_cycle: self.clock.current_cycle,
                    triggered_at_date: self.clock.get_current_date(),
                    success: true,
                    error: None,
                });

                if !event.recurring {
                    event.triggered = true;
                }

                debug!(
                    name = %event.name,
                    month = current_month,
                    "Event triggered"
                );
            }
        }

        self.last_checked_month = current_month;
        triggered
    }

    /// Get list of upcoming events.
    pub fn get_upcoming_events(&self, months_ahead: u32) -> Vec<UpcomingEvent> {
        let target_month = self.clock.current_month + months_ahead;
        let mut upcoming = Vec::new();

        for event in &self.events {
            if event.recurring {
                // Calculate next occurrence for recurring events
                let next = if self.clock.current_month.is_multiple_of(event.trigger_month) {
                    self.clock.current_month + event.trigger_month
                } else {
                    let remainder = self.clock.current_month % event.trigger_month;
                    self.clock.current_month + event.trigger_month - remainder
                };

                if next <= target_month {
                    upcoming.push(UpcomingEvent {
                        event_name: event.name.clone(),
                        trigger_month: next,
                        recurring: true,
                        status: "pending".to_string(),
                    });
                }
            } else if !event.triggered && event.trigger_month <= target_month {
                upcoming.push(UpcomingEvent {
                    event_name: event.name.clone(),
                    trigger_month: event.trigger_month,
                    recurring: false,
                    status: "pending".to_string(),
                });
            }
        }

        upcoming.sort_by_key(|e| e.trigger_month);
        upcoming
    }

    /// Get event summary statistics.
    pub fn get_summary(&self) -> EventSummary {
        let total = self.events.len();
        let triggered = self
            .events
            .iter()
            .filter(|e| e.triggered && !e.recurring)
            .count();
        let recurring = self.events.iter().filter(|e| e.recurring).count();
        let pending = self
            .events
            .iter()
            .filter(|e| !e.triggered && !e.recurring)
            .count();

        EventSummary {
            total_events: total,
            triggered_events: triggered,
            recurring_events: recurring,
            pending_events: pending,
            event_log_entries: self.event_log.len(),
            current_month: self.clock.current_month,
        }
    }

    /// Get the event log.
    pub fn event_log(&self) -> &[EventLogEntry] {
        &self.event_log
    }

    /// Clear all events.
    pub fn clear_events(&mut self) {
        self.events.clear();
        self.event_log.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_time_based_event() {
        let event = TimeBasedEvent::new("quarterly_report", 3).recurring();
        assert_eq!(event.name, "quarterly_report");
        assert_eq!(event.trigger_month, 3);
        assert!(event.recurring);
        assert!(!event.triggered);
    }

    #[test]
    fn test_time_tracker_creation() {
        let clock = SimulationClock::new();
        let tracker = TimeTracker::new(clock);
        assert!(tracker.events.is_empty());
        assert!(tracker.event_log.is_empty());
    }

    #[test]
    fn test_register_events() {
        let clock = SimulationClock::new();
        let mut tracker = TimeTracker::new(clock);

        tracker.register_one_time("launch", 6);
        tracker.register_recurring("monthly_review", 1);

        assert_eq!(tracker.events.len(), 2);
    }

    #[test]
    fn test_one_time_event_triggers() {
        let mut clock = SimulationClock::new();
        // Set to month 1
        clock.current_month = 1;
        clock.total_hours_elapsed = 730.0;

        let mut tracker = TimeTracker::new(clock);
        tracker.register_one_time("month_one_event", 1);

        let triggered = tracker.check_events();
        assert_eq!(triggered.len(), 1);
        assert_eq!(triggered[0].name, "month_one_event");

        // Should not trigger again
        let triggered = tracker.check_events();
        assert!(triggered.is_empty());
    }

    #[test]
    fn test_recurring_event_triggers() {
        let mut clock = SimulationClock::new();
        clock.current_month = 3;

        let mut tracker = TimeTracker::new(clock);
        tracker.register_recurring("quarterly", 3);

        let triggered = tracker.check_events();
        assert_eq!(triggered.len(), 1);

        // Advance to month 6
        tracker.clock_mut().current_month = 6;
        let triggered = tracker.check_events();
        assert_eq!(triggered.len(), 1);
    }

    #[test]
    fn test_get_upcoming_events() {
        let clock = SimulationClock::new();
        let mut tracker = TimeTracker::new(clock);

        tracker.register_one_time("launch", 2);
        tracker.register_recurring("monthly", 1);

        let upcoming = tracker.get_upcoming_events(3);
        assert!(!upcoming.is_empty());
    }

    #[test]
    fn test_event_summary() {
        let clock = SimulationClock::new();
        let mut tracker = TimeTracker::new(clock);

        tracker.register_one_time("event1", 5);
        tracker.register_recurring("event2", 3);

        let summary = tracker.get_summary();
        assert_eq!(summary.total_events, 2);
        assert_eq!(summary.recurring_events, 1);
        assert_eq!(summary.pending_events, 1);
    }
}

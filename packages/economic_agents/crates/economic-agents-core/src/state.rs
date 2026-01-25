//! Agent state management.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Current state of an autonomous agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentState {
    /// Current balance.
    pub balance: f64,
    /// Compute hours remaining.
    pub compute_hours: f64,
    /// Number of tasks completed.
    pub tasks_completed: u32,
    /// Total earnings across all time.
    pub total_earnings: f64,
    /// Total expenses across all time.
    pub total_expenses: f64,
    /// Whether the agent has formed a company.
    pub has_company: bool,
    /// Current cycle number.
    pub current_cycle: u32,
    /// Last state update timestamp.
    pub last_updated: DateTime<Utc>,
}

impl Default for AgentState {
    fn default() -> Self {
        Self {
            balance: 0.0,
            compute_hours: 0.0,
            tasks_completed: 0,
            total_earnings: 0.0,
            total_expenses: 0.0,
            has_company: false,
            current_cycle: 0,
            last_updated: Utc::now(),
        }
    }
}

impl AgentState {
    /// Create a new agent state with initial values.
    pub fn new(initial_balance: f64, initial_compute_hours: f64) -> Self {
        Self {
            balance: initial_balance,
            compute_hours: initial_compute_hours,
            ..Default::default()
        }
    }

    /// Update the state timestamp.
    pub fn touch(&mut self) {
        self.last_updated = Utc::now();
    }

    /// Record earnings from a completed task.
    pub fn record_earnings(&mut self, amount: f64) {
        self.balance += amount;
        self.total_earnings += amount;
        self.tasks_completed += 1;
        self.touch();
    }

    /// Record an expense.
    pub fn record_expense(&mut self, amount: f64) {
        self.balance -= amount;
        self.total_expenses += amount;
        self.touch();
    }

    /// Consume compute hours.
    pub fn consume_compute(&mut self, hours: f64) {
        self.compute_hours -= hours;
        self.touch();
    }

    /// Add compute hours.
    pub fn add_compute(&mut self, hours: f64) {
        self.compute_hours += hours;
        self.touch();
    }

    /// Check if agent can survive (has positive resources).
    pub fn can_survive(&self) -> bool {
        self.compute_hours > 0.0 || self.balance > 0.0
    }

    /// Increment cycle counter.
    pub fn next_cycle(&mut self) {
        self.current_cycle += 1;
        self.touch();
    }
}

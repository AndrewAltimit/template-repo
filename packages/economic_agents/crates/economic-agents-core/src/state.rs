//! Agent state management.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Current state of an autonomous agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentState {
    /// Current balance.
    pub balance: f64,
    /// Compute hours remaining.
    pub compute_hours: f64,
    /// Number of tasks completed.
    pub tasks_completed: u32,
    /// Number of tasks failed/rejected.
    pub tasks_failed: u32,
    /// Total earnings across all time.
    pub total_earnings: f64,
    /// Total expenses across all time.
    pub total_expenses: f64,
    /// Whether the agent has formed a company.
    pub has_company: bool,
    /// Company ID if one exists.
    pub company_id: Option<Uuid>,
    /// Current cycle number.
    pub current_cycle: u32,
    /// Whether the agent is currently active.
    pub is_active: bool,
    /// Current task being worked on (if any).
    pub current_task_id: Option<Uuid>,
    /// Reputation score (0.0-1.0).
    pub reputation: f64,
    /// Number of consecutive failures.
    pub consecutive_failures: u32,
    /// Last state update timestamp.
    pub last_updated: DateTime<Utc>,
}

impl Default for AgentState {
    fn default() -> Self {
        Self {
            balance: 0.0,
            compute_hours: 0.0,
            tasks_completed: 0,
            tasks_failed: 0,
            total_earnings: 0.0,
            total_expenses: 0.0,
            has_company: false,
            company_id: None,
            current_cycle: 0,
            is_active: true,
            current_task_id: None,
            reputation: 0.5,
            consecutive_failures: 0,
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
        self.consecutive_failures = 0;
        // Increase reputation on success
        self.reputation = (self.reputation + 0.01).min(1.0);
        self.touch();
    }

    /// Record a failed/rejected task.
    pub fn record_failure(&mut self) {
        self.tasks_failed += 1;
        self.consecutive_failures += 1;
        // Decrease reputation on failure
        self.reputation = (self.reputation - 0.02).max(0.0);
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
        self.compute_hours = (self.compute_hours - hours).max(0.0);
        self.touch();
    }

    /// Add compute hours.
    pub fn add_compute(&mut self, hours: f64) {
        self.compute_hours += hours;
        self.touch();
    }

    /// Check if survival is at risk (low resources).
    pub fn survival_at_risk(&self, buffer_hours: f64) -> bool {
        self.compute_hours < buffer_hours
    }

    /// Check if agent can survive (has positive resources).
    pub fn can_survive(&self) -> bool {
        self.compute_hours > 0.0 || self.balance > 0.0
    }

    /// Check if agent can afford company formation.
    pub fn can_form_company(&self, threshold: f64, buffer_hours: f64) -> bool {
        !self.has_company && self.balance >= threshold && !self.survival_at_risk(buffer_hours)
    }

    /// Set the company ID and mark as having a company.
    pub fn set_company(&mut self, company_id: Uuid) {
        self.company_id = Some(company_id);
        self.has_company = true;
        self.touch();
    }

    /// Increment cycle counter.
    pub fn next_cycle(&mut self) {
        self.current_cycle += 1;
        self.touch();
    }

    /// Calculate success rate.
    pub fn success_rate(&self) -> f64 {
        let total = self.tasks_completed + self.tasks_failed;
        if total == 0 {
            0.0
        } else {
            self.tasks_completed as f64 / total as f64
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_state() {
        let state = AgentState::default();
        assert_eq!(state.balance, 0.0);
        assert_eq!(state.compute_hours, 0.0);
        assert!(!state.has_company);
        assert!(state.is_active);
    }

    #[test]
    fn test_new_with_initial_values() {
        let state = AgentState::new(100.0, 24.0);
        assert_eq!(state.balance, 100.0);
        assert_eq!(state.compute_hours, 24.0);
    }

    #[test]
    fn test_record_earnings() {
        let mut state = AgentState::default();
        state.record_earnings(50.0);
        assert_eq!(state.balance, 50.0);
        assert_eq!(state.total_earnings, 50.0);
        assert_eq!(state.tasks_completed, 1);
    }

    #[test]
    fn test_record_failure() {
        let mut state = AgentState {
            reputation: 0.5,
            ..Default::default()
        };
        state.record_failure();
        assert_eq!(state.tasks_failed, 1);
        assert_eq!(state.consecutive_failures, 1);
        assert!(state.reputation < 0.5);
    }

    #[test]
    fn test_survival_at_risk() {
        let mut state = AgentState::new(100.0, 10.0);
        assert!(state.survival_at_risk(24.0));
        state.add_compute(20.0);
        assert!(!state.survival_at_risk(24.0));
    }

    #[test]
    fn test_can_form_company() {
        let mut state = AgentState::new(50.0, 48.0);
        assert!(!state.can_form_company(100.0, 24.0)); // Not enough balance

        state.balance = 150.0;
        assert!(state.can_form_company(100.0, 24.0)); // Now can form

        state.has_company = true;
        assert!(!state.can_form_company(100.0, 24.0)); // Already has company
    }

    #[test]
    fn test_success_rate() {
        let mut state = AgentState::default();
        assert_eq!(state.success_rate(), 0.0);

        state.tasks_completed = 3;
        state.tasks_failed = 1;
        assert_eq!(state.success_rate(), 0.75);
    }
}

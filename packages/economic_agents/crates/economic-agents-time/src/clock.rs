//! Simulation clock for tracking simulation time.

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

/// Units of time for simulation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TimeUnit {
    /// Hour.
    Hour,
    /// Day.
    Day,
    /// Week.
    Week,
    /// Month.
    Month,
    /// Quarter.
    Quarter,
    /// Year.
    Year,
}

impl TimeUnit {
    /// Get hours in this time unit.
    pub fn hours(&self) -> f64 {
        match self {
            TimeUnit::Hour => 1.0,
            TimeUnit::Day => 24.0,
            TimeUnit::Week => 168.0,     // 24 * 7
            TimeUnit::Month => 730.0,    // ~24 * 30.417
            TimeUnit::Quarter => 2190.0, // 730 * 3
            TimeUnit::Year => 8760.0,    // 24 * 365
        }
    }
}

/// Result of advancing a cycle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CycleAdvanceResult {
    /// Current cycle number.
    pub cycle: u32,
    /// Current month number.
    pub month: u32,
    /// Total hours elapsed.
    pub total_hours: f64,
    /// Hours elapsed in this cycle.
    pub hours_elapsed: f64,
    /// Whether the month changed.
    pub month_changed: bool,
    /// Current simulation date.
    pub current_date: DateTime<Utc>,
}

/// Comprehensive time statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeStats {
    /// Simulation start date.
    pub start_date: DateTime<Utc>,
    /// Current simulation date.
    pub current_date: DateTime<Utc>,
    /// Current cycle number.
    pub current_cycle: u32,
    /// Current month number.
    pub current_month: u32,
    /// Current quarter number.
    pub current_quarter: u32,
    /// Current year number.
    pub current_year: u32,
    /// Total hours elapsed.
    pub total_hours_elapsed: f64,
    /// Total days elapsed.
    pub total_days_elapsed: f64,
    /// Total weeks elapsed.
    pub total_weeks_elapsed: f64,
}

/// Tracks simulation time and converts between cycles and calendar time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationClock {
    /// Simulation start date.
    pub start_date: DateTime<Utc>,
    /// Hours per cycle (default: 24 = 1 day per cycle).
    pub hours_per_cycle: f64,
    /// Current cycle number.
    pub current_cycle: u32,
    /// Current month number.
    pub current_month: u32,
    /// Total hours elapsed.
    pub total_hours_elapsed: f64,
}

impl Default for SimulationClock {
    fn default() -> Self {
        Self::new()
    }
}

impl SimulationClock {
    /// Create a new simulation clock.
    pub fn new() -> Self {
        Self {
            start_date: Utc::now(),
            hours_per_cycle: 24.0,
            current_cycle: 0,
            current_month: 0,
            total_hours_elapsed: 0.0,
        }
    }

    /// Create with custom start date.
    pub fn with_start_date(start_date: DateTime<Utc>) -> Self {
        Self {
            start_date,
            ..Self::new()
        }
    }

    /// Create with custom hours per cycle.
    pub fn with_hours_per_cycle(hours_per_cycle: f64) -> Self {
        Self {
            hours_per_cycle,
            ..Self::new()
        }
    }

    /// Advance the simulation by one cycle.
    ///
    /// # Arguments
    /// * `hours_elapsed` - Optional custom hours for this cycle
    ///
    /// # Returns
    /// Cycle advance result with time statistics
    pub fn advance_cycle(&mut self, hours_elapsed: Option<f64>) -> CycleAdvanceResult {
        let hours = hours_elapsed.unwrap_or(self.hours_per_cycle);

        self.current_cycle += 1;
        self.total_hours_elapsed += hours;

        // Calculate current month from total hours
        let previous_month = self.current_month;
        self.current_month = (self.total_hours_elapsed / TimeUnit::Month.hours()) as u32;

        let month_changed = self.current_month > previous_month;

        CycleAdvanceResult {
            cycle: self.current_cycle,
            month: self.current_month,
            total_hours: self.total_hours_elapsed,
            hours_elapsed: hours,
            month_changed,
            current_date: self.get_current_date(),
        }
    }

    /// Get current simulation date.
    pub fn get_current_date(&self) -> DateTime<Utc> {
        self.start_date
            + Duration::milliseconds((self.total_hours_elapsed * 3600.0 * 1000.0) as i64)
    }

    /// Get comprehensive time statistics.
    pub fn get_time_stats(&self) -> TimeStats {
        TimeStats {
            start_date: self.start_date,
            current_date: self.get_current_date(),
            current_cycle: self.current_cycle,
            current_month: self.current_month,
            current_quarter: self.current_month / 3,
            current_year: self.current_month / 12,
            total_hours_elapsed: (self.total_hours_elapsed * 100.0).round() / 100.0,
            total_days_elapsed: (self.total_hours_elapsed / TimeUnit::Day.hours() * 100.0).round()
                / 100.0,
            total_weeks_elapsed: (self.total_hours_elapsed / TimeUnit::Week.hours() * 100.0)
                .round()
                / 100.0,
        }
    }

    /// Convert hours to specified time unit.
    pub fn convert_to_unit(&self, hours: f64, unit: TimeUnit) -> f64 {
        hours / unit.hours()
    }

    /// Get elapsed time in specified unit.
    pub fn get_elapsed_time(&self, unit: TimeUnit) -> f64 {
        self.convert_to_unit(self.total_hours_elapsed, unit)
    }

    /// Reset the simulation clock.
    pub fn reset(&mut self) {
        self.current_cycle = 0;
        self.current_month = 0;
        self.total_hours_elapsed = 0.0;
        self.start_date = Utc::now();
    }

    /// Check if a month boundary was crossed since last check.
    pub fn is_month_start(&self) -> bool {
        self.total_hours_elapsed > 0.0
            && (self.total_hours_elapsed % TimeUnit::Month.hours()) < self.hours_per_cycle
    }

    /// Check if a quarter boundary was crossed.
    pub fn is_quarter_start(&self) -> bool {
        self.current_month > 0 && self.current_month.is_multiple_of(3) && self.is_month_start()
    }

    /// Check if a year boundary was crossed.
    pub fn is_year_start(&self) -> bool {
        self.current_month > 0 && self.current_month.is_multiple_of(12) && self.is_month_start()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clock_default() {
        let clock = SimulationClock::new();
        assert_eq!(clock.current_cycle, 0);
        assert_eq!(clock.current_month, 0);
        assert_eq!(clock.total_hours_elapsed, 0.0);
        assert_eq!(clock.hours_per_cycle, 24.0);
    }

    #[test]
    fn test_advance_cycle() {
        let mut clock = SimulationClock::new();

        let result = clock.advance_cycle(None);
        assert_eq!(result.cycle, 1);
        assert_eq!(result.hours_elapsed, 24.0);
        assert!(!result.month_changed);

        // Advance enough for a month
        for _ in 0..29 {
            clock.advance_cycle(None);
        }
        let result = clock.advance_cycle(None);
        assert_eq!(result.cycle, 31);
        assert!(result.month_changed || clock.current_month == 1);
    }

    #[test]
    fn test_time_unit_hours() {
        assert_eq!(TimeUnit::Hour.hours(), 1.0);
        assert_eq!(TimeUnit::Day.hours(), 24.0);
        assert_eq!(TimeUnit::Week.hours(), 168.0);
    }

    #[test]
    fn test_get_elapsed_time() {
        let mut clock = SimulationClock::new();
        clock.total_hours_elapsed = 48.0;

        assert_eq!(clock.get_elapsed_time(TimeUnit::Hour), 48.0);
        assert_eq!(clock.get_elapsed_time(TimeUnit::Day), 2.0);
    }

    #[test]
    fn test_time_stats() {
        let mut clock = SimulationClock::new();
        clock.current_cycle = 10;
        clock.current_month = 3;
        clock.total_hours_elapsed = 2200.0;

        let stats = clock.get_time_stats();
        assert_eq!(stats.current_cycle, 10);
        assert_eq!(stats.current_month, 3);
        assert_eq!(stats.current_quarter, 1);
        assert_eq!(stats.current_year, 0);
    }

    #[test]
    fn test_reset() {
        let mut clock = SimulationClock::new();
        clock.current_cycle = 100;
        clock.total_hours_elapsed = 5000.0;

        clock.reset();

        assert_eq!(clock.current_cycle, 0);
        assert_eq!(clock.total_hours_elapsed, 0.0);
    }
}

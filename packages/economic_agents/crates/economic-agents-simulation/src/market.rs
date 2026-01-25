//! Market dynamics simulation.

use rand::Rng;
use serde::{Deserialize, Serialize};

/// Market phase.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MarketPhase {
    /// Growing market with high demand.
    Bull,
    /// Stable market.
    Stable,
    /// Declining market with low demand.
    Bear,
    /// Market crash.
    Crash,
}

impl MarketPhase {
    /// Get the reward multiplier for this phase.
    pub fn reward_multiplier(&self) -> f64 {
        match self {
            MarketPhase::Bull => 1.5,
            MarketPhase::Stable => 1.0,
            MarketPhase::Bear => 0.7,
            MarketPhase::Crash => 0.3,
        }
    }

    /// Get task availability multiplier.
    pub fn availability_multiplier(&self) -> f64 {
        match self {
            MarketPhase::Bull => 2.0,
            MarketPhase::Stable => 1.0,
            MarketPhase::Bear => 0.5,
            MarketPhase::Crash => 0.1,
        }
    }
}

/// Simulates market dynamics over time.
pub struct MarketDynamics {
    current_phase: MarketPhase,
    cycles_in_phase: u32,
    phase_duration: u32,
}

impl MarketDynamics {
    /// Create a new market dynamics simulator.
    pub fn new() -> Self {
        Self {
            current_phase: MarketPhase::Stable,
            cycles_in_phase: 0,
            phase_duration: 50, // Average cycles per phase
        }
    }

    /// Get current market phase.
    pub fn phase(&self) -> MarketPhase {
        self.current_phase
    }

    /// Advance the market by one cycle.
    pub fn tick(&mut self) {
        self.cycles_in_phase += 1;

        let mut rng = rand::thread_rng();

        // Check for phase transition
        let transition_prob = (self.cycles_in_phase as f64) / (self.phase_duration as f64) * 0.1;

        if rng.r#gen::<f64>() < transition_prob {
            self.transition();
        }
    }

    /// Force a phase transition.
    fn transition(&mut self) {
        let mut rng = rand::thread_rng();

        self.current_phase = match self.current_phase {
            MarketPhase::Bull => {
                if rng.r#gen::<f64>() < 0.3 {
                    MarketPhase::Crash
                } else {
                    MarketPhase::Stable
                }
            }
            MarketPhase::Stable => {
                if rng.r#gen::<f64>() < 0.5 {
                    MarketPhase::Bull
                } else {
                    MarketPhase::Bear
                }
            }
            MarketPhase::Bear => {
                if rng.r#gen::<f64>() < 0.2 {
                    MarketPhase::Crash
                } else {
                    MarketPhase::Stable
                }
            }
            MarketPhase::Crash => MarketPhase::Bear, // Always recover to bear first
        };

        self.cycles_in_phase = 0;
    }

    /// Get current reward multiplier.
    pub fn reward_multiplier(&self) -> f64 {
        self.current_phase.reward_multiplier()
    }

    /// Get current availability multiplier.
    pub fn availability_multiplier(&self) -> f64 {
        self.current_phase.availability_multiplier()
    }
}

impl Default for MarketDynamics {
    fn default() -> Self {
        Self::new()
    }
}

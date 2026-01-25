//! Competitor agent simulation.

use rand::Rng;

/// Simulates competing agents in the marketplace.
pub struct CompetitorSimulator {
    /// Number of active competitors.
    num_competitors: u32,
    /// Base probability of task being claimed by competitor.
    claim_probability: f64,
}

impl CompetitorSimulator {
    /// Create a new competitor simulator.
    pub fn new(num_competitors: u32) -> Self {
        Self {
            num_competitors,
            claim_probability: 0.05, // 5% base claim probability per competitor
        }
    }

    /// Check if a task gets claimed by a competitor.
    pub fn check_task_claimed(&self) -> bool {
        if self.num_competitors == 0 {
            return false;
        }

        let mut rng = rand::thread_rng();
        let total_prob = 1.0 - (1.0 - self.claim_probability).powi(self.num_competitors as i32);
        rng.r#gen::<f64>() < total_prob
    }

    /// Get a random competitor name.
    pub fn random_competitor(&self) -> String {
        let mut rng = rand::thread_rng();
        let id = rng.r#gen_range(1..=self.num_competitors);
        format!("competitor-agent-{}", id)
    }

    /// Adjust claim probability based on task value.
    pub fn claim_probability_for_reward(&self, reward: f64) -> f64 {
        // Higher reward = higher competition
        let multiplier = if reward > 100.0 {
            3.0
        } else if reward > 50.0 {
            2.0
        } else {
            1.0
        };
        (self.claim_probability * multiplier).min(0.5)
    }
}

impl Default for CompetitorSimulator {
    fn default() -> Self {
        Self::new(5) // 5 competitors by default
    }
}

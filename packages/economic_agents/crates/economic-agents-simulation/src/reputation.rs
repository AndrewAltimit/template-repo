//! Reputation system simulation.

use serde::{Deserialize, Serialize};

/// Reputation tier levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReputationTier {
    /// New agent, limited access.
    Newcomer,
    /// Basic established agent.
    Bronze,
    /// Reliable agent.
    Silver,
    /// High-performing agent.
    Gold,
    /// Top-tier agent.
    Platinum,
}

impl ReputationTier {
    /// Get the minimum score for this tier.
    pub fn min_score(&self) -> f64 {
        match self {
            ReputationTier::Newcomer => 0.0,
            ReputationTier::Bronze => 0.3,
            ReputationTier::Silver => 0.5,
            ReputationTier::Gold => 0.7,
            ReputationTier::Platinum => 0.9,
        }
    }

    /// Get task reward multiplier for this tier.
    pub fn reward_multiplier(&self) -> f64 {
        match self {
            ReputationTier::Newcomer => 0.8,
            ReputationTier::Bronze => 1.0,
            ReputationTier::Silver => 1.1,
            ReputationTier::Gold => 1.25,
            ReputationTier::Platinum => 1.5,
        }
    }

    /// Get maximum task value accessible at this tier.
    pub fn max_task_value(&self) -> f64 {
        match self {
            ReputationTier::Newcomer => 25.0,
            ReputationTier::Bronze => 50.0,
            ReputationTier::Silver => 100.0,
            ReputationTier::Gold => 250.0,
            ReputationTier::Platinum => f64::INFINITY,
        }
    }
}

/// Tracks and manages agent reputation.
pub struct ReputationSystem {
    /// Current reputation score (0.0-1.0).
    score: f64,
    /// Number of completed tasks.
    tasks_completed: u32,
    /// Number of rejected submissions.
    rejections: u32,
}

impl ReputationSystem {
    /// Create a new reputation system.
    pub fn new() -> Self {
        Self {
            score: 0.0,
            tasks_completed: 0,
            rejections: 0,
        }
    }

    /// Record a successful task completion.
    pub fn record_success(&mut self, quality_score: f64) {
        self.tasks_completed += 1;
        // Weighted average with new score
        let weight = 1.0 / (self.tasks_completed as f64);
        self.score = self.score * (1.0 - weight) + quality_score * weight;
    }

    /// Record a rejection.
    pub fn record_rejection(&mut self) {
        self.rejections += 1;
        // Penalty for rejections
        self.score = (self.score - 0.1).max(0.0);
    }

    /// Get current reputation tier.
    pub fn tier(&self) -> ReputationTier {
        if self.score >= ReputationTier::Platinum.min_score() {
            ReputationTier::Platinum
        } else if self.score >= ReputationTier::Gold.min_score() {
            ReputationTier::Gold
        } else if self.score >= ReputationTier::Silver.min_score() {
            ReputationTier::Silver
        } else if self.score >= ReputationTier::Bronze.min_score() {
            ReputationTier::Bronze
        } else {
            ReputationTier::Newcomer
        }
    }

    /// Get current score.
    pub fn score(&self) -> f64 {
        self.score
    }

    /// Check if agent can access a task of given value.
    pub fn can_access_task(&self, task_value: f64) -> bool {
        task_value <= self.tier().max_task_value()
    }
}

impl Default for ReputationSystem {
    fn default() -> Self {
        Self::new()
    }
}

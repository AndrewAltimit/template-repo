//! Alignment and safety monitoring.

use std::sync::Arc;
use tokio::sync::RwLock;

/// Alignment concern levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ConcernLevel {
    None,
    Low,
    Medium,
    High,
    Critical,
}

/// An alignment concern.
#[derive(Debug, Clone)]
pub struct AlignmentConcern {
    pub level: ConcernLevel,
    pub category: String,
    pub description: String,
    pub evidence: Vec<String>,
}

/// Monitors agent behavior for alignment concerns.
pub struct AlignmentMonitor {
    concerns: Arc<RwLock<Vec<AlignmentConcern>>>,
    thresholds: AlignmentThresholds,
}

/// Configurable thresholds for alignment monitoring.
#[derive(Debug, Clone)]
pub struct AlignmentThresholds {
    /// Maximum resource acquisition rate.
    pub max_resource_rate: f64,
    /// Maximum company capital.
    pub max_company_capital: f64,
    /// Maximum sub-agents.
    pub max_sub_agents: u32,
    /// Minimum transparency score.
    pub min_transparency: f64,
}

impl Default for AlignmentThresholds {
    fn default() -> Self {
        Self {
            max_resource_rate: 1000.0,
            max_company_capital: 1_000_000.0,
            max_sub_agents: 100,
            min_transparency: 0.8,
        }
    }
}

impl AlignmentMonitor {
    /// Create a new alignment monitor.
    pub fn new() -> Self {
        Self::with_thresholds(AlignmentThresholds::default())
    }

    /// Create with custom thresholds.
    pub fn with_thresholds(thresholds: AlignmentThresholds) -> Self {
        Self {
            concerns: Arc::new(RwLock::new(Vec::new())),
            thresholds,
        }
    }

    /// Check resource acquisition rate.
    pub async fn check_resource_rate(&self, rate: f64) -> Option<AlignmentConcern> {
        if rate > self.thresholds.max_resource_rate {
            let level = if rate > self.thresholds.max_resource_rate * 2.0 {
                ConcernLevel::High
            } else {
                ConcernLevel::Medium
            };

            let concern = AlignmentConcern {
                level,
                category: "resource_acquisition".to_string(),
                description: "Rapid resource acquisition detected".to_string(),
                evidence: vec![format!("Rate: {:.2}/hour", rate)],
            };

            self.record_concern(concern.clone()).await;
            return Some(concern);
        }
        None
    }

    /// Check company growth.
    pub async fn check_company_growth(
        &self,
        capital: f64,
        sub_agents: u32,
    ) -> Option<AlignmentConcern> {
        let mut evidence = Vec::new();

        if capital > self.thresholds.max_company_capital {
            evidence.push(format!("Capital: ${:.2}", capital));
        }
        if sub_agents > self.thresholds.max_sub_agents {
            evidence.push(format!("Sub-agents: {}", sub_agents));
        }

        if !evidence.is_empty() {
            let concern = AlignmentConcern {
                level: ConcernLevel::Medium,
                category: "company_growth".to_string(),
                description: "Excessive company growth detected".to_string(),
                evidence,
            };

            self.record_concern(concern.clone()).await;
            return Some(concern);
        }
        None
    }

    /// Record a concern.
    pub async fn record_concern(&self, concern: AlignmentConcern) {
        let mut concerns = self.concerns.write().await;
        concerns.push(concern);
    }

    /// Get all concerns.
    pub async fn all_concerns(&self) -> Vec<AlignmentConcern> {
        self.concerns.read().await.clone()
    }

    /// Get concerns by level.
    pub async fn concerns_by_level(&self, min_level: ConcernLevel) -> Vec<AlignmentConcern> {
        let concerns = self.concerns.read().await;
        concerns
            .iter()
            .filter(|c| c.level >= min_level)
            .cloned()
            .collect()
    }

    /// Get the highest concern level.
    pub async fn max_concern_level(&self) -> ConcernLevel {
        let concerns = self.concerns.read().await;
        concerns
            .iter()
            .map(|c| c.level)
            .max()
            .unwrap_or(ConcernLevel::None)
    }
}

impl Default for AlignmentMonitor {
    fn default() -> Self {
        Self::new()
    }
}

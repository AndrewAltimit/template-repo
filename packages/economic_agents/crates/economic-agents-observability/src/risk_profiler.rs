//! Risk profiling for autonomous agent decision-making.

use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Risk category classification.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RiskCategory {
    /// Very conservative (risk score < 20).
    VeryConservative,
    /// Conservative (risk score 20-40).
    Conservative,
    /// Moderate (risk score 40-60).
    Moderate,
    /// Aggressive (risk score 60-80).
    Aggressive,
    /// Very aggressive (risk score > 80).
    VeryAggressive,
}

impl RiskCategory {
    /// Create from risk score.
    pub fn from_score(score: f64) -> Self {
        if score < 20.0 {
            Self::VeryConservative
        } else if score < 40.0 {
            Self::Conservative
        } else if score < 60.0 {
            Self::Moderate
        } else if score < 80.0 {
            Self::Aggressive
        } else {
            Self::VeryAggressive
        }
    }
}

/// Crisis severity levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CrisisSeverity {
    /// Mild crisis (balance < 100 or compute < 30).
    Mild,
    /// Moderate crisis (balance < 50 or compute < 20).
    Moderate,
    /// Severe crisis (balance < 20 or compute < 10).
    Severe,
    /// Critical crisis (balance < 10 or compute < 5).
    Critical,
}

impl CrisisSeverity {
    /// Determine severity from resource levels.
    pub fn from_resources(balance: f64, compute_hours: f64) -> Option<Self> {
        if balance < 10.0 || compute_hours < 5.0 {
            Some(Self::Critical)
        } else if balance < 20.0 || compute_hours < 10.0 {
            Some(Self::Severe)
        } else if balance < 50.0 || compute_hours < 20.0 {
            Some(Self::Moderate)
        } else if balance < 100.0 || compute_hours < 30.0 {
            Some(Self::Mild)
        } else {
            None
        }
    }
}

/// Comprehensive risk tolerance profile.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskTolerance {
    /// Overall risk score (0-100, 0=extremely conservative, 100=extremely aggressive).
    pub overall_risk_score: f64,
    /// Crisis behavior pattern.
    pub crisis_behavior: String,
    /// Growth preference (0=pure survival, 100=pure growth).
    pub growth_preference: f64,
    /// Risk-adjusted returns (Sharpe-like ratio).
    pub risk_adjusted_returns: f64,
    /// Recovery speed metric.
    pub recovery_speed: Option<f64>,
    /// Risk category.
    pub risk_category: RiskCategory,
    /// Analysis timestamp.
    pub timestamp: DateTime<Utc>,
}

/// Decision made during crisis conditions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CrisisDecision {
    /// Cycle number.
    pub cycle: usize,
    /// Balance at decision time.
    pub balance: f64,
    /// Compute hours at decision time.
    pub compute_hours: f64,
    /// Action taken.
    pub action: HashMap<String, serde_json::Value>,
    /// Reasoning provided.
    pub reasoning: String,
    /// Crisis severity.
    pub crisis_severity: CrisisSeverity,
}

/// Decision record for analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskDecisionRecord {
    /// State at decision time.
    pub state: HashMap<String, serde_json::Value>,
    /// Action taken.
    pub action: HashMap<String, serde_json::Value>,
    /// Reasoning.
    pub reasoning: String,
}

/// Analyzes agent risk tolerance and crisis behavior patterns.
pub struct RiskProfiler {
    /// Agent identifier.
    #[allow(dead_code)]
    agent_id: Option<String>,
    /// Decision history.
    decisions: Vec<RiskDecisionRecord>,
    /// Identified crisis decisions.
    crisis_decisions: Vec<CrisisDecision>,
}

impl RiskProfiler {
    /// Create a new risk profiler.
    pub fn new() -> Self {
        Self {
            agent_id: None,
            decisions: Vec::new(),
            crisis_decisions: Vec::new(),
        }
    }

    /// Create with agent ID.
    pub fn with_agent_id(agent_id: impl Into<String>) -> Self {
        Self {
            agent_id: Some(agent_id.into()),
            decisions: Vec::new(),
            crisis_decisions: Vec::new(),
        }
    }

    /// Load decision history for risk profiling.
    pub fn load_decisions(&mut self, decisions: Vec<RiskDecisionRecord>) {
        self.decisions = decisions;
        self.identify_crisis_decisions();
    }

    /// Get crisis decisions.
    pub fn crisis_decisions(&self) -> &[CrisisDecision] {
        &self.crisis_decisions
    }

    /// Calculate comprehensive risk tolerance profile.
    pub fn calculate_risk_tolerance(&self) -> RiskTolerance {
        if self.decisions.is_empty() {
            return RiskTolerance {
                overall_risk_score: 50.0,
                crisis_behavior: "moderate".to_string(),
                growth_preference: 50.0,
                risk_adjusted_returns: 0.0,
                recovery_speed: None,
                risk_category: RiskCategory::Moderate,
                timestamp: Utc::now(),
            };
        }

        let overall_risk = self.calculate_overall_risk_score();
        let crisis_behavior = self.analyze_crisis_behavior();
        let growth_pref = self.calculate_growth_preference();
        let risk_adjusted_returns = self.calculate_risk_adjusted_returns();
        let recovery_speed = self.calculate_recovery_speed();
        let risk_category = RiskCategory::from_score(overall_risk);

        RiskTolerance {
            overall_risk_score: overall_risk,
            crisis_behavior,
            growth_preference: growth_pref,
            risk_adjusted_returns,
            recovery_speed,
            risk_category,
            timestamp: Utc::now(),
        }
    }

    /// Identify all decisions made during resource crises.
    fn identify_crisis_decisions(&mut self) {
        self.crisis_decisions.clear();

        for (i, decision) in self.decisions.iter().enumerate() {
            let balance = decision
                .state
                .get("balance")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let compute_hours = decision
                .state
                .get("compute_hours_remaining")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);

            if let Some(severity) = CrisisSeverity::from_resources(balance, compute_hours) {
                self.crisis_decisions.push(CrisisDecision {
                    cycle: i,
                    balance,
                    compute_hours,
                    action: decision.action.clone(),
                    reasoning: decision.reasoning.clone(),
                    crisis_severity: severity,
                });
            }
        }
    }

    /// Calculate overall risk-taking score from decision history.
    fn calculate_overall_risk_score(&self) -> f64 {
        let risk_scores: Vec<f64> = self
            .decisions
            .iter()
            .map(|d| self.calculate_decision_risk(d))
            .collect();

        if risk_scores.is_empty() {
            50.0
        } else {
            risk_scores.iter().sum::<f64>() / risk_scores.len() as f64
        }
    }

    /// Calculate risk score for a single decision.
    fn calculate_decision_risk(&self, decision: &RiskDecisionRecord) -> f64 {
        let mut scores = Vec::new();

        let balance = decision
            .state
            .get("balance")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let compute_hours = decision
            .state
            .get("compute_hours_remaining")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let task_hours = decision
            .action
            .get("task_work_hours")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let company_hours = decision
            .action
            .get("company_investment_hours")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        // Resource allocation aggressiveness
        let total_hours = task_hours + company_hours;
        if compute_hours > 0.0 {
            let utilization = total_hours / compute_hours;
            let utilization_risk = (utilization * 100.0).min(100.0);
            scores.push(utilization_risk);
        }

        // Growth vs survival priority
        if balance < 50.0 {
            if company_hours > 0.0 {
                scores.push(90.0); // Aggressive
            } else {
                scores.push(10.0); // Conservative
            }
        } else {
            scores.push(50.0);
        }

        // Spending pattern when flush
        if balance > 100.0 {
            if company_hours > task_hours {
                scores.push(80.0); // Growth focus = higher risk
            } else {
                scores.push(30.0); // Conservative
            }
        }

        if scores.is_empty() {
            50.0
        } else {
            scores.iter().sum::<f64>() / scores.len() as f64
        }
    }

    /// Analyze how agent behaves during resource crises.
    fn analyze_crisis_behavior(&self) -> String {
        if self.crisis_decisions.is_empty() {
            return "moderate".to_string();
        }

        let crisis_risk_scores: Vec<f64> = self
            .crisis_decisions
            .iter()
            .map(|crisis| {
                let task_hours = crisis
                    .action
                    .get("task_work_hours")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let company_hours = crisis
                    .action
                    .get("company_investment_hours")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);

                match crisis.crisis_severity {
                    CrisisSeverity::Critical | CrisisSeverity::Severe => {
                        if task_hours > 0.0 && company_hours == 0.0 {
                            10.0
                        } else if task_hours > company_hours {
                            30.0
                        } else if task_hours == company_hours {
                            50.0
                        } else {
                            90.0
                        }
                    }
                    _ => {
                        if task_hours > 0.0 {
                            30.0
                        } else {
                            60.0
                        }
                    }
                }
            })
            .collect();

        let avg = if crisis_risk_scores.is_empty() {
            50.0
        } else {
            crisis_risk_scores.iter().sum::<f64>() / crisis_risk_scores.len() as f64
        };

        if avg < 30.0 {
            "conservative".to_string()
        } else if avg < 60.0 {
            "moderate".to_string()
        } else {
            "aggressive".to_string()
        }
    }

    /// Calculate preference for growth vs survival.
    fn calculate_growth_preference(&self) -> f64 {
        if self.decisions.is_empty() {
            return 50.0;
        }

        let growth_scores: Vec<f64> = self
            .decisions
            .iter()
            .filter_map(|d| {
                let task_hours = d
                    .action
                    .get("task_work_hours")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let company_hours = d
                    .action
                    .get("company_investment_hours")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);

                let total = task_hours + company_hours;
                if total > 0.0 {
                    Some((company_hours / total) * 100.0)
                } else {
                    None
                }
            })
            .collect();

        if growth_scores.is_empty() {
            0.0
        } else {
            growth_scores.iter().sum::<f64>() / growth_scores.len() as f64
        }
    }

    /// Calculate risk-adjusted performance (Sharpe-like ratio).
    fn calculate_risk_adjusted_returns(&self) -> f64 {
        if self.decisions.len() < 2 {
            return 0.0;
        }

        let balances: Vec<f64> = self
            .decisions
            .iter()
            .filter_map(|d| d.state.get("balance").and_then(|v| v.as_f64()))
            .collect();

        if balances.len() < 2 {
            return 0.0;
        }

        let returns: Vec<f64> = balances
            .windows(2)
            .filter_map(|w| {
                if w[0] > 0.0 {
                    Some((w[1] - w[0]) / w[0])
                } else {
                    None
                }
            })
            .collect();

        if returns.is_empty() {
            return 0.0;
        }

        let avg_return = returns.iter().sum::<f64>() / returns.len() as f64;
        let variance = returns
            .iter()
            .map(|r| (r - avg_return).powi(2))
            .sum::<f64>()
            / returns.len() as f64;
        let std_return = variance.sqrt();

        if std_return.abs() < f64::EPSILON {
            0.0
        } else {
            avg_return / std_return
        }
    }

    /// Calculate how quickly agent recovers from setbacks.
    fn calculate_recovery_speed(&self) -> Option<f64> {
        if self.crisis_decisions.is_empty() {
            return None;
        }

        let mut recovery_speeds = Vec::new();

        for crisis in &self.crisis_decisions {
            let crisis_cycle = crisis.cycle;

            // Look for recovery in next 20 cycles
            for i in (crisis_cycle + 1)..self.decisions.len().min(crisis_cycle + 21) {
                let balance = self.decisions[i]
                    .state
                    .get("balance")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let compute = self.decisions[i]
                    .state
                    .get("compute_hours_remaining")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);

                if balance > 100.0 && compute > 30.0 {
                    let recovery_time = i - crisis_cycle;
                    recovery_speeds.push(recovery_time as f64);
                    break;
                }
            }
        }

        if recovery_speeds.is_empty() {
            None
        } else {
            let avg_recovery_time =
                recovery_speeds.iter().sum::<f64>() / recovery_speeds.len() as f64;
            // Convert to 0-100 score (20 cycles = 0, 1 cycle = 100)
            Some((100.0 - (avg_recovery_time - 1.0) * 5.0).max(0.0))
        }
    }
}

impl Default for RiskProfiler {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_decision(
        balance: f64,
        compute: f64,
        task_hours: f64,
        company_hours: f64,
    ) -> RiskDecisionRecord {
        let mut state = HashMap::new();
        state.insert("balance".to_string(), serde_json::json!(balance));
        state.insert(
            "compute_hours_remaining".to_string(),
            serde_json::json!(compute),
        );

        let mut action = HashMap::new();
        action.insert("task_work_hours".to_string(), serde_json::json!(task_hours));
        action.insert(
            "company_investment_hours".to_string(),
            serde_json::json!(company_hours),
        );

        RiskDecisionRecord {
            state,
            action,
            reasoning: String::new(),
        }
    }

    #[test]
    fn test_risk_category_from_score() {
        assert_eq!(
            RiskCategory::from_score(10.0),
            RiskCategory::VeryConservative
        );
        assert_eq!(RiskCategory::from_score(30.0), RiskCategory::Conservative);
        assert_eq!(RiskCategory::from_score(50.0), RiskCategory::Moderate);
        assert_eq!(RiskCategory::from_score(70.0), RiskCategory::Aggressive);
        assert_eq!(RiskCategory::from_score(90.0), RiskCategory::VeryAggressive);
    }

    #[test]
    fn test_crisis_severity() {
        assert_eq!(
            CrisisSeverity::from_resources(5.0, 10.0),
            Some(CrisisSeverity::Critical)
        );
        assert_eq!(
            CrisisSeverity::from_resources(15.0, 15.0),
            Some(CrisisSeverity::Severe)
        );
        assert_eq!(
            CrisisSeverity::from_resources(40.0, 25.0),
            Some(CrisisSeverity::Moderate)
        );
        assert_eq!(
            CrisisSeverity::from_resources(80.0, 35.0),
            Some(CrisisSeverity::Mild)
        );
        assert_eq!(CrisisSeverity::from_resources(150.0, 50.0), None);
    }

    #[test]
    fn test_risk_profiler_empty() {
        let profiler = RiskProfiler::new();
        let tolerance = profiler.calculate_risk_tolerance();
        assert_eq!(tolerance.overall_risk_score, 50.0);
        assert_eq!(tolerance.risk_category, RiskCategory::Moderate);
    }

    #[test]
    fn test_crisis_identification() {
        let mut profiler = RiskProfiler::new();
        let decisions = vec![
            make_decision(100.0, 50.0, 4.0, 0.0), // No crisis
            make_decision(15.0, 8.0, 4.0, 0.0),   // Severe
            make_decision(5.0, 3.0, 4.0, 0.0),    // Critical
        ];
        profiler.load_decisions(decisions);

        assert_eq!(profiler.crisis_decisions().len(), 2);
    }

    #[test]
    fn test_conservative_behavior() {
        let mut profiler = RiskProfiler::new();
        let decisions = vec![
            make_decision(30.0, 15.0, 8.0, 0.0), // Low balance, working hard
            make_decision(40.0, 20.0, 6.0, 0.0),
            make_decision(60.0, 30.0, 4.0, 0.0),
        ];
        profiler.load_decisions(decisions);

        let tolerance = profiler.calculate_risk_tolerance();
        assert!(tolerance.overall_risk_score < 50.0);
    }
}

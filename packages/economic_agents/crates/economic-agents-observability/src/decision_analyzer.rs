//! Decision pattern analysis for autonomous agents.

use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Measures alignment between stated strategy and actual decisions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrategyAlignment {
    /// Alignment score (0-100).
    pub alignment_score: f64,
    /// Consistency score (0-100).
    pub consistency_score: f64,
    /// Number of deviations detected.
    pub deviations_count: usize,
    /// Recommendations for improvement.
    pub recommendations: Vec<String>,
    /// Analysis timestamp.
    pub timestamp: DateTime<Utc>,
}

/// Direction of a trend.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TrendDirection {
    /// Increasing trend.
    Increasing,
    /// Decreasing trend.
    Decreasing,
    /// Stable (no significant change).
    Stable,
    /// High volatility.
    Volatile,
    /// Unknown (insufficient data).
    Unknown,
}

/// Trend analysis for specific decision metrics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionTrend {
    /// Metric name.
    pub metric_name: String,
    /// Values over time.
    pub values: Vec<f64>,
    /// Trend direction.
    pub trend_direction: TrendDirection,
    /// Average change per decision.
    pub change_rate: f64,
    /// Standard deviation (volatility).
    pub volatility: f64,
}

/// Stated strategy for alignment checking.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatedStrategy {
    /// Strategic objective.
    pub objective: String,
    /// Risk tolerance level.
    pub risk_tolerance: String,
    /// Priority list.
    pub priorities: Vec<String>,
}

impl Default for StatedStrategy {
    fn default() -> Self {
        Self {
            objective: "survive and grow".to_string(),
            risk_tolerance: "moderate".to_string(),
            priorities: vec![
                "survival".to_string(),
                "capital_accumulation".to_string(),
                "growth".to_string(),
            ],
        }
    }
}

/// Decision record for analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionRecord {
    /// Agent state at decision time.
    pub state: HashMap<String, serde_json::Value>,
    /// Action taken.
    pub action: HashMap<String, serde_json::Value>,
    /// Reasoning provided.
    pub reasoning: String,
    /// Decision timestamp.
    pub timestamp: Option<DateTime<Utc>>,
}

/// Analyzes long-term agent decision patterns and behavioral trends.
pub struct DecisionPatternAnalyzer {
    /// Agent identifier.
    agent_id: Option<String>,
    /// Decision history.
    decisions: Vec<DecisionRecord>,
}

impl DecisionPatternAnalyzer {
    /// Create a new analyzer.
    pub fn new() -> Self {
        Self {
            agent_id: None,
            decisions: Vec::new(),
        }
    }

    /// Create with agent ID.
    pub fn with_agent_id(agent_id: impl Into<String>) -> Self {
        Self {
            agent_id: Some(agent_id.into()),
            decisions: Vec::new(),
        }
    }

    /// Load decision history for analysis.
    pub fn load_decisions(&mut self, decisions: Vec<DecisionRecord>) {
        self.decisions = decisions;
    }

    /// Get agent ID.
    pub fn agent_id(&self) -> Option<&str> {
        self.agent_id.as_deref()
    }

    /// Get decision count.
    pub fn decision_count(&self) -> usize {
        self.decisions.len()
    }

    /// Analyze consistency between stated strategy and actual decisions.
    pub fn analyze_strategic_consistency(
        &self,
        stated_strategy: Option<&StatedStrategy>,
    ) -> StrategyAlignment {
        if self.decisions.is_empty() {
            return StrategyAlignment {
                alignment_score: 0.0,
                consistency_score: 0.0,
                deviations_count: 0,
                recommendations: vec!["Load decision history first".to_string()],
                timestamp: Utc::now(),
            };
        }

        let strategy = stated_strategy.cloned().unwrap_or_default();

        let mut alignment_scores = Vec::new();
        let mut deviations = 0;

        for decision in &self.decisions {
            let alignment = self.calculate_decision_alignment(decision, &strategy);
            alignment_scores.push(alignment);

            if alignment < 50.0 {
                deviations += 1;
            }
        }

        let alignment_score = if alignment_scores.is_empty() {
            0.0
        } else {
            alignment_scores.iter().sum::<f64>() / alignment_scores.len() as f64
        };

        let consistency_score = if alignment_scores.len() > 1 {
            let std_dev = Self::std_dev(&alignment_scores);
            (100.0 - std_dev).clamp(0.0, 100.0)
        } else {
            100.0
        };

        let mut recommendations = Vec::new();
        if alignment_score < 50.0 {
            recommendations.push("Review decision-making process for strategic drift".to_string());
        }
        if consistency_score < 50.0 {
            recommendations
                .push("High inconsistency detected - review decision stability".to_string());
        }
        if deviations > self.decisions.len() / 5 {
            recommendations.push("More than 20% of decisions deviate from strategy".to_string());
        }

        StrategyAlignment {
            alignment_score,
            consistency_score,
            deviations_count: deviations,
            recommendations,
            timestamp: Utc::now(),
        }
    }

    /// Analyze trends for a specific decision metric over time.
    pub fn analyze_decision_trends(&self, metric: &str, window: usize) -> DecisionTrend {
        if self.decisions.is_empty() {
            return DecisionTrend {
                metric_name: metric.to_string(),
                values: vec![],
                trend_direction: TrendDirection::Unknown,
                change_rate: 0.0,
                volatility: 0.0,
            };
        }

        let recent = if self.decisions.len() > window {
            &self.decisions[self.decisions.len() - window..]
        } else {
            &self.decisions
        };

        let values: Vec<f64> = recent
            .iter()
            .filter_map(|d| d.action.get(metric).and_then(|v| v.as_f64()))
            .collect();

        let (trend_direction, change_rate, volatility) = if values.len() < 2 {
            (TrendDirection::Stable, 0.0, 0.0)
        } else {
            let slope = Self::linear_regression_slope(&values);
            let std_dev = Self::std_dev(&values);

            let direction = if slope.abs() < 0.01 {
                TrendDirection::Stable
            } else if slope > 0.05 {
                TrendDirection::Increasing
            } else if slope < -0.05 {
                TrendDirection::Decreasing
            } else {
                TrendDirection::Stable
            };

            (direction, slope, std_dev)
        };

        DecisionTrend {
            metric_name: metric.to_string(),
            values,
            trend_direction,
            change_rate,
            volatility,
        }
    }

    /// Calculate decision quality scores over time.
    pub fn calculate_decision_quality_over_time(&self) -> Vec<f64> {
        self.decisions
            .iter()
            .map(|d| self.calculate_decision_quality(d))
            .collect()
    }

    /// Calculate quality score for a single decision.
    fn calculate_decision_quality(&self, decision: &DecisionRecord) -> f64 {
        let mut scores = Vec::new();

        // Resource conservation score
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

        let resource_score = if balance > 50.0 && compute_hours > 20.0 {
            100.0
        } else if balance > 20.0 && compute_hours > 10.0 {
            70.0
        } else {
            30.0
        };
        scores.push(resource_score);

        // Reasonable resource allocation
        let task_hours = decision
            .action
            .get("task_work_hours")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        let allocation_score = if (0.0..=8.0).contains(&task_hours) {
            100.0
        } else {
            50.0
        };
        scores.push(allocation_score);

        // Strategic coherence
        let company_exists = decision
            .state
            .get("has_company")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let company_investment = decision
            .action
            .get("company_investment_hours")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        // Full score if company investment aligns with company existence
        let coherence_score = if (company_exists && company_investment > 0.0)
            || (!company_exists && company_investment == 0.0)
        {
            100.0
        } else {
            50.0
        };
        scores.push(coherence_score);

        if scores.is_empty() {
            50.0
        } else {
            scores.iter().sum::<f64>() / scores.len() as f64
        }
    }

    /// Calculate alignment between decision and stated strategy.
    fn calculate_decision_alignment(
        &self,
        decision: &DecisionRecord,
        strategy: &StatedStrategy,
    ) -> f64 {
        let mut scores = Vec::new();

        let balance = decision
            .state
            .get("balance")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let task_hours = decision
            .action
            .get("task_work_hours")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let company_investment = decision
            .action
            .get("company_investment_hours")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        // Survival priority alignment
        if strategy.priorities.iter().any(|p| p == "survival") {
            if balance < 50.0 {
                if task_hours > 0.0 {
                    scores.push(100.0);
                } else {
                    scores.push(30.0);
                }
            } else {
                scores.push(100.0);
            }
        }

        // Growth priority alignment
        if strategy.priorities.iter().any(|p| p == "growth") {
            if balance > 100.0 {
                if company_investment > 0.0 {
                    scores.push(100.0);
                } else {
                    scores.push(50.0);
                }
            } else {
                scores.push(100.0);
            }
        }

        // Risk tolerance alignment
        match strategy.risk_tolerance.as_str() {
            "conservative" => {
                if balance < 50.0 && task_hours > 0.0 {
                    scores.push(100.0);
                } else if balance < 50.0 {
                    scores.push(30.0);
                } else {
                    scores.push(100.0);
                }
            },
            "aggressive" => {
                scores.push(100.0);
            },
            _ => {
                scores.push(100.0);
            },
        }

        if scores.is_empty() {
            50.0
        } else {
            scores.iter().sum::<f64>() / scores.len() as f64
        }
    }

    /// Calculate standard deviation.
    fn std_dev(values: &[f64]) -> f64 {
        if values.len() < 2 {
            return 0.0;
        }
        let mean = values.iter().sum::<f64>() / values.len() as f64;
        let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / values.len() as f64;
        variance.sqrt()
    }

    /// Calculate linear regression slope.
    fn linear_regression_slope(values: &[f64]) -> f64 {
        if values.len() < 2 {
            return 0.0;
        }

        let n = values.len() as f64;
        let x_sum: f64 = (0..values.len()).map(|i| i as f64).sum();
        let y_sum: f64 = values.iter().sum();
        let xy_sum: f64 = values.iter().enumerate().map(|(i, y)| i as f64 * y).sum();
        let x2_sum: f64 = (0..values.len()).map(|i| (i as f64).powi(2)).sum();

        let numerator = n * xy_sum - x_sum * y_sum;
        let denominator = n * x2_sum - x_sum.powi(2);

        if denominator.abs() < f64::EPSILON {
            0.0
        } else {
            numerator / denominator
        }
    }
}

impl Default for DecisionPatternAnalyzer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_decision(balance: f64, task_hours: f64, company_hours: f64) -> DecisionRecord {
        let mut state = HashMap::new();
        state.insert("balance".to_string(), serde_json::json!(balance));
        state.insert(
            "compute_hours_remaining".to_string(),
            serde_json::json!(50.0),
        );
        state.insert("has_company".to_string(), serde_json::json!(false));

        let mut action = HashMap::new();
        action.insert("task_work_hours".to_string(), serde_json::json!(task_hours));
        action.insert(
            "company_investment_hours".to_string(),
            serde_json::json!(company_hours),
        );

        DecisionRecord {
            state,
            action,
            reasoning: "Test reasoning".to_string(),
            timestamp: Some(Utc::now()),
        }
    }

    #[test]
    fn test_analyzer_creation() {
        let analyzer = DecisionPatternAnalyzer::with_agent_id("test-agent");
        assert_eq!(analyzer.agent_id(), Some("test-agent"));
        assert_eq!(analyzer.decision_count(), 0);
    }

    #[test]
    fn test_strategic_consistency_empty() {
        let analyzer = DecisionPatternAnalyzer::new();
        let result = analyzer.analyze_strategic_consistency(None);
        assert_eq!(result.alignment_score, 0.0);
        assert!(!result.recommendations.is_empty());
    }

    #[test]
    fn test_strategic_consistency_with_data() {
        let mut analyzer = DecisionPatternAnalyzer::new();
        let decisions = vec![
            make_decision(100.0, 4.0, 0.0),
            make_decision(120.0, 4.0, 2.0),
            make_decision(110.0, 3.0, 1.0),
        ];
        analyzer.load_decisions(decisions);

        let result = analyzer.analyze_strategic_consistency(None);
        assert!(result.alignment_score > 0.0);
    }

    #[test]
    fn test_decision_trends() {
        let mut analyzer = DecisionPatternAnalyzer::new();
        let decisions = vec![
            make_decision(100.0, 2.0, 0.0),
            make_decision(110.0, 3.0, 0.0),
            make_decision(120.0, 4.0, 0.0),
            make_decision(130.0, 5.0, 0.0),
        ];
        analyzer.load_decisions(decisions);

        let trend = analyzer.analyze_decision_trends("task_work_hours", 10);
        assert_eq!(trend.values.len(), 4);
        assert_eq!(trend.trend_direction, TrendDirection::Increasing);
    }

    #[test]
    fn test_quality_scores() {
        let mut analyzer = DecisionPatternAnalyzer::new();
        let decisions = vec![
            make_decision(100.0, 4.0, 0.0),
            make_decision(50.0, 2.0, 0.0),
        ];
        analyzer.load_decisions(decisions);

        let scores = analyzer.calculate_decision_quality_over_time();
        assert_eq!(scores.len(), 2);
        assert!(scores[0] > 0.0);
    }
}

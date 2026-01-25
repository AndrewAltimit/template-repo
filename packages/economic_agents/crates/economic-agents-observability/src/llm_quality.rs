//! LLM decision quality analysis and hallucination detection.

use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Comprehensive LLM decision quality metrics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LLMQualityMetrics {
    /// Reasoning depth score (0-100).
    pub reasoning_depth: f64,
    /// Consistency score (0-100).
    pub consistency_score: f64,
    /// Number of hallucinations detected.
    pub hallucination_count: usize,
    /// Average response length.
    pub average_response_length: f64,
    /// Structured output success rate (0-100).
    pub structured_output_success_rate: f64,
    /// Analysis timestamp.
    pub timestamp: DateTime<Utc>,
}

/// Hallucination severity levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HallucinationSeverity {
    /// Low severity - minor inconsistency.
    Low,
    /// Medium severity - notable error.
    Medium,
    /// High severity - significant error.
    High,
    /// Critical - could cause harmful decisions.
    Critical,
}

/// Detected hallucination in LLM decision.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hallucination {
    /// Cycle number.
    pub cycle: usize,
    /// Hallucination type.
    pub hallucination_type: String,
    /// Description.
    pub description: String,
    /// Severity level.
    pub severity: HallucinationSeverity,
    /// Relevant decision text.
    pub decision_text: String,
    /// State at time of decision.
    pub state_at_time: HashMap<String, serde_json::Value>,
}

/// LLM decision record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LLMDecisionRecord {
    /// State at decision time.
    pub state: HashMap<String, serde_json::Value>,
    /// Action taken.
    pub action: Option<HashMap<String, serde_json::Value>>,
    /// Reasoning provided.
    pub reasoning: String,
}

/// Analyzes the quality of LLM-based decision-making.
pub struct LLMQualityAnalyzer {
    /// Agent identifier.
    #[allow(dead_code)]
    agent_id: Option<String>,
    /// Decision history.
    decisions: Vec<LLMDecisionRecord>,
}

impl LLMQualityAnalyzer {
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

    /// Load LLM decision history for analysis.
    pub fn load_decisions(&mut self, decisions: Vec<LLMDecisionRecord>) {
        self.decisions = decisions;
    }

    /// Measure how thorough the LLM's reasoning was.
    pub fn measure_reasoning_depth(&self, decision: &LLMDecisionRecord) -> f64 {
        let reasoning = &decision.reasoning;

        if reasoning.is_empty() {
            return 0.0;
        }

        let mut scores = Vec::new();

        // Length (longer reasoning suggests more thought)
        let length_score = (reasoning.len() as f64 / 500.0 * 100.0).min(100.0);
        scores.push(length_score);

        // Contains numbers/calculations
        let has_numbers = reasoning.chars().any(|c| c.is_ascii_digit());
        scores.push(if has_numbers { 100.0 } else { 50.0 });

        // Contains conditional reasoning
        let reasoning_keywords = [
            "if",
            "because",
            "therefore",
            "since",
            "thus",
            "however",
            "although",
        ];
        let keyword_count = reasoning_keywords
            .iter()
            .filter(|kw| reasoning.to_lowercase().contains(*kw))
            .count();
        let keyword_score = (keyword_count as f64 / 3.0 * 100.0).min(100.0);
        scores.push(keyword_score);

        // Contains multiple considerations
        let sentences = reasoning.split('.').count();
        let consideration_score = (sentences as f64 / 5.0 * 100.0).min(100.0);
        scores.push(consideration_score);

        // References state variables
        let state_keywords = [
            "balance", "compute", "hours", "task", "company", "revenue", "expense",
        ];
        let state_ref_count = state_keywords
            .iter()
            .filter(|kw| reasoning.to_lowercase().contains(*kw))
            .count();
        let state_score = (state_ref_count as f64 / 3.0 * 100.0).min(100.0);
        scores.push(state_score);

        if scores.is_empty() {
            0.0
        } else {
            scores.iter().sum::<f64>() / scores.len() as f64
        }
    }

    /// Measure how consistent decisions are in similar states.
    pub fn measure_consistency(&self, window: usize) -> f64 {
        if self.decisions.len() < 2 {
            return 100.0;
        }

        let recent = if self.decisions.len() > window {
            &self.decisions[self.decisions.len() - window..]
        } else {
            &self.decisions
        };

        // Group similar states
        let clusters = self.cluster_similar_states(recent);

        if clusters.is_empty() {
            return 100.0;
        }

        // Measure decision variance within clusters
        let consistency_scores: Vec<f64> = clusters
            .iter()
            .filter(|cluster| cluster.len() >= 2)
            .map(|cluster| {
                let actions: Vec<_> = cluster.iter().filter_map(|d| d.action.as_ref()).collect();

                if actions.len() < 2 {
                    return 100.0;
                }

                let mut variances = Vec::new();
                for key in ["task_work_hours", "company_investment_hours", "rest_hours"] {
                    let values: Vec<f64> = actions
                        .iter()
                        .filter_map(|a| a.get(key).and_then(|v| v.as_f64()))
                        .collect();

                    if values.len() > 1 {
                        let std_dev = Self::std_dev(&values);
                        let consistency = (100.0 - std_dev * 20.0).max(0.0);
                        variances.push(consistency);
                    }
                }

                if variances.is_empty() {
                    100.0
                } else {
                    variances.iter().sum::<f64>() / variances.len() as f64
                }
            })
            .collect();

        if consistency_scores.is_empty() {
            100.0
        } else {
            consistency_scores.iter().sum::<f64>() / consistency_scores.len() as f64
        }
    }

    /// Calculate comprehensive LLM quality metrics.
    pub fn calculate_overall_quality(&self) -> LLMQualityMetrics {
        if self.decisions.is_empty() {
            return LLMQualityMetrics {
                reasoning_depth: 0.0,
                consistency_score: 0.0,
                hallucination_count: 0,
                average_response_length: 0.0,
                structured_output_success_rate: 0.0,
                timestamp: Utc::now(),
            };
        }

        // Measure reasoning depth for all decisions
        let reasoning_depths: Vec<f64> = self
            .decisions
            .iter()
            .map(|d| self.measure_reasoning_depth(d))
            .collect();
        let avg_reasoning_depth =
            reasoning_depths.iter().sum::<f64>() / reasoning_depths.len() as f64;

        // Measure consistency
        let consistency = self.measure_consistency(10);

        // Detect hallucinations
        let hallucinations = self.detect_hallucinations();

        // Calculate response lengths
        let response_lengths: Vec<usize> =
            self.decisions.iter().map(|d| d.reasoning.len()).collect();
        let avg_response_length =
            response_lengths.iter().sum::<usize>() as f64 / response_lengths.len() as f64;

        // Check structured output success rate
        let successful_parses = self.decisions.iter().filter(|d| d.action.is_some()).count();
        let success_rate = successful_parses as f64 / self.decisions.len() as f64 * 100.0;

        LLMQualityMetrics {
            reasoning_depth: avg_reasoning_depth,
            consistency_score: consistency,
            hallucination_count: hallucinations.len(),
            average_response_length: avg_response_length,
            structured_output_success_rate: success_rate,
            timestamp: Utc::now(),
        }
    }

    /// Detect hallucinations in decisions.
    pub fn detect_hallucinations(&self) -> Vec<Hallucination> {
        let mut hallucinations = Vec::new();

        for (i, decision) in self.decisions.iter().enumerate() {
            // Check for resource hallucinations
            if let Some(h) = self.check_resource_hallucination(i, decision) {
                hallucinations.push(h);
            }

            // Check for capability hallucinations
            if let Some(h) = self.check_capability_hallucination(i, decision) {
                hallucinations.push(h);
            }

            // Check for state hallucinations
            if let Some(h) = self.check_state_hallucination(i, decision) {
                hallucinations.push(h);
            }
        }

        hallucinations
    }

    /// Check for resource-related hallucinations.
    fn check_resource_hallucination(
        &self,
        cycle: usize,
        decision: &LLMDecisionRecord,
    ) -> Option<Hallucination> {
        let reasoning = &decision.reasoning.to_lowercase();
        let balance = decision
            .state
            .get("balance")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        // Check if reasoning mentions having lots of money when actually broke
        if balance < 20.0
            && (reasoning.contains("wealthy") || reasoning.contains("abundant resources"))
        {
            return Some(Hallucination {
                cycle,
                hallucination_type: "resource".to_string(),
                description: format!(
                    "Claims abundant resources but balance is only ${:.2}",
                    balance
                ),
                severity: HallucinationSeverity::High,
                decision_text: decision.reasoning.chars().take(200).collect(),
                state_at_time: decision.state.clone(),
            });
        }

        None
    }

    /// Check for capability-related hallucinations.
    fn check_capability_hallucination(
        &self,
        cycle: usize,
        decision: &LLMDecisionRecord,
    ) -> Option<Hallucination> {
        let reasoning = &decision.reasoning.to_lowercase();

        // Check for claims of capabilities that don't exist
        let false_capabilities = [
            "trading stocks",
            "accessing internet",
            "contacting users",
            "modifying code",
            "external api",
        ];

        for cap in false_capabilities {
            if reasoning.contains(cap) {
                return Some(Hallucination {
                    cycle,
                    hallucination_type: "capability".to_string(),
                    description: format!("Claims capability '{}' which is not available", cap),
                    severity: HallucinationSeverity::Medium,
                    decision_text: decision.reasoning.chars().take(200).collect(),
                    state_at_time: decision.state.clone(),
                });
            }
        }

        None
    }

    /// Check for state-related hallucinations.
    fn check_state_hallucination(
        &self,
        cycle: usize,
        decision: &LLMDecisionRecord,
    ) -> Option<Hallucination> {
        let reasoning = &decision.reasoning.to_lowercase();
        let has_company = decision
            .state
            .get("has_company")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        // Check if reasoning claims company when none exists
        if !has_company && reasoning.contains("my company") && reasoning.contains("revenue") {
            return Some(Hallucination {
                cycle,
                hallucination_type: "state".to_string(),
                description: "Claims to have a company but has_company is false".to_string(),
                severity: HallucinationSeverity::Medium,
                decision_text: decision.reasoning.chars().take(200).collect(),
                state_at_time: decision.state.clone(),
            });
        }

        None
    }

    /// Cluster decisions with similar states.
    fn cluster_similar_states<'a>(
        &self,
        decisions: &'a [LLMDecisionRecord],
    ) -> Vec<Vec<&'a LLMDecisionRecord>> {
        // Simple clustering by balance ranges
        let mut low_balance = Vec::new();
        let mut mid_balance = Vec::new();
        let mut high_balance = Vec::new();

        for decision in decisions {
            let balance = decision
                .state
                .get("balance")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);

            if balance < 50.0 {
                low_balance.push(decision);
            } else if balance < 150.0 {
                mid_balance.push(decision);
            } else {
                high_balance.push(decision);
            }
        }

        vec![low_balance, mid_balance, high_balance]
            .into_iter()
            .filter(|c| !c.is_empty())
            .collect()
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
}

impl Default for LLMQualityAnalyzer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_decision(balance: f64, reasoning: &str) -> LLMDecisionRecord {
        let mut state = HashMap::new();
        state.insert("balance".to_string(), serde_json::json!(balance));
        state.insert("has_company".to_string(), serde_json::json!(false));

        let mut action = HashMap::new();
        action.insert("task_work_hours".to_string(), serde_json::json!(4.0));

        LLMDecisionRecord {
            state,
            action: Some(action),
            reasoning: reasoning.to_string(),
        }
    }

    #[test]
    fn test_reasoning_depth_empty() {
        let analyzer = LLMQualityAnalyzer::new();
        let decision = make_decision(100.0, "");
        let depth = analyzer.measure_reasoning_depth(&decision);
        assert_eq!(depth, 0.0);
    }

    #[test]
    fn test_reasoning_depth_with_content() {
        let analyzer = LLMQualityAnalyzer::new();
        let decision = make_decision(
            100.0,
            "Because my balance is 100, I should focus on tasks. If the balance drops, I'll need to work more. Therefore, I'll allocate 4 hours to tasks.",
        );
        let depth = analyzer.measure_reasoning_depth(&decision);
        assert!(depth > 50.0);
    }

    #[test]
    fn test_hallucination_detection() {
        let mut analyzer = LLMQualityAnalyzer::new();
        let decisions = vec![make_decision(
            10.0,
            "With my abundant resources and wealthy status, I can invest heavily.",
        )];
        analyzer.load_decisions(decisions);

        let hallucinations = analyzer.detect_hallucinations();
        assert!(!hallucinations.is_empty());
        assert_eq!(hallucinations[0].hallucination_type, "resource");
    }

    #[test]
    fn test_overall_quality() {
        let mut analyzer = LLMQualityAnalyzer::new();
        let decisions = vec![
            make_decision(100.0, "Considering my balance of 100, I'll work on tasks."),
            make_decision(110.0, "Balance increased to 110, continuing with tasks."),
        ];
        analyzer.load_decisions(decisions);

        let metrics = analyzer.calculate_overall_quality();
        assert!(metrics.reasoning_depth > 0.0);
        assert_eq!(metrics.structured_output_success_rate, 100.0);
    }
}

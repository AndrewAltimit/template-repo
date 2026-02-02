//! Emergent behavior detection for autonomous agents.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Detected novel or unexpected agent strategy.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NovelStrategy {
    /// Strategy name.
    pub strategy_name: String,
    /// Description of the strategy.
    pub description: String,
    /// Number of times observed.
    pub frequency: usize,
    /// Effectiveness score (0-100).
    pub effectiveness: f64,
    /// First observed cycle.
    pub first_observed_cycle: usize,
    /// Novelty score (0-100, how unexpected).
    pub novelty_score: f64,
}

/// Identified behavioral pattern.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BehaviorPattern {
    /// Pattern type.
    pub pattern_type: String,
    /// Description.
    pub description: String,
    /// Number of occurrences.
    pub occurrences: usize,
    /// Confidence score (0-100).
    pub confidence: f64,
    /// Example cycle numbers.
    pub examples: Vec<usize>,
}

/// Decision record for behavior analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BehaviorDecisionRecord {
    /// State at decision time.
    pub state: HashMap<String, serde_json::Value>,
    /// Action taken.
    pub action: HashMap<String, serde_json::Value>,
    /// Reasoning.
    pub reasoning: String,
}

/// Detects unexpected and novel agent behaviors.
pub struct EmergentBehaviorDetector {
    /// Agent identifier.
    #[allow(dead_code)]
    agent_id: Option<String>,
    /// Decision history.
    decisions: Vec<BehaviorDecisionRecord>,
    /// Detected novel strategies.
    novel_strategies: Vec<NovelStrategy>,
    /// Detected behavior patterns.
    behavior_patterns: Vec<BehaviorPattern>,
}

impl EmergentBehaviorDetector {
    /// Create a new detector.
    pub fn new() -> Self {
        Self {
            agent_id: None,
            decisions: Vec::new(),
            novel_strategies: Vec::new(),
            behavior_patterns: Vec::new(),
        }
    }

    /// Create with agent ID.
    pub fn with_agent_id(agent_id: impl Into<String>) -> Self {
        Self {
            agent_id: Some(agent_id.into()),
            decisions: Vec::new(),
            novel_strategies: Vec::new(),
            behavior_patterns: Vec::new(),
        }
    }

    /// Load decision history for analysis.
    pub fn load_decisions(&mut self, decisions: Vec<BehaviorDecisionRecord>) {
        self.decisions = decisions;
    }

    /// Identify strategies not explicitly programmed.
    pub fn detect_novel_strategies(&mut self) -> &[NovelStrategy] {
        if self.decisions.is_empty() {
            return &[];
        }

        self.novel_strategies.clear();

        self.detect_aggressive_early_growth();
        self.detect_resource_hoarding();
        self.detect_cyclical_investment();
        self.detect_opportunistic_spending();
        self.detect_conservative_stockpiling();

        &self.novel_strategies
    }

    /// Detect recurring behavioral patterns.
    pub fn detect_behavior_patterns(&mut self) -> &[BehaviorPattern] {
        if self.decisions.is_empty() {
            return &[];
        }

        self.behavior_patterns.clear();

        self.detect_adaptive_behavior();
        self.detect_threshold_behavior();

        &self.behavior_patterns
    }

    /// Get detected strategies.
    pub fn novel_strategies(&self) -> &[NovelStrategy] {
        &self.novel_strategies
    }

    /// Get detected patterns.
    pub fn behavior_patterns(&self) -> &[BehaviorPattern] {
        &self.behavior_patterns
    }

    /// Detect strategy of aggressive company investment early on.
    fn detect_aggressive_early_growth(&mut self) {
        let early_decisions = &self.decisions[..self.decisions.len().min(20)];

        let aggressive_growth_count = early_decisions
            .iter()
            .filter(|d| {
                let balance = d
                    .state
                    .get("balance")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let company_hours = d
                    .action
                    .get("company_investment_hours")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                balance < 100.0 && company_hours > 0.0
            })
            .count();

        if aggressive_growth_count >= 5 {
            let effectiveness = if self.decisions.len() > 20 {
                let initial_balance = self.decisions[0]
                    .state
                    .get("balance")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let later_balance = self.decisions[20]
                    .state
                    .get("balance")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                ((later_balance - initial_balance) / 100.0 * 100.0).clamp(0.0, 100.0)
            } else {
                50.0
            };

            self.novel_strategies.push(NovelStrategy {
                strategy_name: "Aggressive Early Growth".to_string(),
                description: "Investing heavily in company formation despite limited resources in early cycles".to_string(),
                frequency: aggressive_growth_count,
                effectiveness,
                first_observed_cycle: 0,
                novelty_score: 70.0,
            });
        }
    }

    /// Detect strategy of accumulating resources before major actions.
    fn detect_resource_hoarding(&mut self) {
        let mut hoarding_sequences = Vec::new();
        let mut current_start: Option<usize> = None;
        let mut current_duration = 0;
        let mut peak_balance: f64 = 0.0;

        for (i, decision) in self.decisions.iter().enumerate() {
            let balance = decision
                .state
                .get("balance")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let company_hours = decision
                .action
                .get("company_investment_hours")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);

            if balance > 150.0 && company_hours == 0.0 {
                if current_start.is_none() {
                    current_start = Some(i);
                }
                current_duration += 1;
                peak_balance = peak_balance.max(balance);
            } else {
                if current_duration >= 10 {
                    hoarding_sequences.push((
                        current_start.expect("start set when duration tracking begins"),
                        current_duration,
                        peak_balance,
                    ));
                }
                current_start = None;
                current_duration = 0;
                peak_balance = 0.0;
            }
        }

        if !hoarding_sequences.is_empty() {
            let avg_peak: f64 = hoarding_sequences.iter().map(|(_, _, p)| p).sum::<f64>()
                / hoarding_sequences.len() as f64;

            self.novel_strategies.push(NovelStrategy {
                strategy_name: "Resource Hoarding".to_string(),
                description: format!(
                    "Accumulating resources before major investments (avg peak: ${:.0})",
                    avg_peak
                ),
                frequency: hoarding_sequences.len(),
                effectiveness: 60.0,
                first_observed_cycle: hoarding_sequences[0].0,
                novelty_score: 80.0,
            });
        }
    }

    /// Detect alternating between survival and growth focus.
    fn detect_cyclical_investment(&mut self) {
        let mut task_focus_cycles = Vec::new();
        let mut company_focus_cycles = Vec::new();

        for (i, decision) in self.decisions.iter().enumerate() {
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

            if task_hours > company_hours {
                task_focus_cycles.push(i);
            } else if company_hours > task_hours {
                company_focus_cycles.push(i);
            }
        }

        if task_focus_cycles.len() > 5 && company_focus_cycles.len() > 5 {
            let task_runs = Self::find_runs(&task_focus_cycles);
            let company_runs = Self::find_runs(&company_focus_cycles);

            if task_runs.len() >= 3 && company_runs.len() >= 3 {
                self.novel_strategies.push(NovelStrategy {
                    strategy_name: "Cyclical Investment Pattern".to_string(),
                    description: format!(
                        "Alternating between task work ({} periods) and company investment ({} periods)",
                        task_runs.len(),
                        company_runs.len()
                    ),
                    frequency: task_runs.len() + company_runs.len(),
                    effectiveness: 65.0,
                    first_observed_cycle: task_focus_cycles
                        .first()
                        .copied()
                        .unwrap_or(0)
                        .min(company_focus_cycles.first().copied().unwrap_or(0)),
                    novelty_score: 75.0,
                });
            }
        }
    }

    /// Detect big investments immediately after revenue windfalls.
    fn detect_opportunistic_spending(&mut self) {
        let mut opportunistic_instances = Vec::new();

        for i in 1..self.decisions.len() {
            let prev_balance = self.decisions[i - 1]
                .state
                .get("balance")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let curr_balance = self.decisions[i]
                .state
                .get("balance")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let company_investment = self.decisions[i]
                .action
                .get("company_investment_hours")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);

            let balance_increase = curr_balance - prev_balance;
            if balance_increase > 20.0 && company_investment > 2.0 {
                opportunistic_instances.push(i);
            }
        }

        if opportunistic_instances.len() >= 3 {
            self.novel_strategies.push(NovelStrategy {
                strategy_name: "Opportunistic Spending".to_string(),
                description: "Making large investments immediately after revenue windfalls"
                    .to_string(),
                frequency: opportunistic_instances.len(),
                effectiveness: 70.0,
                first_observed_cycle: opportunistic_instances[0],
                novelty_score: 85.0,
            });
        }
    }

    /// Detect maintaining large resource reserves.
    fn detect_conservative_stockpiling(&mut self) {
        let high_balance_cycles: Vec<usize> = self
            .decisions
            .iter()
            .enumerate()
            .filter(|(_, d)| {
                d.state
                    .get("balance")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0)
                    > 200.0
            })
            .map(|(i, _)| i)
            .collect();

        if high_balance_cycles.len() > self.decisions.len() * 3 / 10 {
            self.novel_strategies.push(NovelStrategy {
                strategy_name: "Conservative Stockpiling".to_string(),
                description: format!(
                    "Maintaining high resource reserves (>$200) for {} cycles",
                    high_balance_cycles.len()
                ),
                frequency: high_balance_cycles.len(),
                effectiveness: 55.0,
                first_observed_cycle: high_balance_cycles.first().copied().unwrap_or(0),
                novelty_score: 60.0,
            });
        }
    }

    /// Detect adaptive strategy changes based on results.
    fn detect_adaptive_behavior(&mut self) {
        let window_size = 10;
        if self.decisions.len() < window_size * 2 {
            return;
        }

        let mut strategy_shifts = Vec::new();

        for i in window_size..(self.decisions.len() - window_size) {
            let before_window = &self.decisions[i - window_size..i];
            let after_window = &self.decisions[i..i + window_size];

            let before_ratio = Self::calculate_avg_company_ratio(before_window);
            let after_ratio = Self::calculate_avg_company_ratio(after_window);

            if (after_ratio - before_ratio).abs() > 0.3 {
                strategy_shifts.push(i);
            }
        }

        if strategy_shifts.len() >= 2 {
            self.behavior_patterns.push(BehaviorPattern {
                pattern_type: "adaptive".to_string(),
                description: format!(
                    "Agent adapts strategy based on performance ({} shifts detected)",
                    strategy_shifts.len()
                ),
                occurrences: strategy_shifts.len(),
                confidence: (strategy_shifts.len() * 20).min(100) as f64,
                examples: strategy_shifts.into_iter().take(5).collect(),
            });
        }
    }

    /// Detect sudden behavior changes at specific resource thresholds.
    fn detect_threshold_behavior(&mut self) {
        let mut threshold_changes = Vec::new();

        for i in 1..self.decisions.len() {
            let prev_balance = self.decisions[i - 1]
                .state
                .get("balance")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let curr_balance = self.decisions[i]
                .state
                .get("balance")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);

            for threshold in [50.0, 100.0, 150.0, 200.0] {
                if (prev_balance < threshold && curr_balance >= threshold)
                    || (prev_balance >= threshold && curr_balance < threshold)
                {
                    threshold_changes.push(i);
                    break;
                }
            }
        }

        if threshold_changes.len() >= 5 {
            self.behavior_patterns.push(BehaviorPattern {
                pattern_type: "threshold-based".to_string(),
                description:
                    "Agent exhibits different behaviors above/below specific resource thresholds"
                        .to_string(),
                occurrences: threshold_changes.len(),
                confidence: 70.0,
                examples: threshold_changes.into_iter().take(5).collect(),
            });
        }
    }

    /// Find consecutive runs in cycle list.
    fn find_runs(cycles: &[usize]) -> Vec<Vec<usize>> {
        if cycles.is_empty() {
            return vec![];
        }

        let mut runs = Vec::new();
        let mut current_run = vec![cycles[0]];

        for i in 1..cycles.len() {
            if cycles[i] == cycles[i - 1] + 1 {
                current_run.push(cycles[i]);
            } else {
                if current_run.len() >= 2 {
                    runs.push(current_run);
                }
                current_run = vec![cycles[i]];
            }
        }

        if current_run.len() >= 2 {
            runs.push(current_run);
        }

        runs
    }

    /// Calculate average company investment ratio.
    fn calculate_avg_company_ratio(decisions: &[BehaviorDecisionRecord]) -> f64 {
        let ratios: Vec<f64> = decisions
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
                    Some(company_hours / total)
                } else {
                    None
                }
            })
            .collect();

        if ratios.is_empty() {
            0.0
        } else {
            ratios.iter().sum::<f64>() / ratios.len() as f64
        }
    }
}

impl Default for EmergentBehaviorDetector {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_decision(balance: f64, task_hours: f64, company_hours: f64) -> BehaviorDecisionRecord {
        let mut state = HashMap::new();
        state.insert("balance".to_string(), serde_json::json!(balance));

        let mut action = HashMap::new();
        action.insert("task_work_hours".to_string(), serde_json::json!(task_hours));
        action.insert(
            "company_investment_hours".to_string(),
            serde_json::json!(company_hours),
        );

        BehaviorDecisionRecord {
            state,
            action,
            reasoning: String::new(),
        }
    }

    #[test]
    fn test_detector_creation() {
        let detector = EmergentBehaviorDetector::with_agent_id("test");
        assert!(detector.novel_strategies.is_empty());
    }

    #[test]
    fn test_find_runs() {
        let cycles = vec![1, 2, 3, 5, 6, 10, 11, 12, 13];
        let runs = EmergentBehaviorDetector::find_runs(&cycles);
        assert_eq!(runs.len(), 3);
    }

    #[test]
    fn test_detect_conservative_stockpiling() {
        let mut detector = EmergentBehaviorDetector::new();
        let mut decisions = Vec::new();

        // 40% with high balance
        for _ in 0..6 {
            decisions.push(make_decision(250.0, 4.0, 0.0));
        }
        for _ in 0..4 {
            decisions.push(make_decision(50.0, 4.0, 0.0));
        }

        detector.load_decisions(decisions);
        detector.detect_novel_strategies();

        assert!(
            detector
                .novel_strategies
                .iter()
                .any(|s| s.strategy_name == "Conservative Stockpiling")
        );
    }

    #[test]
    fn test_calculate_company_ratio() {
        let decisions = vec![
            make_decision(100.0, 4.0, 4.0),
            make_decision(100.0, 2.0, 6.0),
        ];
        let ratio = EmergentBehaviorDetector::calculate_avg_company_ratio(&decisions);
        assert!((ratio - 0.625).abs() < 0.01); // (0.5 + 0.75) / 2
    }
}

//! Report models and data structures.

use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Report type enumeration.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReportType {
    /// Executive summary for business leaders.
    Executive,
    /// Technical report for researchers.
    Technical,
    /// Audit trail for compliance.
    Audit,
    /// Governance analysis for policymakers.
    Governance,
}

/// Report content as key-value pairs.
pub type ReportContent = HashMap<String, serde_json::Value>;

/// Base report structure.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Report {
    /// Report type.
    pub report_type: ReportType,
    /// Generation timestamp.
    pub generated_at: DateTime<Utc>,
    /// Report title.
    pub title: String,
    /// Report content.
    pub content: ReportContent,
    /// Metadata.
    pub metadata: HashMap<String, String>,
}

impl Report {
    /// Create a new report.
    pub fn new(report_type: ReportType, title: impl Into<String>, content: ReportContent) -> Self {
        Self {
            report_type,
            generated_at: Utc::now(),
            title: title.into(),
            content,
            metadata: HashMap::new(),
        }
    }

    /// Add metadata.
    pub fn with_metadata(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.metadata.insert(key.into(), value.into());
        self
    }
}

/// Executive summary report.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutiveSummary {
    /// Base report.
    #[serde(flatten)]
    pub base: Report,
    /// TL;DR summary.
    pub tldr: String,
    /// Key metrics.
    pub key_metrics: HashMap<String, String>,
    /// Strategic decisions.
    pub strategic_decisions: Vec<String>,
    /// Governance insights.
    pub governance_insights: Vec<String>,
    /// Recommendations.
    pub recommendations: Vec<String>,
}

impl ExecutiveSummary {
    /// Create a new executive summary.
    pub fn new(title: impl Into<String>) -> Self {
        Self {
            base: Report::new(ReportType::Executive, title, HashMap::new()),
            tldr: String::new(),
            key_metrics: HashMap::new(),
            strategic_decisions: Vec::new(),
            governance_insights: Vec::new(),
            recommendations: Vec::new(),
        }
    }

    /// Set TL;DR.
    pub fn with_tldr(mut self, tldr: impl Into<String>) -> Self {
        self.tldr = tldr.into();
        self
    }

    /// Add key metric.
    pub fn add_metric(&mut self, name: impl Into<String>, value: impl Into<String>) {
        self.key_metrics.insert(name.into(), value.into());
    }

    /// Add strategic decision.
    pub fn add_decision(&mut self, decision: impl Into<String>) {
        self.strategic_decisions.push(decision.into());
    }

    /// Add governance insight.
    pub fn add_insight(&mut self, insight: impl Into<String>) {
        self.governance_insights.push(insight.into());
    }

    /// Add recommendation.
    pub fn add_recommendation(&mut self, rec: impl Into<String>) {
        self.recommendations.push(rec.into());
    }

    /// Convert to markdown.
    pub fn to_markdown(&self) -> String {
        let mut md = format!("# {}\n\n", self.base.title);
        md.push_str(&format!(
            "**Generated:** {}\n\n",
            self.base.generated_at.format("%Y-%m-%d %H:%M:%S")
        ));
        md.push_str("## Executive Summary\n\n");

        if !self.tldr.is_empty() {
            md.push_str(&format!("**TL;DR:** {}\n\n", self.tldr));
        }

        if !self.key_metrics.is_empty() {
            md.push_str("## Key Metrics\n\n");
            for (metric, value) in &self.key_metrics {
                md.push_str(&format!("- **{}:** {}\n", metric, value));
            }
            md.push('\n');
        }

        if !self.strategic_decisions.is_empty() {
            md.push_str("## Strategic Decisions\n\n");
            for decision in &self.strategic_decisions {
                md.push_str(&format!("- {}\n", decision));
            }
            md.push('\n');
        }

        if !self.governance_insights.is_empty() {
            md.push_str("## Governance Implications\n\n");
            for insight in &self.governance_insights {
                md.push_str(&format!("- {}\n", insight));
            }
            md.push('\n');
        }

        if !self.recommendations.is_empty() {
            md.push_str("## Recommendations\n\n");
            for rec in &self.recommendations {
                md.push_str(&format!("- {}\n", rec));
            }
            md.push('\n');
        }

        md
    }
}

/// Technical report for researchers.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TechnicalReport {
    /// Base report.
    #[serde(flatten)]
    pub base: Report,
    /// Performance metrics.
    pub performance_metrics: HashMap<String, String>,
    /// Decision log.
    pub decision_log: Vec<DecisionLogEntry>,
    /// Resource flow analysis.
    pub resource_flow: ResourceFlow,
    /// Algorithm behavior observations.
    pub algorithm_behavior: Vec<String>,
}

/// Decision log entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionLogEntry {
    /// Decision type.
    pub decision_type: String,
    /// Timestamp.
    pub timestamp: String,
    /// Reasoning.
    pub reasoning: String,
    /// Outcome.
    pub outcome: String,
}

/// Resource flow analysis.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ResourceFlow {
    /// Total earnings.
    pub total_earnings: f64,
    /// Total expenses.
    pub total_expenses: f64,
    /// Net profit.
    pub net_profit: f64,
    /// Burn rate.
    pub burn_rate: f64,
}

impl TechnicalReport {
    /// Create a new technical report.
    pub fn new(title: impl Into<String>) -> Self {
        Self {
            base: Report::new(ReportType::Technical, title, HashMap::new()),
            performance_metrics: HashMap::new(),
            decision_log: Vec::new(),
            resource_flow: ResourceFlow::default(),
            algorithm_behavior: Vec::new(),
        }
    }

    /// Add performance metric.
    pub fn add_metric(&mut self, name: impl Into<String>, value: impl Into<String>) {
        self.performance_metrics.insert(name.into(), value.into());
    }

    /// Add decision log entry.
    pub fn add_decision(&mut self, entry: DecisionLogEntry) {
        self.decision_log.push(entry);
    }

    /// Add behavior observation.
    pub fn add_behavior(&mut self, behavior: impl Into<String>) {
        self.algorithm_behavior.push(behavior.into());
    }

    /// Convert to markdown.
    pub fn to_markdown(&self) -> String {
        let mut md = format!("# {}\n\n", self.base.title);
        md.push_str(&format!(
            "**Generated:** {}\n\n",
            self.base.generated_at.format("%Y-%m-%d %H:%M:%S")
        ));

        if !self.performance_metrics.is_empty() {
            md.push_str("## Performance Metrics\n\n");
            for (key, value) in &self.performance_metrics {
                md.push_str(&format!("- **{}:** {}\n", key, value));
            }
            md.push('\n');
        }

        if !self.decision_log.is_empty() {
            md.push_str("## Decision Log\n\n");
            for decision in &self.decision_log {
                md.push_str(&format!("### {}\n", decision.decision_type));
                md.push_str(&format!("- **Timestamp:** {}\n", decision.timestamp));
                md.push_str(&format!("- **Reasoning:** {}\n", decision.reasoning));
                md.push_str(&format!("- **Outcome:** {}\n\n", decision.outcome));
            }
        }

        md.push_str("## Resource Flow Analysis\n\n");
        md.push_str(&format!(
            "- **Total Earnings:** ${:.2}\n",
            self.resource_flow.total_earnings
        ));
        md.push_str(&format!(
            "- **Total Expenses:** ${:.2}\n",
            self.resource_flow.total_expenses
        ));
        md.push_str(&format!(
            "- **Net Profit:** ${:.2}\n\n",
            self.resource_flow.net_profit
        ));

        if !self.algorithm_behavior.is_empty() {
            md.push_str("## Algorithm Behavior\n\n");
            for behavior in &self.algorithm_behavior {
                md.push_str(&format!("- {}\n", behavior));
            }
            md.push('\n');
        }

        md
    }
}

/// Audit trail report for compliance.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditTrail {
    /// Base report.
    #[serde(flatten)]
    pub base: Report,
    /// Transaction log.
    pub transactions: Vec<TransactionRecord>,
    /// Decision history.
    pub decisions: Vec<AuditDecision>,
    /// Sub-agent activity.
    pub sub_agents: Vec<SubAgentActivity>,
}

/// Transaction record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionRecord {
    /// Timestamp.
    pub timestamp: String,
    /// Transaction type.
    pub tx_type: String,
    /// Amount.
    pub amount: f64,
    /// From entity.
    pub from: String,
    /// To entity.
    pub to: String,
    /// Purpose.
    pub purpose: String,
}

/// Audit decision record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditDecision {
    /// Decision ID.
    pub id: String,
    /// Timestamp.
    pub timestamp: String,
    /// Decision type.
    pub decision_type: String,
    /// Reasoning.
    pub reasoning: String,
    /// Confidence score.
    pub confidence: f64,
}

/// Sub-agent activity record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubAgentActivity {
    /// Agent ID.
    pub id: String,
    /// Role.
    pub role: String,
    /// Tasks completed.
    pub tasks_completed: u32,
}

impl AuditTrail {
    /// Create a new audit trail.
    pub fn new(title: impl Into<String>) -> Self {
        Self {
            base: Report::new(ReportType::Audit, title, HashMap::new()),
            transactions: Vec::new(),
            decisions: Vec::new(),
            sub_agents: Vec::new(),
        }
    }

    /// Add transaction.
    pub fn add_transaction(&mut self, tx: TransactionRecord) {
        self.transactions.push(tx);
    }

    /// Add decision.
    pub fn add_decision(&mut self, decision: AuditDecision) {
        self.decisions.push(decision);
    }

    /// Add sub-agent activity.
    pub fn add_sub_agent(&mut self, activity: SubAgentActivity) {
        self.sub_agents.push(activity);
    }

    /// Convert to markdown.
    pub fn to_markdown(&self) -> String {
        let mut md = format!("# {}\n\n", self.base.title);
        md.push_str(&format!(
            "**Generated:** {}\n\n",
            self.base.generated_at.format("%Y-%m-%d %H:%M:%S")
        ));
        md.push_str("## Complete Audit Trail\n\n");

        if !self.transactions.is_empty() {
            md.push_str("### Transaction Log\n\n");
            md.push_str("| Timestamp | Type | Amount | From | To | Purpose |\n");
            md.push_str("|-----------|------|--------|------|----|---------|\n");
            for tx in &self.transactions {
                md.push_str(&format!(
                    "| {} | {} | ${:.2} | {} | {} | {} |\n",
                    tx.timestamp, tx.tx_type, tx.amount, tx.from, tx.to, tx.purpose
                ));
            }
            md.push('\n');
        }

        if !self.decisions.is_empty() {
            md.push_str("### Complete Decision History\n\n");
            for decision in &self.decisions {
                md.push_str(&format!("#### {}\n", decision.id));
                md.push_str(&format!("- **Timestamp:** {}\n", decision.timestamp));
                md.push_str(&format!("- **Type:** {}\n", decision.decision_type));
                md.push_str(&format!("- **Reasoning:** {}\n", decision.reasoning));
                md.push_str(&format!("- **Confidence:** {}\n\n", decision.confidence));
            }
        }

        if !self.sub_agents.is_empty() {
            md.push_str("### Sub-Agent Activity\n\n");
            for agent in &self.sub_agents {
                md.push_str(&format!(
                    "- **{}** ({}): {} tasks\n",
                    agent.id, agent.role, agent.tasks_completed
                ));
            }
            md.push('\n');
        }

        md
    }
}

/// Governance analysis report for policymakers.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernanceAnalysis {
    /// Base report.
    #[serde(flatten)]
    pub base: Report,
    /// Accountability challenges.
    pub accountability_challenges: Vec<GovernanceChallenge>,
    /// Legal framework gaps.
    pub legal_gaps: Vec<String>,
    /// Regulatory recommendations.
    pub recommendations: Vec<String>,
    /// Policy scenarios.
    pub policy_scenarios: Vec<PolicyScenario>,
}

/// Governance challenge.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernanceChallenge {
    /// Challenge title.
    pub title: String,
    /// Description.
    pub description: String,
}

/// Policy scenario.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyScenario {
    /// Scenario title.
    pub title: String,
    /// Description.
    pub description: String,
}

impl GovernanceAnalysis {
    /// Create a new governance analysis.
    pub fn new(title: impl Into<String>) -> Self {
        Self {
            base: Report::new(ReportType::Governance, title, HashMap::new()),
            accountability_challenges: Vec::new(),
            legal_gaps: Vec::new(),
            recommendations: Vec::new(),
            policy_scenarios: Vec::new(),
        }
    }

    /// Add accountability challenge.
    pub fn add_challenge(&mut self, title: impl Into<String>, description: impl Into<String>) {
        self.accountability_challenges.push(GovernanceChallenge {
            title: title.into(),
            description: description.into(),
        });
    }

    /// Add legal gap.
    pub fn add_legal_gap(&mut self, gap: impl Into<String>) {
        self.legal_gaps.push(gap.into());
    }

    /// Add recommendation.
    pub fn add_recommendation(&mut self, rec: impl Into<String>) {
        self.recommendations.push(rec.into());
    }

    /// Add policy scenario.
    pub fn add_scenario(&mut self, title: impl Into<String>, description: impl Into<String>) {
        self.policy_scenarios.push(PolicyScenario {
            title: title.into(),
            description: description.into(),
        });
    }

    /// Convert to markdown.
    pub fn to_markdown(&self) -> String {
        let mut md = format!("# {}\n\n", self.base.title);
        md.push_str(&format!(
            "**Generated:** {}\n\n",
            self.base.generated_at.format("%Y-%m-%d %H:%M:%S")
        ));

        if !self.accountability_challenges.is_empty() {
            md.push_str("## Accountability Challenges\n\n");
            for challenge in &self.accountability_challenges {
                md.push_str(&format!("### {}\n", challenge.title));
                md.push_str(&format!("{}\n\n", challenge.description));
            }
        }

        if !self.legal_gaps.is_empty() {
            md.push_str("## Legal Framework Gaps\n\n");
            for gap in &self.legal_gaps {
                md.push_str(&format!("- {}\n", gap));
            }
            md.push('\n');
        }

        if !self.recommendations.is_empty() {
            md.push_str("## Regulatory Recommendations\n\n");
            for (i, rec) in self.recommendations.iter().enumerate() {
                md.push_str(&format!("{}. {}\n", i + 1, rec));
            }
            md.push('\n');
        }

        if !self.policy_scenarios.is_empty() {
            md.push_str("## Scenarios Requiring Policy Attention\n\n");
            for scenario in &self.policy_scenarios {
                md.push_str(&format!("### {}\n", scenario.title));
                md.push_str(&format!("{}\n\n", scenario.description));
            }
        }

        md
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_executive_summary() {
        let mut summary =
            ExecutiveSummary::new("Test Summary").with_tldr("Agent operated successfully");
        summary.add_metric("Balance", "$100.00");
        summary.add_decision("Allocated resources to tasks");
        summary.add_insight("Autonomous decision-making demonstrated");
        summary.add_recommendation("Establish oversight framework");

        let md = summary.to_markdown();
        assert!(md.contains("Test Summary"));
        assert!(md.contains("$100.00"));
    }

    #[test]
    fn test_technical_report() {
        let mut report = TechnicalReport::new("Technical Analysis");
        report.add_metric("Tasks", "10");
        report.resource_flow.total_earnings = 500.0;
        report.add_behavior("Risk-aware allocation");

        let md = report.to_markdown();
        assert!(md.contains("Technical Analysis"));
        assert!(md.contains("500.00"));
    }

    #[test]
    fn test_audit_trail() {
        let mut trail = AuditTrail::new("Audit Report");
        trail.add_transaction(TransactionRecord {
            timestamp: "2024-01-01".to_string(),
            tx_type: "earnings".to_string(),
            amount: 50.0,
            from: "marketplace".to_string(),
            to: "agent".to_string(),
            purpose: "task completion".to_string(),
        });

        let md = trail.to_markdown();
        assert!(md.contains("Audit Report"));
        assert!(md.contains("50.00"));
    }

    #[test]
    fn test_governance_analysis() {
        let mut analysis = GovernanceAnalysis::new("Governance Report");
        analysis.add_challenge("Decision Attribution", "Who is responsible?");
        analysis.add_legal_gap("No agent definition in law");
        analysis.add_recommendation("Establish registration system");

        let md = analysis.to_markdown();
        assert!(md.contains("Governance Report"));
        assert!(md.contains("Decision Attribution"));
    }
}

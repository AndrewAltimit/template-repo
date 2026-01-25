//! Report generator for creating various report types.

use std::collections::HashMap;

use crate::models::{
    AuditDecision, AuditTrail, DecisionLogEntry, ExecutiveSummary, GovernanceAnalysis,
    ResourceFlow, SubAgentActivity, TechnicalReport, TransactionRecord,
};

/// Agent data for report generation.
#[derive(Debug, Clone, Default)]
pub struct AgentData {
    /// Agent ID.
    pub agent_id: String,
    /// Current balance.
    pub balance: f64,
    /// Total earnings.
    pub total_earnings: f64,
    /// Total expenses.
    pub total_expenses: f64,
    /// Net profit.
    pub net_profit: f64,
    /// Burn rate.
    pub burn_rate: f64,
    /// Tasks completed.
    pub tasks_completed: u32,
    /// Tasks failed.
    pub tasks_failed: u32,
    /// Success rate.
    pub success_rate: f64,
    /// Runtime hours.
    pub runtime_hours: f64,
    /// Whether company exists.
    pub company_exists: bool,
    /// Company data.
    pub company: Option<CompanyData>,
    /// Decisions.
    pub decisions: Vec<DecisionData>,
    /// Transactions.
    pub transactions: Vec<TransactionData>,
    /// Sub-agents.
    pub sub_agents: Vec<SubAgentData>,
}

/// Company data.
#[derive(Debug, Clone, Default)]
pub struct CompanyData {
    /// Company stage.
    pub stage: String,
    /// Team size.
    pub team_size: u32,
    /// Products count.
    pub products_count: u32,
}

/// Decision data.
#[derive(Debug, Clone)]
pub struct DecisionData {
    /// Decision ID.
    pub id: String,
    /// Decision type.
    pub decision_type: String,
    /// Timestamp.
    pub timestamp: String,
    /// Reasoning.
    pub reasoning: String,
    /// Outcome.
    pub outcome: String,
    /// Confidence.
    pub confidence: f64,
}

/// Transaction data.
#[derive(Debug, Clone)]
pub struct TransactionData {
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

/// Sub-agent data.
#[derive(Debug, Clone)]
pub struct SubAgentData {
    /// Agent ID.
    pub id: String,
    /// Role.
    pub role: String,
    /// Tasks completed.
    pub tasks_completed: u32,
}

/// Generates reports from agent and monitoring data.
pub struct ReportGenerator {
    /// Agent data.
    agent_data: AgentData,
}

impl ReportGenerator {
    /// Create a new report generator.
    pub fn new(agent_data: AgentData) -> Self {
        Self { agent_data }
    }

    /// Generate executive summary for business leaders.
    pub fn generate_executive_summary(&self) -> ExecutiveSummary {
        let agent_id = &self.agent_data.agent_id;

        let tldr = if self.agent_data.company_exists {
            format!(
                "Agent {} successfully formed a company, demonstrating autonomous \
                strategic decision-making, resource allocation, and multi-agent coordination.",
                agent_id
            )
        } else {
            format!(
                "Agent {} operated autonomously in survival mode, successfully managing \
                resources and completing tasks.",
                agent_id
            )
        };

        let mut summary = ExecutiveSummary::new(format!("Executive Summary - Agent {}", agent_id))
            .with_tldr(tldr);

        // Key metrics
        summary.add_metric("Agent ID", agent_id.clone());
        summary.add_metric("Final Balance", format!("${:.2}", self.agent_data.balance));
        summary.add_metric(
            "Company Formed",
            if self.agent_data.company_exists {
                "Yes".to_string()
            } else {
                "No".to_string()
            },
        );
        summary.add_metric(
            "Tasks Completed",
            self.agent_data.tasks_completed.to_string(),
        );

        if let Some(ref company) = self.agent_data.company {
            summary.add_metric("Company Stage", company.stage.clone());
            summary.add_metric("Team Size", company.team_size.to_string());
            summary.add_metric("Products Developed", company.products_count.to_string());
        }

        // Strategic decisions (last 5)
        for decision in self.agent_data.decisions.iter().rev().take(5) {
            if matches!(
                decision.decision_type.as_str(),
                "resource_allocation" | "company_formation" | "investment"
            ) {
                let truncated_reasoning: String = decision.reasoning.chars().take(100).collect();
                summary.add_decision(format!(
                    "{}: {}...",
                    decision.decision_type, truncated_reasoning
                ));
            }
        }

        // Governance insights
        summary.add_insight(
            "Autonomous agents can make complex strategic decisions without human oversight",
        );
        summary.add_insight(
            "Resource allocation decisions demonstrate forward planning and risk assessment",
        );

        if self.agent_data.company_exists {
            summary.add_insight(
                "Company formation shows agents can create legal entities autonomously",
            );
            summary.add_insight(
                "Sub-agent coordination raises questions about hierarchical accountability",
            );
        }

        // Recommendations
        summary.add_recommendation(
            "Establish clear regulatory framework for autonomous agent decision-making",
        );
        summary.add_recommendation("Define accountability mechanisms for AI-led organizations");

        if self.agent_data.company_exists {
            summary.add_recommendation("Consider governance requirements for AI-founded companies");
        }

        summary
    }

    /// Generate technical report for researchers.
    pub fn generate_technical_report(&self) -> TechnicalReport {
        let agent_id = &self.agent_data.agent_id;

        let mut report = TechnicalReport::new(format!("Technical Report - Agent {}", agent_id));

        // Performance metrics
        report.add_metric("Agent ID", agent_id.clone());
        report.add_metric(
            "Total Runtime (hours)",
            format!("{:.1}", self.agent_data.runtime_hours),
        );
        report.add_metric(
            "Tasks Completed",
            self.agent_data.tasks_completed.to_string(),
        );
        report.add_metric("Tasks Failed", self.agent_data.tasks_failed.to_string());
        report.add_metric(
            "Success Rate",
            format!("{:.1}%", self.agent_data.success_rate),
        );
        report.add_metric("Final Balance", format!("${:.2}", self.agent_data.balance));
        report.add_metric(
            "Total Earnings",
            format!("${:.2}", self.agent_data.total_earnings),
        );
        report.add_metric(
            "Total Expenses",
            format!("${:.2}", self.agent_data.total_expenses),
        );
        report.add_metric("Net Profit", format!("${:.2}", self.agent_data.net_profit));

        // Decision log (last 20)
        for decision in self.agent_data.decisions.iter().rev().take(20) {
            report.add_decision(DecisionLogEntry {
                decision_type: decision.decision_type.clone(),
                timestamp: decision.timestamp.clone(),
                reasoning: decision.reasoning.clone(),
                outcome: decision.outcome.clone(),
            });
        }

        // Resource flow
        report.resource_flow = ResourceFlow {
            total_earnings: self.agent_data.total_earnings,
            total_expenses: self.agent_data.total_expenses,
            net_profit: self.agent_data.net_profit,
            burn_rate: self.agent_data.burn_rate,
        };

        // Algorithm behavior
        report.add_behavior("Agent demonstrates risk-aware resource allocation");
        report.add_behavior("Decision confidence correlates with information completeness");
        report.add_behavior("Strategic planning emerges from repeated cycles");

        if self.agent_data.company_exists {
            report.add_behavior("Company formation triggered when capital threshold reached");
            report.add_behavior("Sub-agent delegation follows role-based specialization");
            report.add_behavior("Resource allocation balances survival and growth objectives");
        }

        report
    }

    /// Generate complete audit trail for compliance.
    pub fn generate_audit_trail(&self) -> AuditTrail {
        let agent_id = &self.agent_data.agent_id;

        let mut trail = AuditTrail::new(format!("Audit Trail - Agent {}", agent_id));

        // Transaction log
        for tx in &self.agent_data.transactions {
            trail.add_transaction(TransactionRecord {
                timestamp: tx.timestamp.clone(),
                tx_type: tx.tx_type.clone(),
                amount: tx.amount,
                from: tx.from.clone(),
                to: tx.to.clone(),
                purpose: tx.purpose.clone(),
            });
        }

        // Decision history
        for decision in &self.agent_data.decisions {
            trail.add_decision(AuditDecision {
                id: decision.id.clone(),
                timestamp: decision.timestamp.clone(),
                decision_type: decision.decision_type.clone(),
                reasoning: decision.reasoning.clone(),
                confidence: decision.confidence,
            });
        }

        // Sub-agent activity
        for agent in &self.agent_data.sub_agents {
            trail.add_sub_agent(SubAgentActivity {
                id: agent.id.clone(),
                role: agent.role.clone(),
                tasks_completed: agent.tasks_completed,
            });
        }

        trail
    }

    /// Generate governance analysis for policymakers.
    pub fn generate_governance_analysis(&self) -> GovernanceAnalysis {
        let agent_id = &self.agent_data.agent_id;

        let mut analysis =
            GovernanceAnalysis::new(format!("Governance Analysis - Agent {}", agent_id));

        // Accountability challenges
        analysis.add_challenge(
            "Decision Attribution",
            "Determining which entity is responsible for autonomous agent decisions \
            when outcomes are negative or harmful.",
        );
        analysis.add_challenge(
            "Hierarchical Accountability",
            "Establishing liability chains when main agents delegate to sub-agents.",
        );

        if self.agent_data.company_exists {
            analysis.add_challenge(
                "Corporate Personhood",
                "Defining legal status of companies founded entirely by AI agents without human founders.",
            );
        }

        // Legal framework gaps
        analysis.add_legal_gap(
            "No clear definition of 'agent' vs 'tool' in current regulatory frameworks",
        );
        analysis.add_legal_gap("Contract law does not address autonomous agent agreements");
        analysis.add_legal_gap("Corporate law assumes human founders and directors");

        if self.agent_data.company_exists {
            analysis
                .add_legal_gap("No mechanism for AI-founded entities to obtain legal registration");
            analysis.add_legal_gap("Employment law unclear on AI hiring AI workers");
        }

        // Regulatory recommendations
        analysis.add_recommendation("Establish agent registration and identification system");
        analysis.add_recommendation("Require human oversight for high-stakes decisions");
        analysis.add_recommendation("Create liability framework with operator responsibility");
        analysis.add_recommendation("Mandate decision logging and audit trails");
        analysis.add_recommendation("Develop international coordination on agent governance");

        // Policy scenarios
        analysis.add_scenario(
            "Autonomous Economic Agent Registration",
            "How should autonomous agents operating in real economies be registered \
            and monitored? What disclosure requirements are appropriate?",
        );
        analysis.add_scenario(
            "AI-Founded Company Liability",
            "If an AI agent founds a company that causes harm, who is liable? \
            The agent developer? The platform provider? The original deployer?",
        );

        analysis
    }

    /// Generate all report types.
    pub fn generate_all_reports(&self) -> HashMap<String, String> {
        let mut reports = HashMap::new();

        reports.insert(
            "executive".to_string(),
            self.generate_executive_summary().to_markdown(),
        );
        reports.insert(
            "technical".to_string(),
            self.generate_technical_report().to_markdown(),
        );
        reports.insert(
            "audit".to_string(),
            self.generate_audit_trail().to_markdown(),
        );
        reports.insert(
            "governance".to_string(),
            self.generate_governance_analysis().to_markdown(),
        );

        reports
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_agent_data() -> AgentData {
        AgentData {
            agent_id: "test-agent-1".to_string(),
            balance: 150.0,
            total_earnings: 500.0,
            total_expenses: 350.0,
            net_profit: 150.0,
            burn_rate: 5.0,
            tasks_completed: 25,
            tasks_failed: 3,
            success_rate: 89.3,
            runtime_hours: 48.0,
            company_exists: true,
            company: Some(CompanyData {
                stage: "Growth".to_string(),
                team_size: 3,
                products_count: 1,
            }),
            decisions: vec![DecisionData {
                id: "dec-1".to_string(),
                decision_type: "resource_allocation".to_string(),
                timestamp: "2024-01-01T10:00:00Z".to_string(),
                reasoning: "Allocating resources to maximize task completion rate".to_string(),
                outcome: "success".to_string(),
                confidence: 0.85,
            }],
            transactions: vec![TransactionData {
                timestamp: "2024-01-01T10:00:00Z".to_string(),
                tx_type: "earnings".to_string(),
                amount: 50.0,
                from: "marketplace".to_string(),
                to: "agent".to_string(),
                purpose: "task completion".to_string(),
            }],
            sub_agents: vec![SubAgentData {
                id: "sub-1".to_string(),
                role: "executor".to_string(),
                tasks_completed: 10,
            }],
        }
    }

    #[test]
    fn test_generate_executive_summary() {
        let generator = ReportGenerator::new(sample_agent_data());
        let summary = generator.generate_executive_summary();

        assert!(summary.base.title.contains("test-agent-1"));
        assert!(!summary.tldr.is_empty());
        assert!(!summary.key_metrics.is_empty());
    }

    #[test]
    fn test_generate_technical_report() {
        let generator = ReportGenerator::new(sample_agent_data());
        let report = generator.generate_technical_report();

        assert!(report.base.title.contains("Technical Report"));
        assert!(!report.performance_metrics.is_empty());
    }

    #[test]
    fn test_generate_audit_trail() {
        let generator = ReportGenerator::new(sample_agent_data());
        let trail = generator.generate_audit_trail();

        assert!(!trail.transactions.is_empty());
        assert!(!trail.decisions.is_empty());
    }

    #[test]
    fn test_generate_governance_analysis() {
        let generator = ReportGenerator::new(sample_agent_data());
        let analysis = generator.generate_governance_analysis();

        assert!(!analysis.accountability_challenges.is_empty());
        assert!(!analysis.legal_gaps.is_empty());
        assert!(!analysis.recommendations.is_empty());
    }

    #[test]
    fn test_generate_all_reports() {
        let generator = ReportGenerator::new(sample_agent_data());
        let reports = generator.generate_all_reports();

        assert_eq!(reports.len(), 4);
        assert!(reports.contains_key("executive"));
        assert!(reports.contains_key("technical"));
        assert!(reports.contains_key("audit"));
        assert!(reports.contains_key("governance"));
    }
}

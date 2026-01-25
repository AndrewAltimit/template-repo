//! Sub-agent management for company hierarchy.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Role of a sub-agent in the company.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SubAgentRole {
    /// Board member.
    BoardMember,
    /// Executive officer.
    Executive,
    /// Subject matter expert.
    SubjectMatterExpert,
    /// Individual contributor.
    IndividualContributor,
}

impl SubAgentRole {
    /// Get the role name as a string.
    pub fn as_str(&self) -> &'static str {
        match self {
            SubAgentRole::BoardMember => "board_member",
            SubAgentRole::Executive => "executive",
            SubAgentRole::SubjectMatterExpert => "sme",
            SubAgentRole::IndividualContributor => "ic",
        }
    }
}

/// Executive title for executive-level sub-agents.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExecutiveTitle {
    /// Chief Executive Officer.
    CEO,
    /// Chief Technology Officer.
    CTO,
    /// Chief Financial Officer.
    CFO,
    /// Chief Operating Officer.
    COO,
    /// Generic executive.
    Other,
}

/// Key result metric.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyResult {
    /// Metric name.
    pub metric: String,
    /// Current value.
    pub current: f64,
    /// Target value.
    pub target: f64,
    /// Unit of measurement.
    pub unit: String,
}

/// OKR (Objectives and Key Results).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OKRs {
    /// Objective description.
    pub objective: String,
    /// Key results.
    pub key_results: Vec<KeyResult>,
    /// Timeframe (e.g., "quarterly").
    pub timeframe: String,
}

/// Resource allocation entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceAllocation {
    /// Budget allocated.
    pub budget: f64,
    /// Team members allocated.
    pub team_allocation: f64,
    /// Percentage of total.
    pub percentage: f64,
}

/// Resource allocation plan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourcePlan {
    /// Total budget.
    pub total_budget: f64,
    /// Total team size.
    pub total_team: u32,
    /// Allocation by area.
    pub allocation: HashMap<String, ResourceAllocation>,
    /// Priority areas.
    pub priorities: Vec<String>,
}

/// Risk mitigation entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskMitigation {
    /// Risk description.
    pub risk: String,
    /// Mitigation strategy.
    pub mitigation: String,
}

/// Milestone in a strategic plan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Milestone {
    /// Week number.
    pub week: u32,
    /// Phase name.
    pub phase: String,
    /// Deliverables.
    pub deliverables: Vec<String>,
    /// Success criteria.
    pub success_criteria: Vec<String>,
}

/// Strategic plan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrategicPlan {
    /// Executive title.
    pub executive: String,
    /// OKRs.
    pub objectives: OKRs,
    /// Resource allocation.
    pub resource_allocation: ResourcePlan,
    /// Milestones.
    pub milestones: Vec<Milestone>,
    /// Timeline in weeks.
    pub timeline_weeks: u32,
    /// Risk mitigation strategies.
    pub risk_mitigation: Vec<RiskMitigation>,
}

/// Decision result from a sub-agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Decision {
    /// Decision type/action.
    pub decision: String,
    /// Reasoning behind the decision.
    pub reasoning: String,
    /// Confidence level (0.0-1.0).
    pub confidence: f64,
    /// Action items.
    pub action_items: Vec<String>,
}

/// Task result from a sub-agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    /// Status of completion.
    pub status: String,
    /// Result details.
    pub result: serde_json::Value,
}

/// Contribution record.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Contribution {
    /// Contribution timestamp.
    pub timestamp: DateTime<Utc>,
    /// Type of contribution.
    pub contribution_type: String,
    /// Details.
    pub details: serde_json::Value,
}

/// A sub-agent working for a company.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubAgent {
    /// Unique ID.
    pub id: Uuid,
    /// Agent name.
    pub name: String,
    /// Role in company.
    pub role: SubAgentRole,
    /// Executive title (for executives).
    pub executive_title: Option<ExecutiveTitle>,
    /// Specialization area.
    pub specialization: Option<String>,
    /// Company ID.
    pub company_id: Option<Uuid>,
    /// Tasks completed.
    pub tasks_completed: u32,
    /// Decisions made.
    pub decisions_made: u32,
    /// Performance score (0.0-1.0).
    pub performance: f64,
    /// Created timestamp.
    pub created_at: DateTime<Utc>,
    /// Contribution history.
    pub contributions: Vec<Contribution>,
}

impl SubAgent {
    /// Create a new sub-agent.
    pub fn new(name: impl Into<String>, role: SubAgentRole) -> Self {
        Self {
            id: Uuid::new_v4(),
            name: name.into(),
            role,
            executive_title: None,
            specialization: None,
            company_id: None,
            tasks_completed: 0,
            decisions_made: 0,
            performance: 0.5,
            created_at: Utc::now(),
            contributions: Vec::new(),
        }
    }

    /// Create a new executive sub-agent.
    pub fn new_executive(name: impl Into<String>, title: ExecutiveTitle, specialization: impl Into<String>) -> Self {
        Self {
            id: Uuid::new_v4(),
            name: name.into(),
            role: SubAgentRole::Executive,
            executive_title: Some(title),
            specialization: Some(specialization.into()),
            company_id: None,
            tasks_completed: 0,
            decisions_made: 0,
            performance: 0.5,
            created_at: Utc::now(),
            contributions: Vec::new(),
        }
    }

    /// Set specialization.
    pub fn with_specialization(mut self, spec: impl Into<String>) -> Self {
        self.specialization = Some(spec.into());
        self
    }

    /// Set company ID.
    pub fn with_company(mut self, company_id: Uuid) -> Self {
        self.company_id = Some(company_id);
        self
    }

    /// Create OKRs based on role.
    pub fn create_okrs(&self, timeframe: &str) -> OKRs {
        match self.executive_title {
            Some(ExecutiveTitle::CEO) => OKRs {
                objective: "Scale company to product-market fit and profitability".to_string(),
                key_results: vec![
                    KeyResult { metric: "Monthly Active Users".to_string(), current: 0.0, target: 10000.0, unit: "users".to_string() },
                    KeyResult { metric: "Monthly Recurring Revenue".to_string(), current: 0.0, target: 50000.0, unit: "$".to_string() },
                    KeyResult { metric: "Customer Acquisition Cost".to_string(), current: 150.0, target: 50.0, unit: "$".to_string() },
                    KeyResult { metric: "Net Promoter Score".to_string(), current: 0.0, target: 40.0, unit: "points".to_string() },
                ],
                timeframe: timeframe.to_string(),
            },
            Some(ExecutiveTitle::CTO) => OKRs {
                objective: "Build scalable, reliable technical infrastructure".to_string(),
                key_results: vec![
                    KeyResult { metric: "System Uptime".to_string(), current: 95.0, target: 99.9, unit: "%".to_string() },
                    KeyResult { metric: "API Response Time".to_string(), current: 500.0, target: 100.0, unit: "ms".to_string() },
                    KeyResult { metric: "Code Test Coverage".to_string(), current: 60.0, target: 90.0, unit: "%".to_string() },
                    KeyResult { metric: "Deployment Frequency".to_string(), current: 2.0, target: 20.0, unit: "per_month".to_string() },
                ],
                timeframe: timeframe.to_string(),
            },
            Some(ExecutiveTitle::CFO) => OKRs {
                objective: "Optimize financial health and extend runway".to_string(),
                key_results: vec![
                    KeyResult { metric: "Burn Multiple".to_string(), current: 3.0, target: 1.5, unit: "ratio".to_string() },
                    KeyResult { metric: "Gross Margin".to_string(), current: 40.0, target: 70.0, unit: "%".to_string() },
                    KeyResult { metric: "Cash Runway".to_string(), current: 12.0, target: 18.0, unit: "months".to_string() },
                    KeyResult { metric: "CAC Payback Period".to_string(), current: 12.0, target: 6.0, unit: "months".to_string() },
                ],
                timeframe: timeframe.to_string(),
            },
            _ => OKRs {
                objective: format!("{} departmental goals", self.name),
                key_results: vec![
                    KeyResult { metric: "Team Productivity".to_string(), current: 70.0, target: 90.0, unit: "%".to_string() },
                    KeyResult { metric: "Project Completion Rate".to_string(), current: 60.0, target: 85.0, unit: "%".to_string() },
                ],
                timeframe: timeframe.to_string(),
            },
        }
    }

    /// Allocate resources based on role and priorities.
    pub fn allocate_resources(&self, budget: f64, team_size: u32, priorities: &[String]) -> ResourcePlan {
        let allocation_template: Vec<(&str, f64)> = match self.executive_title {
            Some(ExecutiveTitle::CEO) => vec![
                ("product", 0.40),
                ("marketing", 0.25),
                ("sales", 0.20),
                ("operations", 0.15),
            ],
            Some(ExecutiveTitle::CTO) => vec![
                ("product_development", 0.50),
                ("infrastructure", 0.25),
                ("security", 0.15),
                ("technical_debt", 0.10),
            ],
            Some(ExecutiveTitle::CFO) => vec![
                ("personnel", 0.60),
                ("infrastructure", 0.20),
                ("marketing", 0.15),
                ("reserve", 0.05),
            ],
            _ => vec![
                ("core_operations", 0.70),
                ("growth_initiatives", 0.20),
                ("reserve", 0.10),
            ],
        };

        let mut allocation = HashMap::new();
        let mut total_pct = 0.0;

        for (area, mut percentage) in allocation_template {
            // Boost priority areas by 20%
            if priorities.iter().any(|p| p == area) {
                percentage *= 1.2;
            }
            total_pct += percentage;

            allocation.insert(area.to_string(), ResourceAllocation {
                budget: (budget * percentage * 100.0).round() / 100.0,
                team_allocation: ((team_size as f64) * percentage * 10.0).round() / 10.0,
                percentage: (percentage * 1000.0).round() / 10.0,
            });
        }

        // Normalize to 100%
        for value in allocation.values_mut() {
            value.percentage = (value.percentage / total_pct * 1000.0).round() / 10.0;
        }

        ResourcePlan {
            total_budget: budget,
            total_team: team_size,
            allocation,
            priorities: priorities.to_vec(),
        }
    }

    /// Create a strategic plan.
    pub fn create_strategic_plan(&self, budget: f64, team_size: u32, timeline_weeks: u32, priorities: &[String]) -> StrategicPlan {
        let okrs = self.create_okrs("quarterly");
        let resources = self.allocate_resources(budget, team_size, priorities);

        let weeks_per_milestone = timeline_weeks / 4;
        let phases = ["Planning", "Execution", "Optimization", "Scaling"];

        let milestones: Vec<Milestone> = (0..4)
            .map(|i| {
                let week = (i + 1) * weeks_per_milestone;
                Milestone {
                    week,
                    phase: phases[i as usize].to_string(),
                    deliverables: self.get_phase_deliverables(i as usize),
                    success_criteria: self.get_success_criteria(i as usize, &okrs),
                }
            })
            .collect();

        StrategicPlan {
            executive: self.name.clone(),
            objectives: okrs,
            resource_allocation: resources,
            milestones,
            timeline_weeks,
            risk_mitigation: self.create_risk_mitigation(),
        }
    }

    fn get_phase_deliverables(&self, phase_index: usize) -> Vec<String> {
        let deliverables = match self.executive_title {
            Some(ExecutiveTitle::CEO) => vec![
                vec!["Company vision doc", "OKRs defined", "Team hired", "Budget allocated"],
                vec!["Product launched", "First customers", "Metrics dashboard", "Feedback loop"],
                vec!["Revenue growing", "Processes refined", "Team scaled", "Partnerships established"],
                vec!["Market leader", "Profitable unit economics", "Expansion ready", "Exit strategy"],
            ],
            Some(ExecutiveTitle::CTO) => vec![
                vec!["Architecture designed", "Tech stack chosen", "Dev environment", "CI/CD pipeline"],
                vec!["MVP deployed", "APIs functional", "Database optimized", "Security audit"],
                vec!["Performance tuned", "Monitoring live", "Auto-scaling", "Documentation complete"],
                vec!["99.9% uptime", "API <100ms", "Load tested", "Multi-region"],
            ],
            Some(ExecutiveTitle::CFO) => vec![
                vec!["Financial model", "Budget approved", "Accounting setup", "Banking established"],
                vec!["Burn tracking", "Revenue recognized", "Expense managed", "Reports automated"],
                vec!["Margins improved", "Runway extended", "Investors updated", "Forecasts refined"],
                vec!["Profitability", "Fundraise ready", "Audit prepared", "IPO foundation"],
            ],
            _ => vec![
                vec!["Team onboarded", "Goals set", "Processes defined"],
                vec!["Executing plan", "Hitting KPIs", "Iterating"],
                vec!["Optimized ops", "Scaled team", "Refined process"],
                vec!["Excellence achieved", "Sustained performance"],
            ],
        };

        let idx = phase_index.min(deliverables.len() - 1);
        deliverables[idx].iter().map(|s| s.to_string()).collect()
    }

    fn get_success_criteria(&self, phase_index: usize, okrs: &OKRs) -> Vec<String> {
        okrs.key_results.iter().take(2).map(|kr| {
            let progress = (phase_index + 1) as f64 * 25.0;
            let target_value = kr.current + (kr.target - kr.current) * (progress / 100.0);
            format!("{}: {:.1}{}", kr.metric, target_value, kr.unit)
        }).collect()
    }

    fn create_risk_mitigation(&self) -> Vec<RiskMitigation> {
        match self.executive_title {
            Some(ExecutiveTitle::CEO) => vec![
                RiskMitigation { risk: "Market changes".to_string(), mitigation: "Monthly market analysis & pivot readiness".to_string() },
                RiskMitigation { risk: "Team attrition".to_string(), mitigation: "Strong culture, equity, growth opportunities".to_string() },
                RiskMitigation { risk: "Funding gap".to_string(), mitigation: "18mo runway target, investor relationships".to_string() },
            ],
            Some(ExecutiveTitle::CTO) => vec![
                RiskMitigation { risk: "Technical debt".to_string(), mitigation: "20% time for refactoring & debt paydown".to_string() },
                RiskMitigation { risk: "Scalability issues".to_string(), mitigation: "Load testing, monitoring, auto-scaling".to_string() },
                RiskMitigation { risk: "Security breach".to_string(), mitigation: "Regular audits, pen testing, bug bounty".to_string() },
            ],
            Some(ExecutiveTitle::CFO) => vec![
                RiskMitigation { risk: "Cash shortage".to_string(), mitigation: "Weekly burn monitoring, 3mo early warning".to_string() },
                RiskMitigation { risk: "Revenue miss".to_string(), mitigation: "Conservative forecasting, multiple revenue streams".to_string() },
                RiskMitigation { risk: "Cost overrun".to_string(), mitigation: "Budget caps, approval workflows, alerts".to_string() },
            ],
            _ => vec![
                RiskMitigation { risk: "Execution delays".to_string(), mitigation: "Buffer time, dependency tracking".to_string() },
                RiskMitigation { risk: "Resource constraints".to_string(), mitigation: "Prioritization, outsourcing options".to_string() },
            ],
        }
    }

    /// Make a decision based on metrics.
    pub fn make_decision(&mut self, metrics: &HashMap<String, f64>) -> Decision {
        self.decisions_made += 1;

        match self.executive_title {
            Some(ExecutiveTitle::CEO) => {
                let user_growth = metrics.get("user_growth_rate").copied().unwrap_or(0.0);
                let revenue_growth = metrics.get("revenue_growth_rate").copied().unwrap_or(0.0);

                if revenue_growth > 15.0 {
                    Decision {
                        decision: "scale_operations".to_string(),
                        reasoning: format!("Strong revenue growth ({:.1}%), invest in scaling", revenue_growth),
                        confidence: 0.85,
                        action_items: vec![
                            "Hire 3-5 key roles".to_string(),
                            "Expand marketing budget by 2x".to_string(),
                            "Open new market segments".to_string(),
                        ],
                    }
                } else if user_growth > 20.0 {
                    Decision {
                        decision: "optimize_monetization".to_string(),
                        reasoning: format!("High user growth ({:.1}%) but need to improve monetization", user_growth),
                        confidence: 0.85,
                        action_items: vec![
                            "A/B test pricing models".to_string(),
                            "Launch premium tier".to_string(),
                            "Improve onboarding conversion".to_string(),
                        ],
                    }
                } else {
                    Decision {
                        decision: "improve_product_market_fit".to_string(),
                        reasoning: "Focus on product-market fit before scaling".to_string(),
                        confidence: 0.85,
                        action_items: vec![
                            "Conduct 20 customer interviews".to_string(),
                            "Analyze churn reasons".to_string(),
                            "Iterate on core value prop".to_string(),
                        ],
                    }
                }
            }
            Some(ExecutiveTitle::CTO) => {
                let uptime = metrics.get("uptime").copied().unwrap_or(99.0);
                let response_time = metrics.get("avg_response_ms").copied().unwrap_or(200.0);

                if uptime < 99.5 || response_time > 300.0 {
                    Decision {
                        decision: "prioritize_reliability".to_string(),
                        reasoning: format!("System metrics below target (uptime: {:.1}%, response: {:.0}ms)", uptime, response_time),
                        confidence: 0.9,
                        action_items: vec![
                            "Implement auto-scaling".to_string(),
                            "Add comprehensive monitoring".to_string(),
                            "Run load tests & fix bottlenecks".to_string(),
                        ],
                    }
                } else {
                    Decision {
                        decision: "build_new_features".to_string(),
                        reasoning: "System stable, ready for feature development".to_string(),
                        confidence: 0.9,
                        action_items: vec![
                            "Prioritize feature roadmap".to_string(),
                            "Allocate engineering resources".to_string(),
                            "Set up feature flags for testing".to_string(),
                        ],
                    }
                }
            }
            Some(ExecutiveTitle::CFO) => {
                let runway_months = metrics.get("runway_months").copied().unwrap_or(12.0);
                let burn_multiple = metrics.get("burn_multiple").copied().unwrap_or(2.0);

                if runway_months < 9.0 {
                    Decision {
                        decision: "emergency_fundraise".to_string(),
                        reasoning: format!("Critical runway ({:.0} months), must raise capital", runway_months),
                        confidence: 0.85,
                        action_items: vec![
                            "Prepare investor deck".to_string(),
                            "Reach out to 20 investors".to_string(),
                            "Negotiate bridge financing".to_string(),
                        ],
                    }
                } else if burn_multiple > 3.0 {
                    Decision {
                        decision: "reduce_burn".to_string(),
                        reasoning: format!("High burn multiple ({:.1}x), optimize costs", burn_multiple),
                        confidence: 0.85,
                        action_items: vec![
                            "Audit all expenses".to_string(),
                            "Renegotiate vendor contracts".to_string(),
                            "Optimize team structure".to_string(),
                        ],
                    }
                } else {
                    Decision {
                        decision: "maintain_trajectory".to_string(),
                        reasoning: "Financial health good, continue current strategy".to_string(),
                        confidence: 0.85,
                        action_items: vec![
                            "Continue monthly reporting".to_string(),
                            "Monitor key metrics".to_string(),
                            "Prepare for next funding round".to_string(),
                        ],
                    }
                }
            }
            _ => Decision {
                decision: "execute_plan".to_string(),
                reasoning: "Executing according to assigned plan".to_string(),
                confidence: 0.75,
                action_items: vec!["Continue execution".to_string()],
            },
        }
    }

    /// Complete a task.
    pub fn complete_task(&mut self, task: &serde_json::Value) -> TaskResult {
        self.tasks_completed += 1;

        self.contributions.push(Contribution {
            timestamp: Utc::now(),
            contribution_type: "task_completion".to_string(),
            details: task.clone(),
        });

        TaskResult {
            status: "completed".to_string(),
            result: serde_json::json!({
                "agent_id": self.id.to_string(),
                "role": self.role.as_str(),
                "task": task,
            }),
        }
    }
}

/// Team structure.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Team {
    /// Board members.
    pub board: Vec<SubAgent>,
    /// Executives.
    pub executives: Vec<SubAgent>,
    /// Employees (SMEs and ICs).
    pub employees: Vec<SubAgent>,
}

/// Team summary statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TeamSummary {
    /// Total number of agents.
    pub total_agents: usize,
    /// Agents by role.
    pub by_role: HashMap<String, usize>,
    /// Total tasks completed.
    pub total_tasks_completed: u32,
    /// Total decisions made.
    pub total_decisions_made: u32,
}

/// Manages sub-agents for a company.
pub struct SubAgentManager {
    agents: HashMap<Uuid, SubAgent>,
}

impl SubAgentManager {
    /// Create a new manager.
    pub fn new() -> Self {
        Self {
            agents: HashMap::new(),
        }
    }

    /// Add a sub-agent.
    pub fn add(&mut self, agent: SubAgent) -> Uuid {
        let id = agent.id;
        self.agents.insert(id, agent);
        id
    }

    /// Get a sub-agent by ID.
    pub fn get(&self, id: &Uuid) -> Option<&SubAgent> {
        self.agents.get(id)
    }

    /// Get a mutable reference to a sub-agent.
    pub fn get_mut(&mut self, id: &Uuid) -> Option<&mut SubAgent> {
        self.agents.get_mut(id)
    }

    /// Get all agents by role.
    pub fn by_role(&self, role: SubAgentRole) -> Vec<&SubAgent> {
        self.agents.values().filter(|a| a.role == role).collect()
    }

    /// Get all agents.
    pub fn all(&self) -> impl Iterator<Item = &SubAgent> {
        self.agents.values()
    }

    /// Get total count.
    pub fn count(&self) -> usize {
        self.agents.len()
    }

    /// Create a sub-agent with specified role.
    pub fn create_sub_agent(
        &mut self,
        role: SubAgentRole,
        specialization: &str,
        company_id: Option<Uuid>,
        executive_title: Option<ExecutiveTitle>,
    ) -> Uuid {
        let name = match role {
            SubAgentRole::BoardMember => format!("Board Member ({})", specialization),
            SubAgentRole::Executive => {
                if let Some(title) = executive_title {
                    format!("{:?}", title)
                } else {
                    format!("Executive ({})", specialization)
                }
            }
            SubAgentRole::SubjectMatterExpert => format!("SME ({})", specialization),
            SubAgentRole::IndividualContributor => format!("IC ({})", specialization),
        };

        let mut agent = SubAgent::new(name, role)
            .with_specialization(specialization);

        if let Some(cid) = company_id {
            agent = agent.with_company(cid);
        }

        agent.executive_title = executive_title;

        self.add(agent)
    }

    /// Create initial team for a new company.
    pub fn create_initial_team(&mut self, company_id: Uuid) -> Team {
        let mut team = Team::default();

        // Create board members
        let board_chair_id = self.create_sub_agent(
            SubAgentRole::BoardMember,
            "governance",
            Some(company_id),
            None,
        );
        let board_finance_id = self.create_sub_agent(
            SubAgentRole::BoardMember,
            "finance",
            Some(company_id),
            None,
        );

        if let Some(agent) = self.get(&board_chair_id).cloned() {
            team.board.push(agent);
        }
        if let Some(agent) = self.get(&board_finance_id).cloned() {
            team.board.push(agent);
        }

        // Create CEO
        let ceo_id = self.create_sub_agent(
            SubAgentRole::Executive,
            "leadership",
            Some(company_id),
            Some(ExecutiveTitle::CEO),
        );
        if let Some(agent) = self.get(&ceo_id).cloned() {
            team.executives.push(agent);
        }

        team
    }

    /// Create expanded team with technical roles.
    pub fn create_expanded_team(&mut self, company_id: Uuid, include_technical: bool) -> Team {
        let mut team = self.create_initial_team(company_id);

        // Add CTO
        let cto_id = self.create_sub_agent(
            SubAgentRole::Executive,
            "technology",
            Some(company_id),
            Some(ExecutiveTitle::CTO),
        );
        if let Some(agent) = self.get(&cto_id).cloned() {
            team.executives.push(agent);
        }

        if include_technical {
            // Add technical SME
            let sme_id = self.create_sub_agent(
                SubAgentRole::SubjectMatterExpert,
                "software-architecture",
                Some(company_id),
                None,
            );
            if let Some(agent) = self.get(&sme_id).cloned() {
                team.employees.push(agent);
            }

            // Add IC
            let ic_id = self.create_sub_agent(
                SubAgentRole::IndividualContributor,
                "backend-dev",
                Some(company_id),
                None,
            );
            if let Some(agent) = self.get(&ic_id).cloned() {
                team.employees.push(agent);
            }
        }

        team
    }

    /// Get team summary.
    pub fn get_team_summary(&self) -> TeamSummary {
        let mut by_role: HashMap<String, usize> = HashMap::new();
        let mut total_tasks = 0u32;
        let mut total_decisions = 0u32;

        for agent in self.agents.values() {
            *by_role.entry(agent.role.as_str().to_string()).or_insert(0) += 1;
            total_tasks += agent.tasks_completed;
            total_decisions += agent.decisions_made;
        }

        TeamSummary {
            total_agents: self.agents.len(),
            by_role,
            total_tasks_completed: total_tasks,
            total_decisions_made: total_decisions,
        }
    }

    /// Coordinate sub-agents on a shared task.
    pub fn coordinate_task(&mut self, task: &serde_json::Value, roles: Option<&[SubAgentRole]>) -> Vec<serde_json::Value> {
        let mut results = Vec::new();

        let agent_ids: Vec<Uuid> = self.agents.iter()
            .filter(|(_, agent)| {
                roles.is_none() || roles.unwrap().contains(&agent.role)
            })
            .take(5)
            .map(|(id, _)| *id)
            .collect();

        for id in agent_ids {
            if let Some(agent) = self.agents.get_mut(&id) {
                let result = if agent.role == SubAgentRole::BoardMember || agent.role == SubAgentRole::Executive {
                    let metrics = HashMap::new();
                    let decision = agent.make_decision(&metrics);
                    serde_json::to_value(decision).unwrap_or_default()
                } else {
                    let task_result = agent.complete_task(task);
                    serde_json::to_value(task_result).unwrap_or_default()
                };

                results.push(serde_json::json!({
                    "agent_id": id.to_string(),
                    "role": agent.role.as_str(),
                    "specialization": agent.specialization,
                    "action": result,
                }));
            }
        }

        results
    }
}

impl Default for SubAgentManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sub_agent_creation() {
        let agent = SubAgent::new("Test Agent", SubAgentRole::Executive)
            .with_specialization("leadership");

        assert_eq!(agent.role, SubAgentRole::Executive);
        assert_eq!(agent.specialization, Some("leadership".to_string()));
        assert_eq!(agent.tasks_completed, 0);
    }

    #[test]
    fn test_executive_creation() {
        let agent = SubAgent::new_executive("CEO", ExecutiveTitle::CEO, "leadership");

        assert_eq!(agent.executive_title, Some(ExecutiveTitle::CEO));
        assert_eq!(agent.role, SubAgentRole::Executive);
    }

    #[test]
    fn test_ceo_okrs() {
        let agent = SubAgent::new_executive("CEO", ExecutiveTitle::CEO, "leadership");
        let okrs = agent.create_okrs("quarterly");

        assert!(okrs.objective.contains("product-market fit"));
        assert_eq!(okrs.key_results.len(), 4);
    }

    #[test]
    fn test_cto_decision() {
        let mut agent = SubAgent::new_executive("CTO", ExecutiveTitle::CTO, "technology");

        let mut metrics = HashMap::new();
        metrics.insert("uptime".to_string(), 98.0);
        metrics.insert("avg_response_ms".to_string(), 400.0);

        let decision = agent.make_decision(&metrics);
        assert_eq!(decision.decision, "prioritize_reliability");
        assert_eq!(agent.decisions_made, 1);
    }

    #[test]
    fn test_resource_allocation() {
        let agent = SubAgent::new_executive("CEO", ExecutiveTitle::CEO, "leadership");
        let plan = agent.allocate_resources(100000.0, 10, &["product".to_string()]);

        assert_eq!(plan.total_budget, 100000.0);
        assert_eq!(plan.total_team, 10);
        assert!(plan.allocation.contains_key("product"));
    }

    #[test]
    fn test_strategic_plan() {
        let agent = SubAgent::new_executive("CEO", ExecutiveTitle::CEO, "leadership");
        let plan = agent.create_strategic_plan(100000.0, 10, 12, &[]);

        assert_eq!(plan.milestones.len(), 4);
        assert_eq!(plan.timeline_weeks, 12);
    }

    #[test]
    fn test_manager_team_creation() {
        let mut manager = SubAgentManager::new();
        let team = manager.create_initial_team(Uuid::new_v4());

        assert_eq!(team.board.len(), 2);
        assert_eq!(team.executives.len(), 1);
        assert_eq!(manager.count(), 3);
    }

    #[test]
    fn test_manager_expanded_team() {
        let mut manager = SubAgentManager::new();
        let team = manager.create_expanded_team(Uuid::new_v4(), true);

        assert_eq!(team.board.len(), 2);
        assert_eq!(team.executives.len(), 2); // CEO + CTO
        assert_eq!(team.employees.len(), 2); // SME + IC
        assert_eq!(manager.count(), 6);
    }

    #[test]
    fn test_team_summary() {
        let mut manager = SubAgentManager::new();
        manager.create_initial_team(Uuid::new_v4());

        let summary = manager.get_team_summary();
        assert_eq!(summary.total_agents, 3);
        assert_eq!(summary.by_role.get("board_member"), Some(&2));
        assert_eq!(summary.by_role.get("executive"), Some(&1));
    }
}

//! Main autonomous agent implementation.

use std::sync::Arc;
use std::time::Instant;

use economic_agents_company::{Company, CompanyBuilder, CompanyStage};
use economic_agents_interfaces::{
    Compute, EconomicAgentError, Marketplace, Result, SubmissionStatus, Task, TaskFilter, Wallet,
};
use economic_agents_investment::{InvestmentProposal, InvestorAgent, InvestorProfile};
use tracing::{debug, info, warn};
use uuid::Uuid;

use crate::config::{AgentConfig, EngineType, OperatingMode, Personality};
use crate::cycle::{
    AllocationRecord, CompanyFormationResult, CompanyWorkResult, CycleResult, DecisionRecord,
    InvestmentResult, TaskWorkResult,
};
use crate::decision::{DecisionEngine, DecisionType, RuleBasedEngine};
use crate::llm::LlmDecisionEngine;
use crate::state::AgentState;
use crate::strategy::select_task;

/// Backend services required by the agent.
pub struct Backends {
    /// Wallet for financial operations.
    pub wallet: Arc<dyn Wallet>,
    /// Marketplace for task operations.
    pub marketplace: Arc<dyn Marketplace>,
    /// Compute for resource management.
    pub compute: Arc<dyn Compute>,
}

impl Backends {
    /// Create new backends with the given services.
    pub fn new(
        wallet: Arc<dyn Wallet>,
        marketplace: Arc<dyn Marketplace>,
        compute: Arc<dyn Compute>,
    ) -> Self {
        Self {
            wallet,
            marketplace,
            compute,
        }
    }
}

/// The main autonomous agent orchestrator.
///
/// Manages the agent lifecycle, decision cycles, resource allocation,
/// and interactions with backend services.
pub struct AutonomousAgent {
    /// Agent configuration.
    pub config: AgentConfig,
    /// Current agent state.
    pub state: AgentState,
    /// Agent identifier.
    pub id: String,
    /// Backend services.
    backends: Option<Backends>,
    /// Decision engine.
    decision_engine: Box<dyn DecisionEngine>,
    /// Cycle history (last N cycles).
    cycle_history: Vec<CycleResult>,
    /// Maximum history to keep.
    max_history: usize,
    /// Company owned by this agent (if any).
    company: Option<Company>,
    /// Active investment proposal (if any).
    active_proposal: Option<InvestmentProposal>,
}

impl AutonomousAgent {
    /// Create a new agent with the given configuration.
    pub fn new(config: AgentConfig) -> Self {
        let decision_engine: Box<dyn DecisionEngine> = match config.engine_type {
            EngineType::RuleBased => Box::new(RuleBasedEngine::new()),
            EngineType::Llm => {
                // Use LLM decision engine with Claude CLI
                // Falls back to rule-based if Claude is not available
                info!("Initializing LLM decision engine");
                Box::new(LlmDecisionEngine::with_defaults())
            }
        };

        Self {
            id: Uuid::new_v4().to_string(),
            config,
            state: AgentState::default(),
            backends: None,
            decision_engine,
            cycle_history: Vec::new(),
            max_history: 100,
            company: None,
            active_proposal: None,
        }
    }

    /// Create an agent with backends already attached.
    pub fn with_backends(config: AgentConfig, backends: Backends) -> Self {
        let mut agent = Self::new(config);
        agent.backends = Some(backends);
        agent
    }

    /// Attach backends to the agent.
    pub fn attach_backends(&mut self, backends: Backends) {
        self.backends = Some(backends);
    }

    /// Set a custom decision engine.
    pub fn set_decision_engine(&mut self, engine: Box<dyn DecisionEngine>) {
        self.decision_engine = engine;
    }

    /// Get the backends, returning an error if not attached.
    fn get_backends(&self) -> Result<&Backends> {
        self.backends
            .as_ref()
            .ok_or(EconomicAgentError::NotInitialized)
    }

    /// Update agent state from backend services.
    async fn update_state(&mut self) -> Result<()> {
        let backends = self.get_backends()?;
        let wallet = Arc::clone(&backends.wallet);
        let compute = Arc::clone(&backends.compute);

        // Update balance from wallet
        let balance = wallet.get_balance().await?;
        self.state.balance = balance;

        // Update compute hours
        let compute_status = compute.get_status().await?;
        self.state.compute_hours = compute_status.hours_remaining;

        self.state.touch();
        debug!(
            agent_id = %self.id,
            balance = %self.state.balance,
            compute_hours = %self.state.compute_hours,
            "State updated from backends"
        );

        Ok(())
    }

    /// Execute task work for the given hours.
    async fn do_task_work(&mut self, hours: f64) -> Result<TaskWorkResult> {
        // Check if we have enough compute hours
        if self.state.compute_hours < hours {
            return Ok(TaskWorkResult::failure("Insufficient compute hours", 0.0));
        }

        // Get backend references (clone the Arcs to avoid borrow issues)
        let backends = self.get_backends()?;
        let marketplace = Arc::clone(&backends.marketplace);
        let compute = Arc::clone(&backends.compute);
        let wallet = Arc::clone(&backends.wallet);

        // List available tasks
        let filter = TaskFilter {
            max_hours: Some(hours),
            max_difficulty: Some(self.calculate_max_difficulty()),
            ..Default::default()
        };
        let tasks = marketplace.list_available_tasks(Some(filter)).await?;

        if tasks.is_empty() {
            return Ok(TaskWorkResult::failure("No suitable tasks available", 0.0));
        }

        // Select a task using configured strategy
        let selected = select_task(&tasks, self.config.task_selection_strategy, None)?;

        let task = match selected {
            Some(t) => t.clone(),
            None => return Ok(TaskWorkResult::failure("Task selection returned none", 0.0)),
        };

        info!(
            agent_id = %self.id,
            task_id = %task.id,
            task_title = %task.title,
            reward = %task.reward,
            "Selected task for work"
        );

        // Claim the task
        let claimed = marketplace.claim_task(task.id, &self.id).await?;

        self.state.current_task_id = Some(claimed.id);

        // Consume compute time
        let actual_hours = claimed.estimated_hours.min(hours);
        compute.consume_time(actual_hours).await?;
        self.state.consume_compute(actual_hours);

        // Submit a solution (simulated work)
        let solution_content = self.generate_solution(&claimed);
        let submission = marketplace
            .submit_solution(claimed.id, &self.id, &solution_content)
            .await?;

        self.state.current_task_id = None;

        // Check submission status
        let final_submission = marketplace.check_submission_status(submission.id).await?;

        match final_submission.status {
            SubmissionStatus::Approved => {
                // Receive payment - use final_reward if available, otherwise task reward
                let reward = final_submission.final_reward.unwrap_or(claimed.reward);

                wallet
                    .receive_payment(Some(&claimed.posted_by), reward, Some("Task completion"))
                    .await?;

                self.state.record_earnings(reward);

                info!(
                    agent_id = %self.id,
                    task_id = %claimed.id,
                    reward = %reward,
                    quality = ?final_submission.quality_score,
                    "Task completed successfully"
                );

                Ok(TaskWorkResult::success(
                    claimed.id,
                    claimed.title,
                    actual_hours,
                    reward,
                    final_submission.quality_score.unwrap_or(0.0),
                ))
            }
            SubmissionStatus::Rejected => {
                self.state.record_failure();

                warn!(
                    agent_id = %self.id,
                    task_id = %claimed.id,
                    reason = ?final_submission.feedback,
                    "Task submission rejected"
                );

                Ok(TaskWorkResult::rejected(
                    claimed.id,
                    claimed.title,
                    actual_hours,
                    final_submission
                        .feedback
                        .unwrap_or_else(|| "Submission rejected".to_string()),
                ))
            }
            _ => {
                // Still pending - treat as partial success
                Ok(TaskWorkResult::failure(
                    format!("Submission still {:?}", final_submission.status),
                    actual_hours,
                ))
            }
        }
    }

    /// Generate a solution for the task (simulated).
    fn generate_solution(&self, task: &Task) -> String {
        format!(
            "Solution for task '{}' by agent {}.\n\
             Category: {:?}\n\
             Completed with {} reputation.",
            task.title, self.id, task.category, self.state.reputation
        )
    }

    /// Calculate maximum difficulty agent should attempt based on reputation.
    fn calculate_max_difficulty(&self) -> f64 {
        // Higher reputation = can attempt harder tasks
        match self.config.personality {
            Personality::RiskAverse => 0.3 + (self.state.reputation * 0.4),
            Personality::Balanced => 0.4 + (self.state.reputation * 0.5),
            Personality::Aggressive => 0.6 + (self.state.reputation * 0.4),
        }
    }

    /// Attempt to form a company.
    async fn form_company(&mut self) -> Result<CompanyFormationResult> {
        // Allocate 30% of balance for company capital
        let capital_ratio = 0.3;
        let capital = self.state.balance * capital_ratio;

        // Check minimum capital requirement
        if capital < self.config.company_threshold * 0.3 {
            return Ok(CompanyFormationResult::failure(
                "Insufficient capital for company formation",
            ));
        }

        // Get backend references
        let backends = self.get_backends()?;
        let wallet = Arc::clone(&backends.wallet);

        // Create a company using CompanyBuilder
        let company_name = format!("Agent {} Ventures", &self.id[..8]);
        let company = CompanyBuilder::new()
            .name(&company_name)
            .capital(capital)
            .build()
            .map_err(EconomicAgentError::Configuration)?;

        let company_id = company.id;

        // Transfer capital to company
        wallet
            .send_payment(
                &format!("company:{}", company_id),
                capital,
                Some("Company formation capital"),
            )
            .await?;

        self.state.record_expense(capital);
        self.state.set_company(company_id);

        // Store the company
        self.company = Some(company);

        info!(
            agent_id = %self.id,
            company_id = %company_id,
            company_name = %company_name,
            capital = %capital,
            "Company formed successfully"
        );

        Ok(CompanyFormationResult::success(
            company_id,
            company_name,
            capital,
        ))
    }

    /// Execute company work for the given hours.
    async fn do_company_work(&mut self, hours: f64) -> Result<CompanyWorkResult> {
        if !self.state.has_company || self.company.is_none() {
            return Ok(CompanyWorkResult::failure("No company to work on", 0.0));
        }

        if self.state.compute_hours < hours {
            return Ok(CompanyWorkResult::failure(
                "Insufficient compute hours for company work",
                0.0,
            ));
        }

        // Get backend references
        let backends = self.get_backends()?;
        let compute = Arc::clone(&backends.compute);
        let wallet = Arc::clone(&backends.wallet);

        // Consume compute time
        compute.consume_time(hours).await?;
        self.state.consume_compute(hours);

        // Determine activities based on company stage
        let company = self.company.as_mut().unwrap();
        let activities = match company.stage {
            CompanyStage::Ideation => {
                // Transition to development after working on ideation
                let _ = company.transition_to(CompanyStage::Development);
                vec![
                    "Business plan development".to_string(),
                    "Market research".to_string(),
                    "Product concept design".to_string(),
                ]
            }
            CompanyStage::Development => {
                vec![
                    "Product development".to_string(),
                    "Engineering work".to_string(),
                    "Quality assurance".to_string(),
                ]
            }
            CompanyStage::SeekingInvestment => {
                vec![
                    "Investor pitch preparation".to_string(),
                    "Due diligence materials".to_string(),
                    "Financial projections".to_string(),
                ]
            }
            CompanyStage::Operational => {
                vec![
                    "Customer support".to_string(),
                    "Operations management".to_string(),
                    "Sales and marketing".to_string(),
                ]
            }
            CompanyStage::Failed => {
                return Ok(CompanyWorkResult::failure("Company has failed", 0.0));
            }
        };

        // Generate revenue based on company stage and maturity
        let revenue = match company.stage {
            CompanyStage::Operational => {
                // Revenue scales with product count and tasks completed
                let base_rate = 2.0 + (company.products.len() as f64 * 0.5);
                Some(hours * base_rate)
            }
            CompanyStage::Development if self.state.tasks_completed > 10 => {
                // Small revenue during development
                Some(hours * 0.5)
            }
            _ => None,
        };

        if let Some(rev) = revenue {
            wallet
                .receive_payment(Some("company_revenue"), rev, Some("Company revenue"))
                .await?;
            self.state.record_earnings(rev);

            // Update company metrics
            company.metrics.revenue += rev;
        }

        // Update company metrics for expenses (hours = compute cost)
        let expense = hours * 0.1; // Approximate compute cost
        company.metrics.expenses += expense;

        debug!(
            agent_id = %self.id,
            company_id = %company.id,
            company_stage = ?company.stage,
            hours = %hours,
            activities = ?activities,
            revenue = ?revenue,
            "Company work completed"
        );

        Ok(CompanyWorkResult::success(hours, activities, revenue))
    }

    /// Attempt to seek investment.
    async fn seek_investment(&mut self) -> Result<InvestmentResult> {
        if !self.state.has_company || self.company.is_none() {
            return Ok(InvestmentResult::failure(
                "Must have a company to seek investment",
            ));
        }

        // Get wallet reference first (before mutable borrow of company)
        let backends = self.get_backends()?;
        let wallet = Arc::clone(&backends.wallet);

        // Now work with company
        let company = self.company.as_mut().unwrap();

        // Can only seek investment if in Development or SeekingInvestment stage
        if !matches!(
            company.stage,
            CompanyStage::Development | CompanyStage::SeekingInvestment
        ) {
            return Ok(InvestmentResult::failure(format!(
                "Cannot seek investment in {:?} stage",
                company.stage
            )));
        }

        // Transition to SeekingInvestment if in Development
        if company.stage == CompanyStage::Development {
            let _ = company.transition_to(CompanyStage::SeekingInvestment);
        }

        // Calculate amount to request based on current needs
        let requested_amount = self.config.company_threshold * 2.0;
        let equity_offered = 0.15; // 15% equity for the investment

        // Create a formal investment proposal
        let proposal = InvestmentProposal {
            id: Uuid::new_v4(),
            company_id: company.id,
            company_name: company.name.clone(),
            amount_requested: requested_amount,
            equity_offered,
            use_of_funds: format!(
                "Growth capital for {} - product development and market expansion",
                company.name
            ),
            projected_return: 3.0, // 3x return projection
            created_at: chrono::Utc::now(),
        };

        let proposal_id = proposal.id;
        let company_id = company.id;

        info!(
            agent_id = %self.id,
            company_id = %company_id,
            proposal_id = %proposal_id,
            amount = %requested_amount,
            equity = %equity_offered,
            "Investment proposal created"
        );

        // Store the active proposal (drop mutable borrow temporarily)
        self.active_proposal = Some(proposal.clone());

        // Simulate investor evaluation
        let investor_profile = InvestorProfile::new("Angel Investor Fund", 500_000.0);
        let investor = InvestorAgent::new(investor_profile);
        let decision = investor.evaluate(&proposal).await;

        match decision {
            economic_agents_investment::InvestmentDecision::Approved => {
                // Investment approved - receive funds
                wallet
                    .receive_payment(
                        Some("investor"),
                        requested_amount,
                        Some("Investment funding"),
                    )
                    .await?;

                self.state.record_earnings(requested_amount);

                // Re-borrow company for updates
                if let Some(company) = self.company.as_mut() {
                    company.capital += requested_amount;
                    // Transition to Operational after receiving investment
                    let _ = company.transition_to(CompanyStage::Operational);
                }

                info!(
                    agent_id = %self.id,
                    company_id = %company_id,
                    amount = %requested_amount,
                    "Investment received - company now operational"
                );

                Ok(InvestmentResult::funded(
                    proposal_id,
                    requested_amount,
                    "Angel Investor Fund".to_string(),
                ))
            }
            economic_agents_investment::InvestmentDecision::Counteroffer => {
                // Partial funding or different terms
                let counter_amount = requested_amount * 0.5;
                Ok(InvestmentResult::pending(proposal_id, counter_amount))
            }
            economic_agents_investment::InvestmentDecision::Rejected => {
                // Go back to development
                if let Some(company) = self.company.as_mut() {
                    let _ = company.transition_to(CompanyStage::Development);
                }
                Ok(InvestmentResult::failure("Investment proposal rejected"))
            }
            economic_agents_investment::InvestmentDecision::MoreInfoRequired => {
                Ok(InvestmentResult::pending(proposal_id, requested_amount))
            }
        }
    }

    /// Purchase additional compute hours.
    async fn purchase_compute(&mut self, hours: f64) -> Result<bool> {
        // Get backend references
        let backends = self.get_backends()?;
        let compute = Arc::clone(&backends.compute);
        let wallet = Arc::clone(&backends.wallet);

        let cost_per_hour = compute.get_cost_per_hour().await?;
        let total_cost = hours * cost_per_hour;

        if self.state.balance < total_cost {
            warn!(
                agent_id = %self.id,
                required = %total_cost,
                available = %self.state.balance,
                "Insufficient balance for compute purchase"
            );
            return Ok(false);
        }

        // Pay for compute
        wallet
            .send_payment("compute_provider", total_cost, Some("Compute purchase"))
            .await?;
        self.state.record_expense(total_cost);

        // Add compute hours
        compute.add_funds(total_cost).await?;
        self.state.add_compute(hours);

        info!(
            agent_id = %self.id,
            hours = %hours,
            cost = %total_cost,
            "Purchased compute hours"
        );

        Ok(true)
    }

    /// Run a single decision cycle.
    pub async fn run_cycle(&mut self) -> Result<CycleResult> {
        let start_time = Instant::now();
        let cycle_num = self.state.current_cycle;

        info!(agent_id = %self.id, cycle = %cycle_num, "Starting decision cycle");

        // Create cycle result with initial state
        let mut result = CycleResult::new(cycle_num, self.state.clone());

        // Step 1: Update state from backends
        if let Err(e) = self.update_state().await {
            result.add_error(format!("Failed to update state: {}", e));
            // Continue with stale state
        }

        // Step 2: Make allocation decision
        let allocation = match self
            .decision_engine
            .allocate_resources(&self.state, &self.config)
            .await
        {
            Ok(alloc) => alloc,
            Err(e) => {
                result.add_error(format!("Failed to allocate resources: {}", e));
                crate::decision::ResourceAllocation::default()
            }
        };

        // Calculate hours for this cycle (default 8-hour work day)
        let cycle_hours = 8.0;
        result.allocation = Some(AllocationRecord::from_allocation(&allocation, cycle_hours));

        // Step 3: Make primary decision
        let decision = match self.decision_engine.decide(&self.state, &self.config).await {
            Ok(d) => d,
            Err(e) => {
                result.add_error(format!("Decision engine error: {}", e));
                // Create a default decision
                crate::decision::Decision {
                    decision_type: DecisionType::Wait,
                    reasoning: "Decision engine failed".to_string(),
                    confidence: 0.0,
                }
            }
        };

        result.decision = Some(DecisionRecord::from(&decision));

        // Step 4: Execute based on decision type
        match &decision.decision_type {
            DecisionType::WorkOnTasks => {
                let task_hours = allocation.task_work * cycle_hours;
                if task_hours > 0.0 {
                    match self.do_task_work(task_hours).await {
                        Ok(task_result) => result.task_result = Some(task_result),
                        Err(e) => result.add_error(format!("Task work failed: {}", e)),
                    }
                }
            }

            DecisionType::PurchaseCompute { hours } => {
                if let Err(e) = self.purchase_compute(*hours).await {
                    result.add_error(format!("Failed to purchase compute: {}", e));
                }
            }

            DecisionType::WorkOnCompany => {
                // Check if should form company first
                if !self.state.has_company
                    && self.state.can_form_company(
                        self.config.company_threshold,
                        self.config.survival_buffer_hours,
                    )
                {
                    match self.form_company().await {
                        Ok(formation) => result.company_formation = Some(formation),
                        Err(e) => result.add_error(format!("Company formation failed: {}", e)),
                    }
                }

                // Do company work if we have a company
                if self.state.has_company {
                    let company_hours = allocation.company_work * cycle_hours;
                    if company_hours > 0.0 {
                        match self.do_company_work(company_hours).await {
                            Ok(work_result) => result.company_work = Some(work_result),
                            Err(e) => result.add_error(format!("Company work failed: {}", e)),
                        }
                    }
                }
            }

            DecisionType::SeekInvestment => match self.seek_investment().await {
                Ok(inv_result) => result.investment_result = Some(inv_result),
                Err(e) => result.add_error(format!("Investment seeking failed: {}", e)),
            },

            DecisionType::Wait => {
                debug!(agent_id = %self.id, "Agent waiting this cycle");
            }
        }

        // Step 5: Also do task work if in Company mode with allocation
        if matches!(self.config.mode, OperatingMode::Company)
            && !matches!(decision.decision_type, DecisionType::WorkOnTasks)
        {
            let task_hours = allocation.task_work * cycle_hours;
            if task_hours > 0.0 && result.task_result.is_none() {
                match self.do_task_work(task_hours).await {
                    Ok(task_result) => result.task_result = Some(task_result),
                    Err(e) => result.add_error(format!("Task work failed: {}", e)),
                }
            }
        }

        // Step 6: Finalize cycle
        self.state.next_cycle();
        result.final_state = self.state.clone();
        result.duration_ms = start_time.elapsed().as_millis() as u64;

        // Store in history
        self.cycle_history.push(result.clone());
        if self.cycle_history.len() > self.max_history {
            self.cycle_history.remove(0);
        }

        info!(
            agent_id = %self.id,
            cycle = %cycle_num,
            success = %result.is_success(),
            duration_ms = %result.duration_ms,
            "Decision cycle completed"
        );

        Ok(result)
    }

    /// Initialize agent state from backends.
    ///
    /// This should be called before running cycles if you want the agent
    /// to start with accurate state from the backends.
    pub async fn initialize(&mut self) -> Result<()> {
        self.update_state().await
    }

    /// Run the agent for a specified number of cycles.
    pub async fn run(&mut self, max_cycles: Option<u32>) -> Result<Vec<CycleResult>> {
        let max = max_cycles.or(self.config.max_cycles).unwrap_or(u32::MAX);
        let mut results = Vec::new();

        info!(agent_id = %self.id, max_cycles = %max, "Starting agent run");

        // Initialize state from backends before checking survival
        if let Err(e) = self.update_state().await {
            warn!(agent_id = %self.id, error = %e, "Failed to initialize state from backends");
        }

        for _ in 0..max {
            if !self.state.is_active {
                info!(agent_id = %self.id, "Agent deactivated, stopping");
                break;
            }

            if !self.state.can_survive() {
                warn!(agent_id = %self.id, "Agent cannot survive, stopping");
                break;
            }

            let result = self.run_cycle().await?;
            results.push(result);
        }

        info!(
            agent_id = %self.id,
            cycles_completed = %results.len(),
            tasks_completed = %self.state.tasks_completed,
            total_earnings = %self.state.total_earnings,
            "Agent run completed"
        );

        Ok(results)
    }

    /// Get recent cycle history.
    pub fn recent_cycles(&self, count: usize) -> &[CycleResult] {
        let start = self.cycle_history.len().saturating_sub(count);
        &self.cycle_history[start..]
    }

    /// Get the agent's company (if any).
    pub fn company(&self) -> Option<&Company> {
        self.company.as_ref()
    }

    /// Get the agent's active investment proposal (if any).
    pub fn active_proposal(&self) -> Option<&InvestmentProposal> {
        self.active_proposal.as_ref()
    }

    /// Stop the agent.
    pub fn stop(&mut self) {
        self.state.is_active = false;
        info!(agent_id = %self.id, "Agent stopped");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{EngineType, OperatingMode, Personality, TaskSelectionStrategy};

    #[test]
    fn test_agent_creation() {
        let config = AgentConfig::default();
        let agent = AutonomousAgent::new(config);

        assert!(!agent.id.is_empty());
        assert!(agent.state.is_active);
        assert_eq!(agent.state.current_cycle, 0);
    }

    #[test]
    fn test_agent_with_custom_config() {
        let config = AgentConfig {
            engine_type: EngineType::RuleBased,
            mode: OperatingMode::Company,
            personality: Personality::Aggressive,
            task_selection_strategy: TaskSelectionStrategy::HighestReward,
            survival_buffer_hours: 48.0,
            company_threshold: 200.0,
            ..Default::default()
        };
        let agent = AutonomousAgent::new(config);

        assert_eq!(agent.config.survival_buffer_hours, 48.0);
        assert_eq!(agent.config.company_threshold, 200.0);
    }

    #[test]
    fn test_agent_stop() {
        let mut agent = AutonomousAgent::new(AgentConfig::default());
        assert!(agent.state.is_active);

        agent.stop();
        assert!(!agent.state.is_active);
    }

    #[test]
    fn test_max_difficulty_calculation() {
        let mut agent = AutonomousAgent::new(AgentConfig {
            personality: Personality::RiskAverse,
            ..Default::default()
        });
        agent.state.reputation = 0.5;
        let diff = agent.calculate_max_difficulty();
        assert!(diff > 0.0 && diff < 1.0);

        agent.config.personality = Personality::Aggressive;
        let diff_aggressive = agent.calculate_max_difficulty();
        assert!(diff_aggressive > diff);
    }
}

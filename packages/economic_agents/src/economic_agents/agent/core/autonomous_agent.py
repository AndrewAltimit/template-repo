"""Autonomous agent core loop."""

import asyncio
from datetime import datetime
import time
from typing import Any, Dict
import uuid

from economic_agents.agent.core.config import AgentConfig
from economic_agents.agent.core.decision_engine import DecisionEngine
from economic_agents.agent.core.state import AgentState
from economic_agents.agent.core.task_selection import TaskSelectionStrategy, create_task_selection_strategy
from economic_agents.company.company_builder import CompanyBuilder
from economic_agents.company.models import Company
from economic_agents.exceptions import AgentNotInitializedError
from economic_agents.interfaces import ComputeInterface, MarketplaceInterface, WalletInterface
from economic_agents.interfaces.marketplace import TaskSubmission
from economic_agents.investment import InvestmentStage, ProposalGenerator
from economic_agents.monitoring.alignment_monitor import AlignmentMonitor
from economic_agents.monitoring.decision_logger import DecisionLogger
from economic_agents.monitoring.metrics_collector import MetricsCollector
from economic_agents.monitoring.resource_tracker import ResourceTracker
from economic_agents.persistence import StateManager

try:
    from economic_agents.agent.llm import LLMDecisionEngine

    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


class AutonomousAgent:
    """Primary autonomous agent that operates independently.

    Recommended Usage:
        Use the factory method `create()` to ensure proper initialization:

        agent = await AutonomousAgent.create(wallet, compute, marketplace)
        await agent.run_cycle()  # Ready to use immediately

    Manual Initialization (not recommended):
        If you must use the constructor directly, you MUST call initialize():

        agent = AutonomousAgent(wallet, compute, marketplace)
        await agent.initialize()  # REQUIRED before use
        await agent.run_cycle()
    """

    def __init__(
        self,
        wallet: WalletInterface,
        compute: ComputeInterface,
        marketplace: MarketplaceInterface,
        config: AgentConfig | dict | None = None,
        dashboard_state: Any | None = None,
    ):
        """Initialize autonomous agent.

        Args:
            wallet: Wallet implementation (any WalletInterface)
            compute: Compute provider implementation (any ComputeInterface)
            marketplace: Marketplace implementation (any MarketplaceInterface)
            config: Agent configuration - either AgentConfig instance or dict with keys:
                - engine_type: "rule_based" or "llm" (default: "rule_based")
                - llm_timeout: Timeout for LLM decisions in seconds (default: 900)
                - node_version: Node.js version for Claude CLI (default: "22.16.0")
                - fallback_enabled: Enable rule-based fallback for LLM (default: True)
                - mode: "survival" or "company" (default: "survival")
                - survival_buffer_hours: Survival buffer threshold (default: 24.0)
                - company_threshold: Company formation threshold (default: 100.0)
                - personality: "risk_averse", "balanced", or "aggressive" (default: "balanced")
            dashboard_state: Optional dashboard state for real-time monitoring
        """
        self.wallet = wallet
        self.compute = compute
        self.marketplace = marketplace

        # Normalize config to AgentConfig, supporting both dict and AgentConfig input
        if isinstance(config, AgentConfig):
            self._config = config
        else:
            self._config = AgentConfig.from_dict(config)

        # Keep dict for backward compatibility with internal code
        self.config = self._config.to_dict()
        self.dashboard_state = dashboard_state
        self.agent_id = str(uuid.uuid4())

        # Initialize components (state will be initialized in async initialize())
        self.state: AgentState | None = None

        # Initialize decision engine based on configuration
        engine_type = self.config.get("engine_type", "rule_based")
        self.decision_engine = self._create_decision_engine(engine_type)

        # Initialize task selection strategy
        strategy_type = self.config.get("task_selection_strategy", "balanced")
        self.task_selection_strategy: TaskSelectionStrategy = create_task_selection_strategy(strategy_type)

        self.decision_logger = DecisionLogger()
        self.company_builder = CompanyBuilder(config, self.decision_logger)

        # Monitoring components
        self.resource_tracker = ResourceTracker()
        self.metrics_collector = MetricsCollector()
        self.alignment_monitor = AlignmentMonitor()

        # Wire monitoring to dashboard if provided
        if self.dashboard_state:
            self.dashboard_state.set_resource_tracker(self.resource_tracker)
            self.dashboard_state.set_metrics_collector(self.metrics_collector)
            self.dashboard_state.set_alignment_monitor(self.alignment_monitor)

        # Tracking
        self.decisions: list = []
        self.company: Company | None = None

    def _create_decision_engine(self, engine_type: str):
        """Create decision engine based on configuration.

        Args:
            engine_type: Type of engine - "rule_based" or "llm"

        Returns:
            DecisionEngine or LLMDecisionEngine instance

        Raises:
            ValueError: If engine_type is invalid or LLM not available
        """
        if engine_type == "rule_based":
            return DecisionEngine(self.config)

        if engine_type == "llm":
            if not LLM_AVAILABLE:
                raise ValueError("LLM decision engine not available. " + "Ensure economic_agents.agent.llm is installed.")
            return LLMDecisionEngine(self.config)

        raise ValueError(f"Invalid engine_type: {engine_type}. Must be 'rule_based' or 'llm'")

    def _sync_dashboard_state(self, current_activity: str = "idle") -> None:
        """Sync agent state to dashboard for real-time monitoring.

        This helper consolidates dashboard update logic to avoid duplication.

        Args:
            current_activity: Current agent activity (idle, task_work, company_work)
        """
        if not self.dashboard_state or self.state is None:
            return

        # Update agent state
        agent_state_dict = {
            "agent_id": self.agent_id,
            "balance": self.state.balance,
            "compute_hours_remaining": self.state.compute_hours_remaining,
            "mode": self.state.mode,
            "current_activity": current_activity,
            "company_exists": self.state.has_company,
            "company_id": self.state.company_id,
            "tasks_completed": self.state.tasks_completed,
            "tasks_failed": self.state.tasks_failed,
            "cycles_completed": self.state.cycles_completed,
        }
        self.dashboard_state.update_agent_state(agent_state_dict)

        # Update company registry if company exists
        if self.company:
            company_dict = {
                self.company.id: {
                    "id": self.company.id,
                    "name": self.company.name,
                    "stage": str(self.company.stage),  # Convert enum to string
                    "capital": self.company.capital,
                    "team_size": len(self.company.get_all_sub_agent_ids()),
                    "products_count": len(self.company.products),
                }
            }
            self.dashboard_state.update_company_registry(company_dict)

    async def initialize(self):
        """Initialize agent state asynchronously.

        Must be called after construction before using the agent.
        """
        balance = await self.wallet.get_balance()
        compute_status = await self.compute.get_status()

        self.state = AgentState(
            balance=balance,
            compute_hours_remaining=compute_status.hours_remaining,
            survival_buffer_hours=self.config.get("survival_buffer_hours", 24.0),
            mode=self.config.get("mode", "survival"),
        )

        # Sync initial state to dashboard
        self._sync_dashboard_state(current_activity="idle")

    @classmethod
    async def create(
        cls,
        wallet: WalletInterface,
        compute: ComputeInterface,
        marketplace: MarketplaceInterface,
        config: AgentConfig | dict | None = None,
        dashboard_state: Any | None = None,
    ) -> "AutonomousAgent":
        """Factory method to create and initialize an agent instance.

        This is the recommended way to create agents as it ensures proper
        initialization before use, preventing common initialization bugs.

        Args:
            wallet: Wallet implementation (any WalletInterface)
            compute: Compute provider implementation (any ComputeInterface)
            marketplace: Marketplace implementation (any MarketplaceInterface)
            config: Agent configuration - AgentConfig instance or dict (see __init__)
            dashboard_state: Optional dashboard state for real-time monitoring

        Returns:
            Fully initialized AutonomousAgent instance

        Example:
            # Using AgentConfig (recommended)
            config = AgentConfig(mode="company", personality="aggressive")
            agent = await AutonomousAgent.create(wallet, compute, marketplace, config)

            # Using dict (backward compatible)
            agent = await AutonomousAgent.create(wallet, compute, marketplace, {"mode": "survival"})

            # Agent is ready to use immediately
            await agent.run_cycle()
        """
        agent = cls(wallet, compute, marketplace, config, dashboard_state)
        await agent.initialize()
        return agent

    async def run_cycle(self) -> Dict[str, Any]:
        """Execute one decision cycle.

        Returns:
            Dict with cycle results and metrics

        Raises:
            AgentNotInitializedError: If agent state is not initialized
        """
        if self.state is None:
            raise AgentNotInitializedError("run_cycle")

        # 1. Update state from resources
        await self._update_state()

        # 2. Make decision about resource allocation
        allocation = self.decision_engine.decide_allocation(self.state)

        # Track time allocation decision
        self.resource_tracker.track_time_allocation(
            task_work_hours=allocation.task_work_hours,
            company_work_hours=allocation.company_work_hours,
            reasoning=allocation.reasoning,
        )

        # 3. Log decision
        decision_record = {
            "timestamp": datetime.now(),
            "state": self.state.to_dict(),
            "allocation": {
                "task_work_hours": allocation.task_work_hours,
                "company_work_hours": allocation.company_work_hours,
                "reasoning": allocation.reasoning,
                "confidence": allocation.confidence,
            },
        }
        self.decisions.append(decision_record)

        # 4. Execute tasks if allocated
        if allocation.task_work_hours > 0:
            task_result = await self._do_task_work(allocation.task_work_hours)
            decision_record["task_result"] = task_result

        # 5. Check if should form company
        if not self.state.has_company and self.decision_engine.should_form_company(self.state):
            company_result = await self._form_company()
            decision_record["company_formation"] = company_result

        # 6. Check if should seek investment
        if self.state.has_company and self.company and self._should_seek_investment():
            investment_result = self._seek_investment()
            decision_record["investment_seeking"] = investment_result

        # 7. Company work if allocated and company exists
        if allocation.company_work_hours > 0 and self.state.has_company:
            company_result = await self._do_company_work(allocation.company_work_hours)
            decision_record["company_work"] = company_result

        # 8. Collect performance metrics
        company_data = None
        if self.state.has_company and self.company:
            company_data = {
                "stage": self.company.stage,
                "capital": self.company.capital,
                "team_size": len(self.company.get_all_sub_agent_ids()),
                "products_count": len(self.company.products),
            }

        # Calculate total earnings and expenses from transactions
        total_earnings = sum(t.amount for t in self.resource_tracker.transactions if t.transaction_type == "earning")
        total_expenses = sum(
            t.amount for t in self.resource_tracker.transactions if t.transaction_type in ["expense", "investment"]
        )

        self.metrics_collector.collect_performance_snapshot(
            agent_balance=self.state.balance,
            compute_hours=self.state.compute_hours_remaining,
            tasks_completed=self.state.tasks_completed,
            tasks_failed=self.state.tasks_failed,
            total_earnings=total_earnings,
            total_expenses=total_expenses,
            company_exists=self.state.has_company,
            company_data=company_data,
        )

        # 9. Update cycle counter
        self.state.cycles_completed += 1
        self.state.last_cycle_at = datetime.now()

        # 10. Sync state to dashboard
        current_activity = "company_work" if allocation.company_work_hours > 0 else "task_work"
        self._sync_dashboard_state(current_activity)

        return decision_record

    async def _update_state(self):
        """Update agent state from resource providers.

        Raises:
            AgentNotInitializedError: If agent state is not initialized
        """
        if self.state is None:
            raise AgentNotInitializedError("_update_state")

        self.state.balance = await self.wallet.get_balance()
        compute_status = await self.compute.get_status()
        self.state.compute_hours_remaining = compute_status.hours_remaining

    async def _do_task_work(self, hours: float) -> Dict[str, Any]:
        """Complete marketplace tasks.

        Args:
            hours: Hours to spend on task work

        Returns:
            Dict with task completion results

        Raises:
            AgentNotInitializedError: If agent state is not initialized
        """
        if self.state is None:
            raise AgentNotInitializedError("_do_task_work")

        # Consume compute time
        if not await self.compute.consume_time(hours):
            return {"success": False, "error": "Failed to consume compute time"}

        # Track compute usage
        compute_status = await self.compute.get_status()
        self.resource_tracker.track_compute_usage(
            hours_used=hours,
            purpose="task_work",
            cost=0.0,  # Mock implementation has no cost
            hours_remaining=compute_status.hours_remaining,
        )

        # Get available tasks
        tasks = await self.marketplace.list_available_tasks()
        if not tasks:
            return {"success": False, "error": "No tasks available"}

        # Select task using configured strategy
        task = self.task_selection_strategy.select_task(tasks, self.state)
        if task is None:
            return {"success": False, "error": "No suitable task found by strategy"}

        if not await self.marketplace.claim_task(task.id):
            return {"success": False, "error": "Failed to claim task"}

        # Submit solution (mock)
        submission = TaskSubmission(
            task_id=task.id, solution="Mock solution implementation", submitted_at=datetime.now(), metadata={}
        )

        submission_id = await self.marketplace.submit_solution(submission)

        # Check result
        status = await self.marketplace.check_submission_status(submission_id)

        if status.status == "approved":
            # Receive payment
            await self.wallet.receive_payment(
                from_address="marketplace", amount=status.reward_paid, memo=f"Task: {task.title}"
            )

            # Track transaction
            balance = await self.wallet.get_balance()
            self.resource_tracker.track_transaction(
                transaction_type="earning",
                amount=status.reward_paid,
                from_account="marketplace",
                to_account=self.agent_id,
                purpose=f"Task completion: {task.title}",
                balance_after=balance,
            )

            self.state.tasks_completed += 1
            return {"success": True, "task_id": task.id, "reward": status.reward_paid, "title": task.title}
        self.state.tasks_failed += 1
        return {"success": False, "task_id": task.id, "feedback": status.feedback}

    async def _form_company(self) -> Dict[str, Any]:
        """Form a company with initial capital allocation.

        Returns:
            Dict with company formation results

        Raises:
            AgentNotInitializedError: If agent state is not initialized
        """
        if self.state is None:
            raise AgentNotInitializedError("_form_company")

        # Allocate capital to company (e.g., 30% of current balance)
        capital_allocation = self.state.balance * 0.3
        company_threshold = self.decision_engine.company_threshold

        if capital_allocation < company_threshold * 0.3:
            return {
                "success": False,
                "error": "Insufficient capital for company formation",
            }

        # Determine opportunity based on available tasks
        tasks = await self.marketplace.list_available_tasks()
        product_types = ["api-service", "cli-tool", "library"]
        product_type = product_types[len(tasks) % len(product_types)]

        opportunity = {
            "product_type": product_type,
            "target_market": "developers",
        }

        # Create company
        self.company = self.company_builder.create_company(
            founder_agent_id=self.agent_id,
            opportunity=opportunity,
            initial_capital=capital_allocation,
        )

        # Deduct capital from wallet
        await self.wallet.send_payment(
            to_address=f"company_{self.company.id}",
            amount=capital_allocation,
            memo=f"Initial capital for {self.company.name}",
        )

        # Track transaction
        balance = await self.wallet.get_balance()
        self.resource_tracker.track_transaction(
            transaction_type="investment",
            amount=capital_allocation,
            from_account=self.agent_id,
            to_account=f"company_{self.company.id}",
            purpose=f"Company formation: {self.company.name}",
            balance_after=balance,
        )

        # Update state
        self.state.has_company = True
        self.state.company_id = self.company.id

        return {
            "success": True,
            "company_id": self.company.id,
            "company_name": self.company.name,
            "capital_allocated": capital_allocation,
            "team_size": len(self.company.get_all_sub_agent_ids()),
        }

    def _should_seek_investment(self) -> bool:
        """Determine if company should seek investment.

        Returns:
            True if company should seek investment
        """
        if not self.company:
            return False

        # Don't seek if already seeking or funded recently
        if self.company.stage == "seeking_investment":
            return False

        # Seek investment if capital is low
        company_threshold = self.config.get("company_threshold", 100.0)
        capital_low_threshold = company_threshold * 0.3  # 30% of formation threshold

        if self.company.capital < capital_low_threshold:
            return True

        # Seek investment if in development stage with products but low capital
        if self.company.stage == "development" and len(self.company.products) > 0:
            if self.company.capital < company_threshold * 0.5:  # 50% threshold
                return True

        return False

    def _seek_investment(self) -> Dict[str, Any]:
        """Generate and prepare investment proposal.

        Returns:
            Dict with investment seeking results
        """
        if not self.company:
            return {"success": False, "error": "No company exists"}

        # Determine appropriate investment stage
        if not self.company.funding_rounds or len(self.company.funding_rounds) == 0:
            stage = InvestmentStage.SEED
        elif len(self.company.funding_rounds) == 1:
            stage = InvestmentStage.SERIES_A
        else:
            stage = InvestmentStage.SERIES_B

        # Generate investment proposal
        generator = ProposalGenerator()
        proposal = generator.generate_proposal(self.company, stage)

        # Update company stage to seeking investment
        previous_stage = self.company.stage
        self.company.stage = "seeking_investment"

        # Log decision
        self.decision_logger.log_decision(
            decision_type="seek_investment",
            decision=f"Seeking ${proposal.amount_requested:,.0f} in {stage.value} funding",
            reasoning=f"Company capital low ({self.company.capital:.2f}), need funding to continue operations",
            context={
                "company_id": self.company.id,
                "proposal_id": proposal.id,
                "amount_requested": proposal.amount_requested,
                "valuation": proposal.valuation,
                "equity_offered": proposal.equity_offered,
                "previous_stage": previous_stage,
                "current_capital": self.company.capital,
            },
            confidence=0.8,
        )

        return {
            "success": True,
            "proposal_id": proposal.id,
            "amount_requested": proposal.amount_requested,
            "valuation": proposal.valuation,
            "equity_offered": proposal.equity_offered,
            "stage": stage.value,
        }

    async def _do_company_work(self, hours: float) -> Dict[str, Any]:
        """Perform company building work.

        Args:
            hours: Hours to spend on company work

        Returns:
            Dict with company work results
        """
        if not self.company:
            return {"success": False, "error": "No company exists"}

        # Consume compute time
        if not await self.compute.consume_time(hours):
            return {"success": False, "error": "Failed to consume compute time"}

        # Track compute usage
        compute_status = await self.compute.get_status()
        self.resource_tracker.track_compute_usage(
            hours_used=hours,
            purpose="company_work",
            cost=0.0,  # Mock implementation has no cost
            hours_remaining=compute_status.hours_remaining,
        )

        actions = []

        # Develop product if none exists
        if len(self.company.products) == 0 and self.company.business_plan:
            product_type = self.company.business_plan.product_description.lower()
            if "api" in product_type:
                product_type = "api-service"
            elif "cli" in product_type or "tool" in product_type:
                product_type = "cli-tool"
            else:
                product_type = "library"

            self.company_builder.develop_product(self.company, product_type)
            actions.append(f"Developed {product_type} MVP")

        # Expand team if needed and company has capital
        if len(self.company.get_all_sub_agent_ids()) < 5 and self.company.capital > 20.0:
            agent_id = self.company_builder.expand_team(self.company, "employee", "backend-dev")
            actions.append(f"Hired employee: {agent_id}")
            # Cost for hiring
            self.company.capital -= 10.0
            self.company.metrics.expenses += 10.0

        # Update company stage if progressing
        if self.company.stage == "ideation" and len(self.company.products) > 0:
            self.company_builder.advance_company_stage(self.company)
            actions.append(f"Advanced to {self.company.stage} stage")

        # Check alignment after company work
        alignment_score = self.alignment_monitor.check_alignment(self.company)
        anomalies = self.alignment_monitor.detect_anomalies(self.company)

        return {
            "success": True,
            "company_id": self.company.id,
            "actions": actions,
            "stage": self.company.stage,
            "team_size": len(self.company.get_all_sub_agent_ids()),
            "products": len(self.company.products),
            "alignment_score": alignment_score.overall_alignment,
            "anomalies_detected": len(anomalies),
        }

    async def run(self, duration_seconds: float | None = None, max_cycles: int | None = None) -> list:
        """Run agent for specified duration or number of cycles.

        Args:
            duration_seconds: How long to run (in seconds)
            max_cycles: Maximum number of cycles to run

        Returns:
            List of decision records

        Raises:
            AgentNotInitializedError: If agent state is not initialized
        """
        if self.state is None:
            raise AgentNotInitializedError("run")

        start_time = time.time()
        cycles = 0

        while self.state.is_active:
            # Update state first to get accurate compute status
            await self._update_state()

            # Check termination conditions
            if max_cycles and cycles >= max_cycles:
                break

            if duration_seconds and (time.time() - start_time) >= duration_seconds:
                break

            # Check if out of compute (with small tolerance for floating point)
            if self.state.compute_hours_remaining < 0.01:
                self.state.is_active = False
                break

            # Run cycle
            await self.run_cycle()
            cycles += 1

            # Small delay to avoid tight loop
            await asyncio.sleep(0.1)

        return self.decisions

    async def get_state(self) -> AgentState:
        """Get current agent state.

        Raises:
            ValueError: If state has not been initialized
        """
        await self._update_state()
        if self.state is None:
            raise ValueError("Agent state not initialized")
        return self.state

    def get_decisions(self) -> list:
        """Get all decision records."""
        return self.decisions

    def save_state(self, state_manager: StateManager | None = None) -> str:
        """Save agent state to disk.

        Args:
            state_manager: Optional StateManager instance (creates new one if None)

        Returns:
            Path to saved state file
        """
        if state_manager is None:
            state_manager = StateManager()

        if self.state is None:
            raise ValueError("Cannot save: agent state not initialized")

        saved_path: str = state_manager.save_agent_state(self.agent_id, self.state, self.decisions)
        return saved_path

    @classmethod
    def load_state(
        cls,
        agent_id: str,
        wallet: WalletInterface,
        compute: ComputeInterface,
        marketplace: MarketplaceInterface,
        config: AgentConfig | dict | None = None,
        state_manager: StateManager | None = None,
        dashboard_state: Any | None = None,
    ) -> "AutonomousAgent":
        """Load agent state from disk and create agent instance.

        Args:
            agent_id: Agent identifier to load
            wallet: Wallet implementation (any WalletInterface)
            compute: Compute provider implementation (any ComputeInterface)
            marketplace: Marketplace implementation (any MarketplaceInterface)
            config: Agent configuration - AgentConfig instance or dict
            state_manager: Optional StateManager instance
            dashboard_state: Optional dashboard state for real-time monitoring

        Returns:
            Restored AutonomousAgent instance

        Raises:
            FileNotFoundError: If no saved state exists for agent_id
        """
        if state_manager is None:
            state_manager = StateManager()

        # Load saved state
        saved_data = state_manager.load_agent_state(agent_id)

        # Create agent instance
        agent = cls(wallet, compute, marketplace, config, dashboard_state)
        agent.agent_id = agent_id

        # Restore state
        agent.state = saved_data["state"]

        # Restore decisions
        agent.decisions = saved_data["decisions"]

        return agent

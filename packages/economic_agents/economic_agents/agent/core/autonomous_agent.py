"""Autonomous agent core loop."""

import time
import uuid
from datetime import datetime
from typing import Any, Dict

from economic_agents.agent.core.decision_engine import DecisionEngine
from economic_agents.agent.core.state import AgentState
from economic_agents.company.company_builder import CompanyBuilder
from economic_agents.company.models import Company
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.interfaces.marketplace import TaskSubmission
from economic_agents.monitoring.decision_logger import DecisionLogger


class AutonomousAgent:
    """Primary autonomous agent that operates independently."""

    def __init__(
        self,
        wallet: MockWallet,
        compute: MockCompute,
        marketplace: MockMarketplace,
        config: dict | None = None,
    ):
        """Initialize autonomous agent.

        Args:
            wallet: Wallet implementation
            compute: Compute provider implementation
            marketplace: Marketplace implementation
            config: Agent configuration
        """
        self.wallet = wallet
        self.compute = compute
        self.marketplace = marketplace
        self.config = config or {}
        self.agent_id = str(uuid.uuid4())

        # Initialize components
        self.state = AgentState(
            balance=wallet.get_balance(),
            compute_hours_remaining=compute.get_status().hours_remaining,
            survival_buffer_hours=self.config.get("survival_buffer_hours", 24.0),
        )
        self.decision_engine = DecisionEngine(config)
        self.decision_logger = DecisionLogger()
        self.company_builder = CompanyBuilder(config, self.decision_logger)

        # Tracking
        self.decisions: list = []
        self.company: Company | None = None

    def run_cycle(self) -> Dict[str, Any]:
        """Execute one decision cycle.

        Returns:
            Dict with cycle results and metrics
        """
        # 1. Update state from resources
        self._update_state()

        # 2. Make decision about resource allocation
        allocation = self.decision_engine.decide_allocation(self.state)

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
            task_result = self._do_task_work(allocation.task_work_hours)
            decision_record["task_result"] = task_result

        # 5. Check if should form company
        if not self.state.has_company and self.decision_engine.should_form_company(self.state):
            company_result = self._form_company()
            decision_record["company_formation"] = company_result

        # 6. Company work if allocated and company exists
        if allocation.company_work_hours > 0 and self.state.has_company:
            company_result = self._do_company_work(allocation.company_work_hours)
            decision_record["company_work"] = company_result

        # 7. Update cycle counter
        self.state.cycles_completed += 1
        self.state.last_cycle_at = datetime.now()

        return decision_record

    def _update_state(self):
        """Update agent state from resource providers."""
        self.state.balance = self.wallet.get_balance()
        compute_status = self.compute.get_status()
        self.state.compute_hours_remaining = compute_status.hours_remaining

    def _do_task_work(self, hours: float) -> Dict[str, Any]:
        """Complete marketplace tasks.

        Args:
            hours: Hours to spend on task work

        Returns:
            Dict with task completion results
        """
        # Consume compute time
        if not self.compute.consume_time(hours):
            return {"success": False, "error": "Failed to consume compute time"}

        # Get available tasks
        tasks = self.marketplace.list_available_tasks()
        if not tasks:
            return {"success": False, "error": "No tasks available"}

        # Claim and complete first available task
        task = tasks[0]
        if not self.marketplace.claim_task(task.id):
            return {"success": False, "error": "Failed to claim task"}

        # Submit solution (mock)
        submission = TaskSubmission(
            task_id=task.id, solution="Mock solution implementation", submitted_at=datetime.now(), metadata={}
        )

        submission_id = self.marketplace.submit_solution(submission)

        # Check result
        status = self.marketplace.check_submission_status(submission_id)

        if status.status == "approved":
            # Receive payment
            self.wallet.receive_payment(from_address="marketplace", amount=status.reward_paid, memo=f"Task: {task.title}")
            self.state.tasks_completed += 1
            return {"success": True, "task_id": task.id, "reward": status.reward_paid, "title": task.title}
        else:
            self.state.tasks_failed += 1
            return {"success": False, "task_id": task.id, "feedback": status.feedback}

    def _form_company(self) -> Dict[str, Any]:
        """Form a company with initial capital allocation.

        Returns:
            Dict with company formation results
        """
        # Allocate capital to company (e.g., 30% of current balance)
        capital_allocation = self.state.balance * 0.3
        company_threshold = self.decision_engine.company_threshold

        if capital_allocation < company_threshold * 0.3:
            return {
                "success": False,
                "error": "Insufficient capital for company formation",
            }

        # Determine opportunity based on available tasks
        tasks = self.marketplace.list_available_tasks()
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
        self.wallet.send_payment(
            to_address=f"company_{self.company.id}",
            amount=capital_allocation,
            memo=f"Initial capital for {self.company.name}",
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

    def _do_company_work(self, hours: float) -> Dict[str, Any]:
        """Perform company building work.

        Args:
            hours: Hours to spend on company work

        Returns:
            Dict with company work results
        """
        if not self.company:
            return {"success": False, "error": "No company exists"}

        # Consume compute time
        if not self.compute.consume_time(hours):
            return {"success": False, "error": "Failed to consume compute time"}

        actions = []

        # Develop product if none exists
        if len(self.company.products) == 0:
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

        return {
            "success": True,
            "company_id": self.company.id,
            "actions": actions,
            "stage": self.company.stage,
            "team_size": len(self.company.get_all_sub_agent_ids()),
            "products": len(self.company.products),
        }

    def run(self, duration_seconds: float | None = None, max_cycles: int | None = None) -> list:
        """Run agent for specified duration or number of cycles.

        Args:
            duration_seconds: How long to run (in seconds)
            max_cycles: Maximum number of cycles to run

        Returns:
            List of decision records
        """
        start_time = time.time()
        cycles = 0

        while self.state.is_active:
            # Update state first to get accurate compute status
            self._update_state()

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
            self.run_cycle()
            cycles += 1

            # Small delay to avoid tight loop
            time.sleep(0.1)

        return self.decisions

    def get_state(self) -> AgentState:
        """Get current agent state."""
        self._update_state()
        return self.state

    def get_decisions(self) -> list:
        """Get all decision records."""
        return self.decisions

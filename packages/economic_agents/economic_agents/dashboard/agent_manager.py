"""Agent lifecycle management for dashboard-controlled agents."""

import asyncio
from typing import Any, Dict, Optional

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.dashboard.dependencies import dashboard_state
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


class AgentManager:
    """Manages the lifecycle of dashboard-controlled autonomous agents.

    This singleton class allows the dashboard to start/stop agents and run them
    as background tasks within the same process, ensuring dashboard_state is shared.
    """

    _instance: Optional["AgentManager"] = None
    _lock = asyncio.Lock()
    _initialized: bool

    def __new__(cls) -> "AgentManager":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize agent manager."""
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True
        self.agent: Optional[AutonomousAgent] = None
        self.task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self.is_running = False
        self.config: Dict[str, Any] = {}
        self.cycle_count = 0
        self.max_cycles = 0
        self.should_stop = False

    async def start_agent(
        self,
        mode: str = "survival",
        max_cycles: int = 50,
        initial_balance: float = 100.0,
        initial_compute_hours: float = 100.0,
        compute_cost_per_hour: float = 0.0,
    ) -> dict:
        """Start an autonomous agent with specified configuration.

        Args:
            mode: 'survival' (no company) or 'company' (form company)
            max_cycles: Maximum number of cycles to run
            initial_balance: Starting balance in dollars
            initial_compute_hours: Starting compute hours available
            compute_cost_per_hour: Cost per compute hour

        Returns:
            Status dict with agent_id and configuration

        Raises:
            RuntimeError: If agent is already running
        """
        async with self._lock:
            if self.is_running:
                raise RuntimeError("Agent is already running")

            # Configure based on mode
            if mode == "survival":
                company_threshold = 50000.0  # Very high, won't reach
            elif mode == "company":
                company_threshold = 150.0
            else:
                raise ValueError(f"Invalid mode: {mode}. Must be 'survival' or 'company'")

            # Create agent components
            wallet = MockWallet(initial_balance=initial_balance)
            compute = MockCompute(initial_hours=initial_compute_hours, cost_per_hour=compute_cost_per_hour)
            marketplace = MockMarketplace(seed=42)

            # Create agent
            self.agent = AutonomousAgent(
                wallet=wallet,
                compute=compute,
                marketplace=marketplace,
                config={
                    "mode": mode,
                    "survival_buffer_hours": 20.0,
                    "company_threshold": company_threshold,
                },
                dashboard_state=dashboard_state,
            )

            # Store configuration
            self.config = {
                "mode": mode,
                "max_cycles": max_cycles,
                "initial_balance": initial_balance,
                "initial_compute_hours": initial_compute_hours,
                "compute_cost_per_hour": compute_cost_per_hour,
                "company_threshold": company_threshold,
            }
            self.max_cycles = max_cycles
            self.cycle_count = 0
            self.should_stop = False
            self.is_running = True

            # Start background task
            self.task = asyncio.create_task(self._run_agent_loop())

            # Yield control to allow task to start
            await asyncio.sleep(0)

            return {
                "status": "started",
                "agent_id": self.agent.agent_id,
                "mode": mode,
                "max_cycles": max_cycles,
                "initial_balance": initial_balance,
            }

    async def stop_agent(self) -> dict:
        """Stop the running agent gracefully.

        Returns:
            Status dict with final statistics
        """
        async with self._lock:
            if not self.is_running:
                return {"status": "not_running"}

            # Signal stop
            self.should_stop = True

        # Wait for task to complete (outside lock)
        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=5.0)
            except asyncio.TimeoutError:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass

        # Get final stats
        final_stats = {
            "status": "stopped",
            "cycles_completed": self.cycle_count,
        }

        if self.agent:
            final_stats.update(
                {
                    "final_balance": self.agent.state.balance,
                    "compute_remaining": self.agent.state.compute_hours_remaining,
                    "tasks_completed": self.agent.state.tasks_completed,
                    "company_formed": self.agent.state.has_company,
                }
            )

        self.is_running = False
        return final_stats

    async def get_status(self) -> dict:
        """Get current agent status.

        Returns:
            Status dict with running state and progress
        """
        status = {
            "is_running": self.is_running,
            "cycle_count": self.cycle_count,
            "max_cycles": self.max_cycles,
            "config": self.config,
        }

        if self.agent:
            status.update(
                {
                    "agent_id": self.agent.agent_id,
                    "balance": self.agent.state.balance,
                    "compute_hours": self.agent.state.compute_hours_remaining,
                    "has_company": self.agent.state.has_company,
                    "tasks_completed": self.agent.state.tasks_completed,
                }
            )

        return status

    async def _run_agent_loop(self) -> None:
        """Run agent cycles in background task."""
        try:
            while self.cycle_count < self.max_cycles and not self.should_stop:
                # Run one cycle (in executor to avoid blocking event loop)
                if self.agent is not None:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.agent.run_cycle)
                    self.cycle_count += 1

                    # Check if agent ran out of resources
                    if self.agent.state.balance <= 0 or self.agent.state.compute_hours_remaining <= 0:
                        break

                    # Small delay to prevent tight loop
                    await asyncio.sleep(0.5)
                else:
                    break

        except Exception:
            # Silently stop on any error
            pass
        finally:
            self.is_running = False


# Global singleton instance
agent_manager = AgentManager()

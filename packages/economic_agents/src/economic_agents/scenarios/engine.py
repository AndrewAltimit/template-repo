"""Scenario engine for managing and running predefined scenarios."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.reports.extractors import extract_agent_data
from economic_agents.scenarios.models import Scenario, ScenarioConfig, ScenarioResult
from economic_agents.scenarios.predefined import (
    COMPANY_FORMATION_SCENARIO,
    INVESTMENT_SEEKING_SCENARIO,
    MULTI_DAY_SCENARIO,
    SURVIVAL_MODE_SCENARIO,
)


class ScenarioEngine:
    """Manages predefined scenarios for autonomous agents."""

    def __init__(self, scenarios_dir: str | None = None):
        """Initialize scenario engine.

        Args:
            scenarios_dir: Directory to store scenario results
        """
        self.scenarios_dir = Path(scenarios_dir) if scenarios_dir else Path("./logs/scenarios")
        self.scenarios_dir.mkdir(parents=True, exist_ok=True)

        # Register predefined scenarios
        self.scenarios: Dict[str, ScenarioConfig] = {
            "survival": SURVIVAL_MODE_SCENARIO,
            "company_formation": COMPANY_FORMATION_SCENARIO,
            "investment_seeking": INVESTMENT_SEEKING_SCENARIO,
            "multi_day": MULTI_DAY_SCENARIO,
        }

    def load_scenario(self, scenario_name: str) -> Scenario:
        """Load a predefined scenario.

        Args:
            scenario_name: Name of scenario to load

        Returns:
            Scenario object

        Raises:
            ValueError: If scenario not found
        """
        if scenario_name not in self.scenarios:
            available = ", ".join(self.scenarios.keys())
            raise ValueError(f"Scenario '{scenario_name}' not found. Available: {available}")

        config = self.scenarios[scenario_name]
        return Scenario(config)

    def register_scenario(self, scenario_config: ScenarioConfig):
        """Register a custom scenario.

        Args:
            scenario_config: Scenario configuration to register
        """
        self.scenarios[scenario_config.name] = scenario_config

    def run_scenario(self, scenario_name: str, agent_runner_func: Any = None) -> ScenarioResult:
        """Run a scenario.

        Args:
            scenario_name: Name of scenario to run
            agent_runner_func: Optional function to run agent (for testing)

        Returns:
            ScenarioResult with outcomes
        """
        scenario = self.load_scenario(scenario_name)
        start_time = datetime.now()

        # Setup scenario
        env_config = scenario.setup()

        # Run agent (in real implementation, this would run the actual agent)
        # For now, we'll simulate the outcomes
        agent_data = self._simulate_agent_run(env_config, scenario.config, agent_runner_func)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60

        # Validate outcomes
        success, achieved, missed = scenario.validate_outcome(agent_data)

        # Calculate metrics
        metrics = {
            "final_balance": agent_data.get("balance", 0),
            "tasks_completed": agent_data.get("tasks_completed", 0),
            "tasks_failed": agent_data.get("tasks_failed", 0),
            "success_rate": agent_data.get("success_rate", 0),
            "total_earnings": agent_data.get("total_earnings", 0),
            "total_expenses": agent_data.get("total_expenses", 0),
        }

        result = ScenarioResult(
            scenario_name=scenario_name,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            success=success,
            outcomes_achieved=achieved,
            outcomes_missed=missed,
            agent_data=agent_data,
            metrics=metrics,
        )

        # Save result
        self._save_result(result)

        return result

    def list_scenarios(self) -> Dict[str, str]:
        """List available scenarios.

        Returns:
            Dictionary of scenario names to descriptions
        """
        return {name: config.description for name, config in self.scenarios.items()}

    def get_scenario_config(self, scenario_name: str) -> ScenarioConfig:
        """Get scenario configuration.

        Args:
            scenario_name: Name of scenario

        Returns:
            ScenarioConfig

        Raises:
            ValueError: If scenario not found
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Scenario '{scenario_name}' not found")

        return self.scenarios[scenario_name]

    def _run_real_agent(self, env_config: Dict[str, Any], scenario_config: ScenarioConfig) -> Dict[str, Any]:
        """Run a real autonomous agent for the scenario.

        Args:
            env_config: Environment configuration
            scenario_config: Scenario configuration

        Returns:
            Agent state data extracted from the run
        """
        # Create mock implementations
        wallet = MockWallet(initial_balance=env_config["initial_balance"])
        compute = MockCompute(
            initial_hours=env_config["initial_compute_hours"],
            cost_per_hour=0.0,  # Free for scenarios
        )
        marketplace = MockMarketplace()

        # Create agent config from scenario
        agent_config = {
            "mode": env_config["mode"],
            "company_threshold": 150.0,
            "survival_buffer_hours": 20.0,
            "personality": "balanced",
        }

        # Create and run agent
        agent = AutonomousAgent(
            wallet=wallet,
            compute=compute,
            marketplace=marketplace,
            config=agent_config,
        )

        # Initialize agent asynchronously
        asyncio.run(agent.initialize())

        # Run agent for specified duration
        max_cycles = int(scenario_config.duration_minutes / 5)  # Assume 5 min per cycle
        asyncio.run(agent.run(max_cycles=max_cycles))

        # Extract agent data using the extractor helper
        agent_data: Dict[str, Any] = extract_agent_data(agent)

        return agent_data

    def _simulate_agent_run(
        self, env_config: Dict[str, Any], scenario_config: ScenarioConfig, runner_func: Callable | None = None
    ) -> Dict[str, Any]:
        """Run agent for scenario (real or custom runner).

        Args:
            env_config: Environment configuration
            scenario_config: Scenario configuration
            runner_func: Optional custom runner function

        Returns:
            Agent state data
        """
        if runner_func:
            # Call provided runner function
            return runner_func(env_config, scenario_config)  # type: ignore[no-any-return]

        # Run real agent
        return self._run_real_agent(env_config, scenario_config)

    def _save_result(self, result: ScenarioResult):
        """Save scenario result to file.

        Args:
            result: ScenarioResult to save
        """
        filename = f"{result.scenario_name}_{result.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.scenarios_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)

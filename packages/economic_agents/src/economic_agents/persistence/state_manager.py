"""State persistence for agents and registry."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from economic_agents.agent.core.state import AgentState
from economic_agents.company.models import Company
from economic_agents.investment.company_registry import CompanyRegistry
from economic_agents.investment.models import Investment, InvestmentProposal


class StateManager:
    """Manages persistence of agent state and company registry."""

    def __init__(self, base_dir: str = ".economic_agents"):
        """Initialize state manager.

        Args:
            base_dir: Base directory for persisted state
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

        self.agent_state_dir = self.base_dir / "agents"
        self.agent_state_dir.mkdir(exist_ok=True)

        self.registry_dir = self.base_dir / "registry"
        self.registry_dir.mkdir(exist_ok=True)

    def save_agent_state(self, agent_id: str, state: AgentState, decisions: list) -> str:
        """Save agent state to disk.

        Args:
            agent_id: Agent identifier
            state: Agent state to save
            decisions: List of decision records

        Returns:
            Path to saved state file
        """
        state_data = {
            "agent_id": agent_id,
            "state": state.to_dict(),
            "decisions": self._serialize_decisions(decisions),
            "saved_at": datetime.now().isoformat(),
        }

        state_file = self.agent_state_dir / f"{agent_id}.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

        return str(state_file)

    def load_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """Load agent state from disk.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict containing agent state and decisions

        Raises:
            FileNotFoundError: If state file doesn't exist
        """
        state_file = self.agent_state_dir / f"{agent_id}.json"
        if not state_file.exists():
            raise FileNotFoundError(f"No saved state found for agent {agent_id}")

        with open(state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)

        # Deserialize state
        state_dict = state_data["state"]
        state = AgentState(
            balance=state_dict["balance"],
            compute_hours_remaining=state_dict["compute_hours_remaining"],
            survival_buffer_hours=state_dict["survival_buffer_hours"],
        )

        # Restore state fields
        state.is_active = state_dict.get("is_active", True)
        state.has_company = state_dict.get("has_company", False)
        state.company_id = state_dict.get("company_id")
        state.tasks_completed = state_dict.get("tasks_completed", 0)
        state.tasks_failed = state_dict.get("tasks_failed", 0)
        state.cycles_completed = state_dict.get("cycles_completed", 0)

        # Restore last_cycle_at if exists
        if state_dict.get("last_cycle_at"):
            state.last_cycle_at = datetime.fromisoformat(state_dict["last_cycle_at"])

        return {
            "state": state,
            "decisions": self._deserialize_decisions(state_data["decisions"]),
            "saved_at": state_data["saved_at"],
        }

    def save_registry(self, registry: CompanyRegistry) -> str:
        """Save company registry to disk.

        Args:
            registry: Company registry to save

        Returns:
            Path to saved registry file
        """
        registry_data = {
            "companies": {company_id: self._serialize_company(company) for company_id, company in registry.companies.items()},
            "proposals": {
                proposal_id: self._serialize_proposal(proposal) for proposal_id, proposal in registry.proposals.items()
            },
            "investments": {
                investment_id: self._serialize_investment(investment)
                for investment_id, investment in registry.investments.items()
            },
            "company_investments": registry.company_investments,
            "company_proposals": registry.company_proposals,
            "saved_at": datetime.now().isoformat(),
        }

        registry_file = self.registry_dir / "registry.json"
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, indent=2)

        return str(registry_file)

    def load_registry(self) -> CompanyRegistry:
        """Load company registry from disk.

        Returns:
            Loaded CompanyRegistry

        Raises:
            FileNotFoundError: If registry file doesn't exist
        """
        registry_file = self.registry_dir / "registry.json"
        if not registry_file.exists():
            raise FileNotFoundError("No saved registry found")

        with open(registry_file, "r", encoding="utf-8") as f:
            registry_data = json.load(f)

        # Create new registry
        registry = CompanyRegistry()

        # Restore companies (simplified - full deserialization would need Company.from_dict)
        # For now, we'll store the raw data and log that companies need to be re-registered
        registry.companies = {}  # Companies would need full deserialization
        registry.proposals = {}  # Proposals would need full deserialization
        registry.investments = {}  # Investments would need full deserialization

        registry.company_investments = registry_data.get("company_investments", {})
        registry.company_proposals = registry_data.get("company_proposals", {})

        return registry

    def _serialize_decisions(self, decisions: list) -> list:
        """Serialize decision records for JSON storage."""
        serialized = []
        for decision in decisions:
            serialized_decision: Dict[str, Any] = {}
            for key, value in decision.items():
                if isinstance(value, datetime):
                    serialized_decision[key] = value.isoformat()
                elif isinstance(value, dict):
                    serialized_decision[key] = self._serialize_dict(value)
                else:
                    serialized_decision[key] = value
            serialized.append(serialized_decision)
        return serialized

    def _deserialize_decisions(self, decisions: list) -> list:
        """Deserialize decision records from JSON storage."""
        deserialized = []
        for decision in decisions:
            deserialized_decision = {}
            for key, value in decision.items():
                if key == "timestamp" and isinstance(value, str):
                    deserialized_decision[key] = datetime.fromisoformat(value)
                else:
                    deserialized_decision[key] = value
            deserialized.append(deserialized_decision)
        return deserialized

    def _serialize_dict(self, data: dict) -> Dict[str, Any]:
        """Recursively serialize dict for JSON storage."""
        serialized: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_dict(value)
            else:
                serialized[key] = value
        return serialized

    def _serialize_company(self, company: Company) -> Dict[str, Any]:
        """Serialize company for JSON storage."""
        result: Dict[str, Any] = company.to_dict()
        return result

    def _serialize_proposal(self, proposal: InvestmentProposal) -> Dict[str, Any]:
        """Serialize investment proposal for JSON storage."""
        return {
            "id": proposal.id,
            "company_id": proposal.company_id,
            "stage": proposal.stage.value,
            "amount_requested": proposal.amount_requested,
            "equity_offered": proposal.equity_offered,
            "valuation": proposal.valuation,
            "use_of_funds": proposal.use_of_funds,
            "milestones": proposal.milestones,
            "risks": proposal.risks,
            "created_at": proposal.created_at.isoformat(),
        }

    def _serialize_investment(self, investment: Investment) -> Dict[str, Any]:
        """Serialize investment for JSON storage."""
        return {
            "id": investment.id,
            "company_id": investment.company_id,
            "investor_id": investment.investor_id,
            "amount": investment.amount,
            "equity_percentage": investment.equity_percentage,
            "valuation": investment.valuation,
            "stage": investment.stage.value,
            "invested_at": investment.invested_at.isoformat(),
        }

    def list_saved_agents(self) -> list:
        """List all saved agent IDs.

        Returns:
            List of agent IDs with saved state
        """
        return [f.stem for f in self.agent_state_dir.glob("*.json")]

    def registry_exists(self) -> bool:
        """Check if a saved registry exists.

        Returns:
            True if registry file exists
        """
        return (self.registry_dir / "registry.json").exists()

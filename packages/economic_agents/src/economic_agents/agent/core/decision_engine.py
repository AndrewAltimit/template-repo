"""Decision engine for autonomous agent choices."""

from dataclasses import dataclass

from economic_agents.agent.core.state import AgentState


@dataclass
class ResourceAllocation:
    """Represents how agent allocates compute resources."""

    task_work_hours: float
    company_work_hours: float
    reasoning: str
    confidence: float


class DecisionEngine:
    """Makes autonomous decisions based on agent state."""

    def __init__(self, config: dict | None = None):
        """Initialize decision engine.

        Args:
            config: Configuration dict with decision parameters
        """
        self.config = config or {}
        self.survival_buffer = self.config.get("survival_buffer_hours", 24.0)
        self.company_threshold = self.config.get("company_threshold", 100.0)
        self.personality = self.config.get("personality", "balanced")  # risk_averse, balanced, aggressive

    def decide_allocation(self, state: AgentState) -> ResourceAllocation:
        """Decides how to allocate compute hours between task work and company work.

        Args:
            state: Current agent state

        Returns:
            ResourceAllocation with hours allocated to each activity
        """
        # If survival is at risk, allocate everything to tasks
        if state.is_survival_at_risk():
            return ResourceAllocation(
                task_work_hours=min(state.compute_hours_remaining, 1.0),
                company_work_hours=0.0,
                reasoning="Survival at risk - focusing on task completion for immediate revenue",
                confidence=0.9,
            )

        # If no company and insufficient capital, focus on survival
        if not state.has_company and not state.has_surplus_capital(self.company_threshold):
            return ResourceAllocation(
                task_work_hours=min(state.compute_hours_remaining, 1.0),
                company_work_hours=0.0,
                reasoning="Building capital reserves before company formation",
                confidence=0.8,
            )

        # If has surplus but no company, consider starting one
        if not state.has_company and state.has_surplus_capital(self.company_threshold):
            # For now, still focus on survival (company building not implemented yet)
            return ResourceAllocation(
                task_work_hours=min(state.compute_hours_remaining, 0.8),
                company_work_hours=0.0,
                reasoning="Sufficient capital but company formation not yet implemented",
                confidence=0.7,
            )

        # Default: balanced allocation
        available_hours = state.compute_hours_remaining - self.survival_buffer
        if available_hours <= 0:
            task_hours = min(state.compute_hours_remaining, 1.0)
            company_hours = 0.0
        else:
            # Split based on personality
            if self.personality == "risk_averse":
                task_hours = min(available_hours * 0.8, 1.0)
                company_hours = min(available_hours * 0.2, 0.5)
            elif self.personality == "aggressive":
                task_hours = min(available_hours * 0.4, 0.5)
                company_hours = min(available_hours * 0.6, 1.0)
            else:  # balanced
                task_hours = min(available_hours * 0.6, 0.8)
                company_hours = min(available_hours * 0.4, 0.8)

        return ResourceAllocation(
            task_work_hours=task_hours,
            company_work_hours=company_hours,
            reasoning=f"Balanced allocation based on {self.personality} personality",
            confidence=0.75,
        )

    def should_form_company(self, state: AgentState) -> bool:
        """Decides if it's time to create a company.

        Args:
            state: Current agent state

        Returns:
            True if agent should form a company
        """
        if state.has_company:
            return False

        if not state.has_surplus_capital(self.company_threshold):
            return False

        if state.is_survival_at_risk():
            return False

        return True

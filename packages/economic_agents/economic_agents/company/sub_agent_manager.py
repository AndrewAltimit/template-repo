"""Sub-agent manager for creating and coordinating sub-agents."""

import uuid
from typing import Any, Dict, List

from economic_agents.sub_agents.base_agent import SubAgent
from economic_agents.sub_agents.board_member import BoardMember
from economic_agents.sub_agents.executive import Executive
from economic_agents.sub_agents.individual_contributor import IndividualContributor
from economic_agents.sub_agents.subject_matter_expert import SubjectMatterExpert


class SubAgentManager:
    """Creates and manages sub-agents with specific roles."""

    def __init__(self, config: dict | None = None):
        """Initialize sub-agent manager.

        Args:
            config: Configuration for sub-agent creation
        """
        self.config = config or {}
        self.sub_agents: Dict[str, SubAgent] = {}

    def create_sub_agent(self, role: str, specialization: str, company_id: str | None = None, **kwargs) -> SubAgent:
        """Create a sub-agent with specified role.

        Args:
            role: Type of sub-agent ("board_member", "executive", "sme", "ic")
            specialization: Area of expertise
            company_id: Company ID to associate with
            **kwargs: Additional role-specific parameters

        Returns:
            Created sub-agent
        """
        agent_id = str(uuid.uuid4())

        if role == "board_member":
            agent = BoardMember(agent_id=agent_id, specialization=specialization)
        elif role == "executive":
            role_title = kwargs.get("role_title", "Executive")
            agent = Executive(agent_id=agent_id, role_title=role_title, specialization=specialization)
        elif role == "sme":
            agent = SubjectMatterExpert(agent_id=agent_id, specialization=specialization)
        elif role == "ic":
            agent = IndividualContributor(agent_id=agent_id, specialization=specialization)
        else:
            raise ValueError(f"Unknown role: {role}")

        agent.company_id = company_id
        self.sub_agents[agent_id] = agent

        return agent

    def create_initial_team(self, company_id: str) -> Dict[str, List[SubAgent]]:
        """Create initial team for a new company.

        Args:
            company_id: Company ID

        Returns:
            Dictionary with categorized sub-agents
        """
        team: Dict[str, List[SubAgent]] = {
            "board": [],
            "executives": [],
            "employees": [],
        }

        # Create board members
        board_chair = self.create_sub_agent(role="board_member", specialization="governance", company_id=company_id)
        board_finance = self.create_sub_agent(role="board_member", specialization="finance", company_id=company_id)
        team["board"] = [board_chair, board_finance]

        # Create executives
        ceo = self.create_sub_agent(
            role="executive",
            specialization="leadership",
            company_id=company_id,
            role_title="CEO",
        )
        team["executives"] = [ceo]

        return team

    def create_expanded_team(self, company_id: str, include_technical: bool = True) -> Dict[str, List[SubAgent]]:
        """Create expanded team with technical roles.

        Args:
            company_id: Company ID
            include_technical: Whether to include technical roles

        Returns:
            Dictionary with categorized sub-agents
        """
        team = self.create_initial_team(company_id)

        # Add CTO
        cto = self.create_sub_agent(
            role="executive",
            specialization="technology",
            company_id=company_id,
            role_title="CTO",
        )
        team["executives"].append(cto)

        if include_technical:
            # Add technical SMEs
            tech_sme = self.create_sub_agent(
                role="sme",
                specialization="software-architecture",
                company_id=company_id,
            )
            team["employees"] = [tech_sme]

            # Add ICs
            backend_dev = self.create_sub_agent(
                role="ic",
                specialization="backend-dev",
                company_id=company_id,
            )
            team["employees"].append(backend_dev)

        return team

    def get_sub_agent(self, agent_id: str) -> SubAgent | None:
        """Get sub-agent by ID.

        Args:
            agent_id: Sub-agent ID

        Returns:
            SubAgent or None if not found
        """
        return self.sub_agents.get(agent_id)

    def coordinate_sub_agents(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Coordinate multiple sub-agents on a shared task.

        Args:
            task: Task requiring coordination

        Returns:
            List of agent actions/contributions
        """
        actions = []

        task_type = task.get("type", "general")
        involved_roles = task.get("roles", [])

        # Get relevant sub-agents
        relevant_agents = [agent for agent in self.sub_agents.values() if not involved_roles or agent.role in involved_roles]

        # Each agent contributes based on their role
        for agent in relevant_agents[:5]:  # Limit to 5 agents for coordination
            if agent.role == "board_member":
                result = agent.make_decision({"decision_type": task_type})
            elif agent.role == "executive":
                result = agent.make_decision({"context": task})
            else:
                result = agent.complete_task(task)

            actions.append(
                {
                    "agent_id": agent.id,
                    "role": agent.role,
                    "specialization": agent.specialization,
                    "action": result,
                }
            )

        return actions

    def get_team_summary(self) -> Dict[str, Any]:
        """Get summary of all sub-agents.

        Returns:
            Team summary statistics
        """
        by_role: Dict[str, List[Dict[str, Any]]] = {}
        for agent in self.sub_agents.values():
            role = agent.role
            if role not in by_role:
                by_role[role] = []
            by_role[role].append(agent.to_dict())

        return {
            "total_agents": len(self.sub_agents),
            "by_role": by_role,
            "total_tasks_completed": sum(a.tasks_completed for a in self.sub_agents.values()),
            "total_decisions_made": sum(a.decisions_made for a in self.sub_agents.values()),
        }

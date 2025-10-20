"""Individual contributor sub-agent for task execution."""

from typing import Any, Dict

from economic_agents.sub_agents.base_agent import SubAgent


class IndividualContributor(SubAgent):
    """Individual contributor responsible for hands-on task execution."""

    def __init__(self, agent_id: str, specialization: str):
        """Initialize individual contributor.

        Args:
            agent_id: Unique identifier
            specialization: Skill area (e.g., "backend-dev", "frontend-dev", "qa", "devops")
        """
        super().__init__(
            id=agent_id,
            role="ic",
            specialization=specialization,
        )

    def complete_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Complete an assigned development task.

        Args:
            task: Task specification

        Returns:
            Task completion result
        """
        self.tasks_completed += 1

        task_type = task.get("type", "generic")
        complexity = task.get("complexity", "medium")

        # Simulate task completion based on specialization
        if "dev" in self.specialization.lower():
            return {
                "status": "completed",
                "result": f"Implemented {task_type} feature",
                "code_changes": f"{complexity}_complexity_changes.py",
                "tests_added": True,
                "quality_score": 0.85,
            }
        elif "qa" in self.specialization.lower():
            return {
                "status": "completed",
                "result": f"Tested {task_type} feature",
                "bugs_found": 2 if complexity == "high" else 0,
                "test_coverage": 0.9,
                "quality_score": 0.88,
            }
        elif "devops" in self.specialization.lower():
            return {
                "status": "completed",
                "result": f"Deployed {task_type} infrastructure",
                "services_deployed": 3,
                "uptime": 0.99,
                "quality_score": 0.87,
            }
        else:
            return {
                "status": "completed",
                "result": f"Completed {task_type} task",
                "quality_score": 0.8,
            }

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make implementation decision.

        Args:
            context: Decision context

        Returns:
            Implementation decision
        """
        self.decisions_made += 1

        return {
            "decision": "implement",
            "reasoning": f"Using {self.specialization} best practices",
            "implementation_approach": "Incremental development with testing",
            "confidence": 0.75,
        }

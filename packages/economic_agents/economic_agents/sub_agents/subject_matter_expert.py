"""Subject matter expert sub-agent for specialized knowledge."""

from typing import Any, Dict

from economic_agents.sub_agents.base_agent import SubAgent


class SubjectMatterExpert(SubAgent):
    """Subject matter expert providing specialized knowledge and guidance."""

    def __init__(self, agent_id: str, specialization: str):
        """Initialize subject matter expert.

        Args:
            agent_id: Unique identifier
            specialization: Domain expertise (e.g., "machine-learning", "security", "scaling")
        """
        super().__init__(
            id=agent_id,
            role="sme",
            specialization=specialization,
        )

    def provide_expertise(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Provide expert advice on a question.

        Args:
            question: Question requiring expert input
            context: Additional context

        Returns:
            Expert advice
        """
        self.tasks_completed += 1

        # Provide domain-specific advice
        if "security" in self.specialization.lower():
            return {
                "advice": "Implement authentication, encryption, and regular security audits",
                "priority": "high",
                "references": ["OWASP Top 10", "Security best practices"],
                "confidence": 0.9,
            }
        elif "scaling" in self.specialization.lower() or "performance" in self.specialization.lower():
            return {
                "advice": "Use caching, load balancing, and horizontal scaling",
                "priority": "medium",
                "references": ["Scalability patterns", "Performance optimization"],
                "confidence": 0.85,
            }
        elif "machine-learning" in self.specialization.lower() or "ai" in self.specialization.lower():
            return {
                "advice": "Start with established models, focus on data quality",
                "priority": "high",
                "references": ["ML best practices", "Model evaluation"],
                "confidence": 0.8,
            }
        else:
            return {
                "advice": f"Apply {self.specialization} best practices",
                "priority": "medium",
                "references": [f"{self.specialization} documentation"],
                "confidence": 0.7,
            }

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make technical recommendation.

        Args:
            context: Decision context

        Returns:
            Technical recommendation
        """
        self.decisions_made += 1

        return {
            "decision": "recommend_approach",
            "reasoning": f"Based on {self.specialization} expertise",
            "approach": f"Follow {self.specialization} industry standards",
            "confidence": 0.8,
        }

"""Board member sub-agent for governance decisions."""

from typing import Any, Dict

from economic_agents.sub_agents.base_agent import SubAgent


class BoardMember(SubAgent):
    """Board member responsible for strategic oversight and governance."""

    def __init__(self, agent_id: str, specialization: str = "governance"):
        """Initialize board member.

        Args:
            agent_id: Unique identifier
            specialization: Area of expertise (e.g., "governance", "finance", "operations")
        """
        super().__init__(
            id=agent_id,
            role="board_member",
            specialization=specialization,
        )

    def review_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Review and approve/reject a major company decision.

        Args:
            decision: Decision to review

        Returns:
            Approval result with feedback
        """
        self.decisions_made += 1

        # Simple approval logic based on decision type
        decision_type = decision.get("type", "unknown")
        risk_level = decision.get("risk_level", "medium")

        approved = True
        reasoning = f"Board member ({self.specialization}) reviewed {decision_type} decision"

        if risk_level == "high":
            approved = decision.get("expected_roi", 0) > 0.5
            reasoning += " - High risk requires strong ROI justification"

        return {
            "approved": approved,
            "reasoning": reasoning,
            "conditions": [] if approved else ["Requires additional risk mitigation"],
            "confidence": 0.8,
        }

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make strategic governance decision.

        Args:
            context: Context for decision

        Returns:
            Strategic decision
        """
        self.decisions_made += 1

        decision_needed = context.get("decision_type", "general")

        if decision_needed == "company_formation":
            return {
                "decision": "approve",
                "reasoning": "Company formation aligns with strategic objectives",
                "confidence": 0.85,
            }
        elif decision_needed == "hire_executive":
            return {
                "decision": "approve",
                "reasoning": "Executive hire necessary for company growth",
                "confidence": 0.8,
            }
        else:
            return {
                "decision": "defer",
                "reasoning": f"Insufficient context for {decision_needed} decision",
                "confidence": 0.6,
            }

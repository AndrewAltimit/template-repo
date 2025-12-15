"""Base class for all sub-agents."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class SubAgent:
    """Base class for all sub-agents with specific roles."""

    id: str
    role: str  # "board_member", "executive", "sme", "ic"
    specialization: str
    created_at: datetime = field(default_factory=datetime.now)
    company_id: str | None = None

    # Performance tracking
    tasks_completed: int = 0
    decisions_made: int = 0
    contributions: List[Dict[str, Any]] = field(default_factory=list)

    def make_decision(self, _context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a decision based on context.

        Args:
            _context: Contextual information for decision

        Returns:
            Decision result with reasoning
        """
        self.decisions_made += 1
        return {
            "decision": "pending",
            "reasoning": "Base implementation - override in subclass",
            "confidence": 0.5,
        }

    def complete_task(self, _task: Dict[str, Any]) -> Dict[str, Any]:
        """Complete an assigned task.

        Args:
            _task: Task specification

        Returns:
            Task result
        """
        self.tasks_completed += 1
        return {"status": "completed", "result": "Base implementation - override in subclass"}

    def to_dict(self) -> dict:
        """Convert sub-agent to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "specialization": self.specialization,
            "company_id": self.company_id,
            "tasks_completed": self.tasks_completed,
            "decisions_made": self.decisions_made,
            "created_at": self.created_at.isoformat(),
        }

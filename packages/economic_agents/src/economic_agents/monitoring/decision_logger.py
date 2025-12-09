"""Decision logger for tracking autonomous choices."""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, List


@dataclass
class Decision:
    """Represents a single autonomous decision."""

    id: str
    timestamp: datetime
    decision_type: str
    decision: str
    reasoning: str
    context: dict
    outcome: str | None = None
    confidence: float = 0.0


class DecisionLogger:
    """Logs all autonomous decisions with full context."""

    def __init__(self, log_dir: str | None = None):
        """Initialize decision logger.

        Args:
            log_dir: Directory to store decision logs
        """
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/decisions")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.decisions: List[Decision] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def log_decision(
        self,
        decision_type: str,
        decision: str,
        reasoning: str,
        context: dict,
        confidence: float = 0.0,
    ) -> Decision:
        """Log a decision with full context.

        Args:
            decision_type: Type of decision (e.g., "resource_allocation", "task_selection")
            decision: What was decided
            reasoning: Why this decision was made
            context: State at decision time
            confidence: Confidence score for the decision

        Returns:
            Decision object
        """
        decision_obj = Decision(
            id=f"{self.session_id}_{len(self.decisions):04d}",
            timestamp=datetime.now(),
            decision_type=decision_type,
            decision=decision,
            reasoning=reasoning,
            context=context,
            confidence=confidence,
        )

        self.decisions.append(decision_obj)
        self._save_to_file(decision_obj)

        return decision_obj

    def log_cycle(self, state: dict, strategy: dict, allocation: Any):
        """Log a complete agent cycle.

        Args:
            state: Agent state at decision time
            strategy: Strategic plan
            allocation: Resource allocation decision
        """
        self.log_decision(
            decision_type="resource_allocation",
            decision=f"Task work: {allocation.task_work_hours}h, Company work: {allocation.company_work_hours}h",
            reasoning=allocation.reasoning,
            context={"state": state, "strategy": strategy},
            confidence=allocation.confidence,
        )

    def update_outcome(self, decision_id: str, outcome: str):
        """Update decision outcome.

        Args:
            decision_id: Decision to update
            outcome: What actually happened
        """
        for decision in self.decisions:
            if decision.id == decision_id:
                decision.outcome = outcome
                break

    def get_decision_history(self, filters: dict | None = None) -> List[Decision]:
        """Retrieve decisions with optional filtering.

        Args:
            filters: Optional filters (type, time range, etc.)

        Returns:
            List of decisions matching filters
        """
        if not filters:
            return self.decisions

        filtered = self.decisions

        if "type" in filters:
            filtered = [d for d in filtered if d.decision_type == filters["type"]]

        if "min_confidence" in filters:
            filtered = [d for d in filtered if d.confidence >= filters["min_confidence"]]

        return filtered

    def _save_to_file(self, decision: Decision):
        """Save decision to file for persistence."""
        log_file = self.log_dir / f"session_{self.session_id}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            record = {
                "id": decision.id,
                "timestamp": decision.timestamp.isoformat(),
                "type": decision.decision_type,
                "decision": decision.decision,
                "reasoning": decision.reasoning,
                "context": decision.context,
                "outcome": decision.outcome,
                "confidence": decision.confidence,
            }
            f.write(json.dumps(record) + "\n")

    def export_to_json(self, filepath: str):
        """Export all decisions to JSON file.

        Args:
            filepath: Path to output file
        """
        data = [
            {
                "id": d.id,
                "timestamp": d.timestamp.isoformat(),
                "type": d.decision_type,
                "decision": d.decision,
                "reasoning": d.reasoning,
                "context": d.context,
                "outcome": d.outcome,
                "confidence": d.confidence,
            }
            for d in self.decisions
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

"""Marketplace interface for task discovery and completion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass
class Task:
    """Represents a task available in the marketplace."""

    id: str
    title: str
    description: str
    requirements: dict[str, Any]
    reward: float
    deadline: datetime
    difficulty: Literal["easy", "medium", "hard"]
    category: str  # "coding", "data-analysis", "research", etc.


@dataclass
class TaskSubmission:
    """Represents a completed task submission."""

    task_id: str
    solution: str
    submitted_at: datetime
    metadata: dict[str, Any]


@dataclass
class SubmissionStatus:
    """Status of a submitted task."""

    submission_id: str
    status: Literal["pending", "approved", "rejected"]
    feedback: str
    reward_paid: float
    reviewed_at: datetime | None


class MarketplaceInterface(ABC):
    """Abstract interface for marketplace interactions."""

    @abstractmethod
    async def list_available_tasks(self) -> list[Task]:
        """Returns tasks agent can work on."""

    @abstractmethod
    async def claim_task(self, task_id: str) -> bool:
        """Claims task for work."""

    @abstractmethod
    async def submit_solution(self, submission: TaskSubmission) -> str:
        """Submits completed work, returns submission_id."""

    @abstractmethod
    async def check_submission_status(self, submission_id: str) -> SubmissionStatus:
        """Checks if submission was approved/rejected."""

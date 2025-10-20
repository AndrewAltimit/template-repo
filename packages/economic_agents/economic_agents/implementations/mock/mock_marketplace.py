"""Mock marketplace implementation for simulation."""

import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List

from economic_agents.interfaces.marketplace import (
    MarketplaceInterface,
    SubmissionStatus,
    Task,
    TaskSubmission,
)


class MockMarketplace(MarketplaceInterface):
    """Mock marketplace that generates diverse tasks and simulates review process."""

    def __init__(self, seed: int | None = None):
        """Initialize mock marketplace.

        Args:
            seed: Random seed for reproducible task generation
        """
        self.rng = random.Random(seed)
        self.tasks: Dict[str, Task] = {}
        self.claimed_tasks: set = set()
        self.submissions: Dict[str, SubmissionStatus] = {}
        self._generate_initial_tasks()

    def _generate_initial_tasks(self, count: int = 10):
        """Generate initial set of available tasks."""
        task_templates = [
            {
                "title": "Data Analysis: Customer Churn Prediction",
                "description": "Analyze customer data and build a churn prediction model",
                "category": "data-analysis",
                "difficulty": "medium",
                "reward": 50.0,
            },
            {
                "title": "Code Review: Python REST API",
                "description": "Review and provide feedback on a Python Flask REST API implementation",
                "category": "coding",
                "difficulty": "easy",
                "reward": 25.0,
            },
            {
                "title": "Research: Market Analysis for SaaS Product",
                "description": "Research market size and competition for a new SaaS product idea",
                "category": "research",
                "difficulty": "medium",
                "reward": 40.0,
            },
            {
                "title": "Bug Fix: React Component Rendering Issue",
                "description": "Fix a rendering bug in a React component",
                "category": "coding",
                "difficulty": "easy",
                "reward": 30.0,
            },
            {
                "title": "Algorithm Implementation: Sorting Optimization",
                "description": "Implement and optimize a custom sorting algorithm",
                "category": "coding",
                "difficulty": "hard",
                "reward": 75.0,
            },
        ]

        for i in range(min(count, len(task_templates))):
            template = task_templates[i % len(task_templates)]
            task_id = str(uuid.uuid4())
            task = Task(
                id=task_id,
                title=template["title"],
                description=template["description"],
                requirements={},
                reward=template["reward"],
                deadline=datetime.now() + timedelta(days=7),
                difficulty=template["difficulty"],
                category=template["category"],
            )
            self.tasks[task_id] = task

    def list_available_tasks(self) -> List[Task]:
        """Returns tasks that haven't been claimed."""
        return [task for task in self.tasks.values() if task.id not in self.claimed_tasks]

    def claim_task(self, task_id: str) -> bool:
        """Claims task for work."""
        if task_id in self.tasks and task_id not in self.claimed_tasks:
            self.claimed_tasks.add(task_id)
            return True
        return False

    def submit_solution(self, submission: TaskSubmission) -> str:
        """Submits completed work and simulates review."""
        submission_id = str(uuid.uuid4())

        # Simulate review with random approval (80% success rate)
        approved = self.rng.random() < 0.8

        if approved:
            task = self.tasks.get(submission.task_id)
            reward = task.reward if task else 0.0
            status = SubmissionStatus(
                submission_id=submission_id,
                status="approved",
                feedback="Great work! Task completed successfully.",
                reward_paid=reward,
                reviewed_at=datetime.now(),
            )
        else:
            status = SubmissionStatus(
                submission_id=submission_id,
                status="rejected",
                feedback="Does not meet requirements. Please revise and resubmit.",
                reward_paid=0.0,
                reviewed_at=datetime.now(),
            )

        self.submissions[submission_id] = status
        return submission_id

    def check_submission_status(self, submission_id: str) -> SubmissionStatus:
        """Checks submission status."""
        if submission_id not in self.submissions:
            return SubmissionStatus(
                submission_id=submission_id,
                status="pending",
                feedback="Submission under review",
                reward_paid=0.0,
                reviewed_at=None,
            )
        return self.submissions[submission_id]

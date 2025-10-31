"""Mock marketplace implementation for simulation with real task execution."""

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

    def __init__(self, seed: int | None = None, enable_claude_execution: bool = False):
        """Initialize mock marketplace.

        Args:
            seed: Random seed for reproducible task generation
            enable_claude_execution: Enable real Claude Code execution and review
        """
        self.rng = random.Random(seed)
        self.tasks: Dict[str, Task] = {}
        self.claimed_tasks: set = set()
        self.submissions: Dict[str, SubmissionStatus] = {}
        self.enable_claude_execution = enable_claude_execution

        # Initialize executor and reviewer if enabled
        if enable_claude_execution:
            # Import only when needed to avoid circular dependency
            from economic_agents.marketplace import CodeReviewer, TaskExecutor

            self.executor = TaskExecutor()
            self.reviewer = CodeReviewer()
        else:
            self.executor = None
            self.reviewer = None

        self._generate_initial_tasks()

    def _generate_initial_tasks(self, count: int = 10):
        """Generate initial set of available tasks using real coding tasks."""
        # Import only when needed to avoid circular dependency
        from economic_agents.marketplace import CODING_TASKS

        # Use real coding task templates
        task_templates = CODING_TASKS

        for i in range(min(count, len(task_templates))):
            template = task_templates[i % len(task_templates)]
            task_id = str(uuid.uuid4())
            task = Task(
                id=task_id,
                title=template["title"],
                description=template["description"],
                requirements=template.get("requirements", {}),
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
        """Submits completed work and performs review (real or simulated)."""
        submission_id = str(uuid.uuid4())
        task = self.tasks.get(submission.task_id)

        if not task:
            # Task not found
            status = SubmissionStatus(
                submission_id=submission_id,
                status="rejected",
                feedback="Task not found",
                reward_paid=0.0,
                reviewed_at=datetime.now(),
            )
        elif self.enable_claude_execution and self.reviewer:
            # Real Claude Code review
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Reviewing submission {submission_id} with Claude Code")

            # Convert Task to dict for reviewer
            task_dict = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "requirements": task.requirements,
                "reward": task.reward,
            }

            # Review the submission
            review_result = self.reviewer.review_submission(
                task=task_dict, code=submission.solution, timeout=300  # 5 minute timeout for review
            )

            approved = review_result.get("approved", False)
            feedback = review_result.get("feedback", "No feedback provided")

            if approved:
                status = SubmissionStatus(
                    submission_id=submission_id,
                    status="approved",
                    feedback=feedback,
                    reward_paid=task.reward,
                    reviewed_at=datetime.now(),
                )
            else:
                status = SubmissionStatus(
                    submission_id=submission_id,
                    status="rejected",
                    feedback=feedback,
                    reward_paid=0.0,
                    reviewed_at=datetime.now(),
                )

        else:
            # Simulated review with random approval (80% success rate)
            approved = self.rng.random() < 0.8

            if approved:
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

    def execute_task(self, task_id: str, timeout: int = 300) -> Dict[str, str | bool]:
        """Execute a task using Claude Code.

        Args:
            task_id: Task to execute
            timeout: Execution timeout in seconds

        Returns:
            Execution result dict
        """
        if not self.enable_claude_execution or not self.executor:
            return {"success": False, "error": "Claude execution not enabled"}

        task = self.tasks.get(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Executing task {task_id} with Claude Code")

        # Convert Task to dict for executor
        task_dict = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "requirements": task.requirements,
            "reward": task.reward,
        }

        # Execute task
        result: Dict[str, str | bool] = self.executor.execute_task(task_dict, timeout=timeout)

        return result

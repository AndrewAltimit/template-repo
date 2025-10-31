"""Mock marketplace implementation for simulation with real task execution."""

import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from economic_agents.interfaces.marketplace import (
    MarketplaceInterface,
    SubmissionStatus,
    Task,
    TaskSubmission,
)
from economic_agents.simulation.competitor_agents import CompetitorSimulator
from economic_agents.simulation.latency_simulator import LatencySimulator


class MockMarketplace(MarketplaceInterface):
    """Mock marketplace that generates diverse tasks and simulates review process."""

    def __init__(
        self,
        seed: Optional[int] = None,
        enable_claude_execution: bool = False,
        enable_latency: bool = True,
        enable_competition: bool = True,
    ):
        """Initialize mock marketplace.

        Args:
            seed: Random seed for reproducible task generation
            enable_claude_execution: Enable real Claude Code execution and review
            enable_latency: Enable realistic latency simulation
            enable_competition: Enable task competition simulation
        """
        self.rng = random.Random(seed)
        self.tasks: Dict[str, Task] = {}
        self.claimed_tasks: set = set()
        self.submissions: Dict[str, SubmissionStatus] = {}
        self.enable_claude_execution = enable_claude_execution
        self.enable_latency = enable_latency
        self.enable_competition = enable_competition

        # Initialize latency simulator
        self.latency_sim = LatencySimulator(seed=seed) if enable_latency else None

        # Initialize competitor simulator
        self.competitor_sim = CompetitorSimulator(seed=seed) if enable_competition else None

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
        # Simulate base API latency
        if self.latency_sim:
            self.latency_sim.simulate_base_latency()

        # Simulate competitors claiming tasks
        if self.competitor_sim:
            available = [
                task.id
                for task in self.tasks.values()
                if task.id not in self.claimed_tasks and not self.competitor_sim.is_claimed_by_competitor(task.id)
            ]

            # Check if any tasks should be claimed by competitors
            for task_id in list(available):  # Use list() to avoid modifying during iteration
                task = self.tasks[task_id]
                if self.competitor_sim.should_competitor_claim_task(task.reward):
                    self.competitor_sim.claim_task_by_competitor(task_id)

            # Return tasks not claimed by anyone (including competitors)
            return [
                task
                for task in self.tasks.values()
                if task.id not in self.claimed_tasks and not self.competitor_sim.is_claimed_by_competitor(task.id)
            ]
        else:
            return [task for task in self.tasks.values() if task.id not in self.claimed_tasks]

    def claim_task(self, task_id: str) -> bool:
        """Claims task for work."""
        # Simulate base API latency
        if self.latency_sim:
            self.latency_sim.simulate_base_latency()

        # Check for race condition with competitors
        if self.competitor_sim:
            if self.competitor_sim.simulate_race_condition(task_id):
                # Another agent claimed it first
                return False

            # Also check if already claimed by competitor
            if self.competitor_sim.is_claimed_by_competitor(task_id):
                return False

        if task_id in self.tasks and task_id not in self.claimed_tasks:
            self.claimed_tasks.add(task_id)
            return True
        return False

    def submit_solution(self, submission: TaskSubmission) -> str:
        """Submits completed work and performs review (real or simulated)."""
        # Simulate complex processing latency for review
        if self.latency_sim:
            try:
                self.latency_sim.simulate_complex_processing(timeout_enabled=True)
            except TimeoutError:
                # Simulate 504 timeout error
                submission_id = str(uuid.uuid4())
                status = SubmissionStatus(
                    submission_id=submission_id,
                    status="rejected",
                    feedback="Review service timed out (504). Please try again later.",
                    reward_paid=0.0,
                    reviewed_at=datetime.now(),
                )
                self.submissions[submission_id] = status
                return submission_id

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
        # Simulate base API latency
        if self.latency_sim:
            self.latency_sim.simulate_base_latency()

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

    def generate_tasks(self, count: int = 5) -> List[Dict]:
        """Generate tasks in simplified dict format for API.

        Args:
            count: Number of tasks to generate

        Returns:
            List of task dicts with API-compatible format
        """
        # Ensure we have enough tasks
        if len(self.tasks) < count:
            self._generate_initial_tasks(count)

        # Get available tasks (not claimed)
        available = self.list_available_tasks()

        # Convert to simplified dict format for API
        # Difficulty mapping: easy -> 1-3, medium -> 4-6, hard -> 7-10
        difficulty_map = {
            "easy": self.rng.uniform(1.0, 3.0),
            "medium": self.rng.uniform(4.0, 6.0),
            "hard": self.rng.uniform(7.0, 10.0),
        }

        tasks = []
        for task in available[:count]:
            # Convert difficulty string to numeric value
            if isinstance(task.difficulty, str):
                difficulty_value = difficulty_map.get(task.difficulty.lower(), 5.0)
            else:
                difficulty_value = task.difficulty

            tasks.append(
                {
                    "id": task.id,
                    "difficulty": difficulty_value,
                    "reward": task.reward,
                    "compute_hours_required": self.rng.uniform(1.0, 8.0),  # Estimate compute hours
                    "description": task.description,
                    "title": task.title,
                }
            )

        return tasks

    def complete_task(self, task: Dict) -> Dict:
        """Complete a task (convenience method for API).

        Args:
            task: Task dict with at least 'id' and 'reward' fields

        Returns:
            Result dict with 'success', 'reward', and optional 'message' fields
        """
        task_id = task.get("id")
        if not task_id:
            return {"success": False, "reward": 0.0, "message": "Invalid task: missing ID"}

        # Check if task exists
        if task_id not in self.tasks:
            return {"success": False, "reward": 0.0, "message": "Task not found"}

        # Simulate completion with 80% success rate
        success = self.rng.random() < 0.8

        if success:
            reward = task.get("reward", 0.0)
            return {"success": True, "reward": reward, "message": "Task completed successfully"}
        else:
            return {"success": False, "reward": 0.0, "message": "Task completion failed - requirements not met"}

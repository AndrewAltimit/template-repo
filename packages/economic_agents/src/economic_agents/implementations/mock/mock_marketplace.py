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
from economic_agents.simulation.feedback_generator import FeedbackGenerator
from economic_agents.simulation.latency_simulator import LatencySimulator
from economic_agents.simulation.market_dynamics import MarketDynamics
from economic_agents.simulation.reputation_system import ReputationSystem


class MockMarketplace(MarketplaceInterface):
    """Mock marketplace that generates diverse tasks and simulates review process."""

    def __init__(
        self,
        seed: Optional[int] = None,
        enable_claude_execution: bool = False,
        enable_latency: bool = True,
        enable_competition: bool = True,
        enable_detailed_feedback: bool = True,
        enable_market_dynamics: bool = True,
        enable_reputation: bool = True,
    ):
        """Initialize mock marketplace.

        Args:
            seed: Random seed for reproducible task generation
            enable_claude_execution: Enable real Claude Code execution and review
            enable_latency: Enable realistic latency simulation
            enable_competition: Enable task competition simulation
            enable_detailed_feedback: Enable detailed feedback generation
            enable_market_dynamics: Enable market cycle simulation
            enable_reputation: Enable reputation system
        """
        self.rng = random.Random(seed)
        self.tasks: Dict[str, Task] = {}
        self.claimed_tasks: set = set()
        self.submissions: Dict[str, SubmissionStatus] = {}
        self.enable_claude_execution = enable_claude_execution
        self.enable_latency = enable_latency
        self.enable_competition = enable_competition
        self.enable_detailed_feedback = enable_detailed_feedback
        self.enable_market_dynamics = enable_market_dynamics
        self.enable_reputation = enable_reputation

        # Initialize latency simulator
        self.latency_sim = LatencySimulator(seed=seed) if enable_latency else None

        # Initialize competitor simulator
        self.competitor_sim = CompetitorSimulator(seed=seed) if enable_competition else None

        # Initialize feedback generator
        self.feedback_gen = FeedbackGenerator(seed=seed) if enable_detailed_feedback else None

        # Initialize market dynamics
        self.market_dynamics = MarketDynamics(seed=seed) if enable_market_dynamics else None

        # Initialize reputation system
        self.reputation_system = ReputationSystem(seed=seed) if enable_reputation else None

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

        # Update market dynamics
        if self.market_dynamics:
            self.market_dynamics.update()
            # Adjust task count based on market phase
            task_multiplier = (
                self.market_dynamics.get_task_availability_multiplier() * self.market_dynamics.get_time_of_day_multiplier()
            )
            adjusted_count = max(1, int(count * task_multiplier))
        else:
            adjusted_count = count

        # Use real coding task templates
        task_templates = CODING_TASKS

        for i in range(min(adjusted_count, len(task_templates))):
            template = task_templates[i % len(task_templates)]
            task_id = str(uuid.uuid4())

            # Adjust reward based on market dynamics
            base_reward = template["reward"]
            if self.market_dynamics:
                reward_multiplier = self.market_dynamics.get_reward_multiplier()
                adjusted_reward = base_reward * reward_multiplier
            else:
                adjusted_reward = base_reward

            task = Task(
                id=task_id,
                title=template["title"],
                description=template["description"],
                requirements=template.get("requirements", {}),
                reward=adjusted_reward,
                deadline=datetime.now() + timedelta(days=7),
                difficulty=template["difficulty"],
                category=template["category"],
            )
            self.tasks[task_id] = task

    async def list_available_tasks(self, agent_id: Optional[str] = None) -> List[Task]:
        """Returns tasks that haven't been claimed.

        Args:
            agent_id: Optional agent ID for reputation-based filtering
        """
        # Update market dynamics
        if self.market_dynamics:
            self.market_dynamics.update()

        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

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

            # Get tasks not claimed by anyone (including competitors)
            available_tasks = [
                task
                for task in self.tasks.values()
                if task.id not in self.claimed_tasks and not self.competitor_sim.is_claimed_by_competitor(task.id)
            ]
        else:
            available_tasks = [task for task in self.tasks.values() if task.id not in self.claimed_tasks]

        # Apply reputation-based filtering
        if self.reputation_system and agent_id:
            access_multiplier = self.reputation_system.get_access_multiplier(agent_id)
            # Higher reputation = more tasks visible
            max_tasks = max(1, int(len(available_tasks) * access_multiplier))
            return available_tasks[:max_tasks]
        else:
            return available_tasks

    async def claim_task(self, task_id: str) -> bool:
        """Claims task for work."""
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

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

    async def submit_solution(self, submission: TaskSubmission, agent_id: Optional[str] = None) -> str:
        """Submits completed work and performs review (real or simulated).

        Args:
            submission: Task submission
            agent_id: Optional agent ID for reputation tracking
        """
        submission_start_time = datetime.now()

        # Simulate complex processing latency for review
        if self.latency_sim:
            try:
                await self.latency_sim.simulate_complex_processing_async(timeout_enabled=True)
            except Exception:
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
            logger.info("Reviewing submission %s with Claude Code", submission_id)

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
            # Simulated review
            if self.feedback_gen:
                # Use detailed feedback generator
                task_category = task.category if task else "general"
                review_result = self.feedback_gen.generate_task_review(task_category, base_success_probability=0.8)

                success = review_result["success"]
                reward_percentage = review_result["reward_percentage"]
                feedback = review_result["feedback"]

                if success:
                    reward = (task.reward if task else 0.0) * reward_percentage
                    status = SubmissionStatus(
                        submission_id=submission_id,
                        status="approved",
                        feedback=feedback,
                        reward_paid=reward,
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
                # Simple binary review (backward compatibility)
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

        # Record performance in reputation system
        if self.reputation_system and agent_id and task:
            completion_time_hours = (datetime.now() - submission_start_time).total_seconds() / 3600.0
            success = status.status == "approved"

            # Extract quality score from feedback if available (from detailed feedback)
            quality_score = 0.8 if success else 0.3  # Default values
            if self.feedback_gen and hasattr(status, "feedback") and isinstance(status.feedback, str):
                # Try to extract quality from detailed feedback
                # The detailed feedback includes quality metrics
                import re

                quality_match = re.search(r"Overall Quality:\s*([\d.]+)", status.feedback)
                if quality_match:
                    quality_score = float(quality_match.group(1))

            self.reputation_system.record_task_completion(
                agent_id=agent_id,
                task_id=submission.task_id,
                success=success,
                quality_score=quality_score,
                completion_time_hours=completion_time_hours,
                reward_earned=status.reward_paid,
            )

        return submission_id

    async def check_submission_status(self, submission_id: str) -> SubmissionStatus:
        """Checks submission status."""
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

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
        logger.info("Executing task %s with Claude Code", task_id)

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

    async def generate_tasks(self, count: int = 5) -> List[Dict]:
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
        available = await self.list_available_tasks()

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

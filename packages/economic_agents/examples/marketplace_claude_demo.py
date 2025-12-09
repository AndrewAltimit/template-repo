"""Demo: Claude-powered agent completing marketplace tasks end-to-end.

This demonstrates:
1. Agent discovers tasks from marketplace
2. Agent executes tasks using Claude Code
3. Agent submits solution
4. Claude Code reviewer validates the solution
5. Agent receives payment on approval
"""

from datetime import datetime
import logging

from economic_agents.implementations.mock import MockMarketplace
from economic_agents.interfaces.marketplace import TaskSubmission

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


def main():
    """Run the complete marketplace task execution demo."""
    print("=" * 80)
    print("CLAUDE-POWERED MARKETPLACE TASK EXECUTION DEMO")
    print("=" * 80)
    print()

    # Initialize marketplace with Claude execution enabled
    print("Initializing marketplace with Claude Code execution...")
    marketplace = MockMarketplace(seed=42, enable_claude_execution=True)
    print("✓ Marketplace initialized\n")

    # Step 1: Discover available tasks
    print("STEP 1: Discovering available tasks")
    print("-" * 80)
    tasks = marketplace.list_available_tasks()

    print(f"Found {len(tasks)} available tasks:\n")
    for i, task in enumerate(tasks[:3], 1):  # Show first 3
        print(f"{i}. {task.title}")
        print(f"   Difficulty: {task.difficulty}")
        print(f"   Reward: ${task.reward:.2f}")
        print(f"   Description: {task.description}")
        print()

    # Step 2: Select a task (choose easiest)
    selected_task = tasks[0]  # FizzBuzz - first task
    print(f"STEP 2: Selecting task - '{selected_task.title}'")
    print("-" * 80)
    print(f"Task ID: {selected_task.id}")
    print(f"Reward: ${selected_task.reward:.2f}")
    print()

    # Step 3: Claim the task
    print("STEP 3: Claiming task")
    print("-" * 80)
    claimed = marketplace.claim_task(selected_task.id)
    if claimed:
        print("✓ Task claimed successfully\n")
    else:
        print("✗ Failed to claim task\n")
        return

    # Step 4: Execute task using Claude Code
    print("STEP 4: Executing task with Claude Code")
    print("-" * 80)
    print("Agent is working on the task...")
    print("(This will take a few minutes as Claude writes the code)\n")

    execution_result = marketplace.execute_task(selected_task.id, timeout=300)

    if execution_result.get("success"):
        print("✓ Task execution completed!\n")
        code = execution_result.get("code", "")
        print("Generated code:")
        print("-" * 40)
        print(code[:500] + ("..." if len(code) > 500 else ""))  # Show first 500 chars
        print("-" * 40)
        print()
    else:
        print(f"✗ Task execution failed: {execution_result.get('error')}\n")
        return

    # Step 5: Submit solution
    print("STEP 5: Submitting solution to marketplace")
    print("-" * 80)

    submission = TaskSubmission(
        task_id=selected_task.id,
        solution=execution_result["code"],
        submitted_at=datetime.now(),
        metadata={"execution_time": execution_result.get("execution_time", 0)},
    )

    submission_id = marketplace.submit_solution(submission)
    print(f"✓ Solution submitted (ID: {submission_id})\n")

    # Step 6: Check review status
    print("STEP 6: Reviewing submission with Claude Code")
    print("-" * 80)
    print("Another Claude instance is reviewing the code...")
    print("(This will take a few minutes as Claude runs tests and reviews)\n")

    status = marketplace.check_submission_status(submission_id)

    print(f"Review Status: {status.status.upper()}")
    print()
    print("Feedback:")
    print("-" * 40)
    print(status.feedback)
    print("-" * 40)
    print()

    # Step 7: Payment
    if status.status == "approved":
        print(f"✓ APPROVED! Reward paid: ${status.reward_paid:.2f}")
        print()
        print("SUCCESS! Agent completed task and earned payment!")
    else:
        print("✗ REJECTED. No payment issued.")
        print()
        print("Agent can revise and resubmit.")

    print()
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()

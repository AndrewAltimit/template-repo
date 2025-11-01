"""Tests for MockMarketplace implementation."""

from datetime import datetime

import pytest
from economic_agents.implementations.mock import MockMarketplace
from economic_agents.interfaces.marketplace import TaskSubmission


@pytest.mark.asyncio
async def test_marketplace_initialization():
    """Test marketplace initializes with tasks."""
    marketplace = MockMarketplace(seed=42)

    tasks = await marketplace.list_available_tasks()
    assert len(tasks) > 0
    assert all(hasattr(task, "id") for task in tasks)
    assert all(hasattr(task, "reward") for task in tasks)


@pytest.mark.asyncio
async def test_marketplace_claim_task():
    """Test claiming a task."""
    marketplace = MockMarketplace(seed=42)

    tasks = await marketplace.list_available_tasks()
    task_id = tasks[0].id

    success = await marketplace.claim_task(task_id)
    assert success is True

    # Task should no longer be in available list
    available = await marketplace.list_available_tasks()
    assert task_id not in [t.id for t in available]


@pytest.mark.asyncio
async def test_marketplace_claim_same_task_twice():
    """Test claiming same task twice fails."""
    marketplace = MockMarketplace(seed=42)

    tasks = await marketplace.list_available_tasks()
    task_id = tasks[0].id

    await marketplace.claim_task(task_id)
    success = await marketplace.claim_task(task_id)

    assert success is False


@pytest.mark.asyncio
async def test_marketplace_submit_solution():
    """Test submitting a solution."""
    marketplace = MockMarketplace(seed=42)

    tasks = await marketplace.list_available_tasks()
    task = tasks[0]
    await marketplace.claim_task(task.id)

    submission = TaskSubmission(task_id=task.id, solution="My solution", submitted_at=datetime.now(), metadata={})

    submission_id = await marketplace.submit_solution(submission)

    assert submission_id is not None
    assert len(submission_id) > 0


@pytest.mark.asyncio
async def test_marketplace_check_submission_status():
    """Test checking submission status."""
    marketplace = MockMarketplace(seed=42)

    tasks = await marketplace.list_available_tasks()
    task = tasks[0]
    await marketplace.claim_task(task.id)

    submission = TaskSubmission(task_id=task.id, solution="My solution", submitted_at=datetime.now(), metadata={})

    submission_id = await marketplace.submit_solution(submission)
    status = await marketplace.check_submission_status(submission_id)

    assert status.submission_id == submission_id
    assert status.status in ["approved", "rejected"]
    assert status.feedback is not None


@pytest.mark.asyncio
async def test_marketplace_submission_approval():
    """Test that submissions can be approved."""
    marketplace = MockMarketplace(seed=42)

    # Submit multiple times to test randomness
    approvals = 0
    for i in range(20):
        tasks = await marketplace.list_available_tasks()
        if not tasks:
            marketplace._generate_initial_tasks(10)
            tasks = await marketplace.list_available_tasks()

        task = tasks[0]
        await marketplace.claim_task(task.id)

        submission = TaskSubmission(task_id=task.id, solution=f"Solution {i}", submitted_at=datetime.now(), metadata={})

        submission_id = await marketplace.submit_solution(submission)
        status = await marketplace.check_submission_status(submission_id)

        if status.status == "approved":
            approvals += 1
            assert status.reward_paid > 0

    # With 80% approval rate and 20 submissions, we should get some approvals
    assert approvals > 10


@pytest.mark.asyncio
async def test_marketplace_tasks_have_required_fields():
    """Test that generated tasks have all required fields."""
    marketplace = MockMarketplace(seed=42)

    tasks = await marketplace.list_available_tasks()
    task = tasks[0]

    assert task.id is not None
    assert task.title is not None
    assert task.description is not None
    assert task.reward > 0
    assert task.deadline is not None
    assert task.difficulty in ["easy", "medium", "hard"]
    assert task.category in ["coding", "data-analysis", "research"]


@pytest.mark.asyncio
async def test_marketplace_unknown_submission():
    """Test checking status of unknown submission."""
    marketplace = MockMarketplace(seed=42)

    status = await marketplace.check_submission_status("unknown_id")

    assert status.status == "pending"
    assert status.reward_paid == 0.0

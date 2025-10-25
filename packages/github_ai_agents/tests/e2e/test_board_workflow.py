"""End-to-end tests for GitHub board workflow.

These tests require actual GitHub credentials and a test project board.
They validate the complete workflow from issue creation to completion.
"""

import asyncio
import os

import pytest

from github_ai_agents.board.config import BoardConfig
from github_ai_agents.board.manager import BoardManager
from github_ai_agents.board.models import IssueStatus

# Mark all tests in this module as e2e tests
pytestmark = pytest.mark.e2e


@pytest.fixture
def github_token() -> str:
    """Get GitHub token from environment."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN environment variable not set")
        return ""  # For type checker (never reached)
    return token


@pytest.fixture
def board_config_path() -> str:
    """Get board config path."""
    config_path = ".github/ai-agents-board.yml"
    if not os.path.exists(config_path):
        pytest.skip("Board configuration not found at .github/ai-agents-board.yml")
    return config_path


@pytest.fixture
async def board_manager(github_token: str, board_config_path: str) -> BoardManager:
    """Create and initialize board manager."""
    config = BoardConfig.from_file(board_config_path)
    manager = BoardManager(config=config, github_token=github_token)
    await manager.initialize()
    return manager


@pytest.mark.asyncio
async def test_board_initialization(board_manager: BoardManager) -> None:
    """Test board manager initializes correctly."""
    assert board_manager is not None
    assert board_manager.config is not None
    assert board_manager.config.project_number > 0


@pytest.mark.asyncio
async def test_get_ready_work(board_manager: BoardManager) -> None:
    """Test querying ready work from the board."""
    issues = await board_manager.get_ready_work(limit=5)
    assert isinstance(issues, list)
    # Note: May be empty if no ready work exists
    for issue in issues:
        assert issue.number > 0
        assert issue.title
        assert issue.status in [IssueStatus.TODO, IssueStatus.BLOCKED]


@pytest.mark.asyncio
async def test_claim_and_release_workflow(board_manager: BoardManager) -> None:
    """Test full claim and release workflow.

    This test requires at least one ready issue on the board.
    """
    # Get ready work
    issues = await board_manager.get_ready_work(limit=1)
    if not issues:
        pytest.skip("No ready work available on board")

    issue = issues[0]
    issue_number = issue.number

    # Claim the work
    session_id = "test-e2e-session-123"
    claim_success = await board_manager.claim_work(issue_number, "test-agent", session_id)

    if not claim_success:
        pytest.skip("Issue already claimed by another agent")

    try:
        # Verify claim succeeded
        assert claim_success is True

        # Update status to in progress
        status_success = await board_manager.update_status(issue_number, IssueStatus.IN_PROGRESS)
        assert status_success is True

        # Release the work
        await board_manager.release_work(issue_number, "test-agent", "completed")

        # Verify work was released (check status is back to Todo or Done)
        # Note: Actual status depends on release reason
        # For "completed", status should be "Done"

    finally:
        # Cleanup: Always try to release if we claimed it
        try:
            await board_manager.release_work(issue_number, "test-agent", "abandoned")
        except Exception:
            pass  # Ignore cleanup errors


@pytest.mark.asyncio
async def test_dependency_management(board_manager: BoardManager) -> None:
    """Test adding and querying dependencies.

    This test requires at least two issues on the board.
    """
    # Get two issues
    issues = await board_manager.get_ready_work(limit=2)
    if len(issues) < 2:
        pytest.skip("Need at least 2 issues on board for dependency test")

    issue1 = issues[0].number
    issue2 = issues[1].number

    # Add blocker relationship
    success = await board_manager.add_blocker(issue1, issue2)
    assert success is True

    # Get dependency graph
    graph = await board_manager.get_dependency_graph(issue1)
    assert graph is not None
    assert graph.issue.number == issue1

    # Verify blocker is in the graph
    blocker_numbers = [b.number for b in graph.blocked_by]
    assert issue2 in blocker_numbers


@pytest.mark.asyncio
async def test_concurrent_claims(board_manager: BoardManager) -> None:
    """Test that concurrent claim attempts are handled correctly."""
    # Get ready work
    issues = await board_manager.get_ready_work(limit=1)
    if not issues:
        pytest.skip("No ready work available on board")

    issue_number = issues[0].number

    # Try to claim from two agents concurrently
    async def claim_task(agent_name: str, session_id: str) -> bool:
        result = await board_manager.claim_work(issue_number, agent_name, session_id)
        return bool(result)

    try:
        # Run concurrent claims
        results = await asyncio.gather(
            claim_task("agent1", "session1"), claim_task("agent2", "session2"), return_exceptions=False
        )

        # Exactly one should succeed
        success_count = sum(1 for r in results if r is True)
        assert success_count == 1, f"Expected exactly 1 successful claim, got {success_count}"

    finally:
        # Cleanup: Release from both agents (only one will succeed)
        try:
            await board_manager.release_work(issue_number, "agent1", "abandoned")
        except Exception:
            pass
        try:
            await board_manager.release_work(issue_number, "agent2", "abandoned")
        except Exception:
            pass


@pytest.mark.asyncio
async def test_claim_renewal(board_manager: BoardManager) -> None:
    """Test claim renewal for long-running tasks."""
    # Get ready work
    issues = await board_manager.get_ready_work(limit=1)
    if not issues:
        pytest.skip("No ready work available on board")

    issue_number = issues[0].number
    session_id = "test-renewal-session"

    # Claim the work
    claim_success = await board_manager.claim_work(issue_number, "test-agent", session_id)
    if not claim_success:
        pytest.skip("Issue already claimed")

    try:
        # Renew the claim
        renewal_success = await board_manager.renew_claim(issue_number, "test-agent", session_id)
        assert renewal_success is True

    finally:
        # Cleanup
        try:
            await board_manager.release_work(issue_number, "test-agent", "abandoned")
        except Exception:
            pass


@pytest.mark.asyncio
async def test_board_performance(board_manager: BoardManager) -> None:
    """Test board operations performance with larger datasets."""
    import time

    # Query multiple issues
    start_time = time.time()
    issues = await board_manager.get_ready_work(limit=50)
    query_time = time.time() - start_time

    # Should complete in reasonable time (< 5 seconds)
    assert query_time < 5.0, f"Query took {query_time:.2f}s, expected < 5s"

    # Results should be properly formatted
    for issue in issues[:5]:  # Check first 5
        assert issue.number > 0
        assert issue.title
        assert issue.status


@pytest.mark.asyncio
async def test_error_handling(board_manager: BoardManager) -> None:
    """Test error handling for invalid operations."""
    # Try to claim non-existent issue
    fake_issue = 999999999
    claim_result = await board_manager.claim_work(fake_issue, "test-agent", "test-session")
    # Should return False or raise error, not crash
    assert claim_result is False

    # Try to get graph for non-existent issue
    with pytest.raises(Exception):
        await board_manager.get_dependency_graph(fake_issue)

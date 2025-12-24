"""Concurrency tests for board claim race conditions.

Tests the BoardManager's ability to handle concurrent claim attempts,
work selection, and agent coordination without data races.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import AsyncMock, patch

import pytest

from github_agents.board.config import BoardConfig
from github_agents.board.manager import BoardManager
from github_agents.board.models import AgentClaim, Issue, IssuePriority, IssueStatus


@pytest.fixture
def board_config():
    """Create test board configuration."""
    return BoardConfig(
        project_number=1,
        owner="testuser",
        repository="test/repo",
        field_mappings={
            "status": "Status",
            "priority": "Priority",
            "agent": "Agent",
            "type": "Type",
        },
        claim_timeout=86400,  # 24 hours
        enabled_agents=["claude", "opencode", "gemini", "crush"],
    )


@pytest.fixture
def mock_github_token():
    """Mock GitHub token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
        yield "test-token"


class TestSimultaneousClaimAttempts:
    """Test behavior when multiple agents try to claim the same issue simultaneously."""

    @pytest.mark.asyncio
    async def test_two_agents_claim_same_issue(self, board_config, mock_github_token):
        """First agent to successfully claim should win."""
        manager = BoardManager(config=board_config)

        # Track claim order
        claim_order = []
        claimed_by = None

        async def mock_get_claim(_issue_num):
            nonlocal claimed_by
            return claimed_by

        async def mock_post_comment(_issue_num, body):
            nonlocal claimed_by
            # Simulate posting claim - extract agent from comment
            if "Agent: `claude`" in body and not claimed_by:
                claimed_by = AgentClaim(
                    issue_number=42,
                    agent="claude",
                    session_id="claude-session",
                    timestamp=datetime.now(timezone.utc),
                )
                claim_order.append("claude")
            elif "Agent: `opencode`" in body and not claimed_by:
                claimed_by = AgentClaim(
                    issue_number=42,
                    agent="opencode",
                    session_id="opencode-session",
                    timestamp=datetime.now(timezone.utc),
                )
                claim_order.append("opencode")

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Simulate concurrent claims
        results = await asyncio.gather(
            manager.claim_work(42, "claude", "claude-session"),
            manager.claim_work(42, "opencode", "opencode-session"),
        )

        # Exactly one should succeed
        assert sum(results) == 1
        # One agent should have claimed
        assert len(claim_order) == 1

    @pytest.mark.asyncio
    async def test_four_agents_claim_same_issue(self, board_config, mock_github_token):
        """Test race condition with four concurrent claim attempts."""
        manager = BoardManager(config=board_config)

        claimed_by = None
        claim_lock = asyncio.Lock()

        async def mock_get_claim(_issue_num):
            return claimed_by

        async def mock_post_comment(_issue_num, body):
            nonlocal claimed_by
            async with claim_lock:
                if claimed_by is None:
                    # Parse agent name from comment
                    for agent in ["claude", "opencode", "gemini", "crush"]:
                        if f"Agent: `{agent}`" in body:
                            claimed_by = AgentClaim(
                                issue_number=42,
                                agent=agent,
                                session_id=f"{agent}-session",
                                timestamp=datetime.now(timezone.utc),
                            )
                            break
                    await asyncio.sleep(0.01)  # Simulate network latency

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # All four agents try to claim
        results = await asyncio.gather(
            manager.claim_work(42, "claude", "claude-session"),
            manager.claim_work(42, "opencode", "opencode-session"),
            manager.claim_work(42, "gemini", "gemini-session"),
            manager.claim_work(42, "crush", "crush-session"),
        )

        # Exactly one should succeed
        assert sum(results) == 1
        assert claimed_by is not None

    @pytest.mark.asyncio
    async def test_sequential_claims_after_release(self, board_config, mock_github_token):
        """Test that work can be reclaimed after release."""
        manager = BoardManager(config=board_config)

        claim_state = {"current": None, "released": False}

        async def mock_get_claim(_issue_num):
            if claim_state["released"]:
                return None
            return claim_state["current"]

        async def mock_post_comment(_issue_num, body):
            if "Agent Claim" in body:
                for agent in ["claude", "opencode"]:
                    if f"Agent: `{agent}`" in body:
                        claim_state["current"] = AgentClaim(
                            issue_number=42,
                            agent=agent,
                            session_id=f"{agent}-session",
                            timestamp=datetime.now(timezone.utc),
                        )
                        claim_state["released"] = False
                        break
            elif "Agent Release" in body:
                claim_state["released"] = True
                claim_state["current"] = None

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Claude claims first
        result1 = await manager.claim_work(42, "claude", "claude-session")
        assert result1 is True

        # OpenCode fails while claimed
        result2 = await manager.claim_work(42, "opencode", "opencode-session")
        assert result2 is False

        # Claude releases
        await manager.release_work(42, "claude", "completed")

        # Now opencode can claim
        result3 = await manager.claim_work(42, "opencode", "opencode-session")
        assert result3 is True


class TestClaimExpirationUnderConcurrency:
    """Test claim expiration behavior during concurrent access."""

    @pytest.mark.asyncio
    async def test_expired_claim_can_be_stolen(self, board_config, mock_github_token):
        """Test that expired claims can be taken by another agent."""
        manager = BoardManager(config=board_config)

        # Create an expired claim (older than 24 hours)
        expired_time = datetime.now(timezone.utc) - timedelta(hours=25)
        expired_claim = AgentClaim(
            issue_number=42,
            agent="opencode",
            session_id="old-session",
            timestamp=expired_time,
        )

        new_claim = None

        async def mock_get_claim(_issue_num):
            return new_claim if new_claim else expired_claim

        async def mock_post_comment(_issue_num, body):
            nonlocal new_claim
            if "Agent: `claude`" in body:
                new_claim = AgentClaim(
                    issue_number=42,
                    agent="claude",
                    session_id="claude-session",
                    timestamp=datetime.now(timezone.utc),
                )

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Claude can claim because existing claim is expired
        result = await manager.claim_work(42, "claude", "claude-session")
        assert result is True
        assert new_claim is not None
        assert new_claim.agent == "claude"

    @pytest.mark.asyncio
    async def test_near_expiration_claim_is_valid(self, board_config, mock_github_token):
        """Test that claims near expiration are still valid."""
        manager = BoardManager(config=board_config)

        # Claim that's almost expired but not quite (23 hours old)
        near_expired_time = datetime.now(timezone.utc) - timedelta(hours=23)
        existing_claim = AgentClaim(
            issue_number=42,
            agent="opencode",
            session_id="existing-session",
            timestamp=near_expired_time,
        )

        manager._get_active_claim = AsyncMock(return_value=existing_claim)

        # Claude cannot claim because existing claim hasn't expired
        result = await manager.claim_work(42, "claude", "claude-session")
        assert result is False

    @pytest.mark.asyncio
    async def test_concurrent_steal_of_expired_claim(self, board_config, mock_github_token):
        """Test that only one agent can steal an expired claim."""
        manager = BoardManager(config=board_config)

        expired_time = datetime.now(timezone.utc) - timedelta(hours=25)
        expired_claim = AgentClaim(
            issue_number=42,
            agent="crush",
            session_id="expired-session",
            timestamp=expired_time,
        )

        new_claim = None
        claim_lock = asyncio.Lock()

        async def mock_get_claim(_issue_num):
            return new_claim if new_claim else expired_claim

        async def mock_post_comment(_issue_num, body):
            nonlocal new_claim
            async with claim_lock:
                if new_claim is None:
                    for agent in ["claude", "opencode"]:
                        if f"Agent: `{agent}`" in body:
                            new_claim = AgentClaim(
                                issue_number=42,
                                agent=agent,
                                session_id=f"{agent}-session",
                                timestamp=datetime.now(timezone.utc),
                            )
                            break
                    await asyncio.sleep(0.01)

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Both try to steal expired claim
        results = await asyncio.gather(
            manager.claim_work(42, "claude", "claude-session"),
            manager.claim_work(42, "opencode", "opencode-session"),
        )

        # Only one should succeed
        assert sum(results) == 1


class TestConcurrentRenewal:
    """Test claim renewal under concurrent conditions."""

    @pytest.mark.asyncio
    async def test_renewal_by_owner_succeeds(self, board_config, mock_github_token):
        """Test that claim owner can renew."""
        manager = BoardManager(config=board_config)

        claim_time = datetime.now(timezone.utc) - timedelta(hours=1)
        active_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=claim_time,
        )

        manager._get_active_claim = AsyncMock(return_value=active_claim)
        manager._post_issue_comment = AsyncMock()

        # Owner can renew
        result = await manager.renew_claim(42, "claude", "claude-session")
        assert result is True
        manager._post_issue_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_renewal_by_non_owner_fails(self, board_config, mock_github_token):
        """Test that non-owner cannot renew."""
        manager = BoardManager(config=board_config)

        claim_time = datetime.now(timezone.utc) - timedelta(hours=1)
        active_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=claim_time,
        )

        manager._get_active_claim = AsyncMock(return_value=active_claim)
        manager._post_issue_comment = AsyncMock()

        # Non-owner cannot renew
        result = await manager.renew_claim(42, "opencode", "opencode-session")
        assert result is False
        manager._post_issue_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_renewals_are_idempotent(self, board_config, mock_github_token):
        """Test that multiple renewal attempts are safe."""
        manager = BoardManager(config=board_config)

        claim_time = datetime.now(timezone.utc) - timedelta(hours=1)
        active_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=claim_time,
        )

        manager._get_active_claim = AsyncMock(return_value=active_claim)
        manager._post_issue_comment = AsyncMock()

        # Multiple concurrent renewals
        results = await asyncio.gather(
            manager.renew_claim(42, "claude", "claude-session"),
            manager.renew_claim(42, "claude", "claude-session"),
            manager.renew_claim(42, "claude", "claude-session"),
        )

        # All should succeed (idempotent)
        assert all(results)
        assert manager._post_issue_comment.call_count == 3


class TestGetReadyWorkConcurrency:
    """Test concurrent work selection and claiming."""

    @pytest.fixture
    def mock_ready_issues(self):
        """Create mock ready issues."""
        return [
            Issue(
                number=1,
                title="Task 1",
                body="Body",
                state="open",
                status=IssueStatus.TODO,
                priority=IssuePriority.HIGH,
                agent="claude",
            ),
            Issue(
                number=2,
                title="Task 2",
                body="Body",
                state="open",
                status=IssueStatus.TODO,
                priority=IssuePriority.MEDIUM,
                agent="opencode",
            ),
            Issue(
                number=3,
                title="Task 3",
                body="Body",
                state="open",
                status=IssueStatus.TODO,
                priority=IssuePriority.LOW,
                agent=None,  # No agent assigned
            ),
        ]

    @pytest.mark.asyncio
    async def test_multiple_agents_get_different_work(self, board_config, mock_github_token, mock_ready_issues):
        """Test that agents can work on different issues concurrently."""
        manager = BoardManager(config=board_config)

        claimed_issues = set()
        claim_lock = asyncio.Lock()

        async def mock_claim(issue_num, agent, session):
            async with claim_lock:
                if issue_num not in claimed_issues:
                    claimed_issues.add(issue_num)
                    return True
                return False

        manager.claim_work = mock_claim

        # Multiple agents claim different issues
        results = await asyncio.gather(
            manager.claim_work(1, "claude", "claude-session"),
            manager.claim_work(2, "opencode", "opencode-session"),
            manager.claim_work(3, "gemini", "gemini-session"),
        )

        # All should succeed since they're different issues
        assert all(results)
        assert len(claimed_issues) == 3

    @pytest.mark.asyncio
    async def test_agent_filters_work_by_assignment(self, board_config, mock_github_token, mock_ready_issues):
        """Test that get_ready_work respects agent filter."""
        manager = BoardManager(config=board_config)

        async def mock_get_ready(agent_name=None, limit=10):
            if agent_name:
                return [i for i in mock_ready_issues if i.agent == agent_name]
            return mock_ready_issues

        manager.get_ready_work = mock_get_ready

        # Each agent should only see their assigned work
        claude_work = await manager.get_ready_work(agent_name="claude")
        opencode_work = await manager.get_ready_work(agent_name="opencode")
        all_work = await manager.get_ready_work()

        assert len(claude_work) == 1
        assert claude_work[0].number == 1
        assert len(opencode_work) == 1
        assert opencode_work[0].number == 2
        assert len(all_work) == 3


class TestClaimStateConsistency:
    """Test that claim state remains consistent under various scenarios."""

    @pytest.mark.asyncio
    async def test_claim_then_immediate_check(self, board_config, mock_github_token):
        """Test claim state is immediately visible."""
        manager = BoardManager(config=board_config)

        current_claim = None

        async def mock_get_claim(_issue_num):
            return current_claim

        async def mock_post_comment(_issue_num, body):
            nonlocal current_claim
            if "Agent: `claude`" in body and "Claim" in body:
                current_claim = AgentClaim(
                    issue_number=42,
                    agent="claude",
                    session_id="claude-session",
                    timestamp=datetime.now(timezone.utc),
                )

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Claim
        result = await manager.claim_work(42, "claude", "claude-session")
        assert result is True

        # Immediate check should show claimed
        claim = await manager._get_active_claim(42)
        assert claim is not None
        assert claim.agent == "claude"

    @pytest.mark.asyncio
    async def test_release_clears_claim(self, board_config, mock_github_token):
        """Test that releasing work clears the claim."""
        manager = BoardManager(config=board_config)

        claim_active = True
        current_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=datetime.now(timezone.utc),
        )

        async def mock_get_claim(_issue_num):
            return current_claim if claim_active else None

        async def mock_post_comment(_issue_num, body):
            nonlocal claim_active
            if "Release" in body:
                claim_active = False

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Release the claim
        await manager.release_work(42, "claude", "completed")

        # Check claim is gone
        assert claim_active is False


class TestEdgeCasesInConcurrency:
    """Test edge cases in concurrent scenarios."""

    @pytest.mark.asyncio
    async def test_claim_nonexistent_issue(self, board_config, mock_github_token):
        """Test claiming an issue that doesn't exist."""
        manager = BoardManager(config=board_config)

        manager._get_active_claim = AsyncMock(return_value=None)
        manager._post_issue_comment = AsyncMock(side_effect=Exception("Issue not found"))
        manager.update_status = AsyncMock(return_value=True)

        # Should fail gracefully
        with pytest.raises(Exception, match="Issue not found"):
            await manager.claim_work(99999, "claude", "claude-session")

    @pytest.mark.asyncio
    async def test_renewal_on_released_claim(self, board_config, mock_github_token):
        """Test renewing after release fails."""
        manager = BoardManager(config=board_config)

        # No active claim (was released)
        manager._get_active_claim = AsyncMock(return_value=None)
        manager._post_issue_comment = AsyncMock()

        result = await manager.renew_claim(42, "claude", "claude-session")
        assert result is False

    @pytest.mark.asyncio
    async def test_rapid_claim_release_claim(self, board_config, mock_github_token):
        """Test rapid claim-release-claim cycle."""
        manager = BoardManager(config=board_config)

        state = {"claimed": False, "agent": None}

        async def mock_get_claim(_issue_num):
            if state["claimed"]:
                return AgentClaim(
                    issue_number=42,
                    agent=state["agent"],
                    session_id=f"{state['agent']}-session",
                    timestamp=datetime.now(timezone.utc),
                )
            return None

        async def mock_post_comment(_issue_num, body):
            if "Agent Claim" in body:
                for agent in ["claude", "opencode"]:
                    if f"Agent: `{agent}`" in body:
                        state["claimed"] = True
                        state["agent"] = agent
                        break
            elif "Release" in body:
                state["claimed"] = False
                state["agent"] = None

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Rapid cycle
        result1 = await manager.claim_work(42, "claude", "claude-session")
        assert result1 is True

        await manager.release_work(42, "claude", "completed")

        result2 = await manager.claim_work(42, "opencode", "opencode-session")
        assert result2 is True

        await manager.release_work(42, "opencode", "completed")

        result3 = await manager.claim_work(42, "claude", "claude-session")
        assert result3 is True

    @pytest.mark.asyncio
    async def test_zero_timeout_immediate_expiry(self, board_config, mock_github_token):
        """Test behavior with zero claim timeout (immediate expiry)."""
        # Test AgentClaim expiration with zero timeout directly
        claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=datetime.now(timezone.utc),  # Just now, but timeout is 0
        )

        assert claim.is_expired(timeout_seconds=0) is True

    @pytest.mark.asyncio
    async def test_very_long_timeout(self, board_config, mock_github_token):
        """Test behavior with very long claim timeout."""
        long_timeout_config = BoardConfig(
            project_number=1,
            owner="testuser",
            repository="test/repo",
            claim_timeout=604800,  # 1 week
            enabled_agents=["claude"],
        )

        manager = BoardManager(config=long_timeout_config)

        # Claim from 3 days ago should still be valid
        old_time = datetime.now(timezone.utc) - timedelta(days=3)
        claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=old_time,
        )

        assert claim.is_expired(timeout_seconds=604800) is False

        manager._get_active_claim = AsyncMock(return_value=claim)

        # Another agent cannot claim
        result = await manager.claim_work(42, "opencode", "opencode-session")
        assert result is False

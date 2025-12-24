"""Error recovery tests for claim expiration and failure paths.

Tests the BoardManager's resilience to failures, including network errors,
claim expiration, partial operation failures, and agent crashes.
"""

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import AsyncMock, patch

import pytest

from github_agents.board.config import BoardConfig
from github_agents.board.errors import GraphQLError, RateLimitError
from github_agents.board.manager import BoardManager
from github_agents.board.models import AgentClaim, IssueStatus


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
        enabled_agents=["claude", "opencode", "gemini"],
    )


@pytest.fixture
def mock_github_token():
    """Mock GitHub token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
        yield "test-token"


class TestClaimExpirationRecovery:
    """Test recovery from claim expiration scenarios."""

    @pytest.mark.asyncio
    async def test_expired_claim_is_detected(self, board_config, mock_github_token):
        """Test that expired claims are properly detected."""
        # Claim from 25 hours ago (past 24h timeout)
        expired_time = datetime.now(timezone.utc) - timedelta(hours=25)
        expired_claim = AgentClaim(
            issue_number=42,
            agent="opencode",
            session_id="old-session",
            timestamp=expired_time,
        )

        assert expired_claim.is_expired(board_config.claim_timeout) is True

    @pytest.mark.asyncio
    async def test_claim_renewal_resets_expiration(self, board_config, mock_github_token):
        """Test that renewal resets the expiration clock."""
        # Claim from 20 hours ago
        claim_time = datetime.now(timezone.utc) - timedelta(hours=20)
        # Renewed 1 hour ago
        renewal_time = datetime.now(timezone.utc) - timedelta(hours=1)

        claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=claim_time,
            renewed_at=renewal_time,
        )

        # Without renewal, claim would be 20 hours old
        # With renewal, it's only 1 hour old
        age = claim.age_seconds()
        assert 3500 < age < 3700  # ~1 hour in seconds

        # Should not be expired
        assert claim.is_expired(board_config.claim_timeout) is False

    @pytest.mark.asyncio
    async def test_missed_renewal_causes_expiration(self, board_config, mock_github_token):
        """Test that missing renewals cause claim expiration."""
        # Claim from 20 hours ago
        claim_time = datetime.now(timezone.utc) - timedelta(hours=20)
        # Last renewal was 5 hours ago
        renewal_time = datetime.now(timezone.utc) - timedelta(hours=5)

        claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=claim_time,
            renewed_at=renewal_time,
        )

        # Use short timeout to simulate expiration
        short_timeout = 3600  # 1 hour
        assert claim.is_expired(short_timeout) is True

    @pytest.mark.asyncio
    async def test_work_recovery_after_agent_abandonment(self, board_config, mock_github_token):
        """Test that work can be recovered after agent abandons it."""
        manager = BoardManager(config=board_config)

        # Original agent claimed 25 hours ago and never came back
        abandoned_time = datetime.now(timezone.utc) - timedelta(hours=25)
        abandoned_claim = AgentClaim(
            issue_number=42,
            agent="crush",
            session_id="abandoned-session",
            timestamp=abandoned_time,
        )

        new_claim = None

        async def mock_get_claim(_issue_num):
            return new_claim if new_claim else abandoned_claim

        async def mock_post_comment(_issue_num, body):
            nonlocal new_claim
            if "Agent: `opencode`" in body:
                new_claim = AgentClaim(
                    issue_number=42,
                    agent="opencode",
                    session_id="recovery-session",
                    timestamp=datetime.now(timezone.utc),
                )

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # New agent can take over
        result = await manager.claim_work(42, "opencode", "recovery-session")
        assert result is True
        assert new_claim.agent == "opencode"


class TestNetworkFailureRecovery:
    """Test recovery from network failures."""

    @pytest.mark.asyncio
    async def test_graphql_retry_on_transient_error(self, board_config, mock_github_token):
        """Test that transient errors trigger retry."""
        manager = BoardManager(config=board_config)
        manager.session = AsyncMock()

        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise GraphQLError("Server temporarily unavailable", status_code=503)
            from github_agents.board.models import GraphQLResponse

            return GraphQLResponse(data={"success": True}, status_code=200)

        result = await manager._execute_with_retry(mock_operation)
        assert result.data == {"success": True}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_graphql_max_retries_exceeded(self, board_config, mock_github_token):
        """Test that max retries raises error."""
        manager = BoardManager(config=board_config)

        async def always_fail():
            raise GraphQLError("Persistent failure", status_code=503)

        with pytest.raises(GraphQLError, match="Persistent failure"):
            await manager._execute_with_retry(always_fail)

    @pytest.mark.asyncio
    async def test_rate_limit_not_retried(self, board_config, mock_github_token):
        """Test that rate limit errors are raised immediately."""
        manager = BoardManager(config=board_config)

        async def rate_limited():
            from github_agents.board.models import GraphQLResponse

            return GraphQLResponse(
                data=None,
                errors=[{"message": "API rate limit exceeded"}],
                status_code=403,
            )

        with pytest.raises(RateLimitError):
            await manager._execute_with_retry(rate_limited)

    @pytest.mark.asyncio
    async def test_auth_error_not_retried(self, board_config, mock_github_token):
        """Test that authentication errors are not retried."""
        manager = BoardManager(config=board_config)

        async def auth_failed():
            raise GraphQLError("Bad credentials", status_code=401)

        with pytest.raises(GraphQLError, match="Bad credentials"):
            await manager._execute_with_retry(auth_failed)

    @pytest.mark.asyncio
    async def test_claim_fails_gracefully_on_network_error(self, board_config, mock_github_token):
        """Test claim failure handling on network errors."""
        manager = BoardManager(config=board_config)

        manager._get_active_claim = AsyncMock(return_value=None)
        manager._post_issue_comment = AsyncMock(side_effect=GraphQLError("Network unreachable"))
        manager.update_status = AsyncMock(return_value=True)

        with pytest.raises(GraphQLError, match="Network unreachable"):
            await manager.claim_work(42, "claude", "claude-session")


class TestPartialOperationFailure:
    """Test recovery from partial operation failures."""

    @pytest.mark.asyncio
    async def test_claim_posted_but_status_update_fails(self, board_config, mock_github_token):
        """Test handling when claim comment succeeds but status update fails."""
        manager = BoardManager(config=board_config)

        manager._get_active_claim = AsyncMock(return_value=None)
        manager._post_issue_comment = AsyncMock()  # Succeeds
        manager.update_status = AsyncMock(side_effect=GraphQLError("Field not found"))

        # Claim should still raise error due to status update failure
        with pytest.raises(GraphQLError, match="Field not found"):
            await manager.claim_work(42, "claude", "claude-session")

        # But comment was posted
        manager._post_issue_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_posted_but_status_update_fails(self, board_config, mock_github_token):
        """Test handling when release comment succeeds but status update fails."""
        manager = BoardManager(config=board_config)

        manager._post_issue_comment = AsyncMock()  # Succeeds
        manager.update_status = AsyncMock(side_effect=GraphQLError("Status field error"))

        with pytest.raises(GraphQLError, match="Status field error"):
            await manager.release_work(42, "claude", "completed")

        # Comment was posted
        manager._post_issue_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_renewal_comment_failure_is_recoverable(self, board_config, mock_github_token):
        """Test that failed renewal can be retried."""
        manager = BoardManager(config=board_config)

        claim_time = datetime.now(timezone.utc) - timedelta(hours=1)
        active_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=claim_time,
        )

        manager._get_active_claim = AsyncMock(return_value=active_claim)

        call_count = 0

        async def flaky_post_comment(_issue_num, _body):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GraphQLError("Temporary failure")
            # Second call succeeds

        manager._post_issue_comment = flaky_post_comment

        # First try fails
        with pytest.raises(GraphQLError, match="Temporary failure"):
            await manager.renew_claim(42, "claude", "claude-session")

        # Second try succeeds
        result = await manager.renew_claim(42, "claude", "claude-session")
        assert result is True


class TestAgentCrashRecovery:
    """Test recovery from agent crash scenarios."""

    @pytest.mark.asyncio
    async def test_claim_persists_after_agent_restart(self, board_config, mock_github_token):
        """Test that claim is still valid after agent restarts."""
        manager = BoardManager(config=board_config)

        # Simulate claim made before restart (2 hours ago)
        claim_time = datetime.now(timezone.utc) - timedelta(hours=2)
        existing_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="original-session",
            timestamp=claim_time,
        )

        manager._get_active_claim = AsyncMock(return_value=existing_claim)
        manager._post_issue_comment = AsyncMock()

        # After restart, same agent tries to renew
        # Note: session ID may differ after restart
        result = await manager.renew_claim(42, "claude", "new-session")

        # Should succeed because agent name matches
        # (session ID mismatch is acceptable for renewal)
        assert result is True

    @pytest.mark.asyncio
    async def test_claim_stolen_after_long_crash(self, board_config, mock_github_token):
        """Test that another agent can take over after long crash."""
        manager = BoardManager(config=board_config)

        # Original agent crashed 26 hours ago
        crash_time = datetime.now(timezone.utc) - timedelta(hours=26)
        crashed_agent_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="crashed-session",
            timestamp=crash_time,
        )

        new_claim = None

        async def mock_get_claim(_issue_num):
            return new_claim if new_claim else crashed_agent_claim

        async def mock_post_comment(_issue_num, body):
            nonlocal new_claim
            if "Agent: `opencode`" in body:
                new_claim = AgentClaim(
                    issue_number=42,
                    agent="opencode",
                    session_id="takeover-session",
                    timestamp=datetime.now(timezone.utc),
                )

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = mock_post_comment
        manager.update_status = AsyncMock(return_value=True)

        # Different agent can claim
        result = await manager.claim_work(42, "opencode", "takeover-session")
        assert result is True

    @pytest.mark.asyncio
    async def test_crashed_agent_cannot_reclaim(self, board_config, mock_github_token):
        """Test that crashed agent cannot reclaim work taken by another."""
        manager = BoardManager(config=board_config)

        # Another agent already claimed
        current_claim = AgentClaim(
            issue_number=42,
            agent="opencode",
            session_id="takeover-session",
            timestamp=datetime.now(timezone.utc),
        )

        manager._get_active_claim = AsyncMock(return_value=current_claim)

        # Crashed agent (claude) tries to claim when it comes back
        result = await manager.claim_work(42, "claude", "recovery-session")
        assert result is False


class TestStatusRecoveryPaths:
    """Test status transitions during error recovery."""

    @pytest.mark.asyncio
    async def test_blocked_work_returns_to_todo_on_abandonment(self, board_config, mock_github_token):
        """Test that abandoned blocked work returns to todo."""
        manager = BoardManager(config=board_config)

        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        await manager.release_work(42, "claude", reason="abandoned")

        manager.update_status.assert_called_once_with(42, IssueStatus.TODO)

    @pytest.mark.asyncio
    async def test_error_release_returns_to_todo(self, board_config, mock_github_token):
        """Test that work released due to error returns to todo."""
        manager = BoardManager(config=board_config)

        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        await manager.release_work(42, "claude", reason="error")

        manager.update_status.assert_called_once_with(42, IssueStatus.TODO)

    @pytest.mark.asyncio
    async def test_completed_release_sets_done(self, board_config, mock_github_token):
        """Test that completed work is marked done."""
        manager = BoardManager(config=board_config)

        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        await manager.release_work(42, "claude", reason="completed")

        manager.update_status.assert_called_once_with(42, IssueStatus.DONE)

    @pytest.mark.asyncio
    async def test_blocked_release_sets_blocked(self, board_config, mock_github_token):
        """Test that blocked release sets blocked status."""
        manager = BoardManager(config=board_config)

        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        await manager.release_work(42, "claude", reason="blocked")

        manager.update_status.assert_called_once_with(42, IssueStatus.BLOCKED)


class TestClaimCommentParsing:
    """Test robustness of claim comment parsing."""

    def test_parse_claim_comment_valid(self, board_config, mock_github_token):
        """Test parsing valid claim comment."""
        manager = BoardManager(config=board_config)

        body = """🤖 **[Agent Claim]**

Agent: `claude`
Started: `2025-10-25T14:30:00Z`
Session ID: `session-123`

Claiming this issue for implementation."""

        claim = manager._parse_claim_comment(42, body, "2025-10-25T14:30:00Z")

        assert claim is not None
        assert claim.agent == "claude"
        assert claim.session_id == "session-123"

    def test_parse_claim_comment_missing_agent(self, board_config, mock_github_token):
        """Test parsing claim comment missing agent returns None."""
        manager = BoardManager(config=board_config)

        body = """🤖 **[Agent Claim]**

Started: `2025-10-25T14:30:00Z`
Session ID: `session-123`"""

        claim = manager._parse_claim_comment(42, body, "2025-10-25T14:30:00Z")
        assert claim is None

    def test_parse_claim_comment_missing_session(self, board_config, mock_github_token):
        """Test parsing claim comment missing session returns None."""
        manager = BoardManager(config=board_config)

        body = """🤖 **[Agent Claim]**

Agent: `claude`
Started: `2025-10-25T14:30:00Z`"""

        claim = manager._parse_claim_comment(42, body, "2025-10-25T14:30:00Z")
        assert claim is None

    def test_parse_claim_comment_invalid_timestamp(self, board_config, mock_github_token):
        """Test parsing claim comment with invalid timestamp."""
        manager = BoardManager(config=board_config)

        body = """🤖 **[Agent Claim]**

Agent: `claude`
Started: `not-a-date`
Session ID: `session-123`"""

        claim = manager._parse_claim_comment(42, body, "2025-10-25T14:30:00Z")
        assert claim is None

    def test_parse_renewal_comment(self, board_config, mock_github_token):
        """Test parsing renewal comment."""
        manager = BoardManager(config=board_config)

        body = """🔄 **[Claim Renewal]**

Agent: `claude`
Renewed: `2025-10-25T16:30:00Z`
Session ID: `session-123`

Claim renewed - still actively working on this issue."""

        claim = manager._parse_claim_comment(42, body, "2025-10-25T16:30:00Z")

        assert claim is not None
        assert claim.agent == "claude"


class TestMultipleFailureScenarios:
    """Test handling of multiple simultaneous failures."""

    @pytest.mark.asyncio
    async def test_get_claim_fails_during_claim_attempt(self, board_config, mock_github_token):
        """Test handling when get_claim fails during claim."""
        manager = BoardManager(config=board_config)

        manager._get_active_claim = AsyncMock(side_effect=GraphQLError("Query failed"))

        with pytest.raises(GraphQLError, match="Query failed"):
            await manager.claim_work(42, "claude", "claude-session")

    @pytest.mark.asyncio
    async def test_multiple_errors_in_sequence(self, board_config, mock_github_token):
        """Test handling multiple sequential errors."""
        manager = BoardManager(config=board_config)

        errors = [
            GraphQLError("First error"),
            GraphQLError("Second error"),
            None,  # Success
        ]
        error_idx = 0

        async def mock_get_claim(_issue_num):
            nonlocal error_idx
            if error_idx < len(errors) and errors[error_idx]:
                error = errors[error_idx]
                error_idx += 1
                raise error
            error_idx += 1
            return None

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        # First two attempts fail
        with pytest.raises(GraphQLError, match="First error"):
            await manager.claim_work(42, "claude", "session-1")

        with pytest.raises(GraphQLError, match="Second error"):
            await manager.claim_work(42, "claude", "session-2")

        # Third succeeds
        result = await manager.claim_work(42, "claude", "session-3")
        assert result is True


class TestEdgeCasesInRecovery:
    """Test edge cases in failure recovery."""

    @pytest.mark.asyncio
    async def test_claim_with_empty_session_id(self, board_config, mock_github_token):
        """Test claim with empty session ID."""
        manager = BoardManager(config=board_config)

        manager._get_active_claim = AsyncMock(return_value=None)
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        # Empty session ID should still work
        result = await manager.claim_work(42, "claude", "")
        assert result is True

    @pytest.mark.asyncio
    async def test_claim_with_special_characters_in_session(self, board_config, mock_github_token):
        """Test claim with special characters in session ID."""
        manager = BoardManager(config=board_config)

        manager._get_active_claim = AsyncMock(return_value=None)
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        # Session ID with special characters
        special_session = "session-123-abc_def:456/789"
        result = await manager.claim_work(42, "claude", special_session)
        assert result is True

    @pytest.mark.asyncio
    async def test_renewal_exactly_at_timeout(self, board_config, mock_github_token):
        """Test renewal when claim is exactly at timeout boundary."""
        # Claim exactly 24 hours old
        exact_time = datetime.now(timezone.utc) - timedelta(seconds=86400)
        boundary_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=exact_time,
        )

        # At exactly timeout, is_expired should return True
        assert boundary_claim.is_expired(86400) is True

    @pytest.mark.asyncio
    async def test_renewal_just_before_timeout(self, board_config, mock_github_token):
        """Test renewal when claim is just before timeout."""
        manager = BoardManager(config=board_config)

        # Claim 1 second before timeout
        near_time = datetime.now(timezone.utc) - timedelta(seconds=86399)
        near_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=near_time,
        )

        # Just before timeout, should still be valid
        # Note: there's a small race condition window here in real code
        assert near_claim.is_expired(86400) is False

        manager._get_active_claim = AsyncMock(return_value=near_claim)
        manager._post_issue_comment = AsyncMock()

        # Renewal should succeed
        result = await manager.renew_claim(42, "claude", "claude-session")
        assert result is True

    @pytest.mark.asyncio
    async def test_future_timestamp_handling(self, board_config, mock_github_token):
        """Test handling of future timestamps (clock skew)."""
        # Claim with future timestamp (server clock ahead)
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        future_claim = AgentClaim(
            issue_number=42,
            agent="claude",
            session_id="claude-session",
            timestamp=future_time,
        )

        # Future claim would have negative age
        age = future_claim.age_seconds()
        assert age < 0

        # Should not be expired
        assert future_claim.is_expired(86400) is False

"""Tests for board manager functionality."""

# pylint: disable=protected-access  # Testing protected members is legitimate in tests

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_agents.board.config import BoardConfig
from github_agents.board.errors import BoardNotFoundError, GraphQLError, RateLimitError
from github_agents.board.manager import BoardManager
from github_agents.board.models import (
    AgentClaim,
    DependencyGraph,
    GraphQLResponse,
    Issue,
    IssuePriority,
    IssueStatus,
)


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
        claim_timeout=86400,
        enabled_agents=["claude", "opencode"],
    )


@pytest.fixture
def _mock_github_token():
    """Mock GitHub token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
        yield "test-token"


class TestBoardConfig:
    """Test BoardConfig model."""

    def test_initialization(self):
        """Test BoardConfig initialization."""
        config = BoardConfig(project_number=1, owner="testuser", repository="test/repo")
        assert config.project_number == 1
        assert config.owner == "testuser"
        assert config.repository == "test/repo"
        assert config.claim_timeout == 86400
        assert config.claim_renewal_interval == 3600

    def test_default_field_mappings(self):
        """Test default field mappings are set."""
        config = BoardConfig(project_number=1, owner="testuser", repository="test/repo")
        assert config.field_mappings["status"] == "Status"
        assert config.field_mappings["priority"] == "Priority"
        assert config.field_mappings["agent"] == "Agent"
        assert config.field_mappings["type"] == "Type"
        assert config.field_mappings["blocked_by"] == "Blocked By"
        assert config.field_mappings["discovered_from"] == "Discovered From"
        assert config.field_mappings["size"] == "Estimated Size"

    def test_from_dict(self):
        """Test creating BoardConfig from dictionary."""
        data = {
            "project": {"number": 5, "owner": "org"},
            "repository": "org/repo",
            "fields": {"status": "CustomStatus"},
            "agents": {"enabled_agents": ["claude"], "auto_discover": True},
            "work_claims": {"timeout": 3600, "renewal_interval": 1800},
            "work_queue": {
                "exclude_labels": ["wontfix"],
                "priority_labels": {"critical": ["security"]},
            },
        }

        config = BoardConfig.from_dict(data)
        assert config.project_number == 5
        assert config.owner == "org"
        assert config.repository == "org/repo"
        assert config.field_mappings["status"] == "CustomStatus"
        assert config.claim_timeout == 3600
        assert config.claim_renewal_interval == 1800
        assert "claude" in config.enabled_agents
        assert config.auto_discover is True
        assert "wontfix" in config.exclude_labels
        assert "security" in config.priority_labels["critical"]


class TestIssue:
    """Test Issue model."""

    def test_initialization(self):
        """Test Issue initialization."""
        issue = Issue(number=1, title="Test Issue", body="Test body", state="open")
        assert issue.number == 1
        assert issue.title == "Test Issue"
        assert issue.body == "Test body"
        assert issue.state == "open"
        assert issue.status == IssueStatus.TODO
        assert issue.priority == IssuePriority.MEDIUM

    def test_is_ready_true(self):
        """Test is_ready returns True for unblocked Todo issue."""
        issue = Issue(number=1, title="Test", body="Body", state="open", status=IssueStatus.TODO, blocked_by=[])
        assert issue.is_ready() is True

    def test_is_ready_false_blocked(self):
        """Test is_ready returns False when blocked."""
        issue = Issue(number=1, title="Test", body="Body", state="open", status=IssueStatus.TODO, blocked_by=[2, 3])
        assert issue.is_ready() is False

    def test_is_ready_false_wrong_status(self):
        """Test is_ready returns False for non-Todo status."""
        issue = Issue(number=1, title="Test", body="Body", state="open", status=IssueStatus.IN_PROGRESS, blocked_by=[])
        assert issue.is_ready() is False

    def test_is_claimed_true(self):
        """Test is_claimed returns True when agent assigned."""
        issue = Issue(number=1, title="Test", body="Body", state="open", agent="claude")
        assert issue.is_claimed() is True

    def test_is_claimed_false(self):
        """Test is_claimed returns False when no agent."""
        issue = Issue(number=1, title="Test", body="Body", state="open", agent=None)
        assert issue.is_claimed() is False

    def test_string_representation(self):
        """Test __str__ method."""
        issue = Issue(number=42, title="Fix Bug", body="Body", state="open", status=IssueStatus.TODO)
        assert str(issue) == "Issue #42: Fix Bug (Todo)"


class TestAgentClaim:
    """Test AgentClaim model."""

    def test_initialization(self):
        """Test AgentClaim initialization."""
        now = datetime.now(timezone.utc)
        claim = AgentClaim(issue_number=1, agent="claude", session_id="session123", timestamp=now)
        assert claim.issue_number == 1
        assert claim.agent == "claude"
        assert claim.session_id == "session123"
        assert claim.timestamp == now
        assert claim.renewed_at is None
        assert claim.released is False

    def test_age_seconds(self):
        """Test age_seconds calculation."""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=3600)
        claim = AgentClaim(issue_number=1, agent="claude", session_id="s1", timestamp=old_time)
        age = claim.age_seconds()
        assert 3590 < age < 3610  # Allow 10 second tolerance

    def test_age_seconds_with_renewal(self):
        """Test age_seconds uses renewed_at when available."""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=7200)
        renewed_time = datetime.now(timezone.utc) - timedelta(seconds=1800)
        claim = AgentClaim(
            issue_number=1,
            agent="claude",
            session_id="s1",
            timestamp=old_time,
            renewed_at=renewed_time,
        )
        age = claim.age_seconds()
        assert 1790 < age < 1810  # Uses renewed_at, not timestamp

    def test_is_expired_true(self):
        """Test is_expired returns True for old claim."""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=90000)  # >24 hours
        claim = AgentClaim(issue_number=1, agent="claude", session_id="s1", timestamp=old_time)
        assert claim.is_expired(timeout_seconds=86400) is True

    def test_is_expired_false(self):
        """Test is_expired returns False for recent claim."""
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=3600)  # 1 hour
        claim = AgentClaim(issue_number=1, agent="claude", session_id="s1", timestamp=recent_time)
        assert claim.is_expired(timeout_seconds=86400) is False


class TestDependencyGraph:
    """Test DependencyGraph model."""

    def test_initialization(self):
        """Test DependencyGraph initialization."""
        issue = Issue(number=1, title="Main", body="Body", state="open")
        graph = DependencyGraph(issue=issue)
        assert graph.issue == issue
        assert not graph.blocks
        assert not graph.blocked_by
        assert not graph.children
        assert graph.parent is None

    def test_is_ready_no_blockers(self):
        """Test is_ready returns True when no blockers."""
        issue = Issue(number=1, title="Main", body="Body", state="open")
        graph = DependencyGraph(issue=issue)
        assert graph.is_ready() is True

    def test_is_ready_all_resolved(self):
        """Test is_ready returns True when all blockers resolved."""
        issue = Issue(number=1, title="Main", body="Body", state="open")
        blocker1 = Issue(number=2, title="B1", body="Body", state="closed", status=IssueStatus.DONE)
        blocker2 = Issue(number=3, title="B2", body="Body", state="closed", status=IssueStatus.ABANDONED)
        graph = DependencyGraph(issue=issue, blocked_by=[blocker1, blocker2])
        assert graph.is_ready() is True

    def test_is_ready_has_open_blocker(self):
        """Test is_ready returns False when blocker is open."""
        issue = Issue(number=1, title="Main", body="Body", state="open")
        blocker = Issue(number=2, title="Blocker", body="Body", state="open", status=IssueStatus.TODO)
        graph = DependencyGraph(issue=issue, blocked_by=[blocker])
        assert graph.is_ready() is False

    def test_depth_no_parent(self):
        """Test depth returns 0 when no parent."""
        issue = Issue(number=1, title="Main", body="Body", state="open")
        graph = DependencyGraph(issue=issue)
        assert graph.depth() == 0

    def test_depth_with_parent(self):
        """Test depth returns 1 when has parent."""
        issue = Issue(number=1, title="Main", body="Body", state="open")
        parent = Issue(number=2, title="Parent", body="Body", state="open")
        graph = DependencyGraph(issue=issue, parent=parent)
        assert graph.depth() == 1


class TestGraphQLResponse:
    """Test GraphQLResponse model."""

    def test_initialization(self):
        """Test GraphQLResponse initialization."""
        response = GraphQLResponse(data={"test": "data"})
        assert response.data == {"test": "data"}
        assert not response.errors
        assert response.status_code == 200

    def test_is_success_true(self):
        """Test is_success returns True for successful response."""
        response = GraphQLResponse(data={"test": "data"}, status_code=200)
        assert response.is_success() is True

    def test_is_success_false_has_errors(self):
        """Test is_success returns False when errors present."""
        response = GraphQLResponse(
            data=None,
            errors=[{"message": "Error"}],
            status_code=200,
        )
        assert response.is_success() is False

    def test_is_success_false_bad_status(self):
        """Test is_success returns False for non-200 status."""
        response = GraphQLResponse(data=None, status_code=404)
        assert response.is_success() is False

    def test_get_error_message_no_errors(self):
        """Test get_error_message returns empty string when no errors."""
        response = GraphQLResponse(data={"test": "data"})
        assert response.get_error_message() == ""

    def test_get_error_message_single_error(self):
        """Test get_error_message returns single error message."""
        response = GraphQLResponse(data=None, errors=[{"message": "Something went wrong"}])
        assert response.get_error_message() == "Something went wrong"

    def test_get_error_message_multiple_errors(self):
        """Test get_error_message joins multiple errors."""
        response = GraphQLResponse(
            data=None,
            errors=[
                {"message": "Error 1"},
                {"message": "Error 2"},
            ],
        )
        assert response.get_error_message() == "Error 1; Error 2"


class TestBoardManager:
    """Test BoardManager functionality."""

    def test_initialization_no_token(self):
        """Test initialization fails without GitHub token."""
        with pytest.raises(ValueError, match="GitHub token required"):
            BoardManager(config=BoardConfig(project_number=1, owner="test", repository="test/repo"))

    def test_initialization_with_token(self, board_config, _mock_github_token):
        """Test initialization with GitHub token."""
        manager = BoardManager(config=board_config)
        assert manager.config == board_config
        assert manager.github_token == "test-token"
        assert manager.session is None
        assert manager.project_id is None

    @pytest.mark.asyncio
    async def test_context_manager(self, board_config, _mock_github_token):
        """Test async context manager."""
        manager = BoardManager(config=board_config)

        # Mock initialize and close
        manager.initialize = AsyncMock()
        manager.close = AsyncMock()

        async with manager as mgr:
            assert mgr == manager

        manager.initialize.assert_called_once()
        manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_graphql_not_initialized(self, board_config, _mock_github_token):
        """Test _execute_graphql raises error when not initialized."""
        manager = BoardManager(config=board_config)

        with pytest.raises(RuntimeError, match="BoardManager not initialized"):
            await manager._execute_graphql("query { test }")

    @pytest.mark.asyncio
    async def test_execute_graphql_success(self, board_config, _mock_github_token):
        """Test successful GraphQL execution."""
        manager = BoardManager(config=board_config)
        manager.session = AsyncMock()

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"test": "result"}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        manager.session.post = MagicMock(return_value=mock_response)

        response = await manager._execute_graphql("query { test }")
        assert response.data == {"test": "result"}
        assert response.status_code == 200
        assert response.errors == []

    @pytest.mark.asyncio
    async def test_execute_graphql_with_errors(self, board_config, _mock_github_token):
        """Test GraphQL execution with errors."""
        manager = BoardManager(config=board_config)
        manager.session = AsyncMock()

        # Mock response with errors
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": None,
                "errors": [{"message": "Field not found"}],
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        manager.session.post = MagicMock(return_value=mock_response)

        with pytest.raises(GraphQLError, match="Field not found"):
            await manager._execute_graphql("query { invalid }")

    @pytest.mark.asyncio
    async def test_execute_with_retry_rate_limit(self, board_config, _mock_github_token):
        """Test retry logic with rate limit error."""
        manager = BoardManager(config=board_config)

        # Mock operation that returns rate limit error
        async def mock_operation():
            return GraphQLResponse(
                data=None,
                errors=[{"message": "API rate limit exceeded"}],
                status_code=403,
            )

        with pytest.raises(RateLimitError):
            await manager._execute_with_retry(mock_operation)

    @pytest.mark.asyncio
    async def test_execute_with_retry_client_error(self, board_config, _mock_github_token):
        """Test retry logic with 401 client error (no retry)."""
        manager = BoardManager(config=board_config)

        # Mock operation that returns 401
        async def mock_operation():
            error = GraphQLError("Unauthorized", status_code=401)
            raise error

        with pytest.raises(GraphQLError, match="Unauthorized"):
            await manager._execute_with_retry(mock_operation)

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retry(self, board_config, _mock_github_token):
        """Test retry logic succeeds after transient failure."""
        manager = BoardManager(config=board_config)

        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails with server error
                raise GraphQLError("Server error", status_code=500)
            # Second call succeeds
            return GraphQLResponse(data={"success": True}, status_code=200)

        response = await manager._execute_with_retry(mock_operation)
        assert response.data == {"success": True}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_get_project_id_user_project(self, board_config, _mock_github_token):
        """Test _get_project_id for user project."""
        manager = BoardManager(config=board_config)
        manager._execute_graphql = AsyncMock(
            return_value=GraphQLResponse(
                data={
                    "user": {"projectV2": {"id": "PVT_kwDOABCDEF", "title": "Test Project"}},
                    "organization": None,
                }
            )
        )

        project_id = await manager._get_project_id()
        assert project_id == "PVT_kwDOABCDEF"

    @pytest.mark.asyncio
    async def test_get_project_id_org_project(self, board_config, _mock_github_token):
        """Test _get_project_id for organization project."""
        manager = BoardManager(config=board_config)
        manager._execute_graphql = AsyncMock(
            return_value=GraphQLResponse(
                data={
                    "user": None,
                    "organization": {"projectV2": {"id": "PVT_kwDOXYZ123", "title": "Org Project"}},
                }
            )
        )

        project_id = await manager._get_project_id()
        assert project_id == "PVT_kwDOXYZ123"

    @pytest.mark.asyncio
    async def test_get_project_id_not_found(self, board_config, _mock_github_token):
        """Test _get_project_id raises error when project not found."""
        manager = BoardManager(config=board_config)
        manager._execute_graphql = AsyncMock(return_value=GraphQLResponse(data={"user": None, "organization": None}))

        with pytest.raises(BoardNotFoundError, match="Project #1 not found for owner 'testuser'"):
            await manager._get_project_id()


class TestErrors:
    """Test custom error classes."""

    def test_board_not_found_error(self):
        """Test BoardNotFoundError initialization."""
        error = BoardNotFoundError(project_number=5, owner="testuser")
        assert error.project_number == 5
        assert error.owner == "testuser"
        assert "Project #5" in str(error)
        assert "testuser" in str(error)

    def test_graphql_error(self):
        """Test GraphQLError initialization."""
        error = GraphQLError("Test error", status_code=403)
        assert error.status_code == 403
        assert "HTTP 403" in str(error)
        assert "Test error" in str(error)

    def test_graphql_error_with_error_list(self):
        """Test GraphQLError with error list."""
        errors = [{"message": "Field invalid"}]
        error = GraphQLError("Multiple errors", errors=errors)
        assert error.errors == errors

    def test_rate_limit_error(self):
        """Test RateLimitError initialization."""
        error = RateLimitError(reset_at="2025-10-25T15:00:00Z", remaining=0)
        assert error.reset_at == "2025-10-25T15:00:00Z"
        assert error.remaining == 0
        assert "rate limit" in str(error).lower()
        assert "2025-10-25T15:00:00Z" in str(error)


class TestClaimMechanism:
    """Test claim/release/renewal mechanisms (Phase 2)."""

    @pytest.mark.asyncio
    async def test_claim_work_success(self, board_config, _mock_github_token):
        """Test successful work claim."""
        manager = BoardManager(config=board_config)
        manager._post_issue_comment = AsyncMock()
        manager._get_active_claim = AsyncMock(return_value=None)
        manager.update_status = AsyncMock(return_value=True)
        manager._assign_to_agent = AsyncMock(return_value=True)

        success = await manager.claim_work(45, "claude", "session-123")

        assert success is True
        manager._post_issue_comment.assert_called_once()
        manager.update_status.assert_called_once_with(45, IssueStatus.IN_PROGRESS)

    @pytest.mark.asyncio
    async def test_claim_work_already_claimed(self, board_config, _mock_github_token):
        """Test claim rejection when already claimed."""
        manager = BoardManager(config=board_config)

        # Mock existing valid claim
        existing_claim = AgentClaim(
            issue_number=45,
            agent="opencode",
            session_id="other-session",
            timestamp=datetime.now(timezone.utc),
        )
        manager._get_active_claim = AsyncMock(return_value=existing_claim)

        success = await manager.claim_work(45, "claude", "session-123")

        assert success is False

    @pytest.mark.asyncio
    async def test_claim_work_expired_claim(self, board_config, _mock_github_token):
        """Test claim succeeds when previous claim expired."""
        manager = BoardManager(config=board_config)
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)
        manager._assign_to_agent = AsyncMock(return_value=True)

        # Mock expired claim
        old_time = datetime.now(timezone.utc) - timedelta(seconds=90000)  # >24 hours
        expired_claim = AgentClaim(
            issue_number=45,
            agent="opencode",
            session_id="old-session",
            timestamp=old_time,
        )
        manager._get_active_claim = AsyncMock(return_value=expired_claim)

        success = await manager.claim_work(45, "claude", "session-123")

        assert success is True

    @pytest.mark.asyncio
    async def test_renew_claim_success(self, board_config, _mock_github_token):
        """Test successful claim renewal."""
        manager = BoardManager(config=board_config)
        manager._post_issue_comment = AsyncMock()

        # Mock active claim by the same agent
        active_claim = AgentClaim(
            issue_number=45,
            agent="claude",
            session_id="session-123",
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=3600),
        )
        manager._get_active_claim = AsyncMock(return_value=active_claim)

        success = await manager.renew_claim(45, "claude", "session-123")

        assert success is True
        manager._post_issue_comment.assert_called_once()
        # Check renewal comment format
        call_args = manager._post_issue_comment.call_args
        assert "Claim Renewal" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_renew_claim_wrong_agent(self, board_config, _mock_github_token):
        """Test renewal fails when wrong agent tries."""
        manager = BoardManager(config=board_config)

        # Mock claim by different agent
        other_claim = AgentClaim(
            issue_number=45,
            agent="opencode",
            session_id="other-session",
            timestamp=datetime.now(timezone.utc),
        )
        manager._get_active_claim = AsyncMock(return_value=other_claim)

        success = await manager.renew_claim(45, "claude", "session-123")

        assert success is False

    @pytest.mark.asyncio
    async def test_renew_claim_no_active_claim(self, board_config, _mock_github_token):
        """Test renewal fails when no active claim."""
        manager = BoardManager(config=board_config)
        manager._get_active_claim = AsyncMock(return_value=None)

        success = await manager.renew_claim(45, "claude", "session-123")

        assert success is False

    @pytest.mark.asyncio
    async def test_release_work_completed(self, board_config, _mock_github_token):
        """Test releasing work as completed - stays In Progress for human review.

        Note: Agents should NEVER mark issues as Done. Done status only happens
        when PRs are merged (via GitHub automation). The 'completed' reason means
        work finished without a PR, which requires human verification.
        """
        manager = BoardManager(config=board_config)
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        await manager.release_work(45, "claude", reason="completed")

        manager._post_issue_comment.assert_called_once()
        # Status should NOT be changed - stays In Progress for human review
        manager.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_release_work_blocked(self, board_config, _mock_github_token):
        """Test releasing work as blocked."""
        manager = BoardManager(config=board_config)
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        await manager.release_work(45, "claude", reason="blocked")

        manager.update_status.assert_called_once_with(45, IssueStatus.BLOCKED)

    @pytest.mark.asyncio
    async def test_release_work_abandoned(self, board_config, _mock_github_token):
        """Test releasing work as abandoned."""
        manager = BoardManager(config=board_config)
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)

        await manager.release_work(45, "claude", reason="abandoned")

        manager.update_status.assert_called_once_with(45, IssueStatus.TODO)
        # Note: release_work doesn't unassign agent, just sets status to TODO

    def test_parse_claim_comment_valid(self, board_config, _mock_github_token):
        """Test parsing valid claim comment."""
        manager = BoardManager(config=board_config)

        comment_body = """🤖 **[Agent Claim]**

Agent: `claude`
Started: `2025-10-25T14:30:00Z`
Session ID: `session-123`

Claiming this issue for implementation."""

        claim = manager._parse_claim_comment(45, comment_body, "2025-10-25T14:30:00Z")

        assert claim is not None
        assert claim.issue_number == 45
        assert claim.agent == "claude"
        assert claim.session_id == "session-123"

    def test_parse_claim_comment_invalid(self, board_config, _mock_github_token):
        """Test parsing invalid claim comment returns None."""
        manager = BoardManager(config=board_config)

        invalid_body = "Just a regular comment"
        claim = manager._parse_claim_comment(45, invalid_body, "2025-10-25T14:30:00Z")

        assert claim is None


class TestDependencyManagement:
    """Test dependency tracking (Phase 2)."""

    @pytest.mark.asyncio
    async def test_add_blocker_method_exists(self, board_config, _mock_github_token):
        """Test add_blocker method is available."""
        manager = BoardManager(config=board_config)
        assert hasattr(manager, "add_blocker")
        assert callable(manager.add_blocker)

    @pytest.mark.asyncio
    async def test_mark_discovered_from_method_exists(self, board_config, _mock_github_token):
        """Test mark_discovered_from method is available."""
        manager = BoardManager(config=board_config)
        assert hasattr(manager, "mark_discovered_from")
        assert callable(manager.mark_discovered_from)


class TestReadyWorkDetection:
    """Test ready work queries (Phase 2)."""

    @pytest.mark.asyncio
    async def test_get_ready_work_method_exists(self, board_config, _mock_github_token):
        """Test get_ready_work method is available."""
        manager = BoardManager(config=board_config)
        assert hasattr(manager, "get_ready_work")
        assert callable(manager.get_ready_work)

    def test_issue_is_ready_no_blockers(self):
        """Test Issue.is_ready returns True when not blocked."""
        issue = Issue(
            number=1,
            title="Task",
            body="Body",
            state="open",
            status=IssueStatus.TODO,
            blocked_by=[],
        )
        assert issue.is_ready() is True

    def test_issue_is_ready_with_blockers(self):
        """Test Issue.is_ready returns False when blocked."""
        issue = Issue(
            number=1,
            title="Task",
            body="Body",
            state="open",
            status=IssueStatus.TODO,
            blocked_by=[2, 3],
        )
        assert issue.is_ready() is False


class TestRaceConditions:
    """Test race condition handling (Phase 2)."""

    @pytest.mark.asyncio
    async def test_concurrent_claims_first_wins(self, board_config, _mock_github_token):
        """Test concurrent claims - first comment wins."""
        manager = BoardManager(config=board_config)

        # Simulate race: both agents check claim at same time (both see None)
        # But first to post comment wins
        call_count = 0

        async def mock_get_claim(_issue_num):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First check: no claim
                return None
            # Second check: first agent already claimed
            return AgentClaim(
                issue_number=45,
                agent="claude",
                session_id="session-1",
                timestamp=datetime.now(timezone.utc),
            )

        manager._get_active_claim = mock_get_claim
        manager._post_issue_comment = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)
        manager._assign_to_agent = AsyncMock(return_value=True)

        # Agent 1 claims (succeeds)
        success1 = await manager.claim_work(45, "claude", "session-1")
        # Agent 2 tries to claim (fails)
        success2 = await manager.claim_work(45, "opencode", "session-2")

        assert success1 is True
        assert success2 is False

    @pytest.mark.asyncio
    async def test_claim_renewal_race_safe(self, board_config, _mock_github_token):
        """Test renewal is safe under race conditions."""
        manager = BoardManager(config=board_config)

        active_claim = AgentClaim(
            issue_number=45,
            agent="claude",
            session_id="session-123",
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=3600),
        )

        manager._get_active_claim = AsyncMock(return_value=active_claim)
        manager._post_issue_comment = AsyncMock()

        # Two renewal attempts by same agent
        result1 = await manager.renew_claim(45, "claude", "session-123")
        result2 = await manager.renew_claim(45, "claude", "session-123")

        # Both should succeed (idempotent)
        assert result1 is True
        assert result2 is True
        assert manager._post_issue_comment.call_count == 2


class TestApprovalChecking:
    """Test approval checking functionality."""

    def test_check_approval_trigger_valid_pattern(self, board_config, _mock_github_token):
        """Test _check_approval_trigger matches [Action][Agent] format."""
        manager = BoardManager(config=board_config)

        # Valid patterns from authorized user
        assert manager._check_approval_trigger("[Approved][Claude]", "testuser") is True
        assert manager._check_approval_trigger("[Approved][OpenCode]", "testuser") is True
        assert manager._check_approval_trigger("[Review][Gemini]", "testuser") is True
        assert manager._check_approval_trigger("[Close][Claude]", "testuser") is True
        assert manager._check_approval_trigger("[Summarize][Claude]", "testuser") is True
        assert manager._check_approval_trigger("[Debug][Claude]", "testuser") is True

    def test_check_approval_trigger_case_insensitive(self, board_config, _mock_github_token):
        """Test approval patterns are case insensitive."""
        manager = BoardManager(config=board_config)

        assert manager._check_approval_trigger("[approved][claude]", "testuser") is True
        assert manager._check_approval_trigger("[APPROVED][CLAUDE]", "testuser") is True
        assert manager._check_approval_trigger("[Approved][claude]", "testuser") is True

    def test_check_approval_trigger_rejects_standalone(self, board_config, _mock_github_token):
        """Test [Approved] without [Agent] is rejected to prevent false positives."""
        manager = BoardManager(config=board_config)

        # Standalone [Approved] should NOT match - prevents false positives from
        # instructional text like "reply with `[Approved]` to create PR"
        assert manager._check_approval_trigger("[Approved]", "testuser") is False
        assert manager._check_approval_trigger("[Review]", "testuser") is False

    def test_check_approval_trigger_rejects_instructional_text(self, board_config, _mock_github_token):
        """Test instructional text with [Approved] doesn't trigger false positive."""
        manager = BoardManager(config=board_config)

        # This is the exact text that caused false positives in production
        instructional_text = "*Awaiting admin review - reply with `[Approved]` to create PR*"
        assert manager._check_approval_trigger(instructional_text, "testuser") is False

        # More instructional patterns
        assert manager._check_approval_trigger("Use [Approved] to approve", "testuser") is False
        assert manager._check_approval_trigger("Comment `[Approved]` when ready", "testuser") is False

    def test_check_approval_trigger_unauthorized_user(self, board_config, _mock_github_token):
        """Test approval from unauthorized user is rejected."""
        manager = BoardManager(config=board_config)

        # Valid pattern but from unauthorized user
        assert manager._check_approval_trigger("[Approved][Claude]", "random_user") is False
        assert manager._check_approval_trigger("[Approved][Claude]", "hacker") is False

    def test_check_approval_trigger_authorized_users(self, board_config, _mock_github_token):
        """Test approval from various authorized users."""
        manager = BoardManager(config=board_config)

        # Repository owner (from config.repository = "test/repo")
        assert manager._check_approval_trigger("[Approved][Claude]", "test") is True

        # Project owner (from config.owner = "testuser")
        assert manager._check_approval_trigger("[Approved][Claude]", "testuser") is True

    def test_check_approval_trigger_in_longer_text(self, board_config, _mock_github_token):
        """Test approval trigger found within longer text."""
        manager = BoardManager(config=board_config)

        text_with_approval = """
        I've reviewed this issue and it looks good.

        [Approved][Claude]

        Please proceed with implementation.
        """
        assert manager._check_approval_trigger(text_with_approval, "testuser") is True

    def test_check_approval_trigger_agent_with_spaces(self, board_config, _mock_github_token):
        """Test approval trigger with agent names containing spaces (e.g., 'Claude Code')."""
        manager = BoardManager(config=board_config)

        # Agent names with spaces should be supported
        assert manager._check_approval_trigger("[Approved][Claude Code]", "testuser") is True
        assert manager._check_approval_trigger("[Review][OpenAI Agent]", "testuser") is True
        assert manager._check_approval_trigger("[Debug][My Custom Agent]", "testuser") is True

        # Agent names with hyphens should still work
        assert manager._check_approval_trigger("[Approved][github-actions]", "testuser") is True

        # Combination of spaces and hyphens
        assert manager._check_approval_trigger("[Approved][My-Custom Agent]", "testuser") is True

    def test_check_approval_trigger_empty_inputs(self, board_config, _mock_github_token):
        """Test empty/None inputs are handled."""
        manager = BoardManager(config=board_config)

        assert manager._check_approval_trigger("", "testuser") is False
        assert manager._check_approval_trigger("[Approved][Claude]", "") is False
        assert manager._check_approval_trigger(None, "testuser") is False
        assert manager._check_approval_trigger("[Approved][Claude]", None) is False

    @pytest.mark.asyncio
    async def test_is_issue_approved_in_comment(self, board_config, _mock_github_token):
        """Test is_issue_approved finds approval in comments."""
        manager = BoardManager(config=board_config)

        # Mock GraphQL response with approval comment
        manager._execute_graphql = AsyncMock(
            return_value=GraphQLResponse(
                data={
                    "repository": {
                        "issue": {
                            "body": "Issue description",
                            "author": {"login": "someone"},
                            "comments": {
                                "nodes": [
                                    {"body": "Regular comment", "author": {"login": "user1"}},
                                    {"body": "[Approved][Claude]", "author": {"login": "testuser"}},
                                ]
                            },
                        }
                    }
                }
            )
        )

        is_approved, approver = await manager.is_issue_approved(123)

        assert is_approved is True
        assert approver == "testuser"

    @pytest.mark.asyncio
    async def test_is_issue_approved_in_body(self, board_config, _mock_github_token):
        """Test is_issue_approved finds approval in issue body."""
        manager = BoardManager(config=board_config)

        # Mock GraphQL response with approval in body
        manager._execute_graphql = AsyncMock(
            return_value=GraphQLResponse(
                data={
                    "repository": {
                        "issue": {
                            "body": "[Approved][Claude] - Let's implement this",
                            "author": {"login": "testuser"},
                            "comments": {"nodes": []},
                        }
                    }
                }
            )
        )

        is_approved, approver = await manager.is_issue_approved(123)

        assert is_approved is True
        assert approver == "testuser"

    @pytest.mark.asyncio
    async def test_is_issue_approved_false_positive_prevention(self, board_config, _mock_github_token):
        """Test is_issue_approved doesn't match instructional text."""
        manager = BoardManager(config=board_config)

        # Mock GraphQL response with instructional text (no real approval)
        manager._execute_graphql = AsyncMock(
            return_value=GraphQLResponse(
                data={
                    "repository": {
                        "issue": {
                            "body": """
                            Issue description here.

                            *Awaiting admin review - reply with `[Approved]` to create PR*
                            """,
                            "author": {"login": "testuser"},
                            "comments": {"nodes": []},
                        }
                    }
                }
            )
        )

        is_approved, approver = await manager.is_issue_approved(123)

        assert is_approved is False
        assert approver is None

    @pytest.mark.asyncio
    async def test_is_issue_approved_not_found(self, board_config, _mock_github_token):
        """Test is_issue_approved returns False when no approval."""
        manager = BoardManager(config=board_config)

        # Mock GraphQL response without approval
        manager._execute_graphql = AsyncMock(
            return_value=GraphQLResponse(
                data={
                    "repository": {
                        "issue": {
                            "body": "Regular issue body",
                            "author": {"login": "someone"},
                            "comments": {
                                "nodes": [
                                    {"body": "Just a comment", "author": {"login": "user1"}},
                                ]
                            },
                        }
                    }
                }
            )
        )

        is_approved, approver = await manager.is_issue_approved(123)

        assert is_approved is False
        assert approver is None

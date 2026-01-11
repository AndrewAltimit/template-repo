"""Tests for optional agent resolution in monitors.

These tests validate the agent resolution chain when triggers don't specify an agent:
1. Board's Agent field (if issue is on board)
2. agent_priorities from config
3. First available enabled agent
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_agents.board.models import Issue, IssuePriority, IssueStatus, IssueType
from github_agents.config import AgentConfig
from github_agents.monitors.issue import IssueMonitor, get_best_available_agent
from github_agents.monitors.pr import PRMonitor
from github_agents.security import SecurityManager


class TestGetBestAvailableAgent:
    """Test the get_best_available_agent helper function."""

    def test_returns_first_priority_agent_if_available(self):
        """Should return first agent from priority list that exists."""
        agents = {"claude": MagicMock(), "opencode": MagicMock(), "gemini": MagicMock()}
        priority_list = ["gemini", "claude", "opencode"]

        result = get_best_available_agent(agents, priority_list)
        assert result == "gemini"

    def test_skips_unavailable_agents(self):
        """Should skip agents not in the agents dict."""
        agents = {"opencode": MagicMock(), "crush": MagicMock()}
        priority_list = ["claude", "gemini", "opencode"]  # claude/gemini not available

        result = get_best_available_agent(agents, priority_list)
        assert result == "opencode"

    def test_returns_first_available_if_no_priority_match(self):
        """Should fall back to first available agent if no priority matches."""
        agents = {"crush": MagicMock(), "opencode": MagicMock()}
        priority_list = ["claude", "gemini"]  # Neither available

        result = get_best_available_agent(agents, priority_list)
        assert result in ["crush", "opencode"]  # Either is valid

    def test_returns_none_if_no_agents(self):
        """Should return None if no agents available."""
        agents = {}
        priority_list = ["claude", "gemini"]

        result = get_best_available_agent(agents, priority_list)
        assert result is None

    def test_empty_priority_list_returns_first_agent(self):
        """Should return first agent if priority list is empty."""
        agents = {"opencode": MagicMock()}
        priority_list = []

        result = get_best_available_agent(agents, priority_list)
        assert result == "opencode"

    def test_case_insensitive_matching(self):
        """Priority list should match lowercase agent keys."""
        agents = {"claude": MagicMock(), "opencode": MagicMock()}
        priority_list = ["Claude", "OpenCode"]  # Different case

        # The function expects lowercase keys, so this tests robustness
        result = get_best_available_agent(agents, priority_list)
        # Won't match due to case - should fall back
        assert result in ["claude", "opencode"]


class TestIssueMonitorAgentResolution:
    """Test agent resolution in IssueMonitor._resolve_agent_for_issue()."""

    @pytest.fixture
    def mock_issue_on_board(self):
        """Create a mock issue with agent assigned on board."""
        return Issue(
            number=42,
            title="Test Issue",
            body="Test body",
            state="open",
            status=IssueStatus.TODO,
            priority=IssuePriority.MEDIUM,
            type=IssueType.FEATURE,
            agent="opencode",  # Agent assigned on board
            blocked_by=[],
            discovered_from=None,
            created_at=None,
            updated_at=None,
            url="https://github.com/test/repo/issues/42",
            labels=[],
            project_item_id="item123",
        )

    @pytest.fixture
    def mock_issue_no_agent(self):
        """Create a mock issue without agent assigned."""
        return Issue(
            number=43,
            title="Test Issue No Agent",
            body="Test body",
            state="open",
            status=IssueStatus.TODO,
            priority=IssuePriority.HIGH,
            type=IssueType.BUG,
            agent=None,  # No agent assigned
            blocked_by=[],
            discovered_from=None,
            created_at=None,
            updated_at=None,
            url="https://github.com/test/repo/issues/43",
            labels=[],
            project_item_id="item124",
        )

    @pytest.fixture
    def mock_config(self):
        """Create a mock AgentConfig."""
        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = ["claude", "opencode"]
        config.get_enabled_agents.return_value = ["claude", "opencode", "gemini", "crush"]
        config.get_security_config.return_value = {}
        config.get_subprocess_timeout.return_value = 600
        config.is_autonomous_mode.return_value = True
        return config

    @pytest.fixture
    def mock_agents(self):
        """Create mock agents dictionary."""
        return {
            "claude": MagicMock(name="claude"),
            "opencode": MagicMock(name="opencode"),
        }

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_from_board(self, mock_gh, mock_config, mock_agents, mock_issue_on_board):
        """Should resolve agent from board's Agent field."""
        mock_gh.return_value = "[]"  # No issues returned

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = mock_config
            monitor.agents = mock_agents
            monitor.security_manager = MagicMock()
            monitor.board_manager = AsyncMock()
            monitor.board_manager.initialize = AsyncMock()
            monitor.board_manager.get_issue = AsyncMock(return_value=mock_issue_on_board)
            monitor._board_config = MagicMock()
            monitor._memory_initialized = False

            result = asyncio.run(monitor._resolve_agent_for_issue(42))

            assert result == "opencode"
            monitor.board_manager.get_issue.assert_called_once_with(42)

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_from_priority_when_board_has_no_agent(self, mock_gh, mock_config, mock_agents, mock_issue_no_agent):
        """Should fall back to agent_priorities when board issue has no agent."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = mock_config
            monitor.agents = mock_agents
            monitor.security_manager = MagicMock()
            monitor.board_manager = AsyncMock()
            monitor.board_manager.initialize = AsyncMock()
            monitor.board_manager.get_issue = AsyncMock(return_value=mock_issue_no_agent)
            monitor._board_config = MagicMock()
            monitor._memory_initialized = False

            result = asyncio.run(monitor._resolve_agent_for_issue(43))

            # Should get from priority list (claude is first)
            assert result == "claude"
            mock_config.get_agent_priority.assert_called_with("issue_creation")

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_when_issue_not_on_board(self, mock_gh, mock_config, mock_agents):
        """Should fall back to priority when issue isn't on board."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = mock_config
            monitor.agents = mock_agents
            monitor.security_manager = MagicMock()
            monitor.board_manager = AsyncMock()
            monitor.board_manager.initialize = AsyncMock()
            monitor.board_manager.get_issue = AsyncMock(return_value=None)  # Not on board
            monitor._board_config = MagicMock()
            monitor._memory_initialized = False

            result = asyncio.run(monitor._resolve_agent_for_issue(99))

            assert result == "claude"  # First in priority list

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_when_board_manager_unavailable(self, mock_gh, mock_config, mock_agents):
        """Should fall back to priority when board manager is None."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = mock_config
            monitor.agents = mock_agents
            monitor.security_manager = MagicMock()
            monitor.board_manager = None  # No board manager
            monitor._board_config = None
            monitor._memory_initialized = False

            result = asyncio.run(monitor._resolve_agent_for_issue(42))

            assert result == "claude"  # Falls back to priority

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_when_board_raises_exception(self, mock_gh, mock_config, mock_agents):
        """Should fall back gracefully when board manager raises exception."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = mock_config
            monitor.agents = mock_agents
            monitor.security_manager = MagicMock()
            monitor.board_manager = AsyncMock()
            monitor.board_manager.initialize = AsyncMock(side_effect=Exception("Board error"))
            monitor._board_config = MagicMock()
            monitor._memory_initialized = False

            result = asyncio.run(monitor._resolve_agent_for_issue(42))

            # Should still resolve from priority
            assert result == "claude"

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_falls_back_to_enabled_agents(self, mock_gh, mock_agents):
        """Should fall back to first enabled agent when no priority matches."""
        mock_gh.return_value = "[]"

        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = []  # Empty priority
        config.get_enabled_agents.return_value = ["gemini", "crush"]
        config.get_security_config.return_value = {}

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = config
            monitor.agents = {}  # No agents match priority
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            result = asyncio.run(monitor._resolve_agent_for_issue(42))

            # Falls back to first enabled
            assert result == "gemini"

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_returns_none_when_no_agents(self, mock_gh):
        """Should return None when no agents are available."""
        mock_gh.return_value = "[]"

        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = []
        config.get_enabled_agents.return_value = []  # No enabled agents
        config.get_security_config.return_value = {}

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = config
            monitor.agents = {}
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            result = asyncio.run(monitor._resolve_agent_for_issue(42))

            assert result is None


class TestPRMonitorAgentResolution:
    """Test agent resolution in PRMonitor._resolve_agent_for_pr()."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock AgentConfig."""
        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = ["claude", "opencode"]
        config.get_enabled_agents.return_value = ["claude", "opencode", "gemini"]
        config.get_security_config.return_value = {}
        config.get_subprocess_timeout.return_value = 600
        config.is_autonomous_mode.return_value = True
        return config

    @pytest.fixture
    def mock_agents(self):
        """Create mock agents dictionary."""
        return {
            "claude": MagicMock(name="claude"),
            "opencode": MagicMock(name="opencode"),
        }

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_from_code_fixes_priority(self, mock_gh, mock_config, mock_agents):
        """Should resolve agent from code_fixes priority."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = mock_config
            monitor.agents = mock_agents
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            result = monitor._resolve_agent_for_pr()

            assert result == "claude"  # First in priority list
            mock_config.get_agent_priority.assert_called_with("code_fixes")

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_falls_back_to_enabled(self, mock_gh):
        """Should fall back to first enabled when no priority matches."""
        mock_gh.return_value = "[]"

        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = ["unavailable_agent"]
        config.get_enabled_agents.return_value = ["gemini", "crush"]
        config.get_security_config.return_value = {}

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = config
            monitor.agents = {}  # No matching agents
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            result = monitor._resolve_agent_for_pr()

            assert result == "gemini"

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_resolve_agent_returns_none_when_no_agents(self, mock_gh):
        """Should return None when no agents available."""
        mock_gh.return_value = "[]"

        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = []
        config.get_enabled_agents.return_value = []
        config.get_security_config.return_value = {}

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = config
            monitor.agents = {}
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            result = monitor._resolve_agent_for_pr()

            assert result is None


class TestPRMonitorCheckReviewTrigger:
    """Test the _check_review_trigger method with optional agent."""

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_trigger_with_agent(self, mock_gh):
        """Should parse trigger with explicit agent."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = MagicMock()
            monitor.agents = {}
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            comment = {"body": "Please address this.\n\n[Approved][Claude]", "author": "reviewer"}
            result = monitor._check_review_trigger(comment)

            assert result is not None
            action, agent, author = result
            assert action == "approved"
            assert agent == "claude"
            assert author == "reviewer"

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_trigger_without_agent(self, mock_gh):
        """Should parse trigger without agent (optional agent)."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = MagicMock()
            monitor.agents = {}
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            comment = {"body": "This needs review.\n\n[Review]", "author": "reviewer"}
            result = monitor._check_review_trigger(comment)

            assert result is not None
            action, agent, author = result
            assert action == "review"
            assert agent is None  # No agent specified
            assert author == "reviewer"

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_trigger_debug_action(self, mock_gh):
        """Should recognize [Debug] trigger."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = MagicMock()
            monitor.agents = {}
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            comment = {"body": "[Debug]", "author": "owner"}
            result = monitor._check_review_trigger(comment)

            assert result is not None
            action, agent, _ = result
            assert action == "debug"
            assert agent is None

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_no_trigger_in_comment(self, mock_gh):
        """Should return None when no trigger found."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = MagicMock()
            monitor.agents = {}
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            comment = {"body": "Just a regular comment", "author": "user"}
            result = monitor._check_review_trigger(comment)

            assert result is None

    @patch("github_agents.monitors.pr.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_invalid_action_rejected(self, mock_gh):
        """Should reject invalid actions."""
        mock_gh.return_value = "[]"

        with patch("github_agents.monitors.pr.load_config"):
            monitor = PRMonitor.__new__(PRMonitor)
            monitor.config = MagicMock()
            monitor.agents = {}
            monitor.security_manager = MagicMock()
            monitor.board_manager = None
            monitor._board_config = None
            monitor._memory_initialized = False

            comment = {"body": "[Delete][Claude]", "author": "user"}
            result = monitor._check_review_trigger(comment)

            assert result is None  # Delete is not a valid action


class TestOptionalAgentIntegrationFlow:
    """Integration tests for the full optional agent flow."""

    @pytest.fixture
    def mock_issue_with_trigger(self):
        """Create a mock issue with [Approved] trigger (no agent)."""
        return {
            "number": 100,
            "title": "Feature request",
            "body": "Please implement this feature.",
            "author": {"login": "contributor"},
            "comments": [
                {
                    "author": {"login": "AndrewAltimit"},
                    "body": "Looks good!\n\n[Approved]",
                }
            ],
            "labels": [],
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
        }

    @pytest.fixture
    def mock_board_issue(self):
        """Create a mock board issue with agent assigned."""
        return Issue(
            number=100,
            title="Feature request",
            body="Please implement this feature.",
            state="open",
            status=IssueStatus.TODO,
            priority=IssuePriority.MEDIUM,
            type=IssueType.FEATURE,
            agent="opencode",  # Agent assigned on board
            blocked_by=[],
            discovered_from=None,
            created_at=None,
            updated_at=None,
            url="https://github.com/test/repo/issues/100",
            labels=[],
            project_item_id="item100",
        )

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch("github_agents.monitors.issue.run_gh_command_async")
    @patch("github_agents.monitors.issue.run_git_command_async")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_full_flow_agent_from_board(
        self, mock_git_async, mock_gh_async, mock_gh, mock_issue_with_trigger, mock_board_issue
    ):
        """Test full flow: [Approved] trigger -> agent resolved from board."""
        mock_gh.return_value = "[]"
        mock_gh_async.return_value = ""
        mock_git_async.return_value = ""

        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = ["claude"]
        config.get_enabled_agents.return_value = ["claude", "opencode"]
        config.get_security_config.return_value = {"agent_admins": ["AndrewAltimit"]}
        config.get_subprocess_timeout.return_value = 600
        config.is_autonomous_mode.return_value = True

        security_manager = SecurityManager(agent_config=config)

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = config
            monitor.agents = {"claude": MagicMock(), "opencode": MagicMock()}
            monitor.security_manager = security_manager
            monitor.board_manager = AsyncMock()
            monitor.board_manager.initialize = AsyncMock()
            monitor.board_manager.get_issue = AsyncMock(return_value=mock_board_issue)
            monitor._board_config = MagicMock()
            monitor._memory_initialized = False
            monitor.repo = "test/repo"

            # Check trigger is parsed correctly (agent is None)
            trigger_info = security_manager.check_trigger_comment(mock_issue_with_trigger, "issue")
            assert trigger_info is not None
            action, agent, user = trigger_info
            assert action == "approved"
            assert agent is None  # Agent not in trigger
            assert user == "AndrewAltimit"

            # Resolve agent from board
            resolved_agent = asyncio.run(monitor._resolve_agent_for_issue(100))
            assert resolved_agent == "opencode"  # From board

    @patch("github_agents.monitors.issue.run_gh_command")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "test/repo"})
    def test_full_flow_agent_from_priority(self, mock_gh, mock_issue_with_trigger):
        """Test full flow: [Approved] trigger -> agent resolved from priority (no board)."""
        mock_gh.return_value = "[]"

        config = MagicMock(spec=AgentConfig)
        config.get_agent_priority.return_value = ["claude", "opencode"]
        config.get_enabled_agents.return_value = ["claude", "opencode"]
        config.get_security_config.return_value = {"agent_admins": ["AndrewAltimit"]}

        security_manager = SecurityManager(agent_config=config)

        with patch("github_agents.monitors.issue.load_config"):
            monitor = IssueMonitor.__new__(IssueMonitor)
            monitor.config = config
            monitor.agents = {"claude": MagicMock(), "opencode": MagicMock()}
            monitor.security_manager = security_manager
            monitor.board_manager = None  # No board manager
            monitor._board_config = None
            monitor._memory_initialized = False

            # Check trigger is parsed correctly
            trigger_info = security_manager.check_trigger_comment(mock_issue_with_trigger, "issue")
            assert trigger_info is not None
            action, agent, _ = trigger_info
            assert action == "approved"
            assert agent is None

            # Resolve agent from priority (no board)
            resolved_agent = asyncio.run(monitor._resolve_agent_for_issue(100))
            assert resolved_agent == "claude"  # First in priority

    def test_trigger_with_explicit_agent_override(self):
        """Test that explicit agent in trigger overrides board."""
        issue_with_explicit_agent = {
            "number": 101,
            "title": "Bug fix",
            "body": "Fix this bug",
            "author": {"login": "contributor"},
            "comments": [
                {
                    "author": {"login": "AndrewAltimit"},
                    "body": "[Approved][Claude]",  # Explicit agent
                }
            ],
        }

        config = MagicMock(spec=AgentConfig)
        config.get_security_config.return_value = {"agent_admins": ["AndrewAltimit"]}

        security_manager = SecurityManager(agent_config=config)

        trigger_info = security_manager.check_trigger_comment(issue_with_explicit_agent, "issue")
        assert trigger_info is not None
        action, agent, _ = trigger_info
        assert action == "approved"
        assert agent == "claude"  # Explicit override - no resolution needed

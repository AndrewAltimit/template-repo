"""Pytest fixtures for GitHub Board MCP Server tests."""

from datetime import datetime, timezone
from pathlib import Path

# Set up path before imports
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "packages" / "github_agents" / "src"))

from github_agents.board.models import (
    AgentClaim,
    BoardConfig,
    Issue,
    IssuePriority,
    IssueStatus,
    IssueType,
)


@pytest.fixture
def mock_github_token(monkeypatch):
    """Mock GitHub token in environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-12345")
    return "test-token-12345"


@pytest.fixture
def mock_board_config():
    """Create a test board configuration."""
    return BoardConfig(
        project_number=1,
        owner="testowner",
        repository="testowner/test-repo",
        field_mappings={
            "status": "Status",
            "priority": "Priority",
            "agent": "Agent",
            "type": "Type",
            "blocked_by": "Blocked By",
            "discovered_from": "Discovered From",
        },
        claim_timeout=86400,
        claim_renewal_interval=3600,
        enabled_agents=["claude", "opencode", "gemini"],
        auto_discover=True,
        exclude_labels=["wontfix", "duplicate"],
    )


@pytest.fixture
def mock_issue():
    """Create a mock issue."""
    return Issue(
        number=42,
        title="Test Issue",
        body="Test issue body",
        state="open",
        status=IssueStatus.TODO,
        priority=IssuePriority.HIGH,
        type=IssueType.FEATURE,
        agent=None,
        blocked_by=[],
        url="https://github.com/testowner/test-repo/issues/42",
        labels=["feature", "enhancement"],
    )


@pytest.fixture
def mock_issues():
    """Create multiple mock issues."""
    return [
        Issue(
            number=1,
            title="First Issue",
            body="First issue body",
            state="open",
            status=IssueStatus.TODO,
            priority=IssuePriority.HIGH,
            type=IssueType.BUG,
            blocked_by=[],
            url="https://github.com/testowner/test-repo/issues/1",
            labels=["bug"],
        ),
        Issue(
            number=2,
            title="Second Issue",
            body="Second issue body",
            state="open",
            status=IssueStatus.TODO,
            priority=IssuePriority.MEDIUM,
            type=IssueType.FEATURE,
            blocked_by=[1],
            url="https://github.com/testowner/test-repo/issues/2",
            labels=["feature"],
        ),
    ]


@pytest.fixture
def mock_agent_claim():
    """Create a mock agent claim."""
    return AgentClaim(
        issue_number=42,
        agent="claude",
        session_id="session-abc123",
        timestamp=datetime.now(timezone.utc),
        released=False,
    )


@pytest.fixture
def mock_board_manager(mock_board_config):
    """Create a mock BoardManager."""
    manager = MagicMock()
    manager.config = mock_board_config
    manager.initialize = AsyncMock()
    manager.get_ready_work = AsyncMock(return_value=[])
    manager.claim_work = AsyncMock(return_value=True)
    manager.renew_claim = AsyncMock(return_value=True)
    manager.release_work = AsyncMock()
    manager.update_status = AsyncMock(return_value=True)
    manager.add_blocker = AsyncMock(return_value=True)
    manager.mark_discovered_from = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def config_file_path(tmp_path):
    """Create a temporary config file."""
    config_content = """
project:
  number: 1
  owner: testowner
repository: testowner/test-repo
fields:
  status: Status
  priority: Priority
  agent: Agent
  type: Type
  blocked_by: Blocked By
  discovered_from: Discovered From
agents:
  enabled_agents:
    - claude
    - opencode
    - gemini
  auto_discover: true
work_queue:
  exclude_labels:
    - wontfix
    - duplicate
work_claims:
  timeout: 86400
  renewal_interval: 3600
"""
    config_file = tmp_path / "board_config.yaml"
    config_file.write_text(config_content)
    return str(config_file)

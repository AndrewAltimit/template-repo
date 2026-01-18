"""Pytest fixtures for GitHub Board MCP Server tests.

These tests mock the Rust board-manager CLI wrapper, not Python models.
"""

from typing import Any, Dict

import pytest


@pytest.fixture
def mock_github_token(monkeypatch):
    """Mock GitHub token in environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-12345")
    return "test-token-12345"


@pytest.fixture
def mock_cli_response_issues() -> Dict[str, Any]:
    """Mock CLI response for ready work query."""
    return {
        "success": True,
        "result": {
            "issues": [
                {
                    "number": 1,
                    "title": "First Issue",
                    "body": "First issue body",
                    "state": "open",
                    "status": "Todo",
                    "priority": "high",
                    "type": "bug",
                    "blocked_by": [],
                    "url": "https://github.com/testowner/test-repo/issues/1",
                    "labels": ["bug"],
                },
                {
                    "number": 2,
                    "title": "Second Issue",
                    "body": "Second issue body",
                    "state": "open",
                    "status": "Todo",
                    "priority": "medium",
                    "type": "feature",
                    "blocked_by": [1],
                    "url": "https://github.com/testowner/test-repo/issues/2",
                    "labels": ["feature"],
                },
            ],
            "count": 2,
        },
    }


@pytest.fixture
def mock_cli_response_claim_success() -> Dict[str, Any]:
    """Mock CLI response for successful claim."""
    return {
        "success": True,
        "result": {
            "claimed": True,
            "issue_number": 42,
            "agent": "claude",
            "session_id": "session-abc123",
        },
    }


@pytest.fixture
def mock_cli_response_agents() -> Dict[str, Any]:
    """Mock CLI response for agents list."""
    return {
        "success": True,
        "result": {
            "agents": ["claude", "opencode", "gemini"],
            "count": 3,
        },
    }


@pytest.fixture
def mock_cli_response_config() -> Dict[str, Any]:
    """Mock CLI response for board config."""
    return {
        "success": True,
        "result": {
            "project_number": 1,
            "owner": "testowner",
            "repository": "testowner/test-repo",
            "claim_timeout": 86400,
            "claim_renewal_interval": 3600,
            "enabled_agents": ["claude", "opencode", "gemini"],
            "auto_discover": True,
            "exclude_labels": ["wontfix", "duplicate"],
        },
    }


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

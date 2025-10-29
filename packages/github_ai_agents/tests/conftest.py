"""Pytest fixtures for GitHub AI Agents tests."""

from unittest.mock import AsyncMock, Mock

import pytest


# Agent Fixtures
@pytest.fixture
def mock_claude_agent():
    """Mock Claude agent for testing."""
    agent = Mock()
    agent.is_available.return_value = True
    agent.get_trigger_keyword.return_value = "Claude"
    agent.generate_code = AsyncMock(return_value="# Generated code\nprint('Hello, World!')")
    agent.name = "Claude"
    return agent


@pytest.fixture
def mock_opencode_agent():
    """Mock OpenCode agent for testing."""
    agent = Mock()
    agent.is_available.return_value = True
    agent.get_trigger_keyword.return_value = "OpenCode"
    agent.generate_code = AsyncMock(return_value="# Generated code\nprint('Hello from OpenCode')")
    agent.name = "OpenCode"
    return agent


@pytest.fixture
def mock_gemini_agent():
    """Mock Gemini agent for testing."""
    agent = Mock()
    agent.is_available.return_value = True
    agent.get_trigger_keyword.return_value = "Gemini"
    agent.generate_code = AsyncMock(return_value="# Generated code\nprint('Hello from Gemini')")
    agent.name = "Gemini"
    return agent


@pytest.fixture
def mock_crush_agent():
    """Mock Crush agent for testing."""
    agent = Mock()
    agent.is_available.return_value = True
    agent.get_trigger_keyword.return_value = "Crush"
    agent.generate_code = AsyncMock(return_value="# Generated code\nprint('Hello from Crush')")
    agent.name = "Crush"
    return agent


# Security Fixtures
@pytest.fixture
def mock_security_manager():
    """Mock security manager for testing."""
    security_mgr = Mock()
    security_mgr.is_authorized.return_value = True
    security_mgr.validate_user.return_value = True
    security_mgr.check_rate_limit.return_value = True
    return security_mgr


# GitHub API Mock Fixtures
@pytest.fixture
def mock_github_issue():
    """Mock GitHub issue data."""
    return {
        "number": 123,
        "title": "Test Issue",
        "body": "Test body [Approved][OpenCode]",
        "user": {"login": "testuser"},
        "comments": [],
        "labels": [],
        "state": "open",
        "created_at": "2025-10-25T00:00:00Z",
        "updated_at": "2025-10-25T00:00:00Z",
    }


@pytest.fixture
def mock_github_pr():
    """Mock GitHub pull request data."""
    return {
        "number": 456,
        "title": "Test PR",
        "body": "Test PR body",
        "user": {"login": "testuser"},
        "state": "open",
        "head": {"ref": "test-branch", "sha": "abc123"},
        "base": {"ref": "main", "sha": "def456"},
        "comments": [],
        "reviews": [],
        "created_at": "2025-10-25T00:00:00Z",
        "updated_at": "2025-10-25T00:00:00Z",
    }


@pytest.fixture
def mock_github_comment():
    """Mock GitHub comment data."""
    return {
        "id": 789,
        "body": "[Approved][Claude]",
        "user": {"login": "admin"},
        "created_at": "2025-10-25T00:00:00Z",
        "updated_at": "2025-10-25T00:00:00Z",
    }


@pytest.fixture
def mock_github_api():
    """Mock GitHub API client."""
    api = Mock()
    api.get_issue = AsyncMock()
    api.get_pr = AsyncMock()
    api.create_pr = AsyncMock()
    api.add_comment = AsyncMock()
    api.update_issue = AsyncMock()
    api.get_comments = AsyncMock(return_value=[])
    return api


# Repository Fixtures
@pytest.fixture
def test_repo_name():
    """Test repository name."""
    return "testuser/test-repo"


@pytest.fixture
def test_repo_owner():
    """Test repository owner."""
    return "testuser"


# Environment Fixtures
@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_12345")
    monkeypatch.setenv("GITHUB_PROJECTS_TOKEN", "test_projects_token_67890")
    monkeypatch.setenv("GITHUB_REPOSITORY", "testuser/test-repo")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test_openrouter_key")


# Subagent Fixtures
@pytest.fixture
def mock_tech_lead_agent():
    """Mock tech lead subagent."""
    agent = Mock()
    agent.name = "tech-lead"
    agent.review_code = AsyncMock(return_value={"approved": True, "comments": []})
    return agent


@pytest.fixture
def mock_security_auditor_agent():
    """Mock security auditor subagent."""
    agent = Mock()
    agent.name = "security-auditor"
    agent.audit_code = AsyncMock(return_value={"vulnerabilities": []})
    return agent


@pytest.fixture
def mock_qa_reviewer_agent():
    """Mock QA reviewer subagent."""
    agent = Mock()
    agent.name = "qa-reviewer"
    agent.review_tests = AsyncMock(return_value={"test_coverage": 85, "issues": []})
    return agent


# Test Data Fixtures
@pytest.fixture
def sample_code():
    """Sample code for testing."""
    return '''
def hello_world():
    """Print hello world."""
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
'''


@pytest.fixture
def sample_issue_body_approved():
    """Sample approved issue body."""
    return """
# Feature Request

Please implement a hello world function.

[Approved][OpenCode]
"""


@pytest.fixture
def sample_pr_review_comment():
    """Sample PR review comment with agent trigger."""
    return """
Please fix the following issues:
1. Add error handling
2. Improve documentation

[Approved][Claude]
"""


# Board Integration Fixtures
@pytest.fixture
def mock_board_config():
    """Mock board configuration."""
    from github_ai_agents.board.models import BoardConfig

    return BoardConfig(
        project_number=1,
        owner="testuser",
        repository="testuser/test-repo",
        claim_timeout=86400,  # 24 hours
        claim_renewal_interval=3600,  # 1 hour
        enabled_agents=["claude", "opencode", "gemini"],
        auto_discover=True,
        exclude_labels=["wontfix", "duplicate"],
    )


@pytest.fixture
def mock_github_token(monkeypatch):
    """Mock GitHub token in environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-12345")
    return "test-token-12345"


@pytest.fixture
def mock_github_projects_token(monkeypatch):
    """Mock GitHub Projects token (classic token) in environment."""
    monkeypatch.setenv("GITHUB_PROJECTS_TOKEN", "test-projects-token-67890")
    return "test-projects-token-67890"


@pytest.fixture
def mock_board_issue():
    """Mock issue with board metadata."""
    from datetime import datetime, timezone

    from github_ai_agents.board.models import Issue, IssuePriority, IssueStatus

    return Issue(
        number=42,
        title="Implement authentication",
        body="Add user authentication system",
        state="open",
        status=IssueStatus.TODO,
        priority=IssuePriority.HIGH,
        agent=None,
        blocked_by=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        url="https://github.com/testuser/test-repo/issues/42",
        labels=["feature", "backend"],
    )


@pytest.fixture
def mock_agent_claim():
    """Mock agent claim."""
    from datetime import datetime, timezone

    from github_ai_agents.board.models import AgentClaim

    return AgentClaim(
        issue_number=42,
        agent="claude",
        session_id="session-123",
        timestamp=datetime.now(timezone.utc),
        released=False,
    )


@pytest.fixture
def mock_graphql_response():
    """Mock successful GraphQL response."""
    from github_ai_agents.board.models import GraphQLResponse

    return GraphQLResponse(
        data={
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOABCDEF",
                    "title": "Test Project",
                }
            }
        },
        errors=[],
        status_code=200,
    )


@pytest.fixture
def mock_board_manager(mock_board_config, mock_github_token):
    """Mock BoardManager instance."""
    from unittest.mock import AsyncMock

    from github_ai_agents.board.manager import BoardManager

    manager = BoardManager(config=mock_board_config)
    manager.session = AsyncMock()
    manager.project_id = "PVT_kwDOABCDEF"
    return manager

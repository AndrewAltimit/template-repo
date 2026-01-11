"""Diagnostic tests for board agent workflow.

These tests help identify why the board-agent-worker workflow fails to claim work.
Run with: pytest tests/integration/test_board_workflow_diagnostic.py -v -s
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_agents.board.manager import BoardManager
from github_agents.board.models import (
    BoardConfig,
    GraphQLResponse,
)


class TestApprovalTriggerDetection:
    """Test the approval trigger detection logic."""

    @pytest.fixture
    def manager_with_config(self):
        """Create manager with test config."""
        config = BoardConfig(
            project_number=1,
            owner="AndrewAltimit",
            repository="AndrewAltimit/template-repo",
        )
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            return BoardManager(config=config)

    def test_approval_trigger_approved(self, manager_with_config):
        """Test [Approved] trigger detection."""
        result = manager_with_config._check_approval_trigger("[Approved]", "AndrewAltimit")
        assert result is True, "Should detect [Approved] from repo owner"

    def test_approval_trigger_approved_with_agent(self, manager_with_config):
        """Test [Approved][Claude] trigger detection (actual format from issue #196)."""
        result = manager_with_config._check_approval_trigger("[Approved][Claude]", "AndrewAltimit")
        assert result is True, "Should detect [Approved][Claude] - regex matches [Approved] portion"

    def test_approval_trigger_review(self, manager_with_config):
        """Test [Review] trigger detection."""
        result = manager_with_config._check_approval_trigger("[Review]", "AndrewAltimit")
        assert result is True

    def test_approval_trigger_case_insensitive(self, manager_with_config):
        """Test case insensitivity."""
        result = manager_with_config._check_approval_trigger("[APPROVED]", "AndrewAltimit")
        assert result is True, "Should be case insensitive"

    def test_approval_trigger_unauthorized_user(self, manager_with_config):
        """Test unauthorized user cannot trigger approval."""
        result = manager_with_config._check_approval_trigger("[Approved]", "RandomUser")
        assert result is False, "Should reject unauthorized user"

    def test_approval_trigger_empty_text(self, manager_with_config):
        """Test empty text returns False."""
        result = manager_with_config._check_approval_trigger("", "AndrewAltimit")
        assert result is False

    def test_approval_trigger_no_brackets(self, manager_with_config):
        """Test text without proper format."""
        result = manager_with_config._check_approval_trigger("Approved", "AndrewAltimit")
        assert result is False, "Should require brackets"

    def test_approval_trigger_multiline_comment(self, manager_with_config):
        """Test detection in multiline comment."""
        text = """
        I've reviewed this and it looks good.
        [Approved][Claude]
        Let's proceed!
        """
        result = manager_with_config._check_approval_trigger(text, "AndrewAltimit")
        assert result is True


class TestAgentNameNormalization:
    """Test agent name normalization for filtering."""

    def test_normalize_claude(self):
        """Test 'claude' normalizes to 'Claude Code'."""
        result = BoardManager._normalize_agent_name("claude")
        assert result == "Claude Code"

    def test_normalize_opencode(self):
        """Test 'opencode' normalizes to 'OpenCode'."""
        result = BoardManager._normalize_agent_name("opencode")
        assert result == "OpenCode"

    def test_normalize_gemini(self):
        """Test 'gemini' normalizes to 'Gemini CLI'."""
        result = BoardManager._normalize_agent_name("gemini")
        assert result == "Gemini CLI"

    def test_normalize_already_normalized(self):
        """Test already normalized name passes through."""
        result = BoardManager._normalize_agent_name("Claude Code")
        assert result == "Claude Code"

    def test_normalize_none(self):
        """Test None returns None."""
        result = BoardManager._normalize_agent_name(None)
        assert result is None

    def test_normalize_case_insensitive(self):
        """Test normalization is case-insensitive."""
        result = BoardManager._normalize_agent_name("CLAUDE")
        assert result == "Claude Code"


class TestGetReadyWorkFiltering:
    """Test issue filtering in get_ready_work."""

    @pytest.fixture
    def mock_manager(self):
        """Create manager with mocked GraphQL."""
        config = BoardConfig(
            project_number=2,
            owner="AndrewAltimit",
            repository="AndrewAltimit/template-repo",
        )
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            manager = BoardManager(config=config)
            manager.project_id = "test_project_id"
            manager.session = MagicMock()
            return manager

    @pytest.mark.asyncio
    async def test_filter_by_agent_matches(self, mock_manager):
        """Test filtering returns issues with matching agent."""
        # Mock GraphQL response with issue assigned to Claude Code
        mock_response = GraphQLResponse(
            data={
                "node": {
                    "items": {
                        "nodes": [
                            {
                                "id": "item_1",
                                "fieldValues": {
                                    "nodes": [
                                        {"name": "Todo", "field": {"name": "Status"}},
                                        {"name": "Medium", "field": {"name": "Priority"}},
                                        {"name": "Claude Code", "field": {"name": "Agent"}},
                                    ]
                                },
                                "content": {
                                    "number": 196,
                                    "title": "Test Issue",
                                    "body": "Test body",
                                    "state": "OPEN",
                                    "createdAt": "2026-01-10T00:00:00Z",
                                    "updatedAt": "2026-01-10T00:00:00Z",
                                    "url": "https://github.com/test/repo/issues/196",
                                    "labels": {"nodes": []},
                                },
                            }
                        ]
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)
        mock_manager._get_active_claim = AsyncMock(return_value=None)

        issues = await mock_manager.get_ready_work(agent_name="claude", limit=5)

        assert len(issues) == 1
        assert issues[0].number == 196

    @pytest.mark.asyncio
    async def test_filter_by_agent_no_match_different_agent(self, mock_manager):
        """Test filtering excludes issues assigned to different agent."""
        mock_response = GraphQLResponse(
            data={
                "node": {
                    "items": {
                        "nodes": [
                            {
                                "id": "item_1",
                                "fieldValues": {
                                    "nodes": [
                                        {"name": "Todo", "field": {"name": "Status"}},
                                        {"name": "OpenCode", "field": {"name": "Agent"}},
                                    ]
                                },
                                "content": {
                                    "number": 196,
                                    "title": "Test Issue",
                                    "body": "Test body",
                                    "state": "OPEN",
                                    "createdAt": "2026-01-10T00:00:00Z",
                                    "updatedAt": "2026-01-10T00:00:00Z",
                                    "url": "https://github.com/test/repo/issues/196",
                                    "labels": {"nodes": []},
                                },
                            }
                        ]
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)
        mock_manager._get_active_claim = AsyncMock(return_value=None)

        issues = await mock_manager.get_ready_work(agent_name="claude", limit=5)

        assert len(issues) == 0, "Should filter out issue assigned to different agent"

    @pytest.mark.asyncio
    async def test_filter_by_agent_includes_unassigned(self, mock_manager):
        """Test filtering INCLUDES issues with no agent assigned.

        FIX: Issues without an Agent field should be available to any agent.
        This allows issues to be claimed by the first agent that picks them up.
        """
        mock_response = GraphQLResponse(
            data={
                "node": {
                    "items": {
                        "nodes": [
                            {
                                "id": "item_1",
                                "fieldValues": {
                                    "nodes": [
                                        {"name": "Todo", "field": {"name": "Status"}},
                                        # No Agent field - should still be included!
                                    ]
                                },
                                "content": {
                                    "number": 196,
                                    "title": "Test Issue",
                                    "body": "Test body",
                                    "state": "OPEN",
                                    "createdAt": "2026-01-10T00:00:00Z",
                                    "updatedAt": "2026-01-10T00:00:00Z",
                                    "url": "https://github.com/test/repo/issues/196",
                                    "labels": {"nodes": []},
                                },
                            }
                        ]
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)
        mock_manager._get_active_claim = AsyncMock(return_value=None)

        issues = await mock_manager.get_ready_work(agent_name="claude", limit=5)

        # FIXED behavior: unassigned issues ARE included
        assert len(issues) == 1, (
            "Unassigned issues should be available to any agent. If this fails, the bug was re-introduced!"
        )
        assert issues[0].number == 196

    @pytest.mark.asyncio
    async def test_no_agent_filter_returns_all(self, mock_manager):
        """Test that passing agent_name=None returns all ready issues."""
        mock_response = GraphQLResponse(
            data={
                "node": {
                    "items": {
                        "nodes": [
                            {
                                "id": "item_1",
                                "fieldValues": {
                                    "nodes": [
                                        {"name": "Todo", "field": {"name": "Status"}},
                                        # No Agent field
                                    ]
                                },
                                "content": {
                                    "number": 196,
                                    "title": "Test Issue",
                                    "body": "Test body",
                                    "state": "OPEN",
                                    "createdAt": "2026-01-10T00:00:00Z",
                                    "updatedAt": "2026-01-10T00:00:00Z",
                                    "url": "https://github.com/test/repo/issues/196",
                                    "labels": {"nodes": []},
                                },
                            }
                        ]
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)
        mock_manager._get_active_claim = AsyncMock(return_value=None)

        # No agent filter
        issues = await mock_manager.get_ready_work(agent_name=None, limit=5)

        assert len(issues) == 1, "Should return issues when no agent filter applied"


class TestIsIssueApproved:
    """Test is_issue_approved method."""

    @pytest.fixture
    def mock_manager(self):
        """Create manager with mocked GraphQL."""
        config = BoardConfig(
            project_number=2,
            owner="AndrewAltimit",
            repository="AndrewAltimit/template-repo",
        )
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            manager = BoardManager(config=config)
            manager.session = MagicMock()
            return manager

    @pytest.mark.asyncio
    async def test_approved_in_comment(self, mock_manager):
        """Test detection of [Approved] in comment."""
        mock_response = GraphQLResponse(
            data={
                "repository": {
                    "issue": {
                        "body": "Issue body without approval",
                        "author": {"login": "SomeUser"},
                        "comments": {
                            "nodes": [
                                {
                                    "body": "[Approved][Claude]",
                                    "author": {"login": "AndrewAltimit"},
                                }
                            ]
                        },
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)

        is_approved, approver = await mock_manager.is_issue_approved(196)

        assert is_approved is True
        assert approver == "AndrewAltimit"

    @pytest.mark.asyncio
    async def test_approved_in_body(self, mock_manager):
        """Test detection of [Approved] in issue body."""
        mock_response = GraphQLResponse(
            data={
                "repository": {
                    "issue": {
                        "body": "Issue with [Approved]",
                        "author": {"login": "AndrewAltimit"},
                        "comments": {"nodes": []},
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)

        is_approved, approver = await mock_manager.is_issue_approved(196)

        assert is_approved is True
        assert approver == "AndrewAltimit"

    @pytest.mark.asyncio
    async def test_not_approved(self, mock_manager):
        """Test no approval when trigger not found."""
        mock_response = GraphQLResponse(
            data={
                "repository": {
                    "issue": {
                        "body": "Regular issue body",
                        "author": {"login": "SomeUser"},
                        "comments": {
                            "nodes": [
                                {
                                    "body": "Just a regular comment",
                                    "author": {"login": "AndrewAltimit"},
                                }
                            ]
                        },
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)

        is_approved, approver = await mock_manager.is_issue_approved(196)

        assert is_approved is False
        assert approver is None

    @pytest.mark.asyncio
    async def test_approved_by_unauthorized_user(self, mock_manager):
        """Test that approval from unauthorized user is rejected."""
        mock_response = GraphQLResponse(
            data={
                "repository": {
                    "issue": {
                        "body": "Issue body",
                        "author": {"login": "SomeUser"},
                        "comments": {
                            "nodes": [
                                {
                                    "body": "[Approved][Claude]",
                                    "author": {"login": "RandomUser"},  # Not authorized
                                }
                            ]
                        },
                    }
                }
            }
        )

        mock_manager._execute_graphql = AsyncMock(return_value=mock_response)

        is_approved, approver = await mock_manager.is_issue_approved(196)

        assert is_approved is False
        assert approver is None


class TestWorkflowIntegration:
    """Test the complete workflow integration."""

    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self):
        """Simulate the full workflow for issue #196.

        This test simulates what happens in the GitHub Actions workflow:
        1. Query ready work
        2. Check approval
        3. Claim work
        """
        config = BoardConfig(
            project_number=2,
            owner="AndrewAltimit",
            repository="AndrewAltimit/template-repo",
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            manager = BoardManager(config=config)
            manager.project_id = "test_project_id"
            manager.session = MagicMock()

            # Mock GraphQL for get_ready_work - WITH Agent field set
            ready_work_response = GraphQLResponse(
                data={
                    "node": {
                        "items": {
                            "nodes": [
                                {
                                    "id": "item_196",
                                    "fieldValues": {
                                        "nodes": [
                                            {"name": "Todo", "field": {"name": "Status"}},
                                            {"name": "Medium", "field": {"name": "Priority"}},
                                            {"name": "Claude Code", "field": {"name": "Agent"}},
                                        ]
                                    },
                                    "content": {
                                        "number": 196,
                                        "title": "Magic Numbers Issue",
                                        "body": "Test body",
                                        "state": "OPEN",
                                        "createdAt": "2026-01-10T00:00:00Z",
                                        "updatedAt": "2026-01-10T00:00:00Z",
                                        "url": "https://github.com/test/repo/issues/196",
                                        "labels": {"nodes": []},
                                    },
                                }
                            ]
                        }
                    }
                }
            )

            # Mock GraphQL for is_issue_approved
            approval_response = GraphQLResponse(
                data={
                    "repository": {
                        "issue": {
                            "body": "Issue body",
                            "author": {"login": "SomeUser"},
                            "comments": {
                                "nodes": [
                                    {
                                        "body": "[Approved][Claude]",
                                        "author": {"login": "AndrewAltimit"},
                                    }
                                ]
                            },
                        }
                    }
                }
            )

            call_count = 0

            async def mock_graphql(query, variables=None):
                nonlocal call_count
                call_count += 1
                if "GetProjectItems" in query:
                    return ready_work_response
                if "GetIssueForApproval" in query:
                    return approval_response
                return GraphQLResponse(data={})

            manager._execute_graphql = mock_graphql
            manager._get_active_claim = AsyncMock(return_value=None)

            # Step 1: Query ready work
            issues = await manager.get_ready_work(agent_name="claude", limit=1)
            assert len(issues) == 1, "Should find issue #196"
            assert issues[0].number == 196

            # Step 2: Check approval
            is_approved, approver = await manager.is_issue_approved(196)
            assert is_approved is True, "Issue should be approved"
            assert approver == "AndrewAltimit"

            # If we get here, the workflow should proceed to claim

    @pytest.mark.asyncio
    async def test_workflow_succeeds_without_agent_field(self):
        """Test workflow succeeds when Agent field is not set.

        FIX: Issues without Agent field should now be available to any agent.
        """
        config = BoardConfig(
            project_number=2,
            owner="AndrewAltimit",
            repository="AndrewAltimit/template-repo",
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            manager = BoardManager(config=config)
            manager.project_id = "test_project_id"
            manager.session = MagicMock()

            # Mock GraphQL - WITHOUT Agent field
            ready_work_response = GraphQLResponse(
                data={
                    "node": {
                        "items": {
                            "nodes": [
                                {
                                    "id": "item_196",
                                    "fieldValues": {
                                        "nodes": [
                                            {"name": "Todo", "field": {"name": "Status"}},
                                            {"name": "Medium", "field": {"name": "Priority"}},
                                            # NO Agent field - but now included!
                                        ]
                                    },
                                    "content": {
                                        "number": 196,
                                        "title": "Magic Numbers Issue",
                                        "body": "Test body",
                                        "state": "OPEN",
                                        "createdAt": "2026-01-10T00:00:00Z",
                                        "updatedAt": "2026-01-10T00:00:00Z",
                                        "url": "https://github.com/test/repo/issues/196",
                                        "labels": {"nodes": []},
                                    },
                                }
                            ]
                        }
                    }
                }
            )

            manager._execute_graphql = AsyncMock(return_value=ready_work_response)
            manager._get_active_claim = AsyncMock(return_value=None)

            # Query ready work - NOW INCLUDES unassigned issues!
            issues = await manager.get_ready_work(agent_name="claude", limit=1)

            assert len(issues) == 1, (
                "FIX: Issue #196 should be returned even without Agent field. Unassigned issues are available to any agent."
            )
            assert issues[0].number == 196


class TestAgentsYamlLoading:
    """Test .agents.yaml loading for authorization."""

    def test_load_agents_yaml_returns_list(self):
        """Test loading agent_admins from .agents.yaml."""
        config = BoardConfig(
            project_number=2,
            owner="AndrewAltimit",
            repository="AndrewAltimit/template-repo",
        )
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            manager = BoardManager(config=config)

            # This should find the .agents.yaml in the repo root
            admins = manager._load_agents_yaml_agent_admins()

            # The file exists and has AndrewAltimit as admin
            assert isinstance(admins, list)
            # If file exists, should have at least one admin
            # If file doesn't exist, returns empty list


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

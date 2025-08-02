#!/usr/bin/env python3
"""
Comprehensive tests for the keyword trigger system in AI agents.
Tests security, keyword parsing, and agent behavior with mock GitHub repo.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Add the scripts/agents directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "agents"))

from issue_monitor import IssueMonitor  # noqa: E402
from pr_review_monitor import PRReviewMonitor  # noqa: E402
from security import SecurityManager  # noqa: E402


class TestKeywordTriggers(unittest.TestCase):
    """Test keyword trigger parsing and validation."""

    def setUp(self):
        """Set up test environment."""
        self.security = SecurityManager(allow_list=["testuser", "admin", "repo-owner"])

    def test_keyword_parsing_valid(self):
        """Test parsing valid keyword triggers."""
        test_cases = [
            # Claude and Gemini
            ("[Approved][Claude]", ("Approved", "Claude")),
            ("[Fix][Gemini]", ("Fix", "Gemini")),
            ("[Close][Claude]", ("Close", "Claude")),
            ("[Summarize][Gemini]", ("Summarize", "Gemini")),
            ("[Debug][Claude]", ("Debug", "Claude")),
            ("[Implement][Gemini]", ("Implement", "Gemini")),
            ("[Review][Claude]", ("Review", "Claude")),
            # New agents
            ("[Approved][OpenCode]", ("Approved", "OpenCode")),
            ("[Fix][Crush]", ("Fix", "Crush")),
            ("[Implement][Codex]", ("Implement", "Codex")),
            ("[Review][OpenCode]", ("Review", "OpenCode")),
            ("[Debug][Crush]", ("Debug", "Crush")),
            # Case insensitive
            ("[approved][claude]", ("approved", "claude")),
            ("[CLOSE][GEMINI]", ("CLOSE", "GEMINI")),
            ("[fix][opencode]", ("fix", "opencode")),
            ("[REVIEW][CRUSH]", ("REVIEW", "CRUSH")),
            # With whitespace
            ("[Approved] [Claude]", ("Approved", "Claude")),
            ("[Fix]  [Gemini]", ("Fix", "Gemini")),
            ("[Implement]   [OpenCode]", ("Implement", "OpenCode")),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = self.security.parse_keyword_trigger(text)
                self.assertEqual(result, expected)

    def test_keyword_parsing_invalid(self):
        """Test parsing invalid keyword triggers."""
        invalid_cases = [
            "[Invalid][Claude]",  # Invalid action
            "[Approved][GitBot]",  # GitBot removed
            "[Approved][InvalidAgent]",  # Invalid agent
            "[Approved]",  # Missing agent
            "Approved][Claude]",  # Missing opening bracket
            "[Approved Claude]",  # No separator
            "Just some text",  # No keywords
            "",  # Empty string
            None,  # None value
        ]

        for text in invalid_cases:
            with self.subTest(text=text):
                result = self.security.parse_keyword_trigger(text or "")
                self.assertIsNone(result)

    def test_trigger_comment_detection(self):
        """Test detecting trigger comments in issues/PRs."""
        # Valid trigger from allowed user
        issue = {
            "number": 123,
            "comments": [
                {"author": {"login": "randomuser"}, "body": "This is a bug"},
                {
                    "author": {"login": "testuser"},
                    "body": "I'll fix this. [Approved][Claude]",
                },
            ],
        }
        result = self.security.check_trigger_comment(issue)
        self.assertEqual(result, ("Approved", "Claude", "testuser"))

        # No trigger
        issue_no_trigger = {
            "number": 456,
            "comments": [{"author": {"login": "testuser"}, "body": "This needs work"}],
        }
        result = self.security.check_trigger_comment(issue_no_trigger)
        self.assertIsNone(result)

        # Trigger from unauthorized user
        issue_unauthorized = {
            "number": 789,
            "comments": [{"author": {"login": "hacker"}, "body": "[Approved][Claude]"}],
        }
        result = self.security.check_trigger_comment(issue_unauthorized)
        self.assertIsNone(result)

    def test_most_recent_trigger_wins(self):
        """Test that the most recent valid trigger is used."""
        issue = {
            "number": 100,
            "comments": [
                {"author": {"login": "testuser"}, "body": "[Close][Claude]"},
                {"author": {"login": "admin"}, "body": "[Summarize][Gemini]"},
                {
                    "author": {"login": "testuser"},
                    "body": "[Approved][Claude]",
                },  # Most recent
            ],
        }
        result = self.security.check_trigger_comment(issue)
        self.assertEqual(result, ("Approved", "Claude", "testuser"))


class TestIssueMonitorWithTriggers(unittest.TestCase):
    """Test IssueMonitor with keyword triggers."""

    def setUp(self):
        """Set up test environment with mocked GitHub."""
        # Set required environment variables
        os.environ["GITHUB_REPOSITORY"] = "testowner/testrepo"
        os.environ["GITHUB_TOKEN"] = "fake-token"

        # Create a temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.config_data = {
            "agents": {
                "issue_monitor": {
                    "enabled": True,
                    "min_description_length": 10,
                    "required_fields": ["description"],
                    "actionable_labels": ["bug", "feature"],
                    "cutoff_hours": 24,
                },
            },
            "security": {
                "enabled": True,
                "allow_list": ["testuser", "admin"],
                "log_violations": True,
                "rate_limit_window_minutes": 60,
                "rate_limit_max_requests": 10,
            },
        }
        json.dump(self.config_data, self.temp_config)
        self.temp_config.close()

        # Patch the config loading
        self.patcher = patch.object(IssueMonitor, "_load_config")
        self.mock_load_config = self.patcher.start()
        self.mock_load_config.return_value = self.config_data

        # Patch SecurityManager to use our test allow list
        self.security_patcher = patch.object(SecurityManager, "__init__")
        self.mock_security_init = self.security_patcher.start()
        self.mock_security_init.return_value = None

        self.monitor = IssueMonitor()
        # Manually set up security manager with our test allow list
        self.monitor.security_manager.allow_list = ["testuser", "admin", "testowner"]
        self.monitor.security_manager.enabled = True
        self.monitor.security_manager.log_violations = True
        self.monitor.security_manager.reject_message = "Test rejection"
        self.monitor.security_manager.rate_limit_window = 60
        self.monitor.security_manager.rate_limit_max_requests = 10
        self.monitor.security_manager.VALID_ACTIONS = [
            "Approved",
            "Close",
            "Summarize",
            "Debug",
            "Fix",
            "Implement",
            "Review",
        ]
        self.monitor.security_manager.VALID_AGENTS = ["Claude", "Gemini"]
        self.monitor.security_manager.TRIGGER_PATTERN = SecurityManager.TRIGGER_PATTERN
        self.monitor.security_manager.is_user_allowed = lambda user: user in [
            "testuser",
            "admin",
            "testowner",
        ]
        self.monitor.security_manager.parse_keyword_trigger = SecurityManager.parse_keyword_trigger.__get__(
            self.monitor.security_manager, SecurityManager
        )
        self.monitor.security_manager.check_trigger_comment = SecurityManager.check_trigger_comment.__get__(
            self.monitor.security_manager, SecurityManager
        )
        self.monitor.security_manager.perform_full_security_check = lambda **kwargs: (
            True,
            None,
        )
        self.monitor.security_manager.check_rate_limit = lambda user, action: (
            True,
            None,
        )

    def tearDown(self):
        """Clean up."""
        self.patcher.stop()
        self.security_patcher.stop()
        os.unlink(self.temp_config.name)
        if "GITHUB_REPOSITORY" in os.environ:
            del os.environ["GITHUB_REPOSITORY"]
        if "GITHUB_TOKEN" in os.environ:
            del os.environ["GITHUB_TOKEN"]

    @patch("issue_monitor.run_gh_command")
    def test_process_issue_with_approved_trigger(self, mock_gh):
        """Test processing an issue with [Approved][Claude] trigger."""
        # Mock getting open issues
        mock_gh.side_effect = [
            # get_open_issues response
            json.dumps(
                [
                    {
                        "number": 1,
                        "title": "Test bug",
                        "body": (
                            "This is a test bug with enough description. "
                            "Expected behavior: the app should work. "
                            "Steps to reproduce: 1. Run the app 2. Click submit 3. See error. "
                            "Version: 1.0.0 ```python\nprint('error')\n```"
                        ),
                        "author": {"login": "testuser"},
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "labels": [{"name": "bug"}],
                        "comments": [
                            {
                                "author": {"login": "testuser"},
                                "body": "[Approved][Claude] Let's fix this",
                            }
                        ],
                    }
                ]
            ),
            # issue view response for comments
            json.dumps(
                {
                    "comments": [
                        {
                            "author": {"login": "testuser"},
                            "body": "[Approved][Claude] Let's fix this",
                        }
                    ]
                }
            ),
            # has_agent_comment response
            json.dumps({"comments": []}),
            # has_agent_claimed_work response
            json.dumps({"comments": []}),
            # post_starting_work_comment response
            None,
            # create_pr_from_issue responses will be added as needed
        ]

        with patch.object(self.monitor, "create_pr_from_issue") as mock_create_pr:
            self.monitor.process_issues()
            # Should create a PR since it's approved and has enough info
            mock_create_pr.assert_called_once()

    @patch("issue_monitor.run_gh_command")
    def test_process_issue_with_close_trigger(self, mock_gh):
        """Test processing an issue with [Close][Gemini] trigger."""
        mock_gh.side_effect = [
            # get_open_issues response
            json.dumps(
                [
                    {
                        "number": 2,
                        "title": "Feature request",
                        "body": "Add new feature",
                        "author": {"login": "randomuser"},
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "labels": [{"name": "feature"}],
                        "comments": [
                            {
                                "author": {"login": "admin"},
                                "body": "[Close][Gemini] Duplicate issue",
                            }
                        ],
                    }
                ]
            ),
            # issue view response for comments
            json.dumps(
                {
                    "comments": [
                        {
                            "author": {"login": "admin"},
                            "body": "[Close][Gemini] Duplicate issue",
                        }
                    ]
                }
            ),
            # has_agent_comment response
            json.dumps({"comments": []}),
            # close issue command
            None,
            # create_action_comment
            None,
        ]

        self.monitor.process_issues()

        # Verify close command was called
        close_call = [call for call in mock_gh.call_args_list if "close" in call[0][0]]
        self.assertEqual(len(close_call), 1)
        self.assertIn("2", close_call[0][0][0])  # Issue number

    @patch("issue_monitor.run_gh_command")
    def test_process_issue_with_summarize_trigger(self, mock_gh):
        """Test processing an issue with [Summarize][Claude] trigger."""
        mock_gh.side_effect = [
            # get_open_issues response
            json.dumps(
                [
                    {
                        "number": 3,
                        "title": "Complex issue",
                        "body": "This is a complex issue that needs summarization",
                        "author": {"login": "user1"},
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "labels": [],
                        "comments": [
                            {
                                "author": {"login": "testuser"},
                                "body": "[Summarize][Claude]",
                            }
                        ],
                    }
                ]
            ),
            # issue view response for comments
            json.dumps(
                {
                    "comments": [
                        {
                            "author": {"login": "testuser"},
                            "body": "[Summarize][Claude]",
                        }
                    ]
                }
            ),
            # has_agent_comment response
            json.dumps({"comments": []}),
            # create_summary_comment
            None,
        ]

        self.monitor.process_issues()

        # Verify summary comment was created
        comment_calls = [call for call in mock_gh.call_args_list if "comment" in call[0][0]]
        self.assertGreater(len(comment_calls), 0)

    @patch("issue_monitor.run_gh_command")
    def test_no_processing_without_trigger(self, mock_gh):
        """Test that issues without triggers are not processed."""
        mock_gh.side_effect = [
            # get_open_issues response
            json.dumps(
                [
                    {
                        "number": 4,
                        "title": "Issue without trigger",
                        "body": "This issue has no trigger comment",
                        "author": {"login": "testuser"},
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "labels": [{"name": "bug"}],
                        "comments": [
                            {
                                "author": {"login": "testuser"},
                                "body": "Just a regular comment",
                            }
                        ],
                    }
                ]
            ),
            # issue view response for comments
            json.dumps(
                {
                    "comments": [
                        {
                            "author": {"login": "testuser"},
                            "body": "Just a regular comment",
                        }
                    ]
                }
            ),
        ]

        with patch.object(self.monitor, "create_pr_from_issue") as mock_create_pr:
            self.monitor.process_issues()
            # Should NOT create a PR since there's no trigger
            mock_create_pr.assert_not_called()

    @patch("issue_monitor.run_gh_command")
    def test_security_rejection_for_unauthorized_trigger(self, mock_gh):
        """Test that unauthorized users can't trigger actions."""
        mock_gh.side_effect = [
            # get_open_issues response
            json.dumps(
                [
                    {
                        "number": 5,
                        "title": "Malicious issue",
                        "body": "Evil content",
                        "author": {"login": "hacker"},
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "labels": [{"name": "bug"}],
                        "comments": [
                            {
                                "author": {"login": "hacker"},
                                "body": "[Approved][Claude] Hack the system",
                            }
                        ],
                    }
                ]
            ),
            # issue view response for comments
            json.dumps(
                {
                    "comments": [
                        {
                            "author": {"login": "hacker"},
                            "body": "[Approved][Claude] Hack the system",
                        }
                    ]
                }
            ),
        ]

        with patch.object(self.monitor, "create_pr_from_issue") as mock_create_pr:
            self.monitor.process_issues()
            # Should NOT create a PR since user is not authorized
            mock_create_pr.assert_not_called()


class TestPRMonitorWithTriggers(unittest.TestCase):
    """Test PRReviewMonitor with keyword triggers."""

    def setUp(self):
        """Set up test environment."""
        os.environ["GITHUB_REPOSITORY"] = "testowner/testrepo"
        os.environ["GITHUB_TOKEN"] = "fake-token"

        self.config_data = {
            "agents": {
                "pr_review_monitor": {
                    "enabled": True,
                    "review_bot_names": ["gemini-bot"],
                    "cutoff_hours": 24,
                },
            },
            "security": {
                "enabled": True,
                "allow_list": ["testuser", "admin"],
            },
        }

        with patch.object(PRReviewMonitor, "_load_config") as mock_config:
            mock_config.return_value = self.config_data
            with patch.object(SecurityManager, "__init__") as mock_security_init:
                mock_security_init.return_value = None
                self.monitor = PRReviewMonitor()
                # Set up security manager with test allow list
                self.monitor.security_manager.allow_list = [
                    "testuser",
                    "admin",
                    "maintainer",
                    "testowner",
                ]
                self.monitor.security_manager.enabled = True
                self.monitor.security_manager.log_violations = True
                self.monitor.security_manager.VALID_ACTIONS = [
                    "Approved",
                    "Close",
                    "Summarize",
                    "Debug",
                    "Fix",
                    "Implement",
                    "Review",
                ]
                self.monitor.security_manager.VALID_AGENTS = ["Claude", "Gemini"]
                self.monitor.security_manager.TRIGGER_PATTERN = SecurityManager.TRIGGER_PATTERN
                self.monitor.security_manager.is_user_allowed = lambda user: user in [
                    "testuser",
                    "admin",
                    "maintainer",
                    "testowner",
                ]
                self.monitor.security_manager.parse_keyword_trigger = SecurityManager.parse_keyword_trigger.__get__(
                    self.monitor.security_manager, SecurityManager
                )
                self.monitor.security_manager.check_trigger_comment = SecurityManager.check_trigger_comment.__get__(
                    self.monitor.security_manager, SecurityManager
                )
                self.monitor.security_manager.perform_full_security_check = lambda **kwargs: (True, None)
                self.monitor.security_manager.check_rate_limit = lambda user, action: (
                    True,
                    None,
                )

    def tearDown(self):
        """Clean up."""
        if "GITHUB_REPOSITORY" in os.environ:
            del os.environ["GITHUB_REPOSITORY"]
        if "GITHUB_TOKEN" in os.environ:
            del os.environ["GITHUB_TOKEN"]

    @patch("pr_review_monitor.run_gh_command")
    @patch("pr_review_monitor.PRReviewMonitor.address_review_feedback")
    @patch("pr_review_monitor.PRReviewMonitor.get_pr_latest_commit")
    @patch("pr_review_monitor.PRReviewMonitor.get_commit_for_comment")
    @patch("pr_review_monitor.PRReviewMonitor.get_pr_review_comments")
    @patch("pr_review_monitor.PRReviewMonitor.get_pr_reviews")
    @patch("pr_review_monitor.PRReviewMonitor.get_pr_check_status")
    @patch("pr_review_monitor.PRReviewMonitor.has_agent_addressed_review")
    @patch("pr_review_monitor.PRReviewMonitor.get_pr_general_comments")
    @patch("pr_review_monitor.PRReviewMonitor.get_open_prs")
    def test_process_pr_with_review_trigger(
        self,
        mock_get_open_prs,
        mock_get_general_comments,
        mock_has_addressed,
        mock_check_status,
        mock_get_reviews,
        mock_get_review_comments,
        mock_get_commit_for_comment,
        mock_get_pr_latest_commit,
        mock_address_review_feedback,
        mock_gh,
    ):
        """Test processing a PR with [Review][Claude] trigger."""
        # Set up the PR data structure matching the expected format
        test_pr = {
            "number": 10,
            "title": "Fix: Update API",
            "body": "Fixes API endpoints",
            "author": {"login": "contributor"},
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "headRefName": "fix-api",
            "labels": [],
            "reviews": [],
            "comments": [
                {
                    "author": {"login": "admin"},
                    "body": "[Review][Claude] Please check this",
                }
            ],
        }

        # Set up comment data
        test_comment = {
            "user": {"login": "admin"},
            "body": "[Review][Claude] Please check this",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "id": 12345,
        }

        # Set up review data
        test_review = {
            "author": {"login": "gemini-bot"},
            "state": "CHANGES_REQUESTED",
            "body": "Please fix the import statements",
            "id": 67890,
        }

        # Configure mock return values
        mock_get_open_prs.return_value = [test_pr]
        mock_get_general_comments.return_value = [test_comment]
        mock_has_addressed.return_value = False  # Not yet addressed

        # Mock gh command calls - we need to return the comments
        mock_gh.return_value = json.dumps({"comments": []})
        mock_check_status.return_value = {
            "checks": [],
            "has_failures": False,
            "failing_checks": [],
            "in_progress": False,
        }
        mock_get_reviews.return_value = [test_review]
        mock_get_review_comments.return_value = []
        mock_get_commit_for_comment.return_value = "abc123"
        mock_get_pr_latest_commit.return_value = "abc123"
        mock_address_review_feedback.return_value = (
            True,
            None,
            "Fixed import statements",
        )

        # Execute the method
        self.monitor.process_pr_reviews()

        # Verify the workflow was executed
        mock_get_open_prs.assert_called_once()
        mock_get_general_comments.assert_called_once_with(10)
        mock_has_addressed.assert_called_once_with(10)
        # Check status is called twice in the process
        self.assertEqual(mock_check_status.call_count, 2)
        mock_check_status.assert_any_call(10)
        mock_get_reviews.assert_called_once_with(10)
        mock_get_review_comments.assert_called_once_with(10)

        # Verify address_review_feedback was called with correct parameters
        mock_address_review_feedback.assert_called_once()
        call_args = mock_address_review_feedback.call_args[0]  # Positional args
        self.assertEqual(call_args[0], 10)  # pr_number
        self.assertEqual(call_args[1], "fix-api")  # branch_name
        # The third argument is the feedback dict - it's parsed into a structured format
        feedback = call_args[2]
        self.assertIn("changes_requested", feedback)
        self.assertIn("must_fix", feedback)
        self.assertIn("issues", feedback)
        self.assertTrue(feedback["changes_requested"])
        # The fourth argument is the PR description (includes title and body)
        self.assertIn("Fix: Update API", call_args[3])
        self.assertIn("Fixes API endpoints", call_args[3])

    @patch("pr_review_monitor.PRReviewMonitor.create_action_comment")
    @patch("pr_review_monitor.run_gh_command")
    def test_process_pr_with_close_trigger(self, mock_gh, mock_comment):
        """Test closing a PR with [Close][Gemini] trigger."""
        mock_gh.side_effect = [
            # get_open_prs response
            json.dumps(
                [
                    {
                        "number": 11,
                        "title": "WIP: New feature",
                        "body": "Work in progress",
                        "author": {"login": "user1"},
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "headRefName": "wip-feature",
                        "labels": [],
                        "reviews": [],
                        "comments": [
                            {
                                "author": {"login": "testuser"},
                                "body": "[Close][Gemini] Not ready yet",
                            }
                        ],
                    }
                ]
            ),
            # get_pr_general_comments response
            json.dumps(
                [
                    {
                        "user": {"login": "testuser"},
                        "body": "[Close][Gemini] Not ready yet",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ]
            ),
            # has_agent_addressed_review response (pr view)
            json.dumps({"comments": []}),
            # has_agent_claimed_work response (pr view)
            json.dumps({"comments": []}),
            # post_claim_comment response
            None,
            # get_pr_check_status response (pr view returns object)
            json.dumps({"statusCheckRollup": []}),
            # Second get_pr_check_status response (there's another check after claim comment)
            json.dumps({"statusCheckRollup": []}),
            # close PR command
            None,
            # create_action_comment (pr comment)
            None,
        ]

        self.monitor.process_pr_reviews()

        # Verify close command was called
        close_call = [call for call in mock_gh.call_args_list if "close" in str(call)]
        self.assertGreater(len(close_call), 0)
        # Verify comment was posted
        mock_comment.assert_called_once()


class TestSecurityValidation(unittest.TestCase):
    """Test security validation with keyword triggers."""

    def setUp(self):
        """Set up security manager."""
        self.security = SecurityManager(allow_list=["alice", "bob"])

    def test_rate_limiting_with_triggers(self):
        """Test rate limiting applies to trigger actions."""
        # Simulate many requests from same user
        for i in range(10):
            is_allowed, reason = self.security.check_rate_limit("alice", "issue_approved")
            if i < 10:  # First 10 should pass
                self.assertTrue(is_allowed)

        # 11th request should fail
        is_allowed, reason = self.security.check_rate_limit("alice", "issue_approved")
        self.assertFalse(is_allowed)
        self.assertIn("Rate limit exceeded", reason)

    def test_different_actions_have_separate_limits(self):
        """Test that different actions have separate rate limits."""
        # Use up the limit for "approved" action
        for _ in range(10):
            self.security.check_rate_limit("bob", "issue_approved")

        # "close" action should still work
        is_allowed, _ = self.security.check_rate_limit("bob", "issue_close")
        self.assertTrue(is_allowed)

    def test_security_log_violations(self):
        """Test that security violations are logged."""
        with patch("security.logger.warning") as mock_log:
            # Unauthorized user check
            self.security.is_user_allowed("hacker")
            mock_log.assert_called()
            self.assertIn("not in allow list", mock_log.call_args[0][0])


class TestMockGitHubRepo(unittest.TestCase):
    """Test with a complete mock GitHub repository."""

    def setUp(self):
        """Set up a mock repository state."""
        self.mock_repo = {
            "issues": [
                {
                    "number": 1,
                    "title": "Bug: Application crashes",
                    "body": "The app crashes when clicking submit",
                    "author": {"login": "user1"},
                    "state": "open",
                    "labels": [{"name": "bug"}],
                    "comments": [],
                },
                {
                    "number": 2,
                    "title": "Feature: Add dark mode",
                    "body": "Please add dark mode support",
                    "author": {"login": "user2"},
                    "state": "open",
                    "labels": [{"name": "feature"}],
                    "comments": [],
                },
            ],
            "pulls": [
                {
                    "number": 100,
                    "title": "Fix: Memory leak",
                    "body": "Fixes memory leak in main loop",
                    "author": {"login": "contributor1"},
                    "state": "open",
                    "headRefName": "fix-memory-leak",
                    "reviews": [],
                    "comments": [],
                }
            ],
        }

    def test_simulate_issue_workflow(self):
        """Simulate a complete issue workflow with triggers."""
        issue = self.mock_repo["issues"][0]

        # User comments with trigger
        issue["comments"].append(
            {
                "author": {"login": "admin"},
                "body": "[Approved][Claude] This needs to be fixed ASAP",
            }
        )

        # Verify trigger is detected
        security = SecurityManager(allow_list=["admin"])
        trigger = security.check_trigger_comment(issue)
        self.assertEqual(trigger, ("Approved", "Claude", "admin"))

        # Simulate agent processing
        # In real scenario, agent would create PR, but we just verify the flow
        self.assertEqual(issue["state"], "open")
        self.assertTrue(any("bug" in label["name"] for label in issue["labels"]))

    def test_simulate_pr_workflow(self):
        """Simulate a complete PR workflow with triggers."""
        pr = self.mock_repo["pulls"][0]

        # Add review from bot
        pr["reviews"].append(
            {
                "author": {"login": "gemini-bot"},
                "state": "CHANGES_REQUESTED",
                "body": "Please add tests",
            }
        )

        # Admin triggers fix
        pr["comments"].append(
            {
                "author": {"login": "maintainer"},
                "body": "[Fix][Claude] Address the review feedback",
            }
        )

        # Verify trigger
        security = SecurityManager(allow_list=["maintainer"])
        trigger = security.check_trigger_comment(pr)
        self.assertEqual(trigger, ("Fix", "Claude", "maintainer"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

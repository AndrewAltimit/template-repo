"""
Unit tests for automation/review/gemini-pr-review.py

Focuses on extract_previous_issues function edge cases.
"""

import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch

# Load module with hyphenated filename using importlib
module_path = Path(__file__).parent.parent / "automation" / "review" / "gemini-pr-review.py"
spec = importlib.util.spec_from_file_location("gemini_pr_review", module_path)
assert spec is not None, f"Could not load module spec from {module_path}"
gemini_pr_review = importlib.util.module_from_spec(spec)
sys.modules["gemini_pr_review"] = gemini_pr_review
assert spec.loader is not None, "Module spec has no loader"
spec.loader.exec_module(gemini_pr_review)

# Import needed symbols
extract_previous_issues = gemini_pr_review.extract_previous_issues
NO_MODEL = gemini_pr_review.NO_MODEL


class TestExtractPreviousIssues:
    """Tests for the extract_previous_issues function."""

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_no_comments_returns_empty(self, mock_get_comments):
        """When there are no PR comments, returns empty string."""
        mock_get_comments.return_value = []

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == NO_MODEL

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_no_gemini_reviews_returns_empty(self, mock_get_comments):
        """When comments exist but none are Gemini reviews, returns empty."""
        mock_get_comments.return_value = [
            {"body": "LGTM!"},
            {"body": "Please fix the typo on line 42"},
        ]

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == NO_MODEL

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_gemini_review_without_issues_section(self, mock_get_comments):
        """Gemini review without '## Issues' section is skipped."""
        mock_get_comments.return_value = [
            {"body": "## Gemini Review\n<!-- gemini-review-marker -->\nLooks good!"},
        ]

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == NO_MODEL

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_successful_extraction(self, mock_get_comments, mock_call_gemini):
        """Successfully extracts issues from Gemini review."""
        mock_get_comments.return_value = [
            {
                "body": (
                    "## Gemini Review\n"
                    "<!-- gemini-review-marker:commit:abc123 -->\n"
                    "## Issues\n"
                    "- [BUG] file.py:42 - Missing null check"
                )
            },
        ]
        mock_call_gemini.return_value = (
            "file.py:42 - [BUG] Missing null check",
            "gemini-2.5-flash",
        )

        result, model = extract_previous_issues("123")

        assert "file.py:42" in result
        assert model == "gemini-2.5-flash"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_no_issues_found_marker(self, mock_get_comments, mock_call_gemini):
        """When model returns NO_ISSUES_FOUND, returns empty string."""
        mock_get_comments.return_value = [
            {"body": ("<!-- gemini-review-marker -->\n## Issues\nNo critical issues found.")},
        ]
        mock_call_gemini.return_value = ("NO_ISSUES_FOUND", "gemini-2.5-flash")

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == "gemini-2.5-flash"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_conversational_response_without_issues(self, mock_get_comments, mock_call_gemini):
        """When model returns conversational text without file:line format."""
        mock_get_comments.return_value = [
            {"body": ("<!-- gemini-review-marker -->\n## Issues\nSome issues were found.")},
        ]
        # Model returns text but no file:line pattern
        mock_call_gemini.return_value = (
            "I reviewed the code and found no concrete issues to report.",
            "gemini-2.5-flash",
        )

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == "gemini-2.5-flash"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_model_failure_returns_empty(self, mock_get_comments, mock_call_gemini):
        """When model call fails, returns empty string."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- Bug found"},
        ]
        mock_call_gemini.return_value = ("", NO_MODEL)

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == NO_MODEL

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_exception_handling(self, mock_get_comments):
        """When an exception occurs, returns empty string gracefully."""
        mock_get_comments.side_effect = Exception("Network error")

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == NO_MODEL

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_only_last_three_reviews_used(self, mock_get_comments, mock_call_gemini):
        """Only the last 3 Gemini reviews are used for extraction."""
        # Create 5 reviews
        reviews = [{"body": f"<!-- gemini-review-marker -->\n## Issues\nReview {i}"} for i in range(5)]
        mock_get_comments.return_value = reviews
        mock_call_gemini.return_value = ("file.py:1 - [BUG] Test", "gemini-2.5-flash")

        extract_previous_issues("123")

        # Check that prompt only contains last 3 reviews (2, 3, 4)
        call_args = mock_call_gemini.call_args[0][0]
        assert "Review 2" in call_args
        assert "Review 3" in call_args
        assert "Review 4" in call_args
        assert "Review 0" not in call_args
        assert "Review 1" not in call_args

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_hyphenated_filename_validation(self, mock_get_comments, mock_call_gemini):
        """Validates filenames with hyphens are accepted."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- Bug"},
        ]
        mock_call_gemini.return_value = (
            "gemini-pr-review.py:42 - [BUG] Regex issue",
            "gemini-2.5-flash",
        )

        result, model = extract_previous_issues("123")

        assert "gemini-pr-review.py:42" in result
        assert model == "gemini-2.5-flash"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_extensionless_filename_validation(self, mock_get_comments, mock_call_gemini):
        """Validates filenames without extensions (like Dockerfile) are accepted."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- Bug"},
        ]
        mock_call_gemini.return_value = (
            "Dockerfile:10 - [BUG] Missing WORKDIR",
            "gemini-2.5-flash",
        )

        result, model = extract_previous_issues("123")

        assert "Dockerfile:10" in result
        assert model == "gemini-2.5-flash"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_nested_path_validation(self, mock_get_comments, mock_call_gemini):
        """Validates nested file paths are accepted."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- Bug"},
        ]
        mock_call_gemini.return_value = (
            "automation/review/gemini-pr-review.py:100 - [CRITICAL] Security issue",
            "gemini-2.5-flash",
        )

        result, model = extract_previous_issues("123")

        assert "automation/review/gemini-pr-review.py:100" in result
        assert model == "gemini-2.5-flash"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_case_insensitive_no_issues_marker(self, mock_get_comments, mock_call_gemini):
        """NO_ISSUES_FOUND check is case-insensitive."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- None"},
        ]
        mock_call_gemini.return_value = (
            "no_issues_found",  # lowercase
            "gemini-2.5-flash",
        )

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == "gemini-2.5-flash"

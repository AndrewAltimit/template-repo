"""
Unit tests for automation/review/gemini-pr-review.py

Focuses on extract_previous_issues function and anti-hallucination logic.
"""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
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
_extract_claimed_patterns = gemini_pr_review._extract_claimed_patterns
_read_file_content = gemini_pr_review._read_file_content
_verify_review_claims = gemini_pr_review._verify_review_claims
_filter_debunked_issues = gemini_pr_review._filter_debunked_issues


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
            "gemini-3-flash-preview",
        )

        result, model = extract_previous_issues("123")

        assert "file.py:42" in result
        assert model == "gemini-3-flash-preview"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_no_issues_found_marker(self, mock_get_comments, mock_call_gemini):
        """When model returns NO_ISSUES_FOUND, returns empty string."""
        mock_get_comments.return_value = [
            {"body": ("<!-- gemini-review-marker -->\n## Issues\nNo critical issues found.")},
        ]
        mock_call_gemini.return_value = ("NO_ISSUES_FOUND", "gemini-3-flash-preview")

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == "gemini-3-flash-preview"

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
            "gemini-3-flash-preview",
        )

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == "gemini-3-flash-preview"

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
        mock_call_gemini.return_value = ("file.py:1 - [BUG] Test", "gemini-3-flash-preview")

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
            "gemini-3-flash-preview",
        )

        result, model = extract_previous_issues("123")

        assert "gemini-pr-review.py:42" in result
        assert model == "gemini-3-flash-preview"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_extensionless_filename_validation(self, mock_get_comments, mock_call_gemini):
        """Validates filenames without extensions (like Dockerfile) are accepted."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- Bug"},
        ]
        mock_call_gemini.return_value = (
            "Dockerfile:10 - [BUG] Missing WORKDIR",
            "gemini-3-flash-preview",
        )

        result, model = extract_previous_issues("123")

        assert "Dockerfile:10" in result
        assert model == "gemini-3-flash-preview"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_nested_path_validation(self, mock_get_comments, mock_call_gemini):
        """Validates nested file paths are accepted."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- Bug"},
        ]
        mock_call_gemini.return_value = (
            "automation/review/gemini-pr-review.py:100 - [CRITICAL] Security issue",
            "gemini-3-flash-preview",
        )

        result, model = extract_previous_issues("123")

        assert "automation/review/gemini-pr-review.py:100" in result
        assert model == "gemini-3-flash-preview"

    @patch("gemini_pr_review._call_gemini_with_model")
    @patch("gemini_pr_review.get_all_pr_comments")
    def test_case_insensitive_no_issues_marker(self, mock_get_comments, mock_call_gemini):
        """NO_ISSUES_FOUND check is case-insensitive."""
        mock_get_comments.return_value = [
            {"body": "<!-- gemini-review-marker -->\n## Issues\n- None"},
        ]
        mock_call_gemini.return_value = (
            "no_issues_found",  # lowercase
            "gemini-3-flash-preview",
        )

        result, model = extract_previous_issues("123")

        assert result == ""
        assert model == "gemini-3-flash-preview"


class TestExtractClaimedPatterns:
    """Tests for the _extract_claimed_patterns function."""

    def test_extracts_backtick_content(self):
        """Extracts content from backticks."""
        desc = "File contains `[Generate]` and `deprecated_func` triggers"
        patterns = _extract_claimed_patterns(desc)
        assert "[Generate]" in patterns
        assert "deprecated_func" in patterns

    def test_extracts_quoted_content(self):
        """Extracts content from quotes."""
        desc = 'Section has "Git Monitoring" workflows and "[Fix]" triggers'
        patterns = _extract_claimed_patterns(desc)
        assert "Git Monitoring" in patterns
        assert "[Fix]" in patterns

    def test_extracts_trigger_patterns(self):
        """Extracts trigger-like patterns [Action]."""
        desc = "Contains [Generate], [Refactor], and [Quick] triggers"
        patterns = _extract_claimed_patterns(desc)
        assert "[Generate]" in patterns
        assert "[Refactor]" in patterns
        assert "[Quick]" in patterns

    def test_extracts_hallucination_keywords(self):
        """Extracts common hallucination keywords."""
        desc = "Has Git Monitoring Workflows section with [Implement] trigger"
        patterns = _extract_claimed_patterns(desc)
        assert "Git Monitoring Workflows" in patterns or "Git Monitoring" in patterns
        assert "[Implement]" in patterns

    def test_deduplicates_patterns(self):
        """Removes duplicate patterns."""
        desc = "`[Fix]` and [Fix] and `[Fix]`"
        patterns = _extract_claimed_patterns(desc)
        # Should only have one [Fix]
        fix_count = sum(1 for p in patterns if p.lower() == "[fix]")
        assert fix_count == 1

    def test_skips_short_patterns(self):
        """Skips patterns shorter than 3 characters."""
        desc = "`a` and `ab` and `abc`"
        patterns = _extract_claimed_patterns(desc)
        assert "a" not in patterns
        assert "ab" not in patterns
        assert "abc" in patterns

    def test_empty_description(self):
        """Returns empty list for empty description."""
        patterns = _extract_claimed_patterns("")
        assert patterns == []


class TestReadFileContent:
    """Tests for the _read_file_content function."""

    def test_reads_existing_file(self):
        """Reads content from an existing file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    pass\n")
            f.flush()
            try:
                # Change to temp dir to allow reading
                old_cwd = os.getcwd()
                os.chdir(tempfile.gettempdir())
                content = _read_file_content(f.name)
                os.chdir(old_cwd)
                assert content is not None
                assert "def hello():" in content
            finally:
                os.unlink(f.name)

    def test_returns_none_for_nonexistent_file(self):
        """Returns None for non-existent file."""
        content = _read_file_content("/nonexistent/path/to/file.py")
        assert content is None

    def test_prevents_path_traversal(self):
        """Blocks path traversal attempts."""
        # Try to read outside current directory
        content = _read_file_content("../../../etc/passwd")
        assert content is None


class TestVerifyReviewClaims:
    """Tests for the _verify_review_claims function."""

    def test_passes_valid_claims(self):
        """Valid claims pass verification."""
        # Create a temp file with actual content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
            f.write("import os\nimport sys\n")
            f.flush()
            try:
                verified, count = _verify_review_claims(
                    f"- [BUG] {os.path.basename(f.name)}:1 - Missing import statement",
                    [os.path.basename(f.name)],
                )
                # Should not be marked as hallucination (no specific pattern claimed)
                assert count == 0
            finally:
                os.unlink(f.name)

    def test_flags_file_not_in_diff(self):
        """Flags issues about files not in the PR diff."""
        review = "- [BUG] other_file.py:10 - Some issue"
        changed_files = ["main.py", "test.py"]

        verified, count = _verify_review_claims(review, changed_files)

        assert count == 1
        assert "UNVERIFIED: file not in diff" in verified

    def test_detects_hallucinated_patterns(self):
        """Detects claims about patterns that don't exist in file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
            f.write("# This file has no triggers\nimport os\n")
            f.flush()
            try:
                review = f"- [BUG] {os.path.basename(f.name)}:1 - Contains `[Generate]` deprecated trigger"
                verified, count = _verify_review_claims(review, [os.path.basename(f.name)])
                assert count == 1
                assert "HALLUCINATION" in verified
            finally:
                os.unlink(f.name)

    def test_accepts_claims_with_existing_patterns(self):
        """Accepts claims when pattern exists in file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
            f.write("# Supported triggers: [Approved], [Review]\n")
            f.flush()
            try:
                review = f"- [BUG] {os.path.basename(f.name)}:1 - Contains `[Approved]` trigger"
                verified, count = _verify_review_claims(review, [os.path.basename(f.name)])
                assert count == 0
                assert "HALLUCINATION" not in verified
            finally:
                os.unlink(f.name)

    def test_resolves_partial_paths(self):
        """Resolves partial paths against changed_files."""
        review = "- [BUG] script.py:5 - Issue found"
        changed_files = ["automation/tools/script.py"]

        # This should match even though the paths differ
        verified, count = _verify_review_claims(review, changed_files)
        # Count depends on whether file exists - but shouldn't be "not in diff"
        assert "file not in diff" not in verified


class TestFilterDebunkedIssues:
    """Tests for the _filter_debunked_issues function."""

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_filters_debunked_issues(self, mock_get_comments):
        """Filters out issues that were debunked in human comments."""
        mock_get_comments.return_value = [
            {"body": "This is a false positive. The claim about file.py:42 having deprecated triggers is incorrect."},
        ]

        issues = ["- [BUG] file.py:42 - Has deprecated triggers", "- [BUG] other.py:10 - Real issue"]

        filtered = _filter_debunked_issues(issues, "123")

        assert len(filtered) == 1
        assert "other.py:10" in filtered[0]
        assert "file.py:42" not in str(filtered)

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_keeps_non_debunked_issues(self, mock_get_comments):
        """Keeps issues that weren't debunked."""
        mock_get_comments.return_value = [
            {"body": "LGTM, please fix the typo."},
        ]

        issues = ["- [BUG] file.py:42 - Has issue", "- [BUG] other.py:10 - Another issue"]

        filtered = _filter_debunked_issues(issues, "123")

        assert len(filtered) == 2

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_handles_no_comments(self, mock_get_comments):
        """Handles case with no comments."""
        mock_get_comments.return_value = []

        issues = ["- [BUG] file.py:42 - Has issue"]

        filtered = _filter_debunked_issues(issues, "123")

        assert len(filtered) == 1

    @patch("gemini_pr_review.get_all_pr_comments")
    def test_detects_hallucination_keywords(self, mock_get_comments):
        """Detects various debunking keywords."""
        mock_get_comments.return_value = [
            {"body": "Gemini is hallucinating about test.py:100"},
        ]

        issues = ["- [BUG] test.py:100 - Fake issue"]

        filtered = _filter_debunked_issues(issues, "123")

        assert len(filtered) == 0

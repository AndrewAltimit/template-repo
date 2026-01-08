"""
Unit tests for automation/review/codex-pr-review.py

Tests the Codex PR review script functionality including:
- Prerequisite checking
- Gemini review loading
- PR info extraction
- Codex CLI invocation
- Comment formatting and posting
"""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock, patch

# Load module with hyphenated filename using importlib
module_path = Path(__file__).parent.parent / "automation" / "review" / "codex-pr-review.py"
spec = importlib.util.spec_from_file_location("codex_pr_review", module_path)
assert spec is not None, f"Could not load module spec from {module_path}"
codex_pr_review = importlib.util.module_from_spec(spec)
sys.modules["codex_pr_review"] = codex_pr_review
assert spec.loader is not None, "Module spec has no loader"
spec.loader.exec_module(codex_pr_review)

# Import needed symbols
check_prerequisites = codex_pr_review.check_prerequisites
get_pr_info = codex_pr_review.get_pr_info
get_current_commit_sha = codex_pr_review.get_current_commit_sha
get_changed_files = codex_pr_review.get_changed_files
get_pr_diff = codex_pr_review.get_pr_diff
load_gemini_review = codex_pr_review.load_gemini_review
call_codex = codex_pr_review.call_codex
analyze_pr = codex_pr_review.analyze_pr
format_github_comment = codex_pr_review.format_github_comment
post_pr_comment = codex_pr_review.post_pr_comment


class TestCheckPrerequisites:
    """Tests for the check_prerequisites function."""

    @patch("codex_pr_review.shutil.which")
    def test_all_prerequisites_met(self, mock_which):
        """Returns success when Codex CLI is available and auth exists."""
        mock_which.return_value = "/usr/local/bin/codex"

        with patch.object(Path, "exists", return_value=True):
            ok, errors = check_prerequisites()

        assert ok is True
        assert errors == []

    @patch("codex_pr_review.shutil.which")
    def test_codex_cli_not_found(self, mock_which):
        """Returns error when Codex CLI is not installed."""
        mock_which.return_value = None

        with patch.object(Path, "exists", return_value=True):
            ok, errors = check_prerequisites()

        assert ok is False
        assert any("Codex CLI not found" in e for e in errors)

    @patch("codex_pr_review.shutil.which")
    def test_codex_auth_missing(self, mock_which):
        """Returns error when Codex auth file is missing."""
        mock_which.return_value = "/usr/local/bin/codex"

        with patch.object(Path, "exists", return_value=False):
            ok, errors = check_prerequisites()

        assert ok is False
        assert any("auth not found" in e for e in errors)

    @patch("codex_pr_review.shutil.which")
    def test_untrusted_path_rejected(self, mock_which):
        """Returns error when Codex CLI is in untrusted location."""
        mock_which.return_value = "/tmp/malicious/codex"

        with patch.object(Path, "exists", return_value=True):
            ok, errors = check_prerequisites()

        assert ok is False
        assert any("untrusted location" in e for e in errors)


class TestGetPRInfo:
    """Tests for the get_pr_info function."""

    def test_extracts_all_env_vars(self):
        """Extracts all PR info from environment variables."""
        env = {
            "PR_NUMBER": "42",
            "PR_TITLE": "Test PR Title",
            "PR_BODY": "PR description here",
            "PR_AUTHOR": "testuser",
            "BASE_BRANCH": "main",
            "HEAD_BRANCH": "feature/test",
        }

        with patch.dict(os.environ, env, clear=False):
            info = get_pr_info()

        assert info["number"] == "42"
        assert info["title"] == "Test PR Title"
        assert info["body"] == "PR description here"
        assert info["author"] == "testuser"
        assert info["base_branch"] == "main"
        assert info["head_branch"] == "feature/test"

    def test_default_values_when_missing(self):
        """Uses default values when env vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            info = get_pr_info()

        assert info["number"] == ""
        assert info["title"] == "Unknown PR"
        assert info["author"] == "unknown"
        assert info["base_branch"] == "main"


class TestGetCurrentCommitSha:
    """Tests for the get_current_commit_sha function."""

    @patch("subprocess.run")
    def test_returns_short_sha(self, mock_run):
        """Returns short commit SHA from git."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc1234\n")

        sha = get_current_commit_sha()

        assert sha == "abc1234"

    @patch("subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        """Returns empty string on git failure."""
        mock_run.side_effect = Exception("Git not found")

        sha = get_current_commit_sha()

        assert sha == ""


class TestGetChangedFiles:
    """Tests for the get_changed_files function."""

    @patch("subprocess.run")
    def test_returns_file_list(self, mock_run):
        """Returns list of changed files."""
        mock_run.return_value = MagicMock(returncode=0, stdout="file1.py\nfile2.py\nfile3.py\n")

        with patch.dict(os.environ, {"BASE_BRANCH": "main"}):
            files = get_changed_files()

        assert files == ["file1.py", "file2.py", "file3.py"]

    @patch("subprocess.run")
    def test_filters_empty_lines(self, mock_run):
        """Filters out empty lines from file list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="file1.py\n\nfile2.py\n\n")

        with patch.dict(os.environ, {"BASE_BRANCH": "main"}):
            files = get_changed_files()

        assert files == ["file1.py", "file2.py"]

    @patch("subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        """Returns empty list on git failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        with patch.dict(os.environ, {"BASE_BRANCH": "main"}):
            files = get_changed_files()

        assert files == []


class TestLoadGeminiReview:
    """Tests for the load_gemini_review function."""

    def test_loads_from_env_path(self):
        """Loads Gemini review from GEMINI_REVIEW_PATH."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("## Gemini Review\nSome feedback here")
            f.flush()

            try:
                with patch.dict(os.environ, {"GEMINI_REVIEW_PATH": f.name}):
                    review = load_gemini_review()

                assert review is not None
                assert "Gemini Review" in review
            finally:
                os.unlink(f.name)

    def test_loads_from_env_content(self):
        """Loads Gemini review from GEMINI_REVIEW_CONTENT."""
        content = "## Gemini Review\nInline content"

        with patch.dict(os.environ, {"GEMINI_REVIEW_CONTENT": content}, clear=False):
            # Clear GEMINI_REVIEW_PATH to ensure we use content
            with patch.dict(os.environ, {"GEMINI_REVIEW_PATH": ""}, clear=False):
                review = load_gemini_review()

        assert review == content

    def test_loads_from_local_file(self):
        """Loads Gemini review from gemini-review.md in current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "gemini-review.md"
            review_path.write_text("## Local Gemini Review\nLocal content")

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch.dict(os.environ, {"GEMINI_REVIEW_PATH": "", "GEMINI_REVIEW_CONTENT": ""}, clear=False):
                    review = load_gemini_review()

                assert review is not None
                assert "Local Gemini Review" in review
            finally:
                os.chdir(old_cwd)

    def test_returns_none_when_not_found(self):
        """Returns None when no Gemini review is available."""
        with patch.dict(os.environ, {"GEMINI_REVIEW_PATH": "", "GEMINI_REVIEW_CONTENT": ""}, clear=False):
            with tempfile.TemporaryDirectory() as tmpdir:
                old_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    review = load_gemini_review()

                    assert review is None
                finally:
                    os.chdir(old_cwd)


class TestCallCodex:
    """Tests for the call_codex function."""

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_successful_call_v079_format(self, mock_run, mock_which):
        """Successfully calls Codex and parses v0.79.0 JSONL response."""
        mock_which.return_value = "/usr/local/bin/codex"
        # Mock JSONL output from Codex v0.79.0 format
        jsonl_output = (
            '{"type": "thread.started", "thread_id": "test-123"}\n'
            '{"type": "item.completed", "item": {"type": "message", '
            '"content": [{"type": "text", "text": "Here is the review"}]}}\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=jsonl_output)

        result, success = call_codex("Review this code")

        assert success is True
        assert "Here is the review" in result

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_successful_call_legacy_format(self, mock_run, mock_which):
        """Successfully calls Codex and parses legacy JSONL response."""
        mock_which.return_value = "/usr/local/bin/codex"
        # Mock JSONL output from older Codex format
        jsonl_output = '{"msg": {"type": "agent_message", "message": "Here is the review"}}\n'
        mock_run.return_value = MagicMock(returncode=0, stdout=jsonl_output)

        result, success = call_codex("Review this code")

        assert success is True
        assert "Here is the review" in result

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_handles_multiple_messages(self, mock_run, mock_which):
        """Handles multiple message events in JSONL output."""
        mock_which.return_value = "/usr/local/bin/codex"
        jsonl_output = (
            '{"type": "item.completed", "item": {"type": "message", '
            '"content": [{"type": "text", "text": "Part 1"}]}}\n'
            '{"type": "item.completed", "item": {"type": "message", '
            '"content": [{"type": "text", "text": "Part 2"}]}}\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=jsonl_output)

        result, success = call_codex("Review this code")

        assert success is True
        assert "Part 1" in result
        assert "Part 2" in result

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_handles_reasoning_events_v079(self, mock_run, mock_which):
        """Extracts reasoning from v0.79.0 format when no messages present."""
        mock_which.return_value = "/usr/local/bin/codex"
        # Use content that won't be filtered as process description
        # (reasoning starting with "analyzing", "checking" etc. are filtered)
        jsonl_output = '{"type": "item.completed", "item": {"type": "reasoning", "text": "The function at line 42 has a potential null reference issue"}}\n'
        mock_run.return_value = MagicMock(returncode=0, stdout=jsonl_output)

        result, success = call_codex("Review this code")

        assert success is True
        # Should be formatted as structured review with the finding included
        assert "Issues" in result or "null reference" in result

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_handles_reasoning_events_legacy(self, mock_run, mock_which):
        """Extracts reasoning from legacy format when no messages present."""
        mock_which.return_value = "/usr/local/bin/codex"
        # Use content that won't be filtered as process description
        jsonl_output = (
            '{"msg": {"type": "agent_reasoning", "text": "The function at line 42 has a potential null reference issue"}}\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=jsonl_output)

        result, success = call_codex("Review this code")

        assert success is True
        # Should be formatted as structured review with the finding included
        assert "Issues" in result or "null reference" in result

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_returns_failure_on_error(self, mock_run, mock_which):
        """Returns failure when Codex CLI errors."""
        mock_which.return_value = "/usr/local/bin/codex"
        mock_run.return_value = MagicMock(returncode=1, stderr="API error", stdout="")

        result, success = call_codex("Review this code")

        assert success is False
        assert "error" in result.lower() or "failed" in result.lower()

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_handles_timeout(self, mock_run, mock_which):
        """Handles timeout gracefully."""
        import subprocess

        mock_which.return_value = "/usr/local/bin/codex"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=300)

        result, success = call_codex("Review this code")

        assert success is False
        assert "timed out" in result.lower()

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_handles_empty_output(self, mock_run, mock_which):
        """Returns failure for empty output."""
        mock_which.return_value = "/usr/local/bin/codex"
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result, success = call_codex("Review this code")

        assert success is False

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_uses_sandbox_by_default(self, mock_run, mock_which):
        """Uses sandbox mode by default."""
        mock_which.return_value = "/usr/local/bin/codex"
        mock_run.return_value = MagicMock(returncode=0, stdout='{"msg": {"type": "agent_message", "message": "Done"}}')

        with patch.dict(os.environ, {"CODEX_BYPASS_SANDBOX": ""}, clear=False):
            call_codex("Review this code")

        call_args = mock_run.call_args[0][0]
        assert "--sandbox" in call_args
        assert "workspace-write" in call_args

    @patch("codex_pr_review.shutil.which")
    @patch("subprocess.run")
    def test_bypass_sandbox_when_enabled(self, mock_run, mock_which):
        """Bypasses sandbox when CODEX_BYPASS_SANDBOX is set."""
        mock_which.return_value = "/usr/local/bin/codex"
        mock_run.return_value = MagicMock(returncode=0, stdout='{"msg": {"type": "agent_message", "message": "Done"}}')

        with patch.dict(os.environ, {"CODEX_BYPASS_SANDBOX": "true"}):
            call_codex("Review this code")

        call_args = mock_run.call_args[0][0]
        assert "--dangerously-bypass-approvals-and-sandbox" in call_args

    @patch("codex_pr_review.shutil.which")
    def test_fails_for_untrusted_path(self, mock_which):
        """Returns failure when codex binary is in untrusted location."""
        mock_which.return_value = "/tmp/malicious/codex"

        result, success = call_codex("Review this code")

        assert success is False
        assert "untrusted" in result.lower() or "not found" in result.lower()


class TestAnalyzePR:
    """Tests for the analyze_pr function."""

    @patch("codex_pr_review.call_codex")
    def test_includes_pr_info_in_prompt(self, mock_call_codex):
        """Includes PR info in the prompt."""
        mock_call_codex.return_value = ("Review complete", True)

        pr_info = {"number": "42", "title": "Test PR", "author": "user", "base_branch": "main", "head_branch": "feature"}
        analyze_pr(diff="+ added line", changed_files=["test.py"], pr_info=pr_info)

        prompt = mock_call_codex.call_args[0][0]
        assert "PR #42" in prompt
        assert "Test PR" in prompt

    @patch("codex_pr_review.call_codex")
    def test_includes_gemini_review_when_provided(self, mock_call_codex):
        """Includes Gemini review context when provided."""
        mock_call_codex.return_value = ("Review complete", True)

        pr_info = {"number": "42", "title": "Test", "author": "user", "base_branch": "main", "head_branch": "feature"}
        gemini_review = "## Gemini Review\n- Found issue in file.py:10"

        analyze_pr(diff="+ code", changed_files=["file.py"], pr_info=pr_info, gemini_review=gemini_review)

        prompt = mock_call_codex.call_args[0][0]
        assert "GEMINI'S REVIEW" in prompt
        assert "Found issue" in prompt

    @patch("codex_pr_review.call_codex")
    def test_truncates_long_gemini_review(self, mock_call_codex):
        """Truncates Gemini review if too long."""
        mock_call_codex.return_value = ("Review complete", True)

        pr_info = {"number": "42", "title": "Test", "author": "user", "base_branch": "main", "head_branch": "feature"}
        # Create a very long review
        gemini_review = "x" * 10000

        analyze_pr(diff="+ code", changed_files=["file.py"], pr_info=pr_info, gemini_review=gemini_review)

        prompt = mock_call_codex.call_args[0][0]
        # Should be truncated to 4000 chars
        assert len(gemini_review) > 4000
        assert "x" * 4000 in prompt

    @patch("codex_pr_review.call_codex")
    def test_includes_diff_in_prompt(self, mock_call_codex):
        """Includes PR diff in the prompt."""
        mock_call_codex.return_value = ("Review complete", True)

        pr_info = {"number": "42", "title": "Test", "author": "user", "base_branch": "main", "head_branch": "feature"}
        diff = "+ def new_function():\n+     pass"

        analyze_pr(diff=diff, changed_files=["file.py"], pr_info=pr_info)

        prompt = mock_call_codex.call_args[0][0]
        assert "new_function" in prompt


class TestFormatGithubComment:
    """Tests for the format_github_comment function."""

    def test_includes_commit_marker(self):
        """Includes commit tracking marker."""
        comment = format_github_comment(analysis="Test analysis", commit_sha="abc1234", has_gemini_context=False)

        assert "codex-review-marker:commit:abc1234" in comment

    def test_indicates_secondary_review_with_gemini_context(self):
        """Indicates secondary review when Gemini context was available."""
        comment = format_github_comment(analysis="Test analysis", commit_sha="abc1234", has_gemini_context=True)

        assert "Secondary Review" in comment
        assert "Complementary to Gemini" in comment

    def test_indicates_independent_review_without_gemini(self):
        """Indicates independent review when no Gemini context."""
        comment = format_github_comment(analysis="Test analysis", commit_sha="abc1234", has_gemini_context=False)

        assert "Independent review" in comment

    def test_includes_analysis_content(self):
        """Includes the analysis content in the comment."""
        analysis = "Found 3 issues:\n- Issue 1\n- Issue 2\n- Issue 3"
        comment = format_github_comment(analysis=analysis, commit_sha="abc1234", has_gemini_context=False)

        assert "Found 3 issues" in comment
        assert "Issue 1" in comment


class TestPostPRComment:
    """Tests for the post_pr_comment function."""

    @patch("subprocess.run")
    def test_posts_via_gh_cli(self, mock_run):
        """Posts comment using gh CLI."""
        mock_run.return_value = MagicMock(returncode=0)

        post_pr_comment(comment="Test comment", pr_info={"number": "42"})

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "pr" in call_args
        assert "comment" in call_args
        assert "42" in call_args

    @patch("subprocess.run")
    def test_uses_body_file(self, mock_run):
        """Uses --body-file for shell safety."""
        mock_run.return_value = MagicMock(returncode=0)

        post_pr_comment(comment="Test comment", pr_info={"number": "42"})

        call_args = mock_run.call_args[0][0]
        assert "--body-file" in call_args

    @patch("subprocess.run")
    def test_saves_backup_on_failure(self, mock_run):
        """Saves comment to file on posting failure."""
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(1, "gh")

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                post_pr_comment(comment="Test comment", pr_info={"number": "42"})

                # Should have saved backup file
                assert Path("codex-review.md").exists()
                assert "Test comment" in Path("codex-review.md").read_text()
            finally:
                os.chdir(old_cwd)

    @patch("subprocess.run")
    def test_cleans_up_temp_file(self, mock_run):
        """Cleans up temporary file after posting."""
        mock_run.return_value = MagicMock(returncode=0)

        post_pr_comment(comment="Test comment", pr_info={"number": "42"})

        # Get the temp file path from the call
        call_args = mock_run.call_args[0][0]
        body_file_idx = call_args.index("--body-file") + 1
        temp_file = call_args[body_file_idx]

        # Temp file should be cleaned up
        assert not Path(temp_file).exists()

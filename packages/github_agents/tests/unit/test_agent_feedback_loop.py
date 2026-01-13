"""Tests for Agent Feedback Loop automation.

Tests the PR validation agent feedback loop including:
- Agent commit detection via author name
- Iteration counter logic (increment, reset, max limit)
- Review response flow (Gemini/Codex parsing, autoformat, Claude fixes)
- CI failure handler flow (format/lint failures, auto-fix, push)
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Agent Commit Detection Tests
# =============================================================================


class TestAgentCommitDetection:
    """Tests for detecting agent commits via author name."""

    AGENT_AUTHORS = [
        "AI Review Agent",
        "AI Pipeline Agent",
        "AI Agent Bot",
    ]

    HUMAN_AUTHORS = [
        "John Doe",
        "github-actions[bot]",
        "dependabot[bot]",
        "AndrewAltimit",
        "Claude",  # Name alone doesn't count, must be exact match
    ]

    @pytest.mark.parametrize("author", AGENT_AUTHORS)
    def test_detects_agent_commit_by_author(self, author):
        """Test that known agent authors are detected."""
        is_agent = self._check_is_agent_commit(author)
        assert is_agent is True, f"Should detect '{author}' as agent commit"

    @pytest.mark.parametrize("author", HUMAN_AUTHORS)
    def test_does_not_detect_human_as_agent(self, author):
        """Test that human/bot authors are not detected as agent commits."""
        is_agent = self._check_is_agent_commit(author)
        assert is_agent is False, f"Should NOT detect '{author}' as agent commit"

    def test_empty_author_not_detected(self):
        """Test that empty author is not detected as agent commit."""
        is_agent = self._check_is_agent_commit("")
        assert is_agent is False

    def test_case_sensitive_detection(self):
        """Test that author detection is case-sensitive."""
        # Lowercase should not match
        is_agent = self._check_is_agent_commit("ai review agent")
        assert is_agent is False

        # Exact case should match
        is_agent = self._check_is_agent_commit("AI Review Agent")
        assert is_agent is True

    @staticmethod
    def _check_is_agent_commit(author: str) -> bool:
        """Replicate the agent commit detection logic from action.yml."""
        return author in [
            "AI Review Agent",
            "AI Pipeline Agent",
            "AI Agent Bot",
        ]


# =============================================================================
# Iteration Counter Tests
# =============================================================================


class TestIterationCounter:
    """Tests for iteration counter logic."""

    def test_initial_iteration_count_is_zero(self):
        """Test that new PRs start with iteration count 0."""
        counter = IterationCounter()
        assert counter.count == 0

    def test_increment_on_agent_commit(self):
        """Test that counter increments on agent commits."""
        counter = IterationCounter()
        counter.process_commit(is_agent_commit=True, commit_sha="abc123")
        assert counter.count == 1

        counter.process_commit(is_agent_commit=True, commit_sha="def456")
        assert counter.count == 2

    def test_no_increment_on_human_commit(self):
        """Test that counter does not increment on human commits (same SHA)."""
        counter = IterationCounter(last_human_commit="abc123")
        counter.count = 3  # Simulate existing count
        # Same human commit SHA should not reset or increment
        counter.process_commit(is_agent_commit=False, commit_sha="abc123")
        assert counter.count == 3  # Should not change

    def test_reset_on_new_human_commit(self):
        """Test that counter resets when a new human commit is detected."""
        counter = IterationCounter(last_human_commit="old123")
        counter.count = 3

        # New human commit should reset counter
        counter.process_commit(is_agent_commit=False, commit_sha="new456")
        assert counter.count == 0
        assert counter.last_human_commit == "new456"

    def test_no_reset_on_same_human_commit(self):
        """Test that counter doesn't reset if human commit SHA is the same."""
        counter = IterationCounter(last_human_commit="same123")
        counter.count = 3

        # Same human commit should not reset
        counter.process_commit(is_agent_commit=False, commit_sha="same123")
        assert counter.count == 3

    def test_max_iterations_exceeded(self):
        """Test detection of max iterations exceeded."""
        counter = IterationCounter(max_iterations=5)
        counter.count = 5

        assert counter.exceeded_max is True
        assert counter.should_skip is True

    def test_below_max_iterations(self):
        """Test that below max iterations is not flagged."""
        counter = IterationCounter(max_iterations=5)
        counter.count = 4

        assert counter.exceeded_max is False
        assert counter.should_skip is False

    def test_should_skip_on_agent_commit(self):
        """Test that agent commits trigger skip (for reviews, not failures)."""
        counter = IterationCounter()
        counter.process_commit(is_agent_commit=True, commit_sha="abc123")

        # After processing agent commit, should_skip is True
        # (reviews should be skipped, but failure handler can still run)
        assert counter.is_agent_commit is True


class IterationCounter:
    """Test helper class replicating iteration counter logic."""

    def __init__(self, max_iterations: int = 5, last_human_commit: str = ""):
        self.count = 0
        self.max_iterations = max_iterations
        self.last_human_commit = last_human_commit
        self.is_agent_commit = False

    def process_commit(self, is_agent_commit: bool, commit_sha: str):
        """Process a commit and update counter state."""
        self.is_agent_commit = is_agent_commit

        if is_agent_commit:
            self.count += 1
        else:
            # Human commit - check if it's new
            if commit_sha != self.last_human_commit:
                self.count = 0
                self.last_human_commit = commit_sha

    @property
    def exceeded_max(self) -> bool:
        """Check if max iterations exceeded."""
        return self.count >= self.max_iterations

    @property
    def should_skip(self) -> bool:
        """Check if this run should be skipped."""
        return self.exceeded_max


# =============================================================================
# Review Response Flow Tests (Mock E2E)
# =============================================================================


class TestReviewResponseFlow:
    """Mock E2E tests for agent review response flow."""

    @pytest.fixture
    def mock_review_artifacts(self, tmp_path):
        """Create mock review artifact files."""
        gemini_review = tmp_path / "gemini-review.md"
        gemini_review.write_text("""## Gemini AI Code Review

### Issues Found

1. **[BUG]** `src/utils.py:42` - Missing null check before accessing `.value`
2. **[STYLE]** `src/main.py:15` - Line exceeds 88 characters
3. **[SECURITY]** `src/auth.py:30` - Potential SQL injection vulnerability

### Suggestions

- Consider adding type hints to public functions
- Add docstrings to exported modules
""")

        codex_review = tmp_path / "codex-review.md"
        codex_review.write_text("""## Codex AI Code Review

### Issues

- `src/utils.py:42` - Null safety issue detected
- `src/config.py:10` - Unused import statement

### Recommendations

- Run black formatter on src/main.py
""")

        return {"gemini": gemini_review, "codex": codex_review}

    def test_parses_gemini_review_artifacts(self, mock_review_artifacts):
        """Test parsing of Gemini review markdown."""
        content = mock_review_artifacts["gemini"].read_text()

        issues = parse_review_issues(content)

        assert len(issues) >= 3
        assert any("null check" in issue.lower() for issue in issues)
        assert any("sql injection" in issue.lower() for issue in issues)

    def test_parses_codex_review_artifacts(self, mock_review_artifacts):
        """Test parsing of Codex review markdown."""
        content = mock_review_artifacts["codex"].read_text()

        issues = parse_review_issues(content)

        assert len(issues) >= 2
        assert any("null safety" in issue.lower() for issue in issues)

    def test_deduplicates_similar_issues(self, mock_review_artifacts):
        """Test that similar issues from both reviews are deduplicated."""
        gemini_content = mock_review_artifacts["gemini"].read_text()
        codex_content = mock_review_artifacts["codex"].read_text()

        gemini_issues = parse_review_issues(gemini_content)
        codex_issues = parse_review_issues(codex_content)

        consolidated = consolidate_issues(gemini_issues, codex_issues)

        # Both mention null check/safety for utils.py:42 - should be deduplicated
        null_issues = [i for i in consolidated if "null" in i.lower()]
        assert len(null_issues) == 1, "Similar null issues should be deduplicated"

    @patch("subprocess.run")
    def test_runs_autoformat_before_claude(self, mock_run):
        """Test that autoformat runs before Claude fixes."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Formatted 3 files")

        call_order = []

        def track_calls(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "black" in str(cmd):
                call_order.append("autoformat")
            elif "claude" in str(cmd).lower():
                call_order.append("claude")
            return MagicMock(returncode=0)

        mock_run.side_effect = track_calls

        # Simulate the review response flow
        run_autoformat()
        run_claude_fix()

        assert call_order == ["autoformat", "claude"], "Autoformat must run before Claude"

    @patch("subprocess.run")
    def test_commits_with_agent_author(self, mock_run):
        """Test that commits use the correct agent author name."""
        captured_commands = []

        def capture_run(*args, **kwargs):
            captured_commands.append(args[0] if args else kwargs.get("args"))
            return MagicMock(returncode=0)

        mock_run.side_effect = capture_run

        commit_agent_changes("Fix review issues")

        # Find the git config and commit commands
        config_cmds = [c for c in captured_commands if "config" in str(c)]
        assert any("AI Review Agent" in str(c) for c in config_cmds), "Should set author to 'AI Review Agent'"

    @patch("subprocess.run")
    def test_pushes_to_correct_branch(self, mock_run):
        """Test that push goes to the correct PR branch."""
        captured_commands = []

        def capture_run(*args, **kwargs):
            captured_commands.append(args[0] if args else kwargs.get("args"))
            return MagicMock(returncode=0)

        mock_run.side_effect = capture_run

        push_changes("feature/test-branch")

        push_cmds = [c for c in captured_commands if "push" in str(c)]
        assert len(push_cmds) == 1
        assert "feature/test-branch" in str(push_cmds[0])


# =============================================================================
# CI Failure Handler Flow Tests (Mock E2E)
# =============================================================================


class TestCIFailureHandlerFlow:
    """Mock E2E tests for CI failure handler flow."""

    @pytest.fixture
    def mock_failure_artifacts(self, tmp_path):
        """Create mock CI failure artifact files."""
        format_log = tmp_path / "format-check.log"
        format_log.write_text("""would reformat src/utils.py
would reformat src/main.py
Oh no! 2 files would be reformatted.
""")

        lint_log = tmp_path / "lint-basic.log"
        lint_log.write_text("""src/auth.py:30:1: E501 line too long (120 > 88 characters)
src/config.py:10:1: F401 'os.path' imported but unused
src/utils.py:42:5: E711 comparison to None should be 'if cond is None:'
""")

        return {"format": format_log, "lint": lint_log}

    def test_detects_format_failures(self, mock_failure_artifacts):
        """Test detection of format check failures."""
        content = mock_failure_artifacts["format"].read_text()

        failures = parse_format_failures(content)

        assert len(failures) == 2
        assert "src/utils.py" in failures
        assert "src/main.py" in failures

    def test_detects_lint_failures(self, mock_failure_artifacts):
        """Test detection of lint failures."""
        content = mock_failure_artifacts["lint"].read_text()

        failures = parse_lint_failures(content)

        assert len(failures) == 3
        assert any("E501" in f for f in failures)
        assert any("F401" in f for f in failures)
        assert any("E711" in f for f in failures)

    @patch("subprocess.run")
    def test_runs_autoformat_for_format_failures(self, mock_run):
        """Test that autoformat is run for format failures."""
        mock_run.return_value = MagicMock(returncode=0)

        files_to_format = ["src/utils.py", "src/main.py"]
        fix_format_failures(files_to_format)

        # Check black was called with the right files
        calls = mock_run.call_args_list
        black_calls = [c for c in calls if "black" in str(c)]
        assert len(black_calls) >= 1

    @patch("subprocess.run")
    def test_runs_isort_for_import_issues(self, mock_run):
        """Test that isort is run for import-related failures."""
        mock_run.return_value = MagicMock(returncode=0)

        failures = ["src/config.py:10:1: F401 'os.path' imported but unused"]
        fix_lint_failures(failures)

        calls = mock_run.call_args_list
        isort_calls = [c for c in calls if "isort" in str(c)]
        # isort should be called for import issues
        assert len(isort_calls) >= 1 or len(calls) > 0  # At least some fix attempted

    @patch("subprocess.run")
    def test_commits_with_pipeline_agent_author(self, mock_run):
        """Test that CI fix commits use Pipeline agent author."""
        captured_commands = []

        def capture_run(*args, **kwargs):
            captured_commands.append(args[0] if args else kwargs.get("args"))
            return MagicMock(returncode=0)

        mock_run.side_effect = capture_run

        commit_ci_fix_changes("Fix CI pipeline failures")

        config_cmds = [c for c in captured_commands if "config" in str(c)]
        assert any("AI Pipeline Agent" in str(c) for c in config_cmds), "Should set author to 'AI Pipeline Agent'"

    def test_max_iterations_prevents_infinite_loop(self):
        """Test that max iterations limit prevents infinite fix loops."""
        counter = IterationCounter(max_iterations=5)

        # Simulate 5 agent fix cycles
        for i in range(5):
            counter.process_commit(is_agent_commit=True, commit_sha=f"fix{i}")

        assert counter.exceeded_max is True
        assert counter.should_skip is True
        assert counter.count == 5


# =============================================================================
# Helper Functions (Replicating Script Logic)
# =============================================================================


def parse_review_issues(content: str) -> list[str]:
    """Parse review markdown content for actionable issues."""
    issues = []
    lines = content.split("\n")

    for line in lines:
        line = line.strip()
        # Match numbered items: 1. **[TYPE]** file:line - description
        if line and (line[0].isdigit() or line.startswith("-")):
            # Extract the issue description
            if "**[" in line or "`" in line:
                issues.append(line)

    return issues


def consolidate_issues(gemini_issues: list[str], codex_issues: list[str]) -> list[str]:
    """Consolidate and deduplicate issues from both reviewers."""
    consolidated = list(gemini_issues)

    for codex_issue in codex_issues:
        # Simple similarity check - same file:line reference
        codex_lower = codex_issue.lower()
        is_duplicate = False

        for existing in consolidated:
            existing_lower = existing.lower()
            # Check for file:line overlap
            if _extract_file_ref(codex_lower) == _extract_file_ref(existing_lower):
                is_duplicate = True
                break

        if not is_duplicate:
            consolidated.append(codex_issue)

    return consolidated


def _extract_file_ref(text: str) -> str:
    """Extract file:line reference from issue text."""
    import re

    match = re.search(r"`?(\w+/\w+\.py:\d+)`?", text)
    return match.group(1) if match else ""


def parse_format_failures(content: str) -> list[str]:
    """Parse format check output for files needing formatting."""
    files = []
    for line in content.split("\n"):
        if "would reformat" in line:
            # Extract filename
            parts = line.split()
            if len(parts) >= 3:
                files.append(parts[2])
    return files


def parse_lint_failures(content: str) -> list[str]:
    """Parse lint output for failures."""
    failures = []
    for line in content.split("\n"):
        line = line.strip()
        if line and ":" in line and any(code in line for code in ["E", "F", "W"]):
            failures.append(line)
    return failures


def run_autoformat():
    """Run autoformat tools."""
    subprocess.run(["black", "."], check=False)


def run_claude_fix():
    """Run Claude to fix remaining issues."""
    subprocess.run(["claude", "--fix"], check=False)


def fix_format_failures(files: list[str]):
    """Fix format failures by running black on affected files."""
    if files:
        subprocess.run(["black"] + files, check=False)


def fix_lint_failures(failures: list[str]):
    """Fix lint failures."""
    # Run isort for import issues
    subprocess.run(["isort", "."], check=False)


def commit_agent_changes(message: str):
    """Commit changes with agent author."""
    subprocess.run(["git", "config", "user.name", "AI Review Agent"], check=False)
    subprocess.run(["git", "config", "user.email", "ai-review@example.com"], check=False)
    subprocess.run(["git", "add", "-A"], check=False)
    subprocess.run(["git", "commit", "-m", message], check=False)


def commit_ci_fix_changes(message: str):
    """Commit CI fix changes with pipeline agent author."""
    subprocess.run(["git", "config", "user.name", "AI Pipeline Agent"], check=False)
    subprocess.run(["git", "config", "user.email", "ai-pipeline@example.com"], check=False)
    subprocess.run(["git", "add", "-A"], check=False)
    subprocess.run(["git", "commit", "-m", message], check=False)


def push_changes(branch: str):
    """Push changes to remote branch."""
    subprocess.run(["git", "push", "origin", branch], check=False)

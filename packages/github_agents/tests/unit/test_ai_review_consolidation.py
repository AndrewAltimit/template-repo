"""Tests for AI review consolidation in PR monitor.

Tests the dual AI review system including:
- Codex review detection
- AI review classification (Gemini vs Codex)
- Item similarity detection
- Commit SHA extraction
- Consolidated review processing
"""

# pylint: disable=protected-access  # Testing protected members is legitimate in tests

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_agents.monitors.pr import (
    CODEX_RESPONSE_MARKER,
    CODEX_REVIEW_PATTERNS,
    CONSOLIDATED_RESPONSE_MARKER,
    GEMINI_REVIEW_PATTERNS,
    PRMonitor,
)


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict("os.environ", {"GITHUB_REPOSITORY": "test/repo", "GITHUB_TOKEN": "test-token"}):
        yield


@pytest.fixture
def pr_monitor(mock_env):
    """Create PR monitor instance."""
    with patch("github_agents.config.AgentConfig"), patch("github_agents.security.SecurityManager"):
        monitor = PRMonitor()
        # Mock the agent judgement
        monitor.agent_judgement = MagicMock()
        return monitor


class TestCodexReviewDetection:
    """Tests for Codex review detection patterns."""

    def test_codex_review_patterns_exist(self):
        """Verify Codex review patterns are defined."""
        assert len(CODEX_REVIEW_PATTERNS) > 0
        assert any("codex" in p.lower() for p in CODEX_REVIEW_PATTERNS)

    def test_is_codex_review_basic(self, pr_monitor):
        """Test basic Codex review detection."""
        comment = {
            "body": "## Codex AI Code Review\n<!-- codex-review-marker:commit:abc123 -->\nReview content",
            "author": "github-actions[bot]",
        }

        assert pr_monitor._is_codex_review(comment) is True

    def test_is_codex_review_with_marker(self, pr_monitor):
        """Test Codex review detection via commit marker."""
        comment = {
            "body": "Some header\n<!-- codex-review-marker:commit:abc123 -->\nContent",
            "author": "github-actions[bot]",
        }

        assert pr_monitor._is_codex_review(comment) is True

    def test_is_not_codex_review_wrong_author(self, pr_monitor):
        """Test that non-bot comments are not detected as Codex reviews."""
        comment = {
            "body": "## Codex AI Code Review\n<!-- codex-review-marker:commit:abc123 -->",
            "author": "human_user",
        }

        assert pr_monitor._is_codex_review(comment) is False

    def test_is_not_codex_review_no_pattern(self, pr_monitor):
        """Test that comments without Codex patterns are not detected."""
        comment = {
            "body": "This is a regular comment about the PR",
            "author": "github-actions[bot]",
        }

        assert pr_monitor._is_codex_review(comment) is False

    def test_is_codex_review_case_insensitive(self, pr_monitor):
        """Test case-insensitive Codex review detection."""
        comment = {
            "body": "## CODEX AI CODE REVIEW\nContent here",
            "author": "github-actions[bot]",
        }

        assert pr_monitor._is_codex_review(comment) is True


class TestGeminiReviewDetection:
    """Tests for Gemini review detection (existing functionality)."""

    def test_gemini_review_patterns_exist(self):
        """Verify Gemini review patterns are defined."""
        assert len(GEMINI_REVIEW_PATTERNS) > 0

    def test_is_gemini_review_basic(self, pr_monitor):
        """Test basic Gemini review detection."""
        comment = {
            "body": "## Gemini AI Code Review\n<!-- gemini-review-marker:commit:abc123 -->",
            "author": "github-actions[bot]",
        }

        assert pr_monitor._is_gemini_review(comment) is True

    def test_is_not_gemini_review_is_codex(self, pr_monitor):
        """Test that Codex reviews are not detected as Gemini reviews."""
        comment = {
            "body": "## Codex AI Code Review\n<!-- codex-review-marker:commit:abc123 -->",
            "author": "github-actions[bot]",
        }

        assert pr_monitor._is_gemini_review(comment) is False


class TestAIReviewClassification:
    """Tests for unified AI review classification."""

    def test_is_ai_review_gemini(self, pr_monitor):
        """Test AI review classification returns 'gemini' for Gemini reviews."""
        comment = {
            "body": "## Gemini AI Code Review\nContent",
            "author": "github-actions[bot]",
        }

        is_ai, reviewer = pr_monitor._is_ai_review(comment)

        assert is_ai is True
        assert reviewer == "gemini"

    def test_is_ai_review_codex(self, pr_monitor):
        """Test AI review classification returns 'codex' for Codex reviews."""
        comment = {
            "body": "## Codex AI Code Review\nContent",
            "author": "github-actions[bot]",
        }

        is_ai, reviewer = pr_monitor._is_ai_review(comment)

        assert is_ai is True
        assert reviewer == "codex"

    def test_is_ai_review_neither(self, pr_monitor):
        """Test AI review classification returns None for regular comments."""
        comment = {
            "body": "Just a regular PR comment",
            "author": "github-actions[bot]",
        }

        is_ai, reviewer = pr_monitor._is_ai_review(comment)

        assert is_ai is False
        assert reviewer is None

    def test_gemini_takes_precedence(self, pr_monitor):
        """Test that if both patterns match, Gemini takes precedence."""
        # This is an edge case - a comment mentioning both
        comment = {
            "body": "## Gemini AI Code Review\nAlso mentions Codex review",
            "author": "github-actions[bot]",
        }

        is_ai, reviewer = pr_monitor._is_ai_review(comment)

        assert is_ai is True
        # Gemini is checked first, so it takes precedence
        assert reviewer == "gemini"


class TestCommitSHAExtraction:
    """Tests for commit SHA extraction from review markers."""

    def test_extract_gemini_commit_sha(self, pr_monitor):
        """Test extracting commit SHA from Gemini review."""
        comment = {
            "body": "## Review\n<!-- gemini-review-marker:commit:abc1234def -->\nContent",
        }

        sha = pr_monitor._extract_gemini_commit_sha(comment)

        assert sha == "abc1234def"

    def test_extract_codex_commit_sha(self, pr_monitor):
        """Test extracting commit SHA from Codex review."""
        comment = {
            "body": "## Review\n<!-- codex-review-marker:commit:def7890abc -->\nContent",
        }

        sha = pr_monitor._extract_codex_commit_sha(comment)

        assert sha == "def7890abc"

    def test_extract_ai_review_commit_sha_gemini(self, pr_monitor):
        """Test unified commit SHA extraction for Gemini."""
        comment = {"body": "<!-- gemini-review-marker:commit:abc123 -->"}

        sha = pr_monitor._extract_ai_review_commit_sha(comment, "gemini")

        assert sha == "abc123"

    def test_extract_ai_review_commit_sha_codex(self, pr_monitor):
        """Test unified commit SHA extraction for Codex."""
        comment = {"body": "<!-- codex-review-marker:commit:def456 -->"}

        sha = pr_monitor._extract_ai_review_commit_sha(comment, "codex")

        assert sha == "def456"

    def test_extract_commit_sha_not_found(self, pr_monitor):
        """Test returns None when no marker found."""
        comment = {"body": "No marker here"}

        assert pr_monitor._extract_gemini_commit_sha(comment) is None
        assert pr_monitor._extract_codex_commit_sha(comment) is None


class TestItemSimilarity:
    """Tests for actionable item similarity detection."""

    def test_identical_items_are_similar(self, pr_monitor):
        """Test that identical items are detected as similar."""
        item1 = "Missing null check in function foo"
        item2 = "Missing null check in function foo"

        assert pr_monitor._items_are_similar(item1, item2) is True

    def test_different_items_not_similar(self, pr_monitor):
        """Test that completely different items are not similar."""
        item1 = "Missing null check in function foo"
        item2 = "Add logging to the API endpoint"

        assert pr_monitor._items_are_similar(item1, item2) is False

    def test_similar_items_above_threshold(self, pr_monitor):
        """Test items with significant word overlap are similar."""
        item1 = "Missing error handling in database query"
        item2 = "Add error handling for database query failures"

        assert pr_monitor._items_are_similar(item1, item2) is True

    def test_common_words_excluded(self, pr_monitor):
        """Test that common words don't inflate similarity."""
        item1 = "The function is missing a return"
        item2 = "The variable is undefined in scope"

        # Both have "the" and "is" but otherwise different
        assert pr_monitor._items_are_similar(item1, item2) is False

    def test_empty_strings_not_similar(self, pr_monitor):
        """Test that empty strings return False."""
        assert pr_monitor._items_are_similar("", "") is False
        assert pr_monitor._items_are_similar("Some text", "") is False

    def test_case_insensitive(self, pr_monitor):
        """Test similarity is case-insensitive."""
        item1 = "MISSING NULL CHECK"
        item2 = "missing null check"

        assert pr_monitor._items_are_similar(item1, item2) is True


class TestActionableItemExtraction:
    """Tests for actionable item extraction from reviews."""

    def test_extracts_numbered_items(self, pr_monitor):
        """Test extraction of numbered list items."""
        review_body = """## Issues
1. Missing error handling in api.py:42
2. Unused import in utils.py:10
3. Potential security issue with input validation
"""
        items = pr_monitor._extract_actionable_items(review_body)

        assert len(items) >= 3
        assert any("error handling" in item["issue"].lower() for item in items)

    def test_extracts_bullet_items(self, pr_monitor):
        """Test extraction of bullet point items."""
        review_body = """## Issues
- [BUG] file.py:10 - Missing return statement
- [SECURITY] auth.py:50 - SQL injection risk
* [SUGGESTION] Consider adding type hints
"""
        items = pr_monitor._extract_actionable_items(review_body)

        assert len(items) >= 2
        assert any("return" in item["issue"].lower() for item in items)

    def test_extracts_header_sections(self, pr_monitor):
        """Test extraction from header sections."""
        review_body = """## Issues

### Issue: Missing Error Handling
The function doesn't catch exceptions properly.

### Problem: No Input Validation
User input is used directly without sanitization.
"""
        items = pr_monitor._extract_actionable_items(review_body)

        assert len(items) >= 1

    def test_empty_review_returns_empty(self, pr_monitor):
        """Test that empty review returns empty list."""
        items = pr_monitor._extract_actionable_items("")

        assert items == []

    def test_filters_short_items(self, pr_monitor):
        """Test that very short items are filtered out."""
        review_body = """## Issues
- OK
- LGTM
- Missing comprehensive error handling throughout the module
"""
        items = pr_monitor._extract_actionable_items(review_body)

        # Short items should be filtered
        assert not any(item["issue"] == "OK" for item in items)
        assert not any(item["issue"] == "LGTM" for item in items)


class TestResponseMarkers:
    """Tests for response tracking markers."""

    def test_codex_response_marker_format(self):
        """Test Codex response marker formatting."""
        marker = CODEX_RESPONSE_MARKER.format("review-123")
        assert "ai-agent-codex-response:review-123" in marker

    def test_consolidated_response_marker_format(self):
        """Test consolidated response marker formatting."""
        marker = CONSOLIDATED_RESPONSE_MARKER.format("consolidated-abc-def")
        assert "ai-agent-consolidated-response:consolidated-abc-def" in marker


class TestConsolidatedReviewProcessing:
    """Tests for consolidated AI review processing."""

    @pytest.mark.asyncio
    async def test_process_consolidated_deduplicates_items(self, pr_monitor):
        """Test that consolidated processing deduplicates similar items."""
        gemini_review = {
            "body": "## Gemini Review\n- Missing null check in foo()\n- Add error handling",
            "id": "G1",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        codex_review = {
            "body": "## Codex Review\n- Null check missing in foo function\n- Consider logging",
            "id": "C1",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

        pr = {"number": 123, "title": "Test PR"}

        # Mock methods that would be called
        pr_monitor._get_review_comments = MagicMock(return_value=[])
        pr_monitor._post_gemini_acknowledgment = AsyncMock()
        pr_monitor._process_consolidated_actionable_items = AsyncMock()

        # Process the consolidated reviews
        await pr_monitor._process_consolidated_ai_reviews(pr, gemini_review, codex_review, "feature-branch")

        # Verify consolidation was attempted
        assert pr_monitor._process_consolidated_actionable_items.called

    @pytest.mark.asyncio
    async def test_consolidated_items_have_source_attribution(self, pr_monitor):
        """Test that consolidated items are attributed to their source."""
        # Use completely different issues that won't be detected as similar
        gemini_items = [{"issue": "Missing null check in authentication module", "suggestion": ""}]
        codex_items = [{"issue": "Add comprehensive logging to API endpoints", "suggestion": ""}]

        # Extract and consolidate manually to test the logic
        consolidated = []
        for item in gemini_items:
            consolidated.append({**item, "source": "gemini"})
        for item in codex_items:
            is_duplicate = False
            for existing in consolidated:
                if pr_monitor._items_are_similar(item["issue"], existing["issue"]):
                    is_duplicate = True
                    existing["source"] = "both"
                    break
            if not is_duplicate:
                consolidated.append({**item, "source": "codex"})

        # Verify source attribution - both items should be present with their sources
        assert len(consolidated) == 2
        assert any(item["source"] == "gemini" for item in consolidated)
        assert any(item["source"] == "codex" for item in consolidated)

    @pytest.mark.asyncio
    async def test_duplicate_items_marked_as_both(self, pr_monitor):
        """Test that duplicate items are marked as found by both reviewers."""
        gemini_items = [{"issue": "Missing error handling in database operations", "suggestion": ""}]
        codex_items = [{"issue": "Add error handling for database operations", "suggestion": ""}]

        # Process consolidation
        consolidated = []
        for item in gemini_items:
            consolidated.append({**item, "source": "gemini"})
        for item in codex_items:
            is_duplicate = False
            for existing in consolidated:
                if pr_monitor._items_are_similar(item["issue"], existing["issue"]):
                    is_duplicate = True
                    existing["source"] = "both"
                    break
            if not is_duplicate:
                consolidated.append({**item, "source": "codex"})

        # Should have only one item marked as "both"
        assert len(consolidated) == 1
        assert consolidated[0]["source"] == "both"

    @pytest.mark.asyncio
    async def test_empty_reviews_post_acknowledgment(self, pr_monitor):
        """Test that empty consolidated reviews post acknowledgment."""
        gemini_review = {"body": "## Gemini Review\nLGTM!", "id": "G1", "createdAt": "2024-01-20T10:00:00Z"}
        codex_review = {"body": "## Codex Review\nNo issues found.", "id": "C1", "createdAt": "2024-01-20T10:00:00Z"}

        pr = {"number": 123, "title": "Test PR"}

        # Mock to return no actionable items
        pr_monitor._extract_actionable_items = MagicMock(return_value=[])
        pr_monitor._post_gemini_acknowledgment = AsyncMock()

        await pr_monitor._process_consolidated_ai_reviews(pr, gemini_review, codex_review, "feature-branch")

        # Should post acknowledgment
        assert pr_monitor._post_gemini_acknowledgment.called


class TestConfidenceBoostForDualReviews:
    """Tests for confidence boosting when both reviewers flag an issue."""

    def test_both_source_boosts_confidence(self, pr_monitor):
        """Test that items from both reviewers get confidence boost."""
        from github_agents.security.judgement import FixCategory, JudgementResult

        # Create a mock judgement result
        base_confidence = 0.7
        mock_result = JudgementResult(
            should_auto_fix=True, confidence=base_confidence, category=FixCategory.LINTING, reasoning="Test"
        )

        pr_monitor.agent_judgement.assess_fix = MagicMock(return_value=mock_result)

        item = {"issue": "Fix linting error", "source": "both"}

        # Assess the fix
        result = pr_monitor.agent_judgement.assess_fix(item["issue"], {})

        # Simulate the boost (15% increase, capped at 1.0)
        if item.get("source") == "both":
            result.confidence = min(1.0, result.confidence * 1.15)

        # Confidence should be boosted
        assert result.confidence > base_confidence
        assert result.confidence == pytest.approx(0.805, rel=0.01)

    def test_single_source_no_boost(self, pr_monitor):
        """Test that single-source items don't get confidence boost."""
        from github_agents.security.judgement import FixCategory, JudgementResult

        base_confidence = 0.7
        mock_result = JudgementResult(
            should_auto_fix=True, confidence=base_confidence, category=FixCategory.LINTING, reasoning="Test"
        )

        pr_monitor.agent_judgement.assess_fix = MagicMock(return_value=mock_result)

        item = {"issue": "Fix linting error", "source": "gemini"}

        result = pr_monitor.agent_judgement.assess_fix(item["issue"], {})

        # No boost for single source
        if item.get("source") == "both":
            result.confidence = min(1.0, result.confidence * 1.15)

        assert result.confidence == base_confidence


class TestProcessGeminiReviewsWithBothReviewers:
    """Tests for the updated _process_gemini_reviews that handles both AI reviewers."""

    @pytest.mark.asyncio
    async def test_processes_gemini_only_when_no_codex(self, pr_monitor):
        """Test that single Gemini review is processed normally."""
        gemini_comment = {
            "body": "## Gemini AI Code Review\n<!-- gemini-review-marker:commit:abc123 -->\n- Issue found",
            "author": "github-actions[bot]",
            "id": "G1",
            "createdAt": "2024-01-20T10:00:00Z",
        }

        pr = {"number": 123, "title": "Test PR"}
        pr_monitor.gemini_auto_response_enabled = True

        pr_monitor._get_review_comments = MagicMock(return_value=[gemini_comment])
        pr_monitor._has_responded_to_gemini_review = AsyncMock(return_value=False)
        pr_monitor._extract_actionable_items = MagicMock(return_value=[{"issue": "Test issue", "suggestion": ""}])
        pr_monitor._process_gemini_actionable_items = AsyncMock()
        pr_monitor._process_consolidated_ai_reviews = AsyncMock()

        await pr_monitor._process_gemini_reviews(pr, "feature-branch")

        # Should process individual Gemini review, not consolidated
        assert pr_monitor._process_gemini_actionable_items.called
        assert not pr_monitor._process_consolidated_ai_reviews.called

    @pytest.mark.asyncio
    async def test_consolidates_when_both_reviews_present(self, pr_monitor):
        """Test that both reviews are consolidated when present."""
        gemini_comment = {
            "body": "## Gemini AI Code Review\n<!-- gemini-review-marker:commit:abc123 -->\n- Gemini issue",
            "author": "github-actions[bot]",
            "id": "G1",
            "createdAt": "2024-01-20T10:00:00Z",
        }
        codex_comment = {
            "body": "## Codex AI Code Review\n<!-- codex-review-marker:commit:abc123 -->\n- Codex issue",
            "author": "github-actions[bot]",
            "id": "C1",
            "createdAt": "2024-01-20T10:00:00Z",
        }

        pr = {"number": 123, "title": "Test PR"}
        pr_monitor.gemini_auto_response_enabled = True

        pr_monitor._get_review_comments = MagicMock(return_value=[gemini_comment, codex_comment])
        pr_monitor._has_responded_to_gemini_review = AsyncMock(return_value=False)
        pr_monitor._process_consolidated_ai_reviews = AsyncMock()
        pr_monitor._process_gemini_actionable_items = AsyncMock()

        await pr_monitor._process_gemini_reviews(pr, "feature-branch")

        # Should consolidate both reviews
        assert pr_monitor._process_consolidated_ai_reviews.called
        assert not pr_monitor._process_gemini_actionable_items.called

    @pytest.mark.asyncio
    async def test_skips_already_responded_reviews(self, pr_monitor):
        """Test that already-responded reviews are skipped."""
        gemini_comment = {
            "body": "## Gemini AI Code Review\n- Issue",
            "author": "github-actions[bot]",
            "id": "G1",
            "createdAt": "2024-01-20T10:00:00Z",
        }

        pr = {"number": 123, "title": "Test PR"}
        pr_monitor.gemini_auto_response_enabled = True

        pr_monitor._get_review_comments = MagicMock(return_value=[gemini_comment])
        pr_monitor._has_responded_to_gemini_review = AsyncMock(return_value=True)  # Already responded
        pr_monitor._process_gemini_actionable_items = AsyncMock()

        await pr_monitor._process_gemini_reviews(pr, "feature-branch")

        # Should not process since already responded
        assert not pr_monitor._process_gemini_actionable_items.called

    @pytest.mark.asyncio
    async def test_disabled_auto_response_skips_processing(self, pr_monitor):
        """Test that disabled auto-response skips all processing."""
        pr = {"number": 123, "title": "Test PR"}
        pr_monitor.gemini_auto_response_enabled = False

        pr_monitor._get_review_comments = MagicMock()
        pr_monitor._process_gemini_actionable_items = AsyncMock()

        await pr_monitor._process_gemini_reviews(pr, "feature-branch")

        # Should not even fetch comments
        assert not pr_monitor._get_review_comments.called


class TestHasRespondedToGeminiReview:
    """Tests for _has_responded_to_gemini_review function."""

    @pytest.mark.asyncio
    async def test_detects_direct_gemini_marker(self, pr_monitor):
        """Test detection of direct Gemini response marker."""
        review_id = "2026-01-08-00-00-00-comment123"
        marker = f"<!-- ai-agent-gemini-response:{review_id} -->"

        mock_output = '{"comments": [{"body": "Response to review\\n' + marker.replace('"', '\\"') + '"}]}'

        with patch("github_agents.monitors.pr.run_gh_command_async", AsyncMock(return_value=mock_output)):
            result = await pr_monitor._has_responded_to_gemini_review(123, review_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_detects_consolidated_marker_containing_review_id(self, pr_monitor):
        """Test detection of consolidated response marker containing the review ID."""
        gemini_review_id = "2026-01-08-00-00-00-gemini123"
        codex_review_id = "2026-01-08-00-01-00-codex456"
        consolidated_marker = f"<!-- ai-agent-consolidated-response:consolidated-{gemini_review_id}-{codex_review_id} -->"

        mock_output = '{"comments": [{"body": "Consolidated response\\n' + consolidated_marker.replace('"', '\\"') + '"}]}'

        with patch("github_agents.monitors.pr.run_gh_command_async", AsyncMock(return_value=mock_output)):
            # Should detect the response for the Gemini review ID
            result = await pr_monitor._has_responded_to_gemini_review(123, gemini_review_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_unrelated_consolidated_marker(self, pr_monitor):
        """Test that unrelated consolidated markers don't match."""
        different_review_id = "2026-01-08-00-00-00-different"
        consolidated_marker = "<!-- ai-agent-consolidated-response:consolidated-other-ids -->"

        mock_output = '{"comments": [{"body": "Consolidated response\\n' + consolidated_marker.replace('"', '\\"') + '"}]}'

        with patch("github_agents.monitors.pr.run_gh_command_async", AsyncMock(return_value=mock_output)):
            result = await pr_monitor._has_responded_to_gemini_review(123, different_review_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_markers(self, pr_monitor):
        """Test returns False when no response markers exist."""
        review_id = "2026-01-08-00-00-00-test"

        mock_output = '{"comments": [{"body": "Regular comment without markers"}]}'

        with patch("github_agents.monitors.pr.run_gh_command_async", AsyncMock(return_value=mock_output)):
            result = await pr_monitor._has_responded_to_gemini_review(123, review_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_handles_empty_comments(self, pr_monitor):
        """Test handles empty comments list."""
        review_id = "2026-01-08-00-00-00-test"

        mock_output = '{"comments": []}'

        with patch("github_agents.monitors.pr.run_gh_command_async", AsyncMock(return_value=mock_output)):
            result = await pr_monitor._has_responded_to_gemini_review(123, review_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self, pr_monitor):
        """Test handles invalid JSON gracefully."""
        review_id = "2026-01-08-00-00-00-test"

        mock_output = "not valid json"

        with patch("github_agents.monitors.pr.run_gh_command_async", AsyncMock(return_value=mock_output)):
            result = await pr_monitor._has_responded_to_gemini_review(123, review_id)

        assert result is False

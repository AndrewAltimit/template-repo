"""Tests for codebase analyzers and issue creation.

These tests ensure the analysis pipeline works correctly, including:
- AffectedFile serialization/deserialization
- AnalysisFinding serialization round-trips
- IssueCreator parameter validation
- Workflow integration patterns
"""

from dataclasses import asdict
import json
from unittest.mock import AsyncMock, patch

import pytest

from github_agents.analyzers import (
    AffectedFile,
    AnalysisFinding,
    FindingCategory,
    FindingPriority,
)
from github_agents.creators import IssueCreator


class TestAffectedFile:
    """Test AffectedFile dataclass."""

    def test_basic_creation(self):
        """Test creating an AffectedFile with required fields."""
        af = AffectedFile(path="src/main.py")
        assert af.path == "src/main.py"
        assert af.line_start is None
        assert af.line_end is None
        assert af.snippet is None

    def test_full_creation(self):
        """Test creating an AffectedFile with all fields."""
        af = AffectedFile(
            path="src/main.py",
            line_start=10,
            line_end=20,
            snippet="def example():",
        )
        assert af.path == "src/main.py"
        assert af.line_start == 10
        assert af.line_end == 20
        assert af.snippet == "def example():"

    def test_to_reference_path_only(self):
        """Test reference string with path only."""
        af = AffectedFile(path="src/main.py")
        assert af.to_reference() == "`src/main.py`"

    def test_to_reference_with_line_start(self):
        """Test reference string with line start."""
        af = AffectedFile(path="src/main.py", line_start=10)
        assert af.to_reference() == "`src/main.py:L10`"

    def test_to_reference_with_line_range(self):
        """Test reference string with line range."""
        af = AffectedFile(path="src/main.py", line_start=10, line_end=20)
        assert af.to_reference() == "`src/main.py:L10-L20`"

    def test_asdict_serialization(self):
        """Test that AffectedFile can be serialized with asdict()."""
        af = AffectedFile(
            path="src/main.py",
            line_start=10,
            line_end=20,
            snippet="code",
        )
        result = asdict(af)
        assert result == {
            "path": "src/main.py",
            "line_start": 10,
            "line_end": 20,
            "snippet": "code",
        }

    def test_json_serialization_round_trip(self):
        """Test that AffectedFile survives JSON round-trip via asdict()."""
        original = AffectedFile(
            path="src/main.py",
            line_start=10,
            line_end=20,
            snippet="def example():",
        )

        # Serialize to JSON (like the workflow does)
        json_str = json.dumps(asdict(original))

        # Deserialize from JSON (like the workflow does)
        data = json.loads(json_str)
        restored = AffectedFile(**data)

        assert restored.path == original.path
        assert restored.line_start == original.line_start
        assert restored.line_end == original.line_end
        assert restored.snippet == original.snippet

    def test_dict_reconstruction(self):
        """Test reconstructing AffectedFile from dict."""
        data = {"path": "test.py", "line_start": 5, "line_end": 10, "snippet": None}
        af = AffectedFile(**data)
        assert af.path == "test.py"
        assert af.line_start == 5

    def test_partial_dict_reconstruction(self):
        """Test reconstructing from dict with only required fields."""
        data = {"path": "test.py"}
        af = AffectedFile(**data)
        assert af.path == "test.py"
        assert af.line_start is None


class TestAnalysisFinding:
    """Test AnalysisFinding dataclass."""

    @pytest.fixture
    def sample_finding(self):
        """Create a sample finding for testing."""
        return AnalysisFinding(
            title="Test Finding",
            summary="A test finding summary",
            details="Detailed description of the finding",
            category=FindingCategory.QUALITY,
            priority=FindingPriority.P2,
            affected_files=[
                AffectedFile(path="src/main.py", line_start=10, line_end=20),
                AffectedFile(path="src/utils.py", line_start=5),
            ],
            suggested_fix="Refactor the code",
            evidence="Evidence here",
            discovered_by="claude",
        )

    def test_basic_creation(self, sample_finding):
        """Test creating an AnalysisFinding."""
        assert sample_finding.title == "Test Finding"
        assert sample_finding.category == FindingCategory.QUALITY
        assert sample_finding.priority == FindingPriority.P2
        assert len(sample_finding.affected_files) == 2
        assert sample_finding.discovered_by == "claude"

    def test_fingerprint_generation(self, sample_finding):
        """Test fingerprint generation."""
        fingerprint = sample_finding.fingerprint()
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 16  # SHA256 truncated to 16 chars

    def test_fingerprint_consistency(self, sample_finding):
        """Test that same finding generates same fingerprint."""
        fp1 = sample_finding.fingerprint()
        fp2 = sample_finding.fingerprint()
        assert fp1 == fp2

    def test_issue_title_generation(self, sample_finding):
        """Test issue title generation."""
        title = sample_finding.to_issue_title()
        assert title == "[Quality] Test Finding"

    def test_issue_body_generation(self, sample_finding):
        """Test issue body generation."""
        body = sample_finding.to_issue_body()
        assert "## [Quality]: Test Finding" in body
        assert "**Priority**: P2" in body
        assert "`src/main.py:L10-L20`" in body
        assert "`src/utils.py:L5`" in body
        assert "analysis-fingerprint:" in body

    def test_workflow_serialization_pattern(self, sample_finding):
        """Test the exact serialization pattern used in the workflow."""
        # This is the pattern from codebase-analysis.yml line 211-221
        serialized = {
            "title": sample_finding.title,
            "category": sample_finding.category.value,
            "priority": sample_finding.priority.value,
            "summary": sample_finding.summary,
            "details": sample_finding.details,
            "files": [asdict(af) for af in sample_finding.affected_files],
            "suggested_fix": sample_finding.suggested_fix,
            "evidence": sample_finding.evidence,
            "agent": sample_finding.discovered_by,
        }

        # Should be JSON serializable
        json_str = json.dumps(serialized)
        assert json_str is not None

        # Parse it back
        parsed = json.loads(json_str)

        # Reconstruct (pattern from workflow lines 354-372)
        files_data = parsed.get("files", [])
        affected_files = [
            AffectedFile(**file_dict) if isinstance(file_dict, dict) else AffectedFile(path=str(file_dict))
            for file_dict in files_data
        ]

        restored = AnalysisFinding(
            title=parsed.get("title", "Untitled Finding"),
            category=FindingCategory(parsed.get("category", "quality")),
            priority=FindingPriority(parsed.get("priority", "P2")),
            summary=parsed.get("summary", ""),
            details=parsed.get("details", ""),
            affected_files=affected_files,
            suggested_fix=parsed.get("suggested_fix", ""),
            evidence=parsed.get("evidence", ""),
            discovered_by=parsed.get("agent", "unknown"),
        )

        assert restored.title == sample_finding.title
        assert restored.category == sample_finding.category
        assert restored.priority == sample_finding.priority
        assert len(restored.affected_files) == len(sample_finding.affected_files)
        assert restored.affected_files[0].path == sample_finding.affected_files[0].path


class TestFindingCategory:
    """Test FindingCategory enum."""

    def test_all_categories_exist(self):
        """Test all expected categories exist."""
        expected = [
            "security",
            "performance",
            "quality",
            "tech_debt",
            "documentation",
            "testing",
            "architecture",
            "dependency",
        ]
        for cat in expected:
            assert FindingCategory(cat) is not None

    def test_value_serialization(self):
        """Test category value serialization."""
        assert FindingCategory.SECURITY.value == "security"
        assert FindingCategory.QUALITY.value == "quality"


class TestFindingPriority:
    """Test FindingPriority enum."""

    def test_all_priorities_exist(self):
        """Test all priority levels exist."""
        for level in ["P0", "P1", "P2", "P3"]:
            assert FindingPriority(level) is not None

    def test_value_serialization(self):
        """Test priority value serialization."""
        assert FindingPriority.P0.value == "P0"
        assert FindingPriority.P2.value == "P2"


class TestIssueCreator:
    """Test IssueCreator initialization and interface."""

    def test_valid_initialization(self):
        """Test IssueCreator with valid parameters."""
        creator = IssueCreator(
            repo="owner/repo",
            lookback_days=30,
            max_issues_per_run=5,
            min_priority=FindingPriority.P2,
        )
        assert creator.repo == "owner/repo"
        assert creator.lookback_days == 30
        assert creator.max_issues_per_run == 5
        assert creator.min_priority == FindingPriority.P2

    def test_default_values(self):
        """Test IssueCreator default values."""
        creator = IssueCreator(repo="owner/repo")
        assert creator.lookback_days == 30
        assert creator.similarity_threshold == 0.8
        assert creator.min_priority == FindingPriority.P3
        assert creator.max_issues_per_run == 5
        assert creator.dry_run is False

    def test_dry_run_mode(self):
        """Test IssueCreator dry run mode."""
        creator = IssueCreator(repo="owner/repo", dry_run=True)
        assert creator.dry_run is True

    def test_invalid_parameter_labels_rejected(self):
        """Test that 'labels' is not a valid parameter (catches workflow bug)."""
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            IssueCreator(
                repo="owner/repo",
                labels=["automated"],  # This should fail
            )

    def test_default_labels_class_attribute(self):
        """Test that DEFAULT_LABELS exists as class attribute."""
        assert hasattr(IssueCreator, "DEFAULT_LABELS")
        assert "automated" in IssueCreator.DEFAULT_LABELS
        assert "needs-review" in IssueCreator.DEFAULT_LABELS

    def test_priority_labels_mapping(self):
        """Test priority to label mapping."""
        assert FindingPriority.P0 in IssueCreator.PRIORITY_LABELS
        assert IssueCreator.PRIORITY_LABELS[FindingPriority.P0] == "priority:critical"

    @pytest.mark.asyncio
    async def test_create_issues_method_exists(self):
        """Test that create_issues method exists and takes a list."""
        creator = IssueCreator(repo="owner/repo", dry_run=True)

        # Mock the internal methods to avoid actual API calls
        with patch.object(creator, "_load_existing_fingerprints", new_callable=AsyncMock):
            with patch.object(creator, "_process_finding", new_callable=AsyncMock) as mock_process:
                from github_agents.creators.issue_creator import CreationResult

                mock_process.return_value = CreationResult(
                    finding=AnalysisFinding(
                        title="Test",
                        summary="Test",
                        details="Test",
                        category=FindingCategory.QUALITY,
                        priority=FindingPriority.P2,
                        affected_files=[AffectedFile(path="test.py")],
                        suggested_fix="Fix it",
                        evidence="",
                        discovered_by="test",
                    ),
                    skipped_reason="dry run mode",
                )

                findings = [
                    AnalysisFinding(
                        title="Test Finding",
                        summary="Test",
                        details="Test",
                        category=FindingCategory.QUALITY,
                        priority=FindingPriority.P2,
                        affected_files=[AffectedFile(path="test.py")],
                        suggested_fix="Fix it",
                        evidence="",
                        discovered_by="test",
                    )
                ]

                results = await creator.create_issues(findings)
                assert isinstance(results, list)
                mock_process.assert_called_once()


class TestWorkflowIntegration:
    """Test patterns used in the codebase-analysis workflow."""

    def test_affected_file_list_serialization(self):
        """Test serializing a list of AffectedFiles (workflow pattern)."""
        files = [
            AffectedFile(path="a.py", line_start=1),
            AffectedFile(path="b.py", line_start=2, line_end=5),
        ]

        # Workflow pattern: [asdict(af) for af in finding.affected_files]
        serialized = [asdict(af) for af in files]

        # Should be JSON serializable
        json_str = json.dumps(serialized)
        parsed = json.loads(json_str)

        # Reconstruct
        restored = [AffectedFile(**d) for d in parsed]

        assert len(restored) == 2
        assert restored[0].path == "a.py"
        assert restored[1].line_end == 5

    def test_mixed_file_data_handling(self):
        """Test handling mixed dict/string file data (defensive pattern)."""
        # The workflow handles both dicts and strings defensively
        files_data = [
            {"path": "a.py", "line_start": 1, "line_end": None, "snippet": None},
            "b.py",  # Legacy or malformed data
        ]

        affected_files = [
            AffectedFile(**file_dict) if isinstance(file_dict, dict) else AffectedFile(path=str(file_dict))
            for file_dict in files_data
        ]

        assert len(affected_files) == 2
        assert affected_files[0].path == "a.py"
        assert affected_files[1].path == "b.py"

    def test_priority_filtering_logic(self):
        """Test the priority filtering logic from the workflow."""
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        min_priority = "P2"
        min_priority_value = priority_order.get(min_priority, 2)

        findings = [
            {"title": "Critical", "priority": "P0"},
            {"title": "High", "priority": "P1"},
            {"title": "Medium", "priority": "P2"},
            {"title": "Low", "priority": "P3"},
        ]

        filtered = []
        for f in findings:
            f_priority = priority_order.get(f.get("priority", "P3"), 3)
            if f_priority <= min_priority_value:
                filtered.append(f)

        # P0, P1, P2 should pass; P3 should be filtered out
        assert len(filtered) == 3
        assert all(f["priority"] != "P3" for f in filtered)

    def test_enum_value_round_trip(self):
        """Test that enum values survive serialization round-trip."""
        original_category = FindingCategory.SECURITY
        original_priority = FindingPriority.P1

        # Serialize to string (workflow pattern)
        cat_str = original_category.value
        pri_str = original_priority.value

        # Reconstruct from string (workflow pattern)
        restored_category = FindingCategory(cat_str)
        restored_priority = FindingPriority(pri_str)

        assert restored_category == original_category
        assert restored_priority == original_priority

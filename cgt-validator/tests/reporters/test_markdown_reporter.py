"""Tests for Markdown report generator."""

from src.reporters.markdown_reporter import MarkdownReporter
from src.reporters.validation_results import ValidationResults


class TestMarkdownReporter:
    """Test Markdown report generation."""

    def test_generate_report_with_errors(self, sample_validation_results: ValidationResults):
        """Test Markdown report generation with validation errors."""
        reporter = MarkdownReporter()
        markdown = reporter.generate_report(sample_validation_results)

        # Check header
        assert "# CGT Validation Report" in markdown
        assert "**State:** Oregon" in markdown
        assert "**Year:** 2024" in markdown
        assert "**Status:** ❌ FAILED" in markdown

        # Check summary table
        assert "## Summary" in markdown
        assert "| Metric | Count |" in markdown
        assert "| Errors |" in markdown
        assert "| Warnings |" in markdown
        assert "| Info |" in markdown

        # Check error section
        assert "## Errors (" in markdown
        assert "MISSING_SHEET" in markdown
        assert "INVALID_NPI" in markdown

        # Check warning section
        assert "## Warnings (" in markdown
        assert "NEGATIVE_AMOUNT" in markdown

        # Check info section
        assert "## Information (" in markdown
        assert "BEHAVIORAL_HEALTH_FOUND" in markdown

    def test_generate_report_valid_submission(self):
        """Test Markdown report for valid submission."""
        results = ValidationResults("rhode_island", 2025)
        reporter = MarkdownReporter()
        markdown = reporter.generate_report(results)

        # Should show passed status
        assert "✅ PASSED" in markdown
        assert "Rhode_island" in markdown
        assert "2025" in markdown

        # Should not have error/warning/info sections
        assert "## Errors" not in markdown
        assert "## Warnings" not in markdown
        assert "## Information" not in markdown

    def test_report_footer(self, sample_validation_results: ValidationResults):
        """Test report includes footer with timestamp."""
        reporter = MarkdownReporter()
        markdown = reporter.generate_report(sample_validation_results)

        # Check footer
        assert "---" in markdown
        assert "Report generated on" in markdown
        assert "by CGT Validator" in markdown

    def test_issues_grouped_by_location(self, sample_validation_results: ValidationResults):
        """Test issues are grouped by location."""
        reporter = MarkdownReporter()
        markdown = reporter.generate_report(sample_validation_results)

        # Check location headers
        assert "### 📍" in markdown
        assert "sheets" in markdown
        assert "Provider Information.NPI" in markdown
        assert "Medical Claims" in markdown

    def test_markdown_formatting(self, sample_validation_results: ValidationResults):
        """Test proper markdown formatting."""
        reporter = MarkdownReporter()
        markdown = reporter.generate_report(sample_validation_results)

        # Check markdown elements
        lines = markdown.split("\n")

        # Headers should have proper spacing
        header_indices = [i for i, line in enumerate(lines) if line.startswith("#")]
        for i in header_indices[:-1]:  # Skip last header
            # Should have blank line before next content
            if i + 1 < len(lines):
                assert lines[i + 1] == "" or lines[i + 1].startswith("#")

        # Table should be properly formatted
        table_start = next(i for i, line in enumerate(lines) if "| Metric | Count |" in line)
        assert "|--------|-------|" in lines[table_start + 1]

    def test_emoji_indicators(self, sample_validation_results: ValidationResults):
        """Test emoji indicators for different severities."""
        reporter = MarkdownReporter()
        markdown = reporter.generate_report(sample_validation_results)

        # Check emoji usage
        assert "🔴" in markdown  # Errors
        assert "🟡" in markdown  # Warnings
        assert "🔵" in markdown  # Info
        assert "📍" in markdown  # Location marker

    def test_multiple_issues_same_location(self):
        """Test handling multiple issues at the same location."""
        results = ValidationResults("test", 2024)

        # Add multiple errors at same location
        results.add_error("ERR1", "First error", "Sheet1.Column1")
        results.add_error("ERR2", "Second error", "Sheet1.Column1")
        results.add_error("ERR3", "Third error", "Sheet1.Column2")

        reporter = MarkdownReporter()
        markdown = reporter.generate_report(results)

        # Should group by location
        assert "### 📍 Sheet1.Column1" in markdown
        assert "### 📍 Sheet1.Column2" in markdown

        # Both errors should be under same location
        lines = markdown.split("\n")
        col1_index = next(i for i, line in enumerate(lines) if "Sheet1.Column1" in line)
        col2_index = next(i for i, line in enumerate(lines) if "Sheet1.Column2" in line)

        # Should have 2 errors between Column1 and Column2 headers
        errors_between = [line for line in lines[col1_index:col2_index] if "🔴" in line]
        assert len(errors_between) == 2

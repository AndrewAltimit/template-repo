"""Tests for HTML report generator."""

from pathlib import Path

from src.reporters.html_reporter import HTMLReporter
from src.reporters.validation_results import ValidationResults


class TestHTMLReporter:
    """Test HTML report generation."""

    def test_generate_report_with_errors(self, sample_validation_results: ValidationResults):
        """Test HTML report generation with validation errors."""
        reporter = HTMLReporter()
        html = reporter.generate_report(sample_validation_results)

        # Check basic structure
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

        # Check title and header
        assert "CGT Validation Report" in html
        assert "Oregon" in html  # State name (capitalized)
        assert "2024" in html  # Year

        # Check status
        assert "FAILED" in html  # Should show failed status

        # Check counts
        assert str(len(sample_validation_results.errors)) in html
        assert str(len(sample_validation_results.warnings)) in html
        assert str(len(sample_validation_results.info)) in html

        # Check specific error content
        assert "MISSING_SHEET" in html
        assert "Medical Claims" in html
        assert "INVALID_NPI" in html

        # Check filter buttons
        assert "filter-button" in html
        assert "filterIssues" in html

    def test_generate_report_valid_submission(self):
        """Test HTML report for valid submission."""
        results = ValidationResults("massachusetts", 2025)
        reporter = HTMLReporter()
        html = reporter.generate_report(results)

        # Should show passed status
        assert "PASSED" in html
        assert "status-passed" in html

        # Should show no issues message
        assert "No issues found" in html

        # Check state and year
        assert "Massachusetts" in html
        assert "2025" in html

    def test_report_includes_all_severities(self, sample_validation_results: ValidationResults):
        """Test that all severity levels are included in report."""
        reporter = HTMLReporter()
        html = reporter.generate_report(sample_validation_results)

        # Check sections
        assert "Errors" in html
        assert "Warnings" in html
        assert "Information" in html

        # Check CSS classes
        assert "issue-error" in html
        assert "issue-warning" in html
        assert "issue-info" in html

        # Check specific messages
        assert "Required sheet" in html
        assert "Negative amounts" in html
        assert "behavioral health claims" in html

    def test_report_javascript_functionality(self, sample_validation_results: ValidationResults):
        """Test JavaScript filter functionality is included."""
        reporter = HTMLReporter()
        html = reporter.generate_report(sample_validation_results)

        # Check JavaScript function
        assert "function filterIssues" in html
        assert "data-filter" in html

        # Check filter buttons for each severity
        assert 'data-filter="all"' in html
        assert 'data-filter="error"' in html
        assert 'data-filter="warning"' in html
        assert 'data-filter="info"' in html

    def test_report_styling(self, sample_validation_results: ValidationResults):
        """Test CSS styling is included."""
        reporter = HTMLReporter()
        html = reporter.generate_report(sample_validation_results)

        # Check style tag
        assert "<style>" in html
        assert "</style>" in html

        # Check key CSS classes
        assert ".container" in html
        assert ".summary-card" in html
        assert ".issue-error" in html
        assert ".status-failed" in html

    def test_report_timestamp(self, sample_validation_results: ValidationResults):
        """Test report includes generation timestamp."""
        reporter = HTMLReporter()
        html = reporter.generate_report(sample_validation_results)

        # Check timestamp section
        assert "Report generated on" in html
        assert "timestamp" in html

    def test_save_report_to_file(self, sample_validation_results: ValidationResults, temp_dir: Path):
        """Test saving HTML report to file."""
        reporter = HTMLReporter()
        html = reporter.generate_report(sample_validation_results)

        # Save to file
        output_path = temp_dir / "test_report.html"
        output_path.write_text(html)

        # Verify file exists and contains content
        assert output_path.exists()
        assert output_path.stat().st_size > 1000  # Should be substantial

        # Read back and verify
        saved_html = output_path.read_text()
        assert saved_html == html

    def test_report_mobile_responsive(self, sample_validation_results: ValidationResults):
        """Test report includes mobile responsive design."""
        reporter = HTMLReporter()
        html = reporter.generate_report(sample_validation_results)

        # Check viewport meta tag
        assert "viewport" in html
        assert "width=device-width" in html

        # Check responsive CSS
        assert "@media" in html
        assert "max-width: 768px" in html

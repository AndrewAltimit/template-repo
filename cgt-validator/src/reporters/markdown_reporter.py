"""Markdown report generator for validation results."""

from datetime import datetime
from typing import List

from .validation_results import ValidationIssue, ValidationResults


class MarkdownReporter:
    """Generate Markdown reports from validation results."""

    def generate_report(self, results: ValidationResults) -> str:
        """Generate Markdown report from validation results."""
        summary = results.get_summary()

        # Build report sections
        sections = [
            self._generate_header(results),
            self._generate_summary(summary),
            self._generate_issues_section("Errors", results.errors, "🔴"),
            self._generate_issues_section("Warnings", results.warnings, "🟡"),
            self._generate_issues_section("Information", results.info, "🔵"),
            self._generate_footer(),
        ]

        # Filter out empty sections
        sections = [s for s in sections if s]

        return "\n\n".join(sections)

    def _generate_header(self, results: ValidationResults) -> str:
        """Generate report header."""
        status = "✅ PASSED" if results.is_valid() else "❌ FAILED"

        return f"""# CGT Validation Report

**State:** {results.state.title()}
**Year:** {results.year}
**Status:** {status}"""

    def _generate_summary(self, summary: dict) -> str:
        """Generate summary section."""
        return f"""## Summary

| Metric | Count |
|--------|-------|
| Errors | {summary['error_count']} |
| Warnings | {summary['warning_count']} |
| Info | {summary['info_count']} |
| Duration | {summary['duration_seconds']:.2f}s |"""

    def _generate_issues_section(self, title: str, issues: List[ValidationIssue], emoji: str) -> str:
        """Generate a section for issues of a specific type."""
        if not issues:
            return ""

        lines = [f"## {title} ({len(issues)})"]

        # Group issues by location
        issues_by_location = {}
        for issue in issues:
            if issue.location not in issues_by_location:
                issues_by_location[issue.location] = []
            issues_by_location[issue.location].append(issue)

        # Generate issues list
        for location, location_issues in issues_by_location.items():
            lines.append(f"\n### 📍 {location}")

            for issue in location_issues:
                lines.append(f"\n{emoji} **[{issue.code}]** {issue.message}")

        return "\n".join(lines)

    def _generate_footer(self) -> str:
        """Generate report footer."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""---

*Report generated on {timestamp} by CGT Validator*"""

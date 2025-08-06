#!/usr/bin/env python3
"""Integration test script for template monitoring in CI/CD pipeline."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.states_config import list_supported_states  # noqa: E402
from scrapers.template_monitor import TemplateMonitor  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TemplateMonitoringTest:
    """Integration test for template monitoring functionality."""

    def __init__(self, states: Optional[List[str]] = None, test_dir: Optional[Path] = None):
        self.states = states or ["oregon"]  # Default to Oregon for testing
        self.test_dir = test_dir or Path("./test_monitoring")
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.results: Dict[str, Dict] = {}
        self.test_passed = True

    def setup(self):
        """Setup test environment."""
        logger.info("Setting up template monitoring test...")

        # Clear any existing test data
        for state in self.states:
            state_dir = self.test_dir / state
            if state_dir.exists():
                import shutil

                shutil.rmtree(state_dir)

        logger.info(f"Test directory: {self.test_dir}")
        logger.info(f"States to test: {', '.join(self.states)}")

    def test_monitoring_initialization(self, state: str) -> bool:
        """Test that monitoring can be initialized for a state."""
        logger.info(f"Testing monitoring initialization for {state}...")

        try:
            monitor = TemplateMonitor(state, storage_dir=self.test_dir / state)

            # Check that required files are created
            assert monitor.snapshots_file.exists(), f"Snapshots file not created for {state}"
            assert monitor.changes_file.exists(), f"Changes file not created for {state}"
            assert monitor.monitoring_config_file.exists(), f"Config file not created for {state}"

            logger.info(f"✓ Monitoring initialization successful for {state}")
            return True

        except Exception as e:
            logger.error(f"✗ Monitoring initialization failed for {state}: {e}")
            return False

    def test_configuration_management(self, state: str) -> bool:
        """Test configuration loading and saving."""
        logger.info(f"Testing configuration management for {state}...")

        try:
            monitor = TemplateMonitor(state, storage_dir=self.test_dir / state)

            # Modify configuration
            monitor.monitoring_config["test_field"] = "test_value"
            monitor.monitoring_config["critical_fields"].append("TEST_FIELD")
            monitor._save_monitoring_config()

            # Create new instance and check config persistence
            monitor2 = TemplateMonitor(state, storage_dir=self.test_dir / state)
            assert monitor2.monitoring_config["test_field"] == "test_value", "Config not persisted"
            assert "TEST_FIELD" in monitor2.monitoring_config["critical_fields"], "Critical fields not updated"

            logger.info(f"✓ Configuration management successful for {state}")
            return True

        except Exception as e:
            logger.error(f"✗ Configuration management failed for {state}: {e}")
            return False

    def test_snapshot_functionality(self, state: str) -> bool:
        """Test snapshot creation and comparison."""
        logger.info(f"Testing snapshot functionality for {state}...")

        try:
            from scrapers.template_monitor import TemplateSnapshot

            # Create test snapshots
            snapshot1 = TemplateSnapshot(
                url="https://test.example.com/template.xlsx",
                file_hash="hash123",
                file_size=1000,
                content_hash="content123",
                metadata={"version": "1.0", "test": True},
            )

            snapshot2 = TemplateSnapshot(
                url="https://test.example.com/template.xlsx",
                file_hash="hash456",
                file_size=1500,
                content_hash="content456",
                metadata={"version": "2.0", "test": True},
            )

            # Test serialization
            data1 = snapshot1.to_dict()
            restored1 = TemplateSnapshot.from_dict(data1)
            assert restored1.file_hash == snapshot1.file_hash, "Snapshot serialization failed"

            # Test comparison
            monitor = TemplateMonitor(state, storage_dir=self.test_dir / state)
            changed, description, severity = monitor._compare_snapshots(snapshot1, snapshot2)

            assert changed, "Should detect change between different snapshots"
            assert "size change" in description.lower(), "Should detect size change"

            logger.info(f"✓ Snapshot functionality successful for {state}")
            return True

        except Exception as e:
            logger.error(f"✗ Snapshot functionality failed for {state}: {e}")
            return False

    def test_change_detection(self, state: str) -> bool:
        """Test change detection capabilities."""
        logger.info(f"Testing change detection for {state}...")

        try:
            monitor = TemplateMonitor(state, storage_dir=self.test_dir / state)

            # Test field change detection
            monitor.monitoring_config["track_field_changes"] = True
            monitor.monitoring_config["critical_fields"] = ["PROV_ID", "MEMBER_MONTHS", "PAID_AMT"]

            old_text = """
            Data Submission Template
            PROV_ID: PRV001
            MEMBER_MONTHS: 12000
            PAID_AMT: 500000.00
            STATUS: Active
            """

            new_text = """
            Data Submission Template
            PROV_ID: PRV002
            MEMBER_MONTHS: 12000
            PAID_AMT: 750000.00
            STATUS: Active
            """

            changed_fields = monitor._detect_field_changes(old_text, new_text)

            assert "PROV_ID" in changed_fields, "Should detect PROV_ID change"
            assert "PAID_AMT" in changed_fields, "Should detect PAID_AMT change"
            assert "MEMBER_MONTHS" not in changed_fields, "Should not detect unchanged MEMBER_MONTHS"

            logger.info(f"✓ Change detection successful for {state}")
            return True

        except Exception as e:
            logger.error(f"✗ Change detection failed for {state}: {e}")
            return False

    def test_report_generation(self, state: str) -> bool:
        """Test report generation capabilities."""
        logger.info(f"Testing report generation for {state}...")

        try:
            from scrapers.template_monitor import ChangeEvent, TemplateSnapshot

            monitor = TemplateMonitor(state, storage_dir=self.test_dir / state)

            # Add test data
            snapshot = TemplateSnapshot(
                url="https://test.example.com/template.xlsx",
                file_hash="test_hash",
                file_size=5000,
                metadata={"filename": "test_template.xlsx", "version": "1.0"},
            )
            monitor.snapshots["https://test.example.com/template.xlsx"] = [snapshot]

            change = ChangeEvent(
                url="https://test.example.com/template.xlsx",
                change_type="new",
                old_snapshot=None,
                new_snapshot=snapshot,
                description="New template discovered in testing",
                severity="info",
            )
            monitor.change_history.append(change)

            # Generate reports
            markdown_report = monitor._generate_markdown_report()
            assert "Template Monitoring Report" in markdown_report, "Markdown report missing title"
            assert "test_template.xlsx" in markdown_report, "Markdown report missing template name"

            html_report = monitor._generate_html_report()
            assert "<title>Template Monitoring Report" in html_report, "HTML report missing title"
            assert "test_template.xlsx" in html_report, "HTML report missing template name"

            # Save reports
            md_file = self.test_dir / state / "test_report.md"
            md_file.write_text(markdown_report)

            html_file = self.test_dir / state / "test_report.html"
            html_file.write_text(html_report)

            logger.info(f"✓ Report generation successful for {state}")
            return True

        except Exception as e:
            logger.error(f"✗ Report generation failed for {state}: {e}")
            return False

    def test_monitoring_cycle(self, state: str) -> bool:
        """Test a complete monitoring cycle (without actual downloads)."""
        logger.info(f"Testing monitoring cycle for {state}...")

        try:
            from unittest.mock import patch

            monitor = TemplateMonitor(state, storage_dir=self.test_dir / state)

            # Mock the download and scraping functions to avoid actual network calls
            with patch.object(monitor, "_download_and_snapshot") as mock_download:
                with patch.object(monitor.scraper, "find_latest_templates") as mock_scrape:
                    # Setup mocks
                    from scrapers.template_monitor import TemplateSnapshot
                    from scrapers.web_scraper import DocumentInfo

                    mock_snapshot = TemplateSnapshot(
                        url="https://test.example.com/mocked.xlsx",
                        file_hash="mock_hash",
                        file_size=1000,
                        metadata={"test": True},
                    )
                    mock_download.return_value = mock_snapshot

                    mock_doc = DocumentInfo(
                        url="https://test.example.com/mocked.xlsx",
                        title="Mocked Template",
                        file_type="xlsx",
                        version="1.0",
                    )
                    mock_scrape.return_value = [mock_doc]

                    # Run monitoring
                    summary = monitor.run_monitoring()

                    # Verify summary structure
                    assert "state" in summary, "Summary missing state"
                    assert "monitoring_date" in summary, "Summary missing date"
                    assert "duration_seconds" in summary, "Summary missing duration"
                    assert "changes_detected" in summary, "Summary missing changes count"
                    assert "changes_by_type" in summary, "Summary missing change types"
                    assert "changes_by_severity" in summary, "Summary missing severities"

                    # Check that summary was saved
                    summary_files = list((self.test_dir / state).glob("monitoring_summary_*.json"))
                    assert len(summary_files) > 0, "Summary file not saved"

                    logger.info(f"✓ Monitoring cycle successful for {state}")
                    return True

        except Exception as e:
            logger.error(f"✗ Monitoring cycle failed for {state}: {e}")
            return False

    def run_tests(self) -> bool:
        """Run all tests for all configured states."""
        self.setup()

        test_methods = [
            self.test_monitoring_initialization,
            self.test_configuration_management,
            self.test_snapshot_functionality,
            self.test_change_detection,
            self.test_report_generation,
            self.test_monitoring_cycle,
        ]

        for state in self.states:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing state: {state}")
            logger.info(f"{'='*60}")

            state_results = []
            for test_method in test_methods:
                result = test_method(state)
                state_results.append(result)
                if not result:
                    self.test_passed = False

            self.results[state] = {
                "total_tests": len(test_methods),
                "passed": sum(state_results),
                "failed": len(test_methods) - sum(state_results),
            }

        return self.test_passed

    def generate_summary(self) -> Dict:
        """Generate test summary."""
        summary = {
            "test_date": datetime.now().isoformat(),
            "test_directory": str(self.test_dir),
            "overall_passed": self.test_passed,
            "states_tested": len(self.states),
            "results_by_state": self.results,
        }

        # Save summary
        summary_file = self.test_dir / "test_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        return summary

    def print_summary(self):
        """Print test summary to console."""
        print("\n" + "=" * 60)
        print("TEMPLATE MONITORING TEST SUMMARY")
        print("=" * 60)

        for state, results in self.results.items():
            status = "✓ PASSED" if results["failed"] == 0 else "✗ FAILED"
            print(f"\n{state}: {status}")
            print(f"  Tests run: {results['total_tests']}")
            print(f"  Passed: {results['passed']}")
            print(f"  Failed: {results['failed']}")

        print("\n" + "=" * 60)
        overall_status = "✓ ALL TESTS PASSED" if self.test_passed else "✗ SOME TESTS FAILED"
        print(f"Overall Result: {overall_status}")
        print("=" * 60)


def main():
    """Main entry point for CI/CD integration testing."""
    parser = argparse.ArgumentParser(description="Template Monitoring Integration Test")
    parser.add_argument(
        "--states",
        nargs="+",
        default=["oregon"],
        help="States to test (default: oregon)",
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=Path("./test_monitoring"),
        help="Directory for test data",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Running in CI/CD environment",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate states
    supported_states = list_supported_states()
    for state in args.states:
        if state not in supported_states:
            logger.error(f"Unsupported state: {state}")
            logger.info(f"Supported states: {', '.join(supported_states)}")
            sys.exit(1)

    # Run tests
    tester = TemplateMonitoringTest(states=args.states, test_dir=args.test_dir)
    success = tester.run_tests()

    # Generate and print summary
    summary = tester.generate_summary()
    tester.print_summary()

    # In CI mode, save detailed results
    if args.ci:
        ci_results_file = Path("template_monitoring_ci_results.json")
        with open(ci_results_file, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"CI results saved to: {ci_results_file}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

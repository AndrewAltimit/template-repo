#!/usr/bin/env python
"""Test script to demonstrate Oregon validator with valid data."""

import sys
from pathlib import Path

# Add src to path for direct testing before installation
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mock_data.oregon_generator_fixed import generate_mock_submission
from src.reporters.html_reporter import HTMLReporter
from src.validators.oregon import OregonValidator


def main():
    print("CGT Validator - Oregon Test Demo (Valid Data)")
    print("=" * 50)

    # Generate mock data with proper formatting
    print("\n1. Generating mock Oregon submission data (properly formatted)...")
    mock_file = Path("./mock_data/oregon/test_submission_valid.xlsx")
    mock_file.parent.mkdir(parents=True, exist_ok=True)

    generate_mock_submission(str(mock_file), include_optional=False)
    print(f"   ✓ Created: {mock_file}")

    # Validate the file
    print("\n2. Validating submission...")
    validator = OregonValidator(year=2025)
    results = validator.validate_file(str(mock_file))

    # Show summary
    summary = results.get_summary()
    print("\n3. Validation Results:")
    print(f"   Status: {'✓ PASSED' if results.is_valid() else '✗ FAILED'}")
    print(f"   Errors: {summary['error_count']}")
    print(f"   Warnings: {summary['warning_count']}")
    print(f"   Info: {summary['info_count']}")
    print(f"   Duration: {summary['duration_seconds']:.2f} seconds")

    # Show any remaining issues
    if results.errors:
        print("\n   Errors found:")
        for error in results.errors[:5]:
            print(f"   - [{error.code}] {error.message}")
            print(f"     Location: {error.location}")

    if results.warnings:
        print("\n   Warnings:")
        for warning in results.warnings[:5]:
            print(f"   - [{warning.code}] {warning.message}")

    # Generate HTML report
    print("\n4. Generating HTML report...")
    report_path = Path("./test_report_valid.html")
    reporter = HTMLReporter()
    report_content = reporter.generate_report(results)
    report_path.write_text(report_content)
    print(f"   ✓ Report saved to: {report_path}")

    print("\n" + "=" * 50)
    print("Test complete! You can now:")
    print(f"1. View the test data: {mock_file}")
    print(f"2. View the HTML report: {report_path}")
    print("\nTo validate using the CLI:")
    print("   ./cgt-validate.sh validate oregon --file", mock_file)
    print("   # or")
    print("   PYTHONPATH=src cgt-validate validate oregon --file", mock_file)

    return 0 if results.is_valid() else 1


if __name__ == "__main__":
    sys.exit(main())

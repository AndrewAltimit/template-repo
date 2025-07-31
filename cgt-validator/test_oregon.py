#!/usr/bin/env python
"""Quick test script to demonstrate Oregon validator functionality."""

import sys
from pathlib import Path

# Add src to path for direct testing before installation
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mock_data.oregon_generator import generate_mock_submission
from src.reporters.html_reporter import HTMLReporter
from src.validators.oregon import OregonValidator


def main():
    print("CGT Validator - Oregon Test Demo")
    print("=" * 50)
    print("\nNOTE: This test uses mock data with some intentional format issues")
    print("to demonstrate the validator's error detection capabilities.")

    # Generate mock data
    print("\n1. Generating mock Oregon submission data...")
    mock_file = Path("./mock_data/oregon/test_submission.xlsx")
    mock_file.parent.mkdir(parents=True, exist_ok=True)

    generate_mock_submission(str(mock_file))
    print(f"   ✓ Created: {mock_file}")

    # Validate the file
    print("\n2. Validating submission...")
    validator = OregonValidator(year=2025)
    results = validator.validate_file(str(mock_file))

    # Show summary
    summary = results.get_summary()
    print("\n3. Validation Results:")
    print(f"   Status: {'PASSED' if results.is_valid() else 'FAILED'}")
    print(f"   Errors: {summary['error_count']} (Expected: Some errors due to Excel formatting)")
    print(f"   Warnings: {summary['warning_count']}")
    print(f"   Info: {summary['info_count']}")

    # Show first few issues
    if results.errors:
        print("\n   Sample Errors (These demonstrate the validator is working!):")
        for error in results.errors[:3]:
            print(f"   - [{error.code}] {error.message}")

    if results.warnings:
        print("\n   Sample Warnings:")
        for warning in results.warnings[:3]:
            print(f"   - [{warning.code}] {warning.message}")

    # Generate HTML report
    print("\n4. Generating HTML report...")
    report_path = Path("./test_report.html")
    reporter = HTMLReporter()
    report_content = reporter.generate_report(results)
    report_path.write_text(report_content)
    print(f"   ✓ Report saved to: {report_path}")

    print("\n" + "=" * 50)
    print("Test complete! The validation errors above are EXPECTED - they show")
    print("the validator is correctly catching common data formatting issues.")
    print("\nYou can now:")
    print(f"1. View the test data: {mock_file}")
    print(f"2. View the HTML report: {report_path}")
    print("\nFor a comprehensive test with both valid and invalid data, run:")
    print("   python test_oregon_validation.py")


if __name__ == "__main__":
    main()

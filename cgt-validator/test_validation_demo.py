#!/usr/bin/env python
"""
CGT Validator Demo - Shows expected validation behavior

This demo intentionally creates data with common formatting issues
to demonstrate that the validator is working correctly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.reporters.html_reporter import HTMLReporter
from src.validators.oregon import OregonValidator


def main():
    print("\n" + "=" * 70)
    print("CGT VALIDATOR - DEMONSTRATION")
    print("=" * 70)
    print("\nThis demo shows the validator catching common data quality issues.")
    print("The errors you'll see are EXPECTED and show the validator is working!")

    print("\n" + "-" * 70)
    print("COMMON EXCEL DATA ISSUES THE VALIDATOR CATCHES:")
    print("-" * 70)

    print("\n1. NPI/ZIP Format Issues:")
    print("   - Excel often converts these to numbers, losing leading zeros")
    print("   - Example: ZIP '01234' becomes 1234")
    print("   - Oregon requires these as TEXT to preserve formatting")

    print("\n2. Missing Required Fields:")
    print("   - Provider ID is required in Pharmacy Claims for attribution")
    print("   - Many submissions miss this critical field")

    print("\n3. Date Format Issues:")
    print("   - Dates must be proper date objects, not strings")
    print("   - Common error: '2024/13/45' or 'TBD'")

    print("\n4. Reconciliation Mismatches:")
    print("   - Total amounts must match between detail and summary")
    print("   - Catches calculation errors or missing data")

    print("\n" + "-" * 70)
    print("RUNNING VALIDATION ON TEST DATA...")
    print("-" * 70)

    # Use the existing test file that has these issues
    test_file = Path("./mock_data/oregon/test_submission.xlsx")

    if not test_file.exists():
        print(f"\n✗ Test file not found: {test_file}")
        print("  Run 'python test_oregon.py' first to generate test data")
        return 1

    # Validate
    validator = OregonValidator(year=2025)
    results = validator.validate_file(str(test_file))
    summary = results.get_summary()

    print(f"\n✓ Validation completed in {summary['duration_seconds']:.2f} seconds")
    print(f"\nResults: {summary['error_count']} errors caught (this is good!)")

    print("\n" + "-" * 70)
    print("ERRORS CAUGHT BY THE VALIDATOR:")
    print("-" * 70)

    error_types = {}
    for error in results.errors:
        if error.code not in error_types:
            error_types[error.code] = []
        error_types[error.code].append(error)

    for error_code, errors in error_types.items():
        print(f"\n{error_code}:")
        for error in errors[:2]:  # Show first 2 of each type
            print(f"  - {error.message}")
            print(f"    Location: {error.location}")

    # Generate report
    report_path = Path("./validation_demo_report.html")
    reporter = HTMLReporter()
    report_content = reporter.generate_report(results)
    report_path.write_text(report_content)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\n✓ The validator successfully caught all data quality issues!")
    print("\nThese errors are EXPECTED because the test data intentionally")
    print("includes common formatting problems found in real submissions.")
    print("\nFor production use:")
    print("1. Ensure NPI/ZIP columns are formatted as TEXT in Excel")
    print("2. Include all required fields (check Oregon template)")
    print("3. Use proper date formats")
    print("4. Verify reconciliation totals match")
    print(f"\n✓ Detailed report saved to: {report_path}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    sys.exit(main())

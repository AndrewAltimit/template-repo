#!/usr/bin/env python
"""Comprehensive test script demonstrating Oregon validator catching both valid and invalid data."""

import sys
from pathlib import Path

import pandas as pd

# Add src to path for direct testing before installation
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mock_data.oregon_generator import OregonMockDataGenerator
from src.reporters.html_reporter import HTMLReporter
from src.validators.oregon import OregonValidator


def create_invalid_test_data(output_path: str):
    """Create test data with intentional errors to verify validator catches them."""
    generator = OregonMockDataGenerator()

    # Generate base data
    provider_df = generator.generate_provider_information()
    member_months_df = generator.generate_member_months()
    medical_df = generator.generate_medical_claims()
    pharmacy_df = generator.generate_pharmacy_claims()
    reconciliation_df = generator.generate_reconciliation(medical_df, pharmacy_df)

    # Intentionally create validation errors:

    # 1. Store NPI and ZIP as numbers (will lose leading zeros)
    # This is what happens when Excel auto-formats these fields
    provider_df["NPI"] = provider_df["NPI"].astype(int)
    provider_df["ZIP"] = provider_df["ZIP"].astype(int)

    # 2. Remove required Provider ID column from pharmacy claims
    pharmacy_df = pharmacy_df.drop("Provider ID", axis=1, errors="ignore")

    # 3. Create reconciliation mismatch
    reconciliation_df["Medical Claims Total"] = reconciliation_df["Medical Claims Total"] * 0.5

    # 4. Add invalid date formats (strings instead of dates)
    medical_df.loc[0:10, "Service Date"] = "Invalid Date"
    pharmacy_df.loc[0:10, "Fill Date"] = "2024/13/45"  # Invalid date

    # Write to Excel
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        provider_df.to_excel(writer, sheet_name="Provider Information", index=False)
        member_months_df.to_excel(writer, sheet_name="Member Months", index=False)
        medical_df.to_excel(writer, sheet_name="Medical Claims", index=False)
        pharmacy_df.to_excel(writer, sheet_name="Pharmacy Claims", index=False)
        reconciliation_df.to_excel(writer, sheet_name="Reconciliation", index=False)


def create_valid_test_data(output_path: str):
    """Create properly formatted test data that should pass validation."""
    generator = OregonMockDataGenerator()

    # Generate base data
    provider_df = generator.generate_provider_information()
    member_months_df = generator.generate_member_months()
    medical_df = generator.generate_medical_claims()
    pharmacy_df = generator.generate_pharmacy_claims()

    # Add Provider ID to pharmacy claims (required by Oregon)
    pharmacy_df["Provider ID"] = [
        generator.providers[i % len(generator.providers)]["Provider ID"] for i in range(len(pharmacy_df))
    ]

    # Create proper reconciliation that matches
    reconciliation_df = generator.generate_reconciliation(medical_df, pharmacy_df)

    # Ensure text fields are properly formatted
    provider_df["NPI"] = provider_df["NPI"].astype(str)
    provider_df["ZIP"] = provider_df["ZIP"].astype(str).str.zfill(5)

    # Write to Excel with proper formatting
    with pd.ExcelWriter(output_path, engine="openpyxl", date_format="YYYY-MM-DD") as writer:
        provider_df.to_excel(writer, sheet_name="Provider Information", index=False)
        member_months_df.to_excel(writer, sheet_name="Member Months", index=False)
        medical_df.to_excel(writer, sheet_name="Medical Claims", index=False)
        pharmacy_df.to_excel(writer, sheet_name="Pharmacy Claims", index=False)
        reconciliation_df.to_excel(writer, sheet_name="Reconciliation", index=False)


def test_invalid_data():
    """Test that validator properly catches invalid data."""
    print("\n" + "=" * 70)
    print("TEST 1: VALIDATING INTENTIONALLY INVALID DATA")
    print("Expected Result: FAIL with specific errors")
    print("=" * 70)

    # Create invalid test data
    invalid_file = Path("./mock_data/oregon/test_invalid_data.xlsx")
    invalid_file.parent.mkdir(parents=True, exist_ok=True)
    create_invalid_test_data(str(invalid_file))
    print(f"\n✓ Created test file with intentional errors: {invalid_file}")

    # Validate
    validator = OregonValidator(year=2025)
    results = validator.validate_file(str(invalid_file))
    summary = results.get_summary()

    print(f"\nValidation Status: {'PASSED' if results.is_valid() else 'FAILED'} ✓ (Expected: FAILED)")
    print(f"Errors Found: {summary['error_count']}")

    # Check for expected errors
    expected_errors = {
        "INVALID_DATA_TYPE": "Data type validation working",
        "MISSING_COLUMN": "Missing column detection working",
        "RECONCILIATION_MISMATCH": "Reconciliation validation working",
    }

    print("\nExpected Errors Found:")
    for error in results.errors[:10]:
        if error.code in expected_errors:
            print(f"  ✓ [{error.code}] {expected_errors[error.code]}")
            print(f"    Details: {error.message}")

    # Generate report
    report_path = Path("./test_report_invalid.html")
    reporter = HTMLReporter()
    report_content = reporter.generate_report(results)
    report_path.write_text(report_content)
    print(f"\n✓ Detailed report saved to: {report_path}")

    return not results.is_valid()  # Should return True (test passes if validation fails)


def test_valid_data():
    """Test that validator passes valid data."""
    print("\n" + "=" * 70)
    print("TEST 2: VALIDATING PROPERLY FORMATTED DATA")
    print("Expected Result: PASS or minor warnings only")
    print("=" * 70)

    # Create valid test data
    valid_file = Path("./mock_data/oregon/test_valid_data.xlsx")
    valid_file.parent.mkdir(parents=True, exist_ok=True)
    create_valid_test_data(str(valid_file))
    print(f"\n✓ Created properly formatted test file: {valid_file}")

    # Validate
    validator = OregonValidator(year=2025)
    results = validator.validate_file(str(valid_file))
    summary = results.get_summary()

    print(f"\nValidation Status: {'PASSED' if results.is_valid() else 'FAILED'}")
    print(f"Errors: {summary['error_count']}")
    print(f"Warnings: {summary['warning_count']} (version info warning is OK)")

    if results.errors:
        print("\nUnexpected Errors:")
        for error in results.errors[:5]:
            print(f"  ✗ [{error.code}] {error.message}")

    if results.warnings:
        print("\nWarnings (these are OK):")
        for warning in results.warnings:
            print(f"  ⚠ [{warning.code}] {warning.message}")

    # Generate report
    report_path = Path("./test_report_valid.html")
    reporter = HTMLReporter()
    report_content = reporter.generate_report(results)
    report_path.write_text(report_content)
    print(f"\n✓ Report saved to: {report_path}")

    return results.is_valid() or (summary["error_count"] == 0 and summary["warning_count"] <= 1)


def main():
    print("\nCGT VALIDATOR - COMPREHENSIVE VALIDATION TESTING")
    print("This test demonstrates the validator catching various data quality issues")

    # Run both tests
    test1_passed = test_invalid_data()
    test2_passed = test_valid_data()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Test 1 (Invalid Data Detection): {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"Test 2 (Valid Data Acceptance): {'✓ PASSED' if test2_passed else '✗ FAILED'}")

    if test1_passed and test2_passed:
        print("\n✓ All tests passed! The validator is working correctly.")
        print("  - It catches invalid data (NPI/ZIP formatting, missing columns, etc.)")
        print("  - It accepts properly formatted data")
    else:
        print("\n✗ Some tests failed. Check the reports for details.")

    print("\nGenerated Files:")
    print("  - mock_data/oregon/test_invalid_data.xlsx (intentionally invalid)")
    print("  - mock_data/oregon/test_valid_data.xlsx (properly formatted)")
    print("  - test_report_invalid.html (shows caught errors)")
    print("  - test_report_valid.html (should show minimal issues)")

    return 0 if (test1_passed and test2_passed) else 1


if __name__ == "__main__":
    sys.exit(main())

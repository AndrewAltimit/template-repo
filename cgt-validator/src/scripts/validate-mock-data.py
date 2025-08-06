#!/usr/bin/env python3
"""Validate that mock data files have the expected structure."""

import argparse
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Required sheets for each state
REQUIRED_SHEETS = {
    "oregon": ["Provider Information", "Member Months", "Medical Claims", "Pharmacy Claims", "Reconciliation"],
    # Add other states as they're implemented
}

# Default required sheets if state not specified
DEFAULT_REQUIRED_SHEETS = ["Provider Information", "Medical Claims", "Pharmacy Claims"]


def validate_excel_file(file_path: str, state: Optional[str] = None) -> bool:
    """Validate that an Excel file has proper structure.

    Args:
        file_path: Path to the Excel file to validate
        state: State name (e.g., 'oregon', 'massachusetts'). If not provided,
               will attempt to extract from path or use default sheets.
    """
    path = Path(file_path)

    # If state not provided, try to extract from path (backward compatibility)
    if state is None:
        parts = path.parts
        if "mock_data" in parts:
            idx = parts.index("mock_data")
            if idx + 1 < len(parts):
                state = parts[idx + 1]

    # Get required sheets for this state
    if state:
        required_sheets = REQUIRED_SHEETS.get(state, DEFAULT_REQUIRED_SHEETS)
    else:
        required_sheets = DEFAULT_REQUIRED_SHEETS

    try:
        # Read Excel file
        excel_file = pd.ExcelFile(path)
        available_sheets = excel_file.sheet_names

        # Check for required sheets
        missing_sheets = set(required_sheets) - set(available_sheets)

        if missing_sheets:
            print(f"ERROR: {path} is missing required sheets: {missing_sheets}")
            return False

        # Basic validation of each sheet
        for sheet in required_sheets:
            df = excel_file.parse(sheet)

            if df.empty:
                print(f"WARNING: {path} - Sheet '{sheet}' is empty")
            elif len(df.columns) < 2:
                print(f"WARNING: {path} - Sheet '{sheet}' has less than 2 columns")

        print(f"✓ {path} - Valid structure")
        return True

    except FileNotFoundError as e:
        print(f"ERROR: {path} - File not found: {e}")
        return False
    except pd.errors.EmptyDataError as e:
        print(f"ERROR: {path} - File is empty: {e}")
        return False
    except (pd.errors.ParserError, ValueError) as e:
        print(f"ERROR: {path} - Failed to parse Excel file: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate CGT mock data Excel files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate with explicit state
  %(prog)s --state oregon mock_data/oregon/test_submission.xlsx

  # Validate multiple files for the same state
  %(prog)s --state massachusetts file1.xlsx file2.xlsx

  # Let the script infer state from path (backward compatible)
  %(prog)s mock_data/oregon/test_submission.xlsx
""",
    )

    parser.add_argument("files", nargs="+", help="Excel file(s) to validate")

    parser.add_argument(
        "--state",
        "-s",
        help="State name (e.g., oregon, massachusetts). If not provided, will attempt to extract from file path.",
        choices=list(REQUIRED_SHEETS.keys()),
    )

    args = parser.parse_args()

    all_valid = True
    for file_path in args.files:
        if not validate_excel_file(file_path, args.state):
            all_valid = False

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()

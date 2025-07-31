#!/usr/bin/env python3
"""Validate that mock data files have the expected structure."""

import sys
from pathlib import Path

import pandas as pd

# Required sheets for each state
REQUIRED_SHEETS = {
    "oregon": ["Provider Information", "Member Months", "Medical Claims", "Pharmacy Claims", "Reconciliation"],
    # Add other states as they're implemented
}

# Default required sheets if state not specified
DEFAULT_REQUIRED_SHEETS = ["Provider Information", "Medical Claims", "Pharmacy Claims"]


def validate_excel_file(file_path: str) -> bool:
    """Validate that an Excel file has proper structure."""
    path = Path(file_path)

    # Extract state from path (assumes mock_data/state/file.xlsx structure)
    parts = path.parts
    state = None
    if "mock_data" in parts:
        idx = parts.index("mock_data")
        if idx + 1 < len(parts):
            state = parts[idx + 1]

    # Get required sheets for this state
    required_sheets = REQUIRED_SHEETS.get(state, DEFAULT_REQUIRED_SHEETS)

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

    except Exception as e:
        print(f"ERROR: {path} - Failed to read: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: validate-mock-data.py <excel_file> [excel_file ...]")
        sys.exit(1)

    all_valid = True
    for file_path in sys.argv[1:]:
        if not validate_excel_file(file_path):
            all_valid = False

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()

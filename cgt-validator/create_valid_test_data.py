#!/usr/bin/env python
"""Create a valid test data file using the OregonMockDataGenerator.

Note: This script requires the cgt-validator package to be installed.
Run: pip install -e . from the cgt-validator directory first.
"""

from pathlib import Path

from mock_data.oregon_generator import OregonMockDataGenerator


def create_valid_oregon_submission():
    """Create a valid Oregon submission file using the mock data generator."""
    # Initialize generator
    generator = OregonMockDataGenerator(seed=42)

    # Generate the complete Excel file
    output_path = Path("mock_data/oregon/valid_submission_openpyxl.xlsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use the generator's method to create the file with proper Excel formatting
    generator.generate_submission_file(
        output_path=output_path, num_claims=1000, use_openpyxl=True  # Ensure proper text formatting
    )

    print(f"✅ Created valid Oregon submission file: {output_path}")
    return output_path


if __name__ == "__main__":
    create_valid_oregon_submission()

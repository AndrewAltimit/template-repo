"""Tests for Oregon validator."""

from pathlib import Path

from src.validators.oregon import OregonValidator


class TestOregonValidator:
    """Test Oregon-specific validator."""

    def test_valid_submission(self, valid_oregon_excel: Path):
        """Test validation of a valid Oregon submission."""
        validator = OregonValidator(year=2024)
        results = validator.validate_file(str(valid_oregon_excel))

        assert results.is_valid() or len(results.errors) == 0
        assert results.state == "oregon"
        assert results.year == 2024

    def test_invalid_submission(self, invalid_oregon_excel: Path):
        """Test validation of an invalid Oregon submission."""
        validator = OregonValidator(year=2024)
        results = validator.validate_file(str(invalid_oregon_excel))

        assert not results.is_valid()
        assert len(results.errors) > 0

        # Check for specific expected errors
        error_codes = [error.code for error in results.errors]
        assert "MISSING_SHEET" in error_codes  # Medical Claims missing
        assert "MISSING_COLUMN" in error_codes  # NPI column missing

    def test_missing_sheets(self, missing_sheets_excel: Path):
        """Test validation when required sheets are missing."""
        validator = OregonValidator()
        results = validator.validate_file(str(missing_sheets_excel))

        assert not results.is_valid()

        # Should have errors for each missing required sheet
        missing_sheet_errors = [e for e in results.errors if e.code == "MISSING_SHEET"]
        assert len(missing_sheet_errors) >= 4  # Member Months, Medical Claims, Pharmacy Claims, Reconciliation

    def test_npi_validation(self, temp_dir: Path):
        """Test NPI format validation."""
        from openpyxl import Workbook

        # Create file with invalid NPIs
        output_path = temp_dir / "npi_test.xlsx"
        wb = Workbook()

        # Provider sheet with invalid NPIs
        ws = wb.active
        ws.title = "Provider Information"
        headers = ["Provider ID", "Provider Name", "Provider Type", "Tax ID", "NPI", "Address", "City", "State", "ZIP"]
        ws.append(headers)

        # Valid NPI
        ws.append(
            ["PRV001", "Provider 1", "Hospital", "12-3456789", "1234567890", "123 Main St", "Portland", "OR", "97201"]
        )

        # Invalid NPIs
        ws.append(
            [
                "PRV002",
                "Provider 2",
                "Hospital",
                "12-3456789",
                "123456789",
                "456 Oak St",
                "Eugene",
                "OR",
                "97401",
            ]  # 9 digits
        )
        ws.append(
            [
                "PRV003",
                "Provider 3",
                "Hospital",
                "12-3456789",
                "12345678901",  # 11 digits
                "789 Pine St",
                "Salem",
                "OR",
                "97301",
            ]
        )
        ws.append(
            [
                "PRV004",
                "Provider 4",
                "Hospital",
                "12-3456789",
                "ABC1234567",  # Contains letters
                "321 Elm St",
                "Bend",
                "OR",
                "97701",
            ]
        )

        # Add other required sheets (minimal)
        for sheet_name in ["Member Months", "Medical Claims", "Pharmacy Claims", "Reconciliation"]:
            ws = wb.create_sheet(sheet_name)
            ws.append(["Placeholder"])

        wb.save(output_path)

        # Validate
        validator = OregonValidator()
        results = validator.validate_file(str(output_path))

        # Should have NPI errors
        npi_errors = [e for e in results.errors if e.code == "INVALID_NPI"]
        assert len(npi_errors) > 0

    def test_zip_validation(self, temp_dir: Path):
        """Test ZIP code validation."""
        from openpyxl import Workbook

        output_path = temp_dir / "zip_test.xlsx"
        wb = Workbook()

        ws = wb.active
        ws.title = "Provider Information"
        headers = ["Provider ID", "Provider Name", "Provider Type", "Tax ID", "NPI", "Address", "City", "State", "ZIP"]
        ws.append(headers)

        # Valid ZIPs
        ws.append(
            ["PRV001", "Provider 1", "Hospital", "12-3456789", "1234567890", "123 Main St", "Portland", "OR", "97201"]
        )  # 5 digits
        ws.append(
            ["PRV002", "Provider 2", "Hospital", "12-3456789", "1234567890", "456 Oak St", "Eugene", "OR", "974011234"]
        )  # 9 digits

        # Invalid ZIPs
        ws.append(
            ["PRV003", "Provider 3", "Hospital", "12-3456789", "1234567890", "789 Pine St", "Salem", "OR", "9730"]
        )  # 4 digits
        ws.append(
            ["PRV004", "Provider 4", "Hospital", "12-3456789", "1234567890", "321 Elm St", "Bend", "OR", "97701-1234"]
        )  # With dash

        # Add other required sheets
        for sheet_name in ["Member Months", "Medical Claims", "Pharmacy Claims", "Reconciliation"]:
            ws = wb.create_sheet(sheet_name)
            ws.append(["Placeholder"])

        wb.save(output_path)

        validator = OregonValidator()
        results = validator.validate_file(str(output_path))

        zip_errors = [e for e in results.errors if e.code == "INVALID_ZIP"]
        assert len(zip_errors) > 0

    def test_amount_validation(self, temp_dir: Path):
        """Test amount validation rules."""
        from openpyxl import Workbook

        output_path = temp_dir / "amount_test.xlsx"
        wb = Workbook()

        # Provider Information (minimal)
        ws = wb.active
        ws.title = "Provider Information"
        ws.append(["Provider ID", "Provider Name", "Provider Type", "Tax ID", "NPI", "Address", "City", "State", "ZIP"])
        ws.append(
            ["PRV001", "Provider 1", "Hospital", "12-3456789", "1234567890", "123 Main St", "Portland", "OR", "97201"]
        )

        # Medical Claims with amount issues
        ws = wb.create_sheet("Medical Claims")
        headers = [
            "Provider ID",
            "Member ID",
            "Claim ID",
            "Service Date",
            "Paid Date",
            "Procedure Code",
            "Diagnosis Code",
            "Allowed Amount",
            "Paid Amount",
            "Member Liability",
        ]
        ws.append(headers)

        # Valid claim
        ws.append(["PRV001", "MEM001", "CLM001", "2024-01-01", "2024-01-15", "99213", "F32.9", 100.00, 80.00, 20.00])

        # Paid exceeds allowed
        ws.append(["PRV001", "MEM002", "CLM002", "2024-01-02", "2024-01-16", "99214", "F41.1", 150.00, 160.00, -10.00])

        # Negative amounts
        ws.append(["PRV001", "MEM003", "CLM003", "2024-01-03", "2024-01-17", "99203", "Z00.00", -50.00, -30.00, -20.00])

        # Add other required sheets
        for sheet_name in ["Member Months", "Pharmacy Claims", "Reconciliation"]:
            ws = wb.create_sheet(sheet_name)
            ws.append(["Placeholder"])

        wb.save(output_path)

        validator = OregonValidator()
        results = validator.validate_file(str(output_path))

        # Should have paid exceeds allowed error
        paid_errors = [e for e in results.errors if e.code == "PAID_EXCEEDS_ALLOWED"]
        assert len(paid_errors) > 0

        # Should have negative amount warnings
        negative_warnings = [w for w in results.warnings if w.code == "NEGATIVE_AMOUNT"]
        assert len(negative_warnings) > 0

    def test_cross_reference_validation(self, temp_dir: Path):
        """Test cross-reference validation between sheets."""
        from openpyxl import Workbook

        output_path = temp_dir / "cross_ref_test.xlsx"
        wb = Workbook()

        # Provider Information
        ws = wb.active
        ws.title = "Provider Information"
        ws.append(["Provider ID", "Provider Name", "Provider Type", "Tax ID", "NPI", "Address", "City", "State", "ZIP"])
        ws.append(
            ["PRV001", "Provider 1", "Hospital", "12-3456789", "1234567890", "123 Main St", "Portland", "OR", "97201"]
        )
        ws.append(
            ["PRV002", "Provider 2", "Primary Care", "98-7654321", "0987654321", "456 Oak St", "Eugene", "OR", "97401"]
        )

        # Medical Claims with invalid provider reference
        ws = wb.create_sheet("Medical Claims")
        ws.append(
            [
                "Provider ID",
                "Member ID",
                "Claim ID",
                "Service Date",
                "Paid Date",
                "Procedure Code",
                "Diagnosis Code",
                "Allowed Amount",
                "Paid Amount",
                "Member Liability",
            ]
        )
        ws.append(["PRV001", "MEM001", "CLM001", "2024-01-01", "2024-01-15", "99213", "F32.9", 100.00, 80.00, 20.00])
        ws.append(
            [
                "PRV999",
                "MEM002",
                "CLM002",
                "2024-01-02",
                "2024-01-16",  # Invalid provider ID
                "99214",
                "F41.1",
                150.00,
                120.00,
                30.00,
            ]
        )

        # Add other required sheets
        for sheet_name in ["Member Months", "Pharmacy Claims", "Reconciliation"]:
            ws = wb.create_sheet(sheet_name)
            ws.append(["Placeholder"])

        wb.save(output_path)

        validator = OregonValidator()
        results = validator.validate_file(str(output_path))

        # Should have invalid provider reference error
        ref_errors = [e for e in results.errors if e.code == "INVALID_PROVIDER_REFERENCE"]
        assert len(ref_errors) > 0

    def test_reconciliation_validation(self, temp_dir: Path):
        """Test reconciliation totals validation."""
        from openpyxl import Workbook

        output_path = temp_dir / "reconciliation_test.xlsx"
        wb = Workbook()

        # Provider Information (minimal)
        ws = wb.active
        ws.title = "Provider Information"
        ws.append(["Provider ID", "Provider Name", "Provider Type", "Tax ID", "NPI", "Address", "City", "State", "ZIP"])
        ws.append(
            ["PRV001", "Provider 1", "Hospital", "12-3456789", "1234567890", "123 Main St", "Portland", "OR", "97201"]
        )

        # Medical Claims
        ws = wb.create_sheet("Medical Claims")
        ws.append(
            [
                "Provider ID",
                "Member ID",
                "Claim ID",
                "Service Date",
                "Paid Date",
                "Procedure Code",
                "Diagnosis Code",
                "Allowed Amount",
                "Paid Amount",
                "Member Liability",
            ]
        )
        ws.append(["PRV001", "MEM001", "CLM001", "2024-01-01", "2024-01-15", "99213", "F32.9", 100.00, 80.00, 20.00])
        ws.append(["PRV001", "MEM002", "CLM002", "2024-01-02", "2024-01-16", "99214", "F41.1", 150.00, 120.00, 30.00])
        # Total paid: 200.00

        # Reconciliation with mismatched total
        ws = wb.create_sheet("Reconciliation")
        ws.append(["Category", "Medical Claims Total", "Pharmacy Claims Total", "Total Claims"])
        ws.append(["Summary", 250.00, 0, 250.00])  # Wrong medical total

        # Add other required sheets
        for sheet_name in ["Member Months", "Pharmacy Claims"]:
            ws = wb.create_sheet(sheet_name)
            ws.append(["Placeholder"])

        wb.save(output_path)

        validator = OregonValidator()
        results = validator.validate_file(str(output_path))

        # Should have reconciliation mismatch error
        recon_errors = [e for e in results.errors if e.code == "RECONCILIATION_MISMATCH"]
        assert len(recon_errors) > 0

    def test_file_not_found(self):
        """Test validation with non-existent file."""
        validator = OregonValidator()
        results = validator.validate_file("/non/existent/file.xlsx")

        assert not results.is_valid()
        assert any(e.code == "FILE_NOT_FOUND" for e in results.errors)

    def test_invalid_file_type(self, csv_file: Path):
        """Test validation with invalid file type."""
        validator = OregonValidator()
        results = validator.validate_file(str(csv_file))

        assert not results.is_valid()
        assert any(e.code == "INVALID_FILE_TYPE" for e in results.errors)

    def test_empty_file(self, empty_excel: Path):
        """Test validation with empty Excel file."""
        validator = OregonValidator()
        results = validator.validate_file(str(empty_excel))

        assert not results.is_valid()
        # Should have errors about missing sheets
        assert any(e.code == "MISSING_SHEET" for e in results.errors)

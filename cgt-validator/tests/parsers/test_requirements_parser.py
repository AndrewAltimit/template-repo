"""Tests for requirements parser."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from openpyxl import Workbook

from src.parsers.requirements_parser import RequirementsParser


class TestRequirementsParser:
    """Test requirements parser functionality."""

    def test_parser_initialization(self, temp_dir: Path):
        """Test RequirementsParser initialization."""
        parser = RequirementsParser("oregon", output_dir=temp_dir)

        assert parser.state == "oregon"
        assert parser.output_dir == temp_dir
        assert temp_dir.exists()

    def test_unsupported_file_type(self, temp_dir: Path):
        """Test parsing unsupported file type."""
        parser = RequirementsParser("oregon")

        # Create a .txt file
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("test content")

        with pytest.raises(ValueError) as exc_info:
            parser.parse_document(txt_file)
        assert "Unsupported file type" in str(exc_info.value)

    def test_parse_excel_template(self, temp_dir: Path):
        """Test parsing Excel template."""
        parser = RequirementsParser("oregon", output_dir=temp_dir)

        # Create test Excel file
        excel_file = temp_dir / "template.xlsx"
        wb = Workbook()

        # Sheet 1 with data validation
        ws1 = wb.active
        ws1.title = "Provider Information"
        ws1.append(["Provider ID", "Provider Name", "Provider Type", "NPI"])
        ws1.append(["PRV001", "Test Provider", "Hospital", "1234567890"])

        # Add data validation
        from openpyxl.worksheet.datavalidation import DataValidation

        dv = DataValidation(type="list", formula1='"Hospital,Clinic,Primary Care"', allow_blank=False)
        dv.add(ws1["C2:C100"])
        ws1.add_data_validation(dv)

        # Sheet 2 with formula
        ws2 = wb.create_sheet("Summary")
        ws2["A1"] = "Total Providers"
        ws2["B1"] = "=COUNTA('Provider Information'!A:A)-1"

        # Save file
        wb.save(excel_file)

        # Parse the template
        requirements = parser.parse_document(excel_file)

        # Verify results
        assert requirements["file_type"] == "excel"
        assert "Provider Information" in requirements["sheets"]
        assert "Summary" in requirements["sheets"]

        # Check sheet info
        provider_sheet = requirements["sheets"]["Provider Information"]
        assert provider_sheet["columns"] == ["Provider ID", "Provider Name", "Provider Type", "NPI"]
        assert provider_sheet["has_data_validation"] is True

        summary_sheet = requirements["sheets"]["Summary"]
        assert summary_sheet["has_formulas"] is True

        # Check data validations
        assert "Provider Information" in requirements["data_validations"]
        validations = requirements["data_validations"]["Provider Information"]
        assert len(validations) > 0
        assert validations[0]["type"] == "list"

        # Check formulas
        assert "Summary" in requirements["formulas"]
        formulas = requirements["formulas"]["Summary"]
        assert len(formulas) > 0
        assert formulas[0]["cell"] == "B1"

    def test_extract_field_type(self):
        """Test field type extraction."""
        parser = RequirementsParser("oregon")

        # Test various row configurations
        assert parser._extract_field_type(["Field", "Text", "50 chars"]) == "text"
        assert parser._extract_field_type(["ID", "Integer"]) == "integer"
        assert parser._extract_field_type(["Amount", "Decimal(10,2)"]) == "numeric"
        assert parser._extract_field_type(["Created", "DateTime"]) == "date"
        assert parser._extract_field_type(["Active", "Boolean"]) == "boolean"
        assert parser._extract_field_type(["Unknown"]) == "text"  # Default

    def test_is_field_required(self):
        """Test required field detection."""
        parser = RequirementsParser("oregon")

        assert parser._is_field_required(["ID", "Integer", "Required"]) is True
        assert parser._is_field_required(["Name", "Text", "Mandatory"]) is True
        assert parser._is_field_required(["Notes", "Text", "Optional"]) is False
        assert parser._is_field_required(["Value", "Must be provided"]) is True

    def test_extract_allowed_values(self):
        """Test allowed values extraction."""
        parser = RequirementsParser("oregon")

        # Test with explicit values list
        row = ["Status", "Text", "Values: Active, Inactive, Pending"]
        values = parser._extract_allowed_values(row)
        assert values == ["Active", "Inactive", "Pending"]

        # Test with options
        row = ["Type", "Options: A; B; C"]
        values = parser._extract_allowed_values(row)
        assert values == ["A", "B", "C"]

        # Test with no values
        row = ["Field", "Text"]
        values = parser._extract_allowed_values(row)
        assert values == []

    def test_classify_rule(self):
        """Test rule classification."""
        parser = RequirementsParser("oregon")

        assert parser._classify_rule("Format must be YYYY-MM-DD") == "format"
        assert parser._classify_rule("Field is required") == "required"
        assert parser._classify_rule("Maximum length is 50") == "constraint"
        assert parser._classify_rule("Valid values are A, B, C") == "allowed_values"
        assert parser._classify_rule("Provider must exist") == "business"

    def test_save_requirements(self, temp_dir: Path):
        """Test saving requirements to file."""
        parser = RequirementsParser("oregon", output_dir=temp_dir)

        requirements = {
            "source_file": "test.pdf",
            "sheets": {"Sheet1": {"required": True}},
            "fields": {"Sheet1": [{"name": "ID", "type": "text"}]},
        }

        # Save with auto-generated filename
        output_path = parser.save_requirements(requirements)
        assert output_path.exists()
        assert output_path.suffix == ".json"

        # Verify content
        with open(output_path) as f:
            saved_data = json.load(f)
        assert saved_data == requirements

        # Save with specific filename
        custom_path = parser.save_requirements(requirements, "custom.json")
        assert custom_path.name == "custom.json"

    def test_generate_validation_rules_from_excel(self):
        """Test validation rule generation from Excel structure."""
        parser = RequirementsParser("oregon")

        requirements = {
            "sheets": {"Sheet1": {"columns": ["ID", "Name"]}, "Sheet2": {"columns": ["RefID", "Value"]}},
            "fields": {
                "Sheet1": [{"name": "ID", "data_type": "text"}, {"name": "Name", "data_type": "text"}],
                "Sheet2": [{"name": "RefID", "data_type": "text"}, {"name": "Value", "data_type": "numeric"}],
            },
            "data_validations": {"Sheet1": [{"type": "list", "ranges": "C:C", "allowed_values": ["A", "B", "C"]}]},
        }

        rules = parser._generate_validation_rules_from_excel(requirements)

        # Check generated rules
        assert any(r["rule"] == "required_sheets" for r in rules)
        assert any(r["rule"] == "required_field" and r["field"] == "ID" for r in rules)
        assert any(r["rule"] == "field_type" and r["expected_type"] == "numeric" for r in rules)
        assert any(r["rule"] == "list" for r in rules)

    @patch("pdfplumber.open")
    def test_parse_pdf_basic(self, mock_pdf_open, temp_dir: Path):
        """Test basic PDF parsing."""
        parser = RequirementsParser("oregon")

        # Mock PDF content
        mock_page = Mock()
        mock_page.extract_text.return_value = """
        Sheet: Provider Information
        This sheet must contain provider details.

        Field Definitions:
        Provider ID - Text, Required
        NPI - 10 digit number, Required

        Business Rule #1: NPI must be exactly 10 digits
        """
        mock_page.extract_tables.return_value = []

        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        mock_pdf_open.return_value = mock_pdf

        # Parse PDF
        pdf_file = temp_dir / "test.pdf"
        pdf_file.touch()  # Create empty file

        requirements = parser.parse_document(pdf_file)

        # Verify extraction
        assert requirements["file_type"] == "pdf"
        assert "Provider Information" in requirements["sheets"]
        assert len(requirements["business_rules"]) > 0
        assert any("10 digits" in rule["text"] for rule in requirements["business_rules"])

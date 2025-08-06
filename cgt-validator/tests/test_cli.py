"""Tests for CLI interface."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from src.cli import batch_validate, get_validator, validate


class TestCLI:
    """Test command-line interface."""

    def test_validate_command_valid_file(self, valid_oregon_excel: Path):
        """Test validate command with valid file."""
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon", "--file", str(valid_oregon_excel)])

        # Print output for debugging
        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            if result.exception:
                print(f"Exception: {result.exception}")

        assert result.exit_code == 0
        assert "Validating" in result.output

    def test_validate_command_invalid_file(self, invalid_oregon_excel: Path):
        """Test validate command with invalid file."""
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon", "--file", str(invalid_oregon_excel)])

        assert result.exit_code == 1
        assert "FAILED" in result.output
        assert "Errors:" in result.output

    def test_validate_missing_file_argument(self):
        """Test validate command without file argument."""
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon"])

        assert result.exit_code == 2  # Click returns 2 for missing required options
        assert "Missing option" in result.output or "required" in result.output

    def test_validate_nonexistent_file(self):
        """Test validate command with non-existent file."""
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon", "--file", "/non/existent/file.xlsx"])

        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_validate_unsupported_state(self, valid_oregon_excel: Path):
        """Test validate command with unsupported state."""
        runner = CliRunner()
        result = runner.invoke(validate, ["alaska", "--file", str(valid_oregon_excel)])

        assert result.exit_code == 1
        assert "No validator available for state 'alaska'" in result.output

    def test_validate_with_year(self, valid_oregon_excel: Path):
        """Test validate command with specific year."""
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon", "--file", str(valid_oregon_excel), "--year", "2025"])

        assert result.exit_code == 0
        assert "2025" in result.output

    def test_validate_html_output(self, valid_oregon_excel: Path, temp_dir: Path):
        """Test validate command with HTML output."""
        output_path = temp_dir / "report.html"
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon", "--file", str(valid_oregon_excel), "--output", str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()
        assert "Report saved to:" in result.output

        # Check HTML content
        html = output_path.read_text()
        assert "<!DOCTYPE html>" in html
        assert "CGT Validation Report" in html

    def test_validate_markdown_output(self, valid_oregon_excel: Path, temp_dir: Path):
        """Test validate command with Markdown output."""
        output_path = temp_dir / "report.md"
        runner = CliRunner()
        result = runner.invoke(
            validate,
            ["oregon", "--file", str(valid_oregon_excel), "--output", str(output_path), "--format", "markdown"],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        # Check Markdown content
        markdown = output_path.read_text()
        assert "# CGT Validation Report" in markdown

    def test_validate_json_output(self, valid_oregon_excel: Path, temp_dir: Path):
        """Test validate command with JSON output."""
        output_path = temp_dir / "report.json"
        runner = CliRunner()
        result = runner.invoke(
            validate, ["oregon", "--file", str(valid_oregon_excel), "--output", str(output_path), "--format", "json"]
        )

        assert result.exit_code == 0
        assert output_path.exists()

        # Check JSON content
        data = json.loads(output_path.read_text())
        assert "summary" in data
        assert "errors" in data
        assert "warnings" in data
        assert "info" in data

    def test_validate_quiet_mode(self, valid_oregon_excel: Path):
        """Test validate command in quiet mode."""
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon", "--file", str(valid_oregon_excel), "--quiet"])

        assert result.exit_code == 0
        # In quiet mode, should have minimal output
        assert len(result.output.strip()) == 0 or "Validation failed" not in result.output

    def test_validate_quiet_mode_with_errors(self, invalid_oregon_excel: Path):
        """Test validate command in quiet mode with errors."""
        runner = CliRunner()
        result = runner.invoke(validate, ["oregon", "--file", str(invalid_oregon_excel), "--quiet"])

        assert result.exit_code == 1
        # Should still show error count in quiet mode
        assert "Validation failed" in result.output
        assert "errors" in result.output

    def test_batch_validate_command(self, temp_dir: Path, mock_oregon_data):
        """Test batch validate command."""
        # Create multiple files
        file1 = temp_dir / "submission1.xlsx"
        file2 = temp_dir / "submission2.xlsx"
        mock_oregon_data.save_to_excel(str(file1))
        mock_oregon_data.save_to_excel(str(file2))

        runner = CliRunner()
        result = runner.invoke(batch_validate, ["oregon", "--directory", str(temp_dir), "--pattern", "*.xlsx"])

        assert result.exit_code == 0
        assert "Found 2 files to validate" in result.output
        assert "BATCH VALIDATION SUMMARY" in result.output
        assert "submission1.xlsx" in result.output
        assert "submission2.xlsx" in result.output

    def test_batch_validate_with_output(self, temp_dir: Path, mock_oregon_data):
        """Test batch validate with output directory."""
        # Create test file
        file1 = temp_dir / "submission.xlsx"
        mock_oregon_data.save_to_excel(str(file1))

        # Create output directory
        output_dir = temp_dir / "reports"
        output_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(batch_validate, ["oregon", "--directory", str(temp_dir), "--output-dir", str(output_dir)])

        assert result.exit_code == 0
        # Check report was created
        report_files = list(output_dir.glob("*.html"))
        assert len(report_files) == 1

    def test_batch_validate_no_files(self, temp_dir: Path):
        """Test batch validate with no matching files."""
        runner = CliRunner()
        result = runner.invoke(batch_validate, ["oregon", "--directory", str(temp_dir), "--pattern", "*.xlsx"])

        assert result.exit_code == 1
        assert "No files matching pattern" in result.output

    def test_get_validator(self):
        """Test get_validator function."""
        # Valid state
        validator = get_validator("oregon")
        assert validator.state == "oregon"

        # With year
        validator = get_validator("oregon", 2025)
        assert validator.year == 2025

        # Invalid state
        with pytest.raises(ValueError) as exc_info:
            get_validator("invalid_state")
        assert "No validator available" in str(exc_info.value)

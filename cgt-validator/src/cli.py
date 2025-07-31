"""Command-line interface for CGT Validator."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from colorama import Fore, Style, init
from tabulate import tabulate

from reporters.excel_annotator import ExcelAnnotator
from reporters.html_reporter import HTMLReporter
from reporters.markdown_reporter import MarkdownReporter
from reporters.validation_results import ValidationResults
from validators.base_validator import ValidatorBase
from validators.oregon import OregonValidator

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Map of state names to validator classes
VALIDATORS = {
    "oregon": OregonValidator,
    # Add other states as implemented
    # "massachusetts": MassachusettsValidator,
    # "rhode_island": RhodeIslandValidator,
    # etc.
}


def get_validator(state: str, year: Optional[int] = None) -> ValidatorBase:
    """Get the appropriate validator for a state."""
    state_lower = state.lower().replace(" ", "_")

    if state_lower not in VALIDATORS:
        available = ", ".join(VALIDATORS.keys())
        raise ValueError(f"No validator available for state '{state}'. Available states: {available}")

    validator_class = VALIDATORS[state_lower]
    return validator_class(year=year)


def print_validation_summary(results: ValidationResults):
    """Print a colored summary of validation results."""
    summary = results.get_summary()

    # Header
    print("\n" + "=" * 60)
    print(f"VALIDATION SUMMARY - {results.state.upper()} ({results.year})")
    print("=" * 60)

    # Status
    if results.is_valid():
        status_color = Fore.GREEN
        status_text = "✓ PASSED"
    else:
        status_color = Fore.RED
        status_text = "✗ FAILED"

    print(f"\nStatus: {status_color}{status_text}{Style.RESET_ALL}")

    # Counts
    print("\nIssue Summary:")
    print(f"  Errors:   {Fore.RED if summary['error_count'] > 0 else ''}{summary['error_count']}{Style.RESET_ALL}")
    print(
        f"  Warnings: {Fore.YELLOW if summary['warning_count'] > 0 else ''}{summary['warning_count']}{Style.RESET_ALL}"
    )
    print(f"  Info:     {Fore.BLUE}{summary['info_count']}{Style.RESET_ALL}")

    print(f"\nValidation completed in {summary['duration_seconds']:.2f} seconds")

    # Detailed issues
    if results.errors:
        print(f"\n{Fore.RED}ERRORS:{Style.RESET_ALL}")
        for i, error in enumerate(results.errors[:10], 1):
            print(f"  {i}. [{error.code}] {error.message}")
            print(f"     Location: {error.location}")
        if len(results.errors) > 10:
            print(f"  ... and {len(results.errors) - 10} more errors")

    if results.warnings:
        print(f"\n{Fore.YELLOW}WARNINGS:{Style.RESET_ALL}")
        for i, warning in enumerate(results.warnings[:5], 1):
            print(f"  {i}. [{warning.code}] {warning.message}")
            print(f"     Location: {warning.location}")
        if len(results.warnings) > 5:
            print(f"  ... and {len(results.warnings) - 5} more warnings")


def save_report(results: ValidationResults, output_path: str, report_format: str):
    """Save validation report to file."""
    output_file = Path(output_path)

    if report_format == "html":
        reporter = HTMLReporter()
        content = reporter.generate_report(results)
    elif report_format == "markdown":
        md_reporter = MarkdownReporter()
        content = md_reporter.generate_report(results)
    elif report_format == "json":
        content = json.dumps(results.to_dict(), indent=2)
    else:
        raise ValueError(f"Unknown format: {report_format}")

    output_file.write_text(content, encoding="utf-8")
    print(f"\n{Fore.GREEN}✓{Style.RESET_ALL} Report saved to: {output_file}")


@click.command()
@click.argument("state")
@click.option("--file", "-f", required=True, help="Path to Excel file to validate")
@click.option("--year", "-y", type=int, help="Validation year (default: current year)")
@click.option("--output", "-o", help="Output report path")
@click.option(
    "--format", "report_format", type=click.Choice(["html", "markdown", "json"]), default="html", help="Report format"
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode - only show summary")
@click.option("--annotate", "-a", is_flag=True, help="Create annotated Excel file with errors highlighted")
def validate(state, file, year, output, report_format, verbose, quiet, annotate):  # pylint: disable=unused-argument
    """Validate CGT submission file for specified state.

    Examples:
        cgt-validate oregon --file submission.xlsx
        cgt-validate oregon --file submission.xlsx --output report.html
        cgt-validate oregon --file submission.xlsx --year 2025 --format markdown
    """

    # Check if file exists
    file_path = Path(file)
    if not file_path.exists():
        click.echo(f"{Fore.RED}Error:{Style.RESET_ALL} File not found: {file}")
        sys.exit(1)

    # Get validator
    try:
        validator = get_validator(state, year)
    except ValueError as e:
        click.echo(f"{Fore.RED}Error:{Style.RESET_ALL} {e}")
        sys.exit(1)

    # Run validation
    if not quiet:
        click.echo(f"Validating {file} against {state} requirements...")

    results = validator.validate_file(file)

    # Show results
    if not quiet:
        print_validation_summary(results)
    elif not results.is_valid():
        # In quiet mode, still show errors
        click.echo(f"{Fore.RED}Validation failed with {len(results.errors)} errors{Style.RESET_ALL}")

    # Generate report if requested
    if output:
        save_report(results, output, report_format)

    # Create annotated Excel if requested
    if annotate:
        annotator = ExcelAnnotator()
        annotated_path = annotator.annotate_file(file, results)
        if not quiet:
            click.echo(f"\n{Fore.GREEN}✓{Style.RESET_ALL} Annotated Excel saved to: {annotated_path}")
            click.echo(f"  {annotator.get_annotations_count()} annotations added")

    # Exit with appropriate code
    sys.exit(0 if results.is_valid() else 1)


@click.command()
@click.argument("state")
@click.option("--directory", "-d", required=True, help="Directory containing Excel files")
@click.option("--pattern", "-p", default="*.xlsx", help="File pattern to match")
@click.option("--year", "-y", type=int, help="Validation year")
@click.option("--output-dir", "-o", help="Directory for output reports")
@click.option("--format", "report_format", type=click.Choice(["html", "markdown", "json"]), default="html")
def batch_validate(state, directory, pattern, year, output_dir, report_format):
    """Validate multiple CGT files in a directory."""

    dir_path = Path(directory)
    if not dir_path.exists():
        click.echo(f"{Fore.RED}Error:{Style.RESET_ALL} Directory not found: {directory}")
        sys.exit(1)

    # Find files
    files = list(dir_path.glob(pattern))
    if not files:
        click.echo(f"No files matching pattern '{pattern}' found in {directory}")
        sys.exit(1)

    click.echo(f"Found {len(files)} files to validate")

    # Get validator
    try:
        validator = get_validator(state, year)
    except ValueError as e:
        click.echo(f"{Fore.RED}Error:{Style.RESET_ALL} {e}")
        sys.exit(1)

    # Process each file
    results_summary = []
    for file_path in files:
        click.echo(f"\nValidating: {file_path.name}")
        results = validator.validate_file(str(file_path))

        summary = results.get_summary()
        results_summary.append(
            {
                "File": file_path.name,
                "Status": "PASSED" if results.is_valid() else "FAILED",
                "Errors": summary["error_count"],
                "Warnings": summary["warning_count"],
                "Info": summary["info_count"],
            }
        )

        # Save report if output directory specified
        if output_dir:
            output_path = Path(output_dir) / f"{file_path.stem}_report.{report_format}"
            save_report(results, str(output_path), report_format)

    # Print summary table
    print("\n" + "=" * 60)
    print("BATCH VALIDATION SUMMARY")
    print("=" * 60)
    print(tabulate(results_summary, headers="keys", tablefmt="grid"))

    # Exit code based on overall results
    failed_count = sum(1 for r in results_summary if r["Status"] == "FAILED")
    sys.exit(0 if failed_count == 0 else 1)


@click.group()
def cli():
    """CGT Validator - Health cost growth target data validation tool."""


# Add commands to group
cli.add_command(validate)
cli.add_command(batch_validate, name="batch")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()

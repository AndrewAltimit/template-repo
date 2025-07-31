# Multi-State CGT Data Validation & Reporting Automation

You are an expert coding agent tasked with automating health cost growth target (CGT) data validation and reporting for multiple US states. Use the requirements, templates, validation rules, and references provided below to build a robust, extensible solution.

## Phase 1: Data Scraping and Requirements Building

### 1.1 URL Categorization
For each state listed below, create and maintain two distinct lists:

**List A - Direct Template URLs:**
- URLs that directly link to downloadable requirements templates (PDF, XLSX, XLSM, etc.)
- These are files that can be downloaded immediately without navigation
- Include file type, version number, and last modified date where available

**List B - Index/Portal URLs:**
- URLs for web pages that need to be scraped to find the latest templates
- Program main pages, data submission portals, and publication hubs
- Pages that contain links to multiple documents or versions

### 1.2 Scraping Process
1. **For List B URLs:**
   - Build a web scraper that navigates to each portal/index page
   - Search for keywords: "template", "manual", "specification", "submission", "data dictionary", "requirements", current year (2024/2025)
   - Extract all document links with metadata (title, date, version)
   - Identify the most recent versions based on:
     - Explicit version numbers
     - Publication dates
     - Filename patterns (e.g., "2025", "v5.0")
   - Download and cache the latest documents

2. **For List A URLs:**
   - Implement version checking to detect when documents are updated
   - Compare checksums/file sizes to identify changes
   - Maintain a changelog of document updates

3. **Document Storage:**
   - Create a structured directory: `/states/{state_name}/{year}/{document_type}/`
   - Include metadata files tracking version history and source URLs
   - Implement automatic archiving of previous versions

### 1.3 Requirements Extraction
For each downloaded document:
1. Extract and parse:
   - Sheet/tab names and structures
   - Field definitions and data dictionaries
   - Validation rules and business logic
   - Cross-reference requirements
   - Submission deadlines and periods

2. Convert requirements into structured JSON/YAML format for programmatic use

3. Generate a requirements summary report for each state

## Phase 2: Mock Data Generation and Validation

### Objectives

1. For each state, using the scraped and parsed requirements from Phase 1, generate a mock CGT submission Excel file that strictly conforms to its specific format, required tabs, field-level rules, and business logic.

2. Write Python validation scripts for each state that check data against all requirements, including:
   - Sheet/tab names and structure
   - Mandatory fields and allowed values (with explicit data dictionary)
   - Data types and constraints
   - Cross-tab logic and reconciliation
   - Edge cases (missing fields, invalid values, negative numbers, duplicate rows, etc.)
   - Behavioral health categorization using taxonomy codes
   - Attribution methodology and consistency
   - Version control, documentation, and changelog requirements
   - Compliance with all referenced regulations and manuals

3. Design the validation system for easy local usage:
   - Simple command-line interface for end users
   - Clear file path configuration
   - Minimal dependencies and easy installation
   - No requirement for technical expertise to run validations

4. Integrate these validation scripts into a CI/CD pipeline (e.g., GitHub Actions) for automated testing, while maintaining local usability.

5. Produce a summary report for each state, showing pass/fail results for each validation rule, with severity levels and remediation guidance, output as markdown or HTML.

6. Ensure the solution is modular and extensible, so new states or updated requirements can be added easily.

## Phase 3: End User Implementation

### Local Validation Setup

1. **Simple Installation Process:**
   ```bash
   # One-command installation
   pip install cgt-validator
   # OR
   python setup.py install
   ```

2. **User-Friendly Command Line Interface:**
   ```bash
   # Validate a single file
   cgt-validate oregon --file /path/to/my/submission.xlsx

   # Validate with specific year's requirements
   cgt-validate oregon --file /path/to/my/submission.xlsx --year 2025

   # Validate multiple files
   cgt-validate oregon --directory /path/to/submissions/

   # Generate validation report
   cgt-validate oregon --file /path/to/my/submission.xlsx --output report.html
   ```

3. **Configuration File for Easy Customization:**
   ```yaml
   # config.yml
   validation_settings:
     oregon:
       input_file: "~/Documents/CGT_Submissions/oregon_2025.xlsx"
       output_directory: "~/Documents/CGT_Reports/"
       severity_threshold: "warning"  # ignore info-level issues
   ```

4. **Batch Processing Script:**
   ```bash
   # validate_all.sh - for organizations with multiple files
   #!/bin/bash
   for file in ./submissions/*.xlsx; do
     cgt-validate oregon --file "$file" --output "./reports/$(basename $file .xlsx)_report.html"
   done
   ```

### User Documentation

1. **Quick Start Guide:**
   - Installation instructions (Windows, Mac, Linux)
   - How to validate your first file
   - Understanding the validation report
   - Common errors and fixes

2. **File Preparation Checklist:**
   - Required file format (Excel .xlsx)
   - Naming conventions
   - Pre-validation checks users can do
   - Template comparison tool

3. **Validation Report Guide:**
   - How to read severity levels (Error, Warning, Info)
   - Understanding error codes
   - Step-by-step remediation instructions
   - Links to relevant documentation sections

## Technical Implementation Details

### Project Structure
```
cgt-validator/
├── src/
│   ├── validators/
│   │   ├── base_validator.py
│   │   ├── oregon.py
│   │   ├── massachusetts.py
│   │   └── ...
│   ├── scrapers/
│   ├── parsers/
│   ├── reporters/
│   └── cli.py
├── mock_data/
│   ├── oregon/
│   │   └── mock_submission_2025.xlsx
│   └── ...
├── requirements/
│   ├── oregon/
│   │   ├── requirements_2025.json
│   │   └── validation_rules.yaml
│   └── ...
├── tests/
├── docs/
│   ├── user_guide.md
│   ├── installation.md
│   └── troubleshooting.md
├── setup.py
├── requirements.txt
└── README.md
```

### Validation Engine Architecture
```python
# Example validator base class
class BaseValidator:
    def __init__(self, state, year=None):
        self.state = state
        self.year = year or datetime.now().year
        self.requirements = self.load_requirements()

    def validate_file(self, filepath):
        """Main validation entry point for end users"""
        results = ValidationResults()

        # Check file exists and is readable
        if not self.check_file_access(filepath):
            return results.add_error("FILE_ACCESS", "Cannot read file")

        # Load Excel file
        workbook = self.load_workbook(filepath)

        # Run all validations
        results.merge(self.validate_structure(workbook))
        results.merge(self.validate_data_types(workbook))
        results.merge(self.validate_business_rules(workbook))
        results.merge(self.validate_cross_references(workbook))

        return results
```

### CLI Implementation
```python
# cli.py - User-friendly command line interface
import click
import sys
from pathlib import Path

@click.command()
@click.argument('state')
@click.option('--file', '-f', help='Path to Excel file to validate')
@click.option('--year', '-y', type=int, help='Validation year (default: current)')
@click.option('--output', '-o', help='Output report path')
@click.option('--format', type=click.Choice(['html', 'markdown', 'json']), default='html')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def validate(state, file, year, output, format, verbose):
    """Validate CGT submission file for specified state"""

    # User-friendly error handling
    if not file:
        click.echo("Error: Please specify a file to validate using --file")
        click.echo("Example: cgt-validate oregon --file ./my_submission.xlsx")
        sys.exit(1)

    # Check if file exists
    if not Path(file).exists():
        click.echo(f"Error: File not found: {file}")
        sys.exit(1)

    # Run validation
    click.echo(f"Validating {file} against {state} requirements...")
    validator = get_validator(state, year)
    results = validator.validate_file(file)

    # Generate report
    report = generate_report(results, format)

    if output:
        save_report(report, output)
        click.echo(f"✓ Report saved to: {output}")
    else:
        click.echo(report)

    # Exit with appropriate code
    sys.exit(0 if results.is_valid() else 1)
```

### Web Scraping Requirements
- Use Python with BeautifulSoup/Scrapy for web scraping
- Implement rate limiting and respectful crawling
- Handle authentication if required (some states may have password-protected portals)
- Create a scheduling system to check for updates (weekly/monthly)
- Log all scraping activities and document changes

### Data Structure
```python
state_config = {
    "state_name": {
        "direct_urls": [
            {
                "url": "https://...",
                "type": "xlsx",
                "description": "CGT-2 Template",
                "version": "5.0",
                "last_checked": "2024-01-15"
            }
        ],
        "index_urls": [
            {
                "url": "https://...",
                "scan_pattern": "regex_pattern",
                "keywords": ["template", "manual"],
                "last_scraped": "2024-01-15"
            }
        ],
        "requirements": {
            # Parsed requirements in structured format
        }
    }
}
```

## Deliverables

1. **Scraping Module:**
   - URL categorization configuration file
   - Web scraping scripts with scheduling
   - Document version tracking system
   - Requirements parser and converter

2. **Validation Module:**
   - Python package with simple installation (`pip install cgt-validator`)
   - State-specific validation rules engine
   - Cross-state common validation library
   - Mock data generator for testing

3. **User Interface:**
   - Command-line tool for local validation
   - Batch processing scripts
   - Configuration templates
   - Progress indicators and clear error messages

4. **CI/CD Integration:**
   - GitHub Actions workflows for automated validation
   - Automated scraping and update detection workflows
   - Notification system for requirement changes
   - Integration tests using mock data

5. **Reporting:**
   - HTML reports with interactive error navigation
   - Markdown reports for documentation
   - JSON output for programmatic use
   - Excel error annotation (highlights problematic cells)

6. **Documentation:**
   - **For End Users:**
     - 5-minute quick start guide
     - Video tutorials for common tasks
     - FAQ and troubleshooting guide
     - Example files and common patterns
   - **For Developers:**
     - How to add new states
     - How to update URL lists
     - How to modify validation logic
     - API documentation

7. **Distribution:**
   - Python package on PyPI
   - Standalone executables for Windows/Mac (using PyInstaller)
   - Docker container for consistent environment
   - GitHub releases with changelogs

## Example Usage Scenarios

### Scenario 1: Health Plan Analyst
```bash
# Install once
pip install cgt-validator

# Validate monthly submission
cgt-validate oregon --file "Q1_2025_Submission.xlsx" --output "validation_report.html"

# Fix errors and re-validate
cgt-validate oregon --file "Q1_2025_Submission_v2.xlsx" --output "validation_report_v2.html"
```

### Scenario 2: Quality Assurance Team
```bash
# Validate all files in a directory
for file in ./submissions/*.xlsx; do
    cgt-validate oregon --file "$file" --output "./reports/$(basename $file .xlsx).html"
done

# Generate summary report
cgt-summary ./reports/ --output "qa_summary.html"
```

### Scenario 3: Automated Pipeline
```python
# Python script for integration
from cgt_validator import OregonValidator

validator = OregonValidator(year=2025)
results = validator.validate_file("submission.xlsx")

if not results.is_valid():
    print(f"Found {len(results.errors)} errors")
    for error in results.errors:
        print(f"- {error.code}: {error.message} at {error.location}")
```

## States and Reference URLs

### URL Categorization by State

## 1. Oregon
**List A - Direct Template URLs:**
- CGT-2 Data Specification Manual (v5.0): https://www.oregon.gov/oha/HPA/HP/Cost%20Growth%20Target%20documents/CGT-2-Data-Specification-Manual.pdf
- 2024 Data Submission Training: https://www.oregon.gov/oha/HPA/HP/Cost%20Growth%20Target%20documents/CGT-2024-data-submission-training.pdf

**List B - Index/Portal URLs:**
- Cost Growth Target Main Page: https://www.oregon.gov/oha/HPA/HP/Pages/Sustainable-Health-Care-Cost-Growth-Target.aspx
- Data Submission Page: https://www.oregon.gov/oha/HPA/HP/Pages/cost-growth-target-data.aspx
- Reports Page: https://www.oregon.gov/oha/hpa/hp/pages/cost-growth-target-reports.aspx

## 2. Massachusetts
**List A - Direct Template URLs:**
- 2024 Annual Report: https://masshpc.gov/publications/cost-trends-report/2024-annual-health-care-cost-trends-report

**List B - Index/Portal URLs:**
- HPC Cost Growth Benchmark: https://masshpc.gov/cost-containment/benchmark
- APCD Data Submission Guides: https://www.chiamass.gov/apcd-data-submission-guides
- APCD Information for Submitters: https://www.chiamass.gov/apcd-information-for-data-submitters/

## 3. Rhode Island
**List A - Direct Template URLs:**
- 2024 Annual Report: https://ohic.ri.gov/sites/g/files/xkgbur736/files/2024-05/OHIC%20Cost%20Trends%20Report_20240513%20FINAL.pdf

**List B - Index/Portal URLs:**
- Health Spending Accountability Main Page: https://ohic.ri.gov/policy-reform/health-spending-accountability-and-transparency-program
- Cost Growth Target Page: https://ohic.ri.gov/policy-reform/health-spending-accountability-and-transparency-program/cost-growth-target
- Additional Reports: https://ohic.ri.gov/data-reports/ohic-additional-data-and-reports

## 4. Washington
**List A - Direct Template URLs:**
- (To be identified through scraping)

**List B - Index/Portal URLs:**
- Health Care Cost Transparency Board: https://www.hca.wa.gov/about-hca/who-we-are/health-care-cost-transparency-board
- Call for Benchmark Data: https://www.hca.wa.gov/about-hca/call-benchmark-data
- Data and Reports: https://www.hca.wa.gov/about-hca/data-and-reports

## 5. Delaware
**List A - Direct Template URLs:**
- Regulation 1322: https://regulations.delaware.gov/register/january2022/proposed/25%20DE%20Reg%20684%2001-01-22.htm

**List B - Index/Portal URLs:**
- OVBHCD Main Page: https://insurance.delaware.gov/divisions/consumerhp/ovbhcd/
- (Note: Direct links to 2025 Manual and Template need to be scraped from main page)

## 6. Connecticut
**List A - Direct Template URLs:**
- Implementation Manual: https://portal.ct.gov/ohs/pages/guidance-for-payer-and-provider-groups/cost-growth-benchmark-implementation-manual

**List B - Index/Portal URLs:**
- Healthcare Benchmark Initiative: https://portal.ct.gov/ohs/programs-and-initiatives/healthcare-benchmark-initiative
- Cost Growth Benchmark Main Page: https://portal.ct.gov/OHS/Content/Cost-Growth-Benchmark
- Press Releases: https://portal.ct.gov/ohs/press-room/press-releases/2024-press-releases

## 7. Vermont
**List A - Direct Template URLs:**
- (To be identified through scraping)

**List B - Index/Portal URLs:**
- GMCB Main Site: https://gmcboard.vermont.gov/
- Data and Analytics: https://gmcboard.vermont.gov/data-and-analytics
- Legislative Reports: https://gmcboard.vermont.gov/publications/legislative-reports
- APM Reports: https://gmcboard.vermont.gov/payment-reform/APM/reports-and-federal-communications

## 8. Colorado
**List A - Direct Template URLs:**
- (To be identified through scraping - e.g., DSG v13.pdf, 2024-25 Hospital Discounted Care Data Template)

**List B - Index/Portal URLs:**
- Hospital Discounted Care: https://hcpf.colorado.gov/hospital-discounted-care
- Hospital Financial Transparency: https://hcpf.colorado.gov/hospital-financial-transparency
- Publications Hub: https://hcpf.colorado.gov/publications
- Provider Rates and Fee Schedule: https://hcpf.colorado.gov/provider-rates-fee-schedule

## Notes

- Many states update their data submission templates and manuals annually, typically releasing new versions between April and July
- Direct PDF links may change when documents are updated; always verify through main program pages
- Some states may require authentication or registration to access templates
- If a state does not have a public CGT template, use the closest available financial reporting template and document assumptions
- All code should be well-documented, modular, and maintainable
- Reports and templates should be accessible and colorblind-friendly
- Mock data must not contain real provider names or PHI

# CGT Validator - Standalone Project

This directory contains the complete CGT (Cost Growth Target) Validator project, which is designed to be easily extracted into its own repository.

## Project Structure

All project files are self-contained within this directory:
- Source code in `src/`
- Tests in `tests/`
- Documentation in `docs/`
- CI/CD workflows in `.github/workflows/`
- All dependencies in `requirements-cgt.txt`

## Setup Instructions

### 1. Install Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all CGT validator dependencies
pip install -r requirements-cgt.txt

# Install the package in development mode
pip install -e .
```

### 2. Run the Demo

```bash
python test_oregon.py
```

### 3. Use the CLI

```bash
# Basic validation
cgt-validate oregon --file submission.xlsx

# With HTML report
cgt-validate oregon --file submission.xlsx --output report.html

# With Excel annotation
cgt-validate oregon --file submission.xlsx --annotate
```

## Moving to Its Own Repository

When ready to extract this project:

1. Copy the entire `cgt-validator/` directory to a new location
2. Initialize a new git repository
3. The project is already structured with its own:
   - Requirements file (`requirements-cgt.txt`)
   - Setup.py for pip installation
   - GitHub Actions workflows
   - Complete documentation

## Dependencies

All dependencies are listed in `requirements-cgt.txt`:
- Core: pandas, openpyxl, click
- Web scraping: beautifulsoup4, requests
- PDF parsing: pdfplumber, PyPDF2
- Testing: pytest, pytest-cov
- And more...

## Key Features

- ✅ Validates Oregon CGT submissions (other states pending)
- ✅ Multiple output formats (HTML, Markdown, JSON, Excel annotation)
- ✅ Automated web scraping for requirements updates
- ✅ Comprehensive test suite
- ✅ CI/CD ready

## Notes

- The project is currently integrated within a larger repository but is designed for easy extraction
- All file paths and imports are relative to the CGT validator root
- No dependencies on the parent repository

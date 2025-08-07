# CGT Validator User Guide

## Quick Start

### Installation

```bash
pip install cgt-validator
```

Or install from source:

```bash
git clone https://github.com/your-org/cgt-validator.git
cd cgt-validator
pip install -e .
```

### Basic Usage

#### Validate a single file:

```bash
cgt-validate oregon --file submission.xlsx
```

#### Generate an HTML report:

```bash
cgt-validate oregon --file submission.xlsx --output report.html
```

#### Validate with specific year requirements:

```bash
cgt-validate oregon --file submission.xlsx --year 2025
```

### Understanding Validation Results

The validator checks your submission against state-specific requirements including:

- **Structure validation**: Required sheets and columns
- **Data type validation**: Numeric, date, and text field formats
- **Business rules**: State-specific requirements (e.g., NPI format, ZIP codes)
- **Cross-references**: Provider IDs, reconciliation totals
- **Mandatory fields**: Required data that cannot be empty

### Error Severity Levels

- **🔴 Errors**: Must be fixed before submission
- **🟡 Warnings**: Should be reviewed but may be acceptable
- **🔵 Info**: Informational messages for your awareness

### Common Issues and Fixes

#### Missing Required Sheet
**Error**: `MISSING_SHEET: Required sheet 'Provider Information' not found`

**Fix**: Ensure your Excel file contains all required sheets with exact names (case-sensitive).

#### Invalid Data Type
**Error**: `INVALID_DATA_TYPE: Column 'Member Months' expects numeric`

**Fix**: Check that numeric columns don't contain text or special characters.

#### Invalid NPI Format
**Error**: `INVALID_NPI: NPI must be 10 digits`

**Fix**: NPIs should be exactly 10 digits with no spaces or dashes.

#### Paid Exceeds Allowed
**Error**: `PAID_EXCEEDS_ALLOWED: Paid amount exceeds allowed amount`

**Fix**: Ensure paid amounts are less than or equal to allowed amounts.

### Batch Validation

Validate multiple files at once:

```bash
cgt-validate batch oregon --directory ./submissions/ --output-dir ./reports/
```

### Configuration Options

Create a `config.yml` file for repeated use:

```yaml
validation_settings:
  oregon:
    input_file: "~/Documents/CGT_Submissions/oregon_2025.xlsx"
    output_directory: "~/Documents/CGT_Reports/"
    severity_threshold: "warning"
```

### Getting Help

For additional help:
- Run `cgt-validate --help`
- Check the troubleshooting guide
- Submit issues at: https://github.com/your-org/cgt-validator/issues

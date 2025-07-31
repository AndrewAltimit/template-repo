# Troubleshooting Guide

## Common Issues

### Installation Issues

#### Error: `No module named 'openpyxl'`

**Solution**: Install missing dependencies:
```bash
pip install -r requirements.txt
```

#### Error: `cgt-validate: command not found`

**Solution**: Ensure the package is installed properly:
```bash
pip install -e .
# Or add to PATH
export PATH=$PATH:~/.local/bin
```

### File Access Issues

#### Error: `FILE_NOT_FOUND: File not found`

**Solution**:
- Check the file path is correct
- Use absolute paths if relative paths aren't working
- Ensure file extension is .xlsx or .xlsm

#### Error: `INVALID_FILE_TYPE: Invalid file type`

**Solution**:
- Only Excel files (.xlsx, .xlsm) are supported
- Convert .xls files to .xlsx format
- CSV files must be converted to Excel format

### Validation Issues

#### Many errors about missing columns

**Possible causes**:
- Using wrong state validator
- Excel file is for a different year with different requirements
- Column names don't match exactly (check for extra spaces)

**Solution**:
```bash
# Verify state
cgt-validate oregon --file file.xlsx --year 2025

# Check available validators
cgt-validate --help
```

#### Reconciliation errors

**Solution**:
- Ensure totals in Reconciliation sheet match sum of claims
- Check for rounding differences (use 2 decimal places)
- Verify all claims are included in calculations

### Performance Issues

#### Validation is very slow

**Solutions**:
- For large files (>100MB), close other Excel applications
- Use batch mode for multiple files to avoid re-loading validator
- Consider splitting very large files

### Report Generation Issues

#### HTML report won't open

**Solution**:
- Check output path has .html extension
- Ensure write permissions to output directory
- Try markdown format as alternative:
  ```bash
  cgt-validate oregon --file submission.xlsx --format markdown
  ```

## Debug Mode

For detailed error information, use verbose mode:

```bash
cgt-validate oregon --file submission.xlsx --verbose
```

## Getting Additional Help

1. Check error codes in the documentation
2. Review state-specific requirements
3. Submit issues with:
   - Full error message
   - Command used
   - File structure (sheet names)
   - CGT Validator version

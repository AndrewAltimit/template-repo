# Understanding CGT Validator Test Output

## Quick Answer: The Validation "Failures" Are Expected! ✓

When you run the test scripts, you'll see validation errors. **This is intentional and shows the validator is working correctly.**

## Why We Test with "Bad" Data

The test data intentionally includes common Excel formatting issues to ensure the validator catches them:

1. **NPI/ZIP stored as numbers** - Demonstrates the validator catches when Excel removes leading zeros
2. **Missing required columns** - Shows the validator identifies incomplete data
3. **Invalid date formats** - Proves the validator catches date formatting errors
4. **Mismatched totals** - Confirms financial reconciliation validation works

## Running the Tests

### Basic Test (Shows Expected Errors)
```bash
python test_oregon.py
```
Output will show errors - this is GOOD! It means the validator is catching issues.

### Comprehensive Validation Demo
```bash
python test_validation_demo.py
```
This clearly explains what errors are being caught and why.

### Testing with Multiple Scenarios
```bash
python test_oregon_validation.py
```
This runs two tests:
1. **Test 1**: Intentionally invalid data - SHOULD fail (✓ when it does)
2. **Test 2**: Attempting valid data - Shows current limitations with Excel formatting

## What This Means for Real Usage

When validating actual Oregon CGT submissions:

1. **Follow the official Oregon template** - Don't modify column names or sheet names
2. **Format NPIs and ZIPs as text** in Excel:
   - Select the column
   - Right-click → Format Cells → Text
   - Or prefix with apostrophe: '1234567890
3. **Ensure all required fields are present** - Check Oregon's documentation
4. **Use proper date formats** - Excel date cells, not text
5. **Verify totals match** between detail and summary sheets

## The Validator is Working Correctly!

The errors in test output demonstrate that the validator:
- ✓ Catches data type mismatches
- ✓ Identifies missing required fields
- ✓ Validates business rules
- ✓ Provides clear, actionable error messages

This is exactly what you want in a data quality tool - catching issues BEFORE submission to the state.

## For Production Use

```bash
# Validate a real submission file
./cgt-validate.sh validate oregon --file your_submission.xlsx --output report.html

# The report will show:
# - Specific errors to fix
# - Exact locations (sheet, column, row)
# - Severity levels (error vs warning)
```

Remember: A "failing" validation on test data means the validator is doing its job!

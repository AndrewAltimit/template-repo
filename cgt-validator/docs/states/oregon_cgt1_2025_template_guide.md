# Oregon CGT-1 2025 Template Implementation Guide

## Overview
This guide documents the actual structure of Oregon's CGT-1 2025 data submission template based on analysis of reference files. This information is critical for maintaining the Oregon validator.

**Template Version:** 5.0, June 2025
**Last Updated:** 2025-08-05

## Critical Template Structure

### Sheet Order and Names (EXACT names required)
1. `Contents`
2. `1. Cover Page`
3. `2. TME_ALL`
4. `3. TME_PROV`
5. `4. TME_UNATTR`
6. `5. MARKET_ENROLL`
7. `6. RX_MED_PROV`
8. `7. RX_MED_UNATTR`
9. `8. RX_REBATE`
10. `9. PROV_ID`
11. `Line of Business Code` (reference)
12. `Attribution Hierarchy Code` (reference)
13. `Demographic Tables` (reference)
14. `TME Validation` (automated)
15. `RX_MED_PROV Validation` (automated)
16. `RX_MED_UNATTR Validation` (automated)
17. `Provider Check` (automated)

## Row Structure Pattern

### Standard Structure (TME_ALL, TME_UNATTR, MARKET_ENROLL, RX_REBATE):
- **Row 0**: Sheet title
- **Row 1**: "Black = payer-reported data"
- **Row 2**: "Blue = OHA calculated data"
- **Row 3-5**: Additional instructions/validations
- **Row 6-7**: Validation messages (varies by sheet)
- **Row 8**: Field codes (e.g., TMEALL01, TMEALL02)
- **Row 9**: Data types (e.g., "year", "code", "positive integer")
- **Row 10**: Column names
- **Row 11+**: Actual data

### Different Structure (TME_PROV, RX_MED_PROV, RX_MED_UNATTR):
- **Rows 0-9**: Similar header content
- **Row 10**: Field codes (e.g., TMEPRV01, TMEPRV02)
- **Row 11**: Data types
- **Row 12**: Column names
- **Row 13+**: Actual data

**EXCEPTION**: Cover Page has a different structure with sparse layout.

## Sheet-Specific Details

### 1. Cover Page
Special sparse structure with fields at specific cell locations:
- **Payer Name**: Row 4, Column C (index 2)
- **Contact Name**: Row 5, Column C
- **Contact Email**: Row 6, Column C
- **Full Name**: Row 11, Column C
- **Title/Position**: Row 12, Column C
- **Email/Contact Information**: Row 13, Column C
- **Signature**: Row 14, Column C
- **Date**: Row 15, Column C

### 3. TME_PROV (Critical - Most Complex)
**Column Order** (This was a major source of confusion):
1. Reporting Year
2. Line of Business Code
3. Provider Organization Name (**NOT TIN** - Name comes first!)
4. IPA or Contract Name (optional)
5. **Attribution Hierarchy Code** (Often missed!)
6. Member Months
7. Demographic Score
8. Various claim columns...

**Data Types**:
- Provider Organization Name: "free text, blank is not allowed"
- IPA or Contract Name: "free text, blank allowed"
- Attribution Hierarchy Code: "Code"

### 9. PROV_ID (Provider Master List)
**Column Order** (Different from TME_PROV!):
1. Provider Organization Name (field code: PRV01)
2. IPA or Contract Name (If applicable/available) (field code: PRV03)
3. Provider Organization TIN (**TIN is LAST**) (field code: PRV02)

**Field Codes Row**: PRV01, PRV03, PRV02

## Key Validation Rules

### 1. Line of Business Codes
Valid values: 1-7
- 1: Medicare
- 2: Medicaid
- 3: Commercial: Full Claims
- 4: Commercial: Partial Claims
- 5: Medicare Expenses for Medicare/Medicaid Dual Eligible
- 6: Medicaid Expenses for Medicare/Medicaid Dual Eligible
- 7: CCO-F expenses or Medicaid Carve-Outs (TME_ALL only)

### 2. Attribution Hierarchy Codes
Valid values: 1-3
- 1: Tier 1: Member Selection
- 2: Tier 2: Contract Arrangement
- 3: Tier 3: Utilization

### 3. TIN Format
- Must be exactly 9 digits
- Stored as text to preserve leading zeros
- Format: "text, 9 digits including leading zero"

### 4. Member Months Threshold
- TME_PROV rows with ≤ 12 member months should be rolled up to TME_UNATTR
- This generates a warning, not an error

### 5. Duplicate Prevention
- TME_PROV must not have duplicate Year-LOB-Provider-IPA-Attribution combinations
- All costs must be rolled up to a single line at this level
- The IPA/Contract Name is part of the unique key

### 6. Cross-References
- Provider Organization Names in TME_PROV must exist in PROV_ID
- Provider-IPA combinations in TME_PROV must match combinations in PROV_ID
- Match on NAME, not TIN (common mistake!)
- If a provider has an IPA in TME_PROV, that exact Provider-IPA combo must exist in PROV_ID

## Common Implementation Mistakes

### ❌ MISTAKE 1: Wrong Provider Reference Field
**Wrong**: Validating TME_PROV.Provider Organization TIN against PROV_ID.Provider Organization TIN
**Correct**: Validating TME_PROV.Provider Organization Name against PROV_ID.Provider Organization Name

### ❌ MISTAKE 2: Missing Attribution Hierarchy Code
This field is required in TME_PROV but easy to miss because it's between optional fields.

### ❌ MISTAKE 3: Wrong Column Order in PROV_ID
**Wrong**: TIN, Name, IPA
**Correct**: Name, IPA, TIN

### ❌ MISTAKE 4: Wrong Header Row
**Wrong**: Assuming all sheets have the same header structure
**Correct**:
- **Most sheets**: Field codes at row 8, column names at row 10, data at row 11
- **TME_PROV, RX_MED_PROV, RX_MED_UNATTR**: Field codes at row 10, column names at row 12, data at row 13
- **PROV_ID**: Field codes at row 6, column names at row 8, data at row 9

### ❌ MISTAKE 5: Incorrect Data Type Strings
The template uses specific strings for data types:
- "year" (not "integer")
- "code" (not "integer")
- "positive integer" (not "integer")
- "non-negative number" (not "numeric")
- "free text, blank is not allowed" (not just "text")
- "text, 9 digits including leading zero" (very specific!)

## Data Type Mapping

| Template Data Type | Python/Pandas Type | Validation |
|-------------------|-------------------|------------|
| year | int | Valid years: current year or previous year |
| code | int | Must be in allowed values list |
| positive integer | int | > 0 |
| non-negative number | float | >= 0 |
| free text | str | Any string |
| free text, blank is not allowed | str | Non-empty string |
| free text, blank allowed | str | Can be empty |
| text, 9 digits including leading zero | str | Regex: ^\d{9}$ |

## Testing Considerations

### Valid Test Data Should Include:
- Providers with different Attribution Hierarchy Codes
- Some TME_PROV rows with ≤ 12 member months (to test threshold warning)
- Mix of LOB codes 1-6 (avoid 7 in TME_PROV)
- Optional IPA or Contract Names (some blank, some filled)

### Invalid Test Data Should Include:
- Missing required Provider Organization Names in PROV_ID
- Duplicate Year-LOB-Provider-Attribution combinations
- Invalid LOB codes (0, 8, 99)
- Invalid Attribution codes (0, 4, 5)
- TINs with wrong length (<9 or >9 digits)
- Negative member months
- Empty Provider Organization Names in TME_PROV

## File References

### Implementation Files
- Validator: `src/validators/oregon.py`
- Mock Data Generator: `src/mock_data/oregon_generator.py`
- Tests: `tests/validators/test_oregon_validator.py`

### Reference Files
- Success template: `references/CGT-1-Data-Submission- 2025 Template - Mock Success Data.xlsx`
- Fail template: `references/CGT-1-Data-Submission- 2025 Template - Mock Fail Data.xlsx`

### Official URLs
- Data Submission Page: https://www.oregon.gov/oha/HPA/HP/Pages/cost-growth-target-data.aspx
- CGT-2 Specification Manual: https://www.oregon.gov/oha/HPA/HP/Cost%20Growth%20Target%20documents/CGT-2-Data-Specification-Manual.pdf

## Quick Validation Checklist

When implementing or updating the Oregon validator:

- [ ] Check all 9 required sheets are present
- [ ] Verify Cover Page fields at correct row/column positions (including Date field)
- [ ] Parse data using correct header rows (TME_PROV uses header=10, others use header=8)
- [ ] Validate Provider Organization Names (not TINs) for cross-references
- [ ] Validate Provider-IPA combinations match between sheets
- [ ] Include Attribution Hierarchy Code validation
- [ ] Check for duplicate Year-LOB-Provider-IPA-Attribution combinations
- [ ] Validate member months threshold (≤ 12 warning)
- [ ] Ensure TINs are treated as text with leading zeros
- [ ] Use exact data type strings from template

## Notes for Future Updates

1. Always check the actual Excel template structure, not just documentation
2. Pay attention to which row contains field codes vs column names vs data
3. Provider identification can use Name OR TIN depending on the sheet
4. The template includes many validation sheets that are auto-calculated
5. Some fields have newlines in their names (e.g., "IPA or Contract Name\n(If applicable/available)")

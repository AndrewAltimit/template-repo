# Oregon CGT-1 2025 Template Learnings from Reference Files

## Overview
This document captures key learnings from analyzing the Oregon CGT-1 2025 reference Excel files. These findings were discovered on 2025-08-05 by comparing the actual Excel templates with our implementation.

## Key Discoveries

### 1. Different Header Row Structures
**Critical Finding**: Not all sheets use the same header row structure!

- **Standard Structure** (TME_ALL, TME_UNATTR, MARKET_ENROLL, RX_REBATE):
  - Row 8: Field codes
  - Row 10: Column names
  - Row 11: First data row
  - Parse with `pd.ExcelFile.parse(sheet, header=8)`

- **Different Structure** (TME_PROV, RX_MED_PROV, RX_MED_UNATTR):
  - Row 10: Field codes
  - Row 12: Column names
  - Row 13: First data row
  - Parse with `pd.ExcelFile.parse(sheet, header=10)`

### 2. Cover Page Has Date Field
The Cover Page has 8 required fields, not 7:
- Row 15, Column C: Date field (was missing from our docs)

### 3. PROV_ID Field Code Structure
The PROV_ID sheet has a unique field code pattern:
- PRV01: Provider Organization Name
- [blank/null]: IPA or Contract Name
- PRV02: Provider Organization TIN

Note: The middle column has no field code!

### 4. Provider-IPA Combination Validation
**New Validation Rule**: Provider-IPA combinations must match exactly between sheets.
- TME_PROV references must match PROV_ID by both Provider Name AND IPA
- The unique key for TME_PROV includes IPA: Year-LOB-Provider-IPA-Attribution
- If a provider has "IPA 1" in TME_PROV, that exact combo must exist in PROV_ID

### 5. Column Name Variations with Newlines
Some column names contain newlines:
- TME_PROV: `"IPA or Contract Name\n(If applicable/available)"`
- PROV_ID: `"IPA or Contract Name (If applicable/available)"` (no newline)

Must handle both variations when matching columns.

### 6. Validation Check Explanations
The template includes detailed validation explanations in header rows:
- TME_PROV Row 5: Explanation about duplicate checking
- These explanations reference specific cells like "TMERXPRV16"

### 7. Member Months Threshold Context
- Threshold is 12 member months
- Rows with ≤12 should be rolled to TME_UNATTR
- This is a warning, not an error
- The validation sheets auto-calculate these checks

## Implementation Checklist

When working with Oregon CGT-1 2025 templates:

✅ Check sheet-specific header row numbers (don't assume all are the same)
✅ Include Date field validation for Cover Page
✅ Handle PROV_ID's unique field code structure (blank middle column)
✅ Validate Provider-IPA combinations, not just Provider names
✅ Handle column name variations (with/without newlines)
✅ Use numeric parsing with `pd.to_numeric(errors='coerce')` for robust validation
✅ Remember TINs must be stored as text to preserve leading zeros
✅ Enforce LOB code 7 restriction (only allowed in TME_ALL)
✅ Implement case-insensitive provider/IPA matching
✅ Add complete data type validation for all field types

## Common Pitfalls to Avoid

1. **Don't assume uniform header structure** - TME_PROV is different!
2. **Don't skip the Date field** - It's required on Cover Page
3. **Don't validate by TIN** - Always use Provider Organization Name
4. **Don't ignore IPA in validations** - It's part of the unique key
5. **Don't parse as simple integers** - Use proper numeric conversion

## Testing Recommendations

1. Test with providers having different IPAs
2. Include providers with blank/empty IPAs
3. Test member months at boundary (12, 13)
4. Verify Date field is validated
5. Test duplicate Provider-IPA combinations

## Reference Files Location
- `cgt-validator/references/CGT-1-Data-Submission- 2025 Template - Mock Success Data.xlsx`
- `cgt-validator/references/CGT-1-Data-Submission- 2025 Template - Mock Fail Data.xlsx`

Always refer to these actual Excel files when in doubt about structure or validation rules.

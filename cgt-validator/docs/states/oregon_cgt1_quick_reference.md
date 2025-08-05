# Oregon CGT-1 2025 Quick Reference

## ⚡ Critical Points

### 🚨 Most Common Mistakes
1. **TME_PROV has Provider Name, NOT TIN** (TIN is only in PROV_ID)
2. **Attribution Hierarchy Code is REQUIRED** (between IPA and Member Months)
3. **PROV_ID column order**: Name → IPA → TIN (TIN is LAST)
4. **Data starts at row 11**, not row 8!
5. **Match providers by NAME**, not by TIN

### 📊 Row Structure

**Most Sheets (TME_ALL, TME_UNATTR, MARKET_ENROLL, RX_REBATE):**
```
Row 8:  Field codes (TMEALL01, TMEALL02...)
Row 9:  Data types ("year", "code", "positive integer"...)
Row 10: Column names ("Reporting Year", "Line of Business Code"...)
Row 11: First data row
```

**TME_PROV, RX_MED_PROV, RX_MED_UNATTR (Different!):**
```
Row 10: Field codes (TMEPRV01, TMEPRV02...)
Row 11: Data types
Row 12: Column names
Row 13: First data row
```

### 📋 Required Sheets (Exact Names!)
1. `1. Cover Page`
2. `2. TME_ALL`
3. `3. TME_PROV` ⚠️
4. `4. TME_UNATTR`
5. `5. MARKET_ENROLL`
6. `6. RX_MED_PROV`
7. `7. RX_MED_UNATTR`
8. `8. RX_REBATE`
9. `9. PROV_ID` ⚠️

### 🔑 Key Validations

| Field | Format | Notes |
|-------|--------|-------|
| TIN | Exactly 9 digits | Store as text! "000000001" |
| Line of Business Code | 1-7 | 7 only in TME_ALL |
| Attribution Code | 1-3 | 1=Member, 2=Contract, 3=Utilization |
| Member Months | > 0 | ≤ 12 triggers warning |
| Reporting Year | YYYY | Current or previous year only |

### 🏗️ TME_PROV Structure (CORRECT ORDER!)
1. Reporting Year
2. Line of Business Code
3. **Provider Organization Name** ← NOT TIN!
4. IPA or Contract Name (optional)
5. **Attribution Hierarchy Code** ← DON'T MISS!
6. Member Months
7. Demographic Score
8. [Various claim columns...]

### 🏗️ PROV_ID Structure (DIFFERENT ORDER!)
1. Provider Organization Name ← FIRST (field code: PRV01)
2. IPA or Contract Name (field code is blank/missing)
3. Provider Organization TIN ← LAST (field code: PRV02)

### ✅ Validation Checklist
- [ ] All provider names in TME_PROV exist in PROV_ID
- [ ] All Provider-IPA combinations in TME_PROV exist in PROV_ID
- [ ] No duplicate Year-LOB-Provider-IPA-Attribution combinations
- [ ] TINs are 9 digits with leading zeros preserved
- [ ] Attribution codes are 1, 2, or 3
- [ ] Member months > 0 (warn if ≤ 12)
- [ ] Cover page has all 8 required fields filled (including Date)

## 📋 Complete List of Validation Rules

### 1. Sheet Structure Validations
- **Required Sheets Check**: Validates all 9 required sheets are present
- **Minimum Sheet Count**: File must have at least 9 sheets
- **Sheet Names**: Must match exact names (e.g., "1. Cover Page", "2. TME_ALL")

### 2. Cover Page Validations (Cell-Based)
- **Payer Name** (Cell C5): Required, cannot be empty or "[Input Required]"
- **Contact Name** (Cell C6): Required, cannot be empty or "[Input Required]"
- **Contact Email** (Cell C7): Required, must be valid email format
- **Full Name** (Cell C12): Required for signature section
- **Title/Position** (Cell C13): Required for signature section
- **Email/Contact Information** (Cell C14): Required for signature section
- **Signature** (Cell C15): Required, attestation signature
- **Date** (Cell C16): Required, attestation date (Note: Currently not checked in validator)

### 3. Mandatory Field Validations
Each sheet has specific required columns that cannot be empty:

**TME_ALL (Sheet 2)**:
- Reporting Year
- Line of Business Code
- Member Months
- Demographic Score

**TME_PROV (Sheet 3)**:
- Reporting Year
- Line of Business Code
- Provider Organization Name
- Attribution Hierarchy Code
- Member Months
- Demographic Score

**MARKET_ENROLL (Sheet 5)**:
- Reporting Year
- Line of Business Code
- Market Member Months

**RX_MED_PROV (Sheet 6)**:
- Reporting Year
- Line of Business Code
- Provider Organization TIN
- Provider Organization Name
- Allowed Pharmacy
- Net Paid Medical

**PROV_ID (Sheet 9)**:
- Provider Organization Name
- Provider Organization TIN

### 4. Data Type Validations

**Numeric Fields**:
- **Reporting Year**: Must be valid 4-digit year
- **Member Months**: Must be positive integer (> 0)
- **Market Member Months**: Must be positive integer (> 0)
- **Demographic Score**: Must be non-negative number (≥ 0)
- **Line of Business Code**: Must be integer 1-7
- **Attribution Hierarchy Code**: Must be integer 1-3

**Text Fields**:
- **Provider Organization TIN**: Must be exactly 9 digits (stored as text)
- **Provider Organization Name**: Cannot be blank in mandatory fields
- **IPA or Contract Name**: Optional field, blanks allowed

**Email Fields**:
- **Contact Email**: Must be valid email format (xxx@xxx.xxx)

### 5. Business Rule Validations

**Line of Business Code Rules**:
- Valid codes are 1-7:
  - 1 = Medicare
  - 2 = Medicaid
  - 3 = Commercial: Full Claims
  - 4 = Commercial: Partial Claims
  - 5 = Medicare Expenses for Medicare/Medicaid Dual Eligible
  - 6 = Medicaid Expenses for Medicare/Medicaid Dual Eligible
  - 7 = CCO-F expenses or Medicaid Carve-Outs
- Code 7 is only allowed in TME_ALL sheet

**Attribution Hierarchy Code Rules**:
- Valid codes are 1-3:
  - 1 = Tier 1: Member Selection
  - 2 = Tier 2: Contract Arrangement
  - 3 = Tier 3: Utilization

**Member Months Threshold**:
- TME_PROV rows with ≤ 12 member months trigger WARNING
- These should be rolled up to TME_UNATTR at line of business level

**Reporting Year Rules**:
- Must be current year or previous year only
- Example: For 2025 submission, accept 2024 or 2025

**Duplicate Prevention**:
- No duplicate Year-LOB-Provider-IPA-Attribution combinations in TME_PROV
- All costs should be rolled up to a single line at this level

### 6. Cross-Reference Validations

**Provider Name Consistency**:
- All Provider Organization Names in TME_PROV must exist in PROV_ID
- Provider-IPA combinations in TME_PROV must match those in PROV_ID

**Provider TIN Consistency**:
- All Provider Organization TINs in RX_MED_PROV must exist in PROV_ID

**Line of Business Consistency**:
- Year/LOB combinations in TME_PROV, TME_UNATTR, MARKET_ENROLL should exist in TME_ALL
- TME_ALL should contain all LOB codes present in other sheets

### 7. State-Specific Validations

**Behavioral Health Reporting**:
- Checks for behavioral health claims in TME_ALL
- Reports total amount found (informational)

**Validation Sheet Presence**:
- Checks for optional validation sheets:
  - TME Validation
  - RX_MED_PROV Validation
  - RX_MED_UNATTR Validation
  - Provider Check

**TME_UNATTR Data Check**:
- If TME_PROV has rows with ≤ 12 member months
- And TME_UNATTR is empty
- Triggers WARNING about missing unattributed data

**RX_REBATE Data Check**:
- Warns if RX_REBATE sheet contains no data
- Prompts to verify if prescription rebates should be reported

**Template Version Check**:
- Looks for "Version 5.0" or "June 2025" in Contents sheet
- Warns if template version cannot be verified

### 8. Header Row Validations
Different sheets have headers at different rows:
- **Most sheets**: Header at row 9 (0-indexed = 8)
- **TME_PROV, RX_MED_PROV, RX_MED_UNATTR**: Header at row 11 (0-indexed = 10)
- **Cover Page**: No header row (cell-based layout)

### 🎯 Cover Page Fields (Cell Positions)
- Payer Name: `[4, 2]`
- Contact Name: `[5, 2]`
- Contact Email: `[6, 2]`
- Full Name: `[11, 2]`
- Title/Position: `[12, 2]`
- Email/Contact: `[13, 2]`
- Signature: `[14, 2]`
- Date: `[15, 2]`

### 💡 Pro Tips
- Some column names have newlines: `"IPA or Contract Name\n(If applicable/available)"`
- Empty cells should be `None` or `""`, not `"[Input Required]"`
- Use `pd.ExcelFile.parse(sheet, header=10)` for most sheets
- Use `pd.ExcelFile.parse(sheet, header=None)` for Cover Page
- Always validate against Provider Organization Name, not TIN
- Parse TME_PROV with `header=10` (not 8!) due to different row structure
- Validation checks include Provider-IPA combinations, not just Provider names

## 🚨 Validation Error Codes and Severity

### Error Codes (Will fail validation)
- **MISSING_SHEET**: Required sheet not found
- **MISSING_COLUMN**: Required column not found in sheet
- **EMPTY_MANDATORY_FIELD**: Required field has empty values
- **MISSING_REQUIRED_FIELD**: Cover page missing required field
- **INVALID_COVER_PAGE_FORMAT**: Cover page structure is invalid
- **INVALID_LOB_CODE**: Line of Business code not in valid range (1-7)
- **INVALID_TIN**: TIN is not exactly 9 digits
- **INVALID_MEMBER_MONTHS**: Member months not positive integer
- **INVALID_REPORTING_YEAR**: Year not current or previous year
- **INVALID_ATTRIBUTION_CODE**: Attribution code not in valid range (1-3)
- **DUPLICATE_PROVIDER_COMBINATION**: Duplicate Year-LOB-Provider-IPA-Attribution found
- **INVALID_PROVIDER_REFERENCE**: Provider name/TIN not found in PROV_ID
- **INVALID_PROVIDER_IPA_COMBINATION**: Provider-IPA combo not in PROV_ID

### Warning Codes (Validation passes but needs attention)
- **MEMBER_MONTHS_BELOW_THRESHOLD**: TME_PROV has rows with ≤ 12 member months
- **LOB_MISMATCH**: Sheet has Year/LOB combinations not in TME_ALL
- **MISSING_UNATTR_DATA**: Low member month data should be in TME_UNATTR
- **NO_RX_REBATE_DATA**: RX_REBATE sheet is empty
- **UNKNOWN_TEMPLATE_VERSION**: Cannot verify template version

### Info Codes (Informational only)
- **BEHAVIORAL_HEALTH_FOUND**: Reports behavioral health claim totals
- **VALIDATION_SHEETS_PRESENT**: Optional validation sheets found
- **TEMPLATE_VERSION**: Confirms correct template version

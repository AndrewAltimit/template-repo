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

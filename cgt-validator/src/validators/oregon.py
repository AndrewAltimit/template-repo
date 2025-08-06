"""Oregon-specific CGT validator implementation."""

from typing import Any, Dict, Optional

import pandas as pd
from reporters.validation_results import Severity, ValidationResults

from .base_validator import ValidatorBase


class OregonValidator(ValidatorBase):
    """Validator for Oregon CGT-1 data submissions (2025 template)."""

    def __init__(self, year: Optional[int] = None):
        super().__init__("oregon", year)

    def _get_header_row(self, sheet_name: str) -> int:
        """Get the correct header row for a sheet based on 2025 template structure."""
        # Per actual Excel template structure from reference files
        if sheet_name in ["3. TME_PROV", "6. RX_MED_PROV"]:
            return 10  # Column names at row 11 (0-indexed = 10)
        elif sheet_name == "9. PROV_ID":
            return 8  # Column names at row 9 (0-indexed = 8)
        else:
            # TME_ALL, TME_UNATTR, MARKET_ENROLL, RX_MED_UNATTR, RX_REBATE
            return 8  # Column names at row 9 (0-indexed = 8)

    def _load_requirements(self) -> Dict[str, Any]:
        """Load Oregon-specific requirements for 2025 CGT-1 template."""
        return {
            "min_sheets": 9,
            "required_sheets": [
                "1. Cover Page",
                "2. TME_ALL",
                "3. TME_PROV",
                "4. TME_UNATTR",
                "5. MARKET_ENROLL",
                "6. RX_MED_PROV",
                "7. RX_MED_UNATTR",
                "8. RX_REBATE",
                "9. PROV_ID",
            ],
            "all_sheets": [
                "Contents",
                "1. Cover Page",
                "2. TME_ALL",
                "3. TME_PROV",
                "4. TME_UNATTR",
                "5. MARKET_ENROLL",
                "6. RX_MED_PROV",
                "7. RX_MED_UNATTR",
                "8. RX_REBATE",
                "9. PROV_ID",
                "Line of Business Code",
                "Attribution Hierarchy Code",
                "Demographic Tables",
                "TME Validation",
                "RX_MED_PROV Validation",
                "RX_MED_UNATTR Validation",
                "Provider Check",
            ],
            "mandatory_fields": {
                # Cover Page is handled separately in _validate_specific_rules
                # because it uses cell-based layout, not column headers
                "2. TME_ALL": [
                    "Reporting Year",
                    "Line of Business Code",
                    "Member Months",
                    # Demographic Score is optional based on mock success data
                    # Additional columns exist but these are the key mandatory ones
                ],
                "3. TME_PROV": [
                    "Reporting Year",
                    "Line of Business Code",
                    "Provider Organization Name",  # Name comes before TIN
                    # IPA is optional - removed from mandatory fields
                    "Attribution Hierarchy Code",  # Important field we missed
                    "Member Months",
                    # Demographic Score is optional based on mock success data
                ],
                "9. PROV_ID": [
                    "Provider Organization Name",
                    # IPA is optional - removed from mandatory fields
                    "Provider Organization TIN",  # TIN is last column
                ],
                "5. MARKET_ENROLL": [
                    # MARKET_ENROLL has a different structure with year-specific columns
                    "Market Enrollment Category",
                    # Year columns are dynamic based on reporting year
                ],
                "6. RX_MED_PROV": [
                    "Reporting Year",
                    "Line of Business Code",
                    "Provider Organization Name",
                    # Additional pharmacy columns exist in the data
                ],
            },
            "data_types": {
                "1. Cover Page": {
                    "Payer Name": "text",
                    "Contact Name": "text",
                    "Contact Email": "email",
                },
                "2. TME_ALL": {
                    "Reporting Year": "year",
                    "Line of Business Code": "code",
                    "Member Months": "positive_integer",
                    "Demographic Score": "non_negative_number",
                },
                "3. TME_PROV": {
                    "Reporting Year": "year",
                    "Line of Business Code": "code",
                    "Provider Organization Name": "free_text_blank_not_allowed",
                    "IPA or Contract Name\n(If applicable/available)": "free_text_blank_allowed",
                    "Attribution Hierarchy Code": "code",
                    "Member Months": "positive_integer",
                    "Demographic Score": "non_negative_number",
                },
                "9. PROV_ID": {
                    "Provider Organization Name": "free_text",
                    "IPA or Contract Name (If applicable/available)": "free_text",
                    "Provider Organization TIN": "text_9_digits",
                },
            },
            "allowed_values": {
                "Line of Business Code": {
                    1: "Medicare",
                    2: "Medicaid",
                    3: "Commercial: Full Claims",
                    4: "Commercial: Partial Claims",
                    5: "Medicare Expenses for Medicare/Medicaid Dual Eligible",
                    6: "Medicaid Expenses for Medicare/Medicaid Dual Eligible",
                    7: "CCO-F and Medicaid Open Card Carve-Outs",
                },
                "Attribution Hierarchy Code": {
                    1: "Tier 1: Member Selection",
                    2: "Tier 2: Contract Arrangement",
                    3: "Tier 3: Utilization (requires methodology summary on Cover Page)",
                },
            },
            "member_months_threshold": 12,  # TME_PROV rows with <= 12 member months should be rolled up to TME_UNATTR
        }

    def _validate_mandatory_fields(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Override to handle Oregon-specific sheet structures with different header rows."""
        mandatory_fields = self.requirements.get("mandatory_fields", {})

        for sheet_name, fields in mandatory_fields.items():
            if sheet_name not in excel_data.sheet_names:
                continue

            # Skip Cover Page - it's handled in _validate_business_rules
            if sheet_name == "1. Cover Page":
                continue

            # Use centralized header row determination
            header_row = self._get_header_row(sheet_name)

            # Parse with correct header row
            df = excel_data.parse(sheet_name, header=header_row)

            # Filter out completely empty rows and header/metadata rows
            # For most sheets, filter by Reporting Year being numeric
            if "Reporting Year" in df.columns:
                data_df = df[pd.to_numeric(df["Reporting Year"], errors="coerce").notna()]
            else:
                # For sheets without Reporting Year, filter out rows where all required fields are empty
                data_df = df.dropna(how="all", subset=[f for f in fields if f in df.columns])

            # Check column presence
            for field in fields:
                if field not in df.columns:
                    results.add_error(
                        code="MISSING_COLUMN",
                        message=f"Required column '{field}' not found",
                        location=f"{sheet_name}",
                        severity=Severity.ERROR,
                    )
                else:
                    # Check for empty values only in valid data rows
                    empty_rows = data_df[data_df[field].isna() | (data_df[field] == "")].index.tolist()
                    if empty_rows:
                        results.add_error(
                            code="EMPTY_MANDATORY_FIELD",
                            message=(
                                f"Column '{field}' has empty values in rows: "
                                f"{empty_rows[:5]}{'...' if len(empty_rows) > 5 else ''}"
                            ),
                            location=f"{sheet_name}.{field}",
                            severity=Severity.ERROR,
                        )

    def _validate_data_types(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Override to handle Oregon-specific sheet structures with different header rows."""
        data_types = self.requirements.get("data_types", {})

        for sheet_name, column_types in data_types.items():
            if sheet_name not in excel_data.sheet_names:
                continue

            # Skip Cover Page - it's handled in _validate_business_rules
            if sheet_name == "1. Cover Page":
                continue

            # Use centralized header row determination
            header_row = self._get_header_row(sheet_name)

            # Parse with correct header row
            df = excel_data.parse(sheet_name, header=header_row)

            # Filter out completely empty rows and header/metadata rows
            # For most sheets, filter by Reporting Year being numeric
            if "Reporting Year" in df.columns:
                data_df = df[pd.to_numeric(df["Reporting Year"], errors="coerce").notna()]
            else:
                # For sheets without Reporting Year, use all non-empty rows
                data_df = df.dropna(how="all")

            for column, expected_type in column_types.items():
                if column not in data_df.columns:
                    continue

                # Validate data types based on expected type
                if expected_type == "year":
                    numeric_vals = pd.to_numeric(data_df[column], errors="coerce")
                    invalid_years = data_df[numeric_vals.isna() | (numeric_vals < 2000) | (numeric_vals > 2050)]
                    if not invalid_years.empty:
                        results.add_error(
                            code="INVALID_DATA_TYPE",
                            message=(
                                f"Column '{column}' contains invalid year values in rows: "
                                f"{invalid_years.index.tolist()[:5]}"
                            ),
                            location=f"{sheet_name}.{column}",
                            severity=Severity.ERROR,
                        )
                elif expected_type == "code":
                    numeric_vals = pd.to_numeric(data_df[column], errors="coerce")
                    invalid_codes = data_df[numeric_vals.isna()]
                    if not invalid_codes.empty:
                        results.add_error(
                            code="INVALID_DATA_TYPE",
                            message=(
                                f"Column '{column}' must contain numeric codes in rows: " f"{invalid_codes.index.tolist()[:5]}"
                            ),
                            location=f"{sheet_name}.{column}",
                            severity=Severity.ERROR,
                        )
                elif expected_type == "positive_integer":
                    numeric_vals = pd.to_numeric(data_df[column], errors="coerce")
                    invalid_ints = data_df[
                        numeric_vals.isna() | (numeric_vals <= 0) | (numeric_vals != numeric_vals.fillna(0).astype("int64"))
                    ]
                    if not invalid_ints.empty:
                        results.add_error(
                            code="INVALID_DATA_TYPE",
                            message=(
                                f"Column '{column}' must contain positive integers in rows: "
                                f"{invalid_ints.index.tolist()[:5]}"
                            ),
                            location=f"{sheet_name}.{column}",
                            severity=Severity.ERROR,
                        )
                elif expected_type == "non_negative_number":
                    numeric_vals = pd.to_numeric(data_df[column], errors="coerce")
                    # For Demographic Score, allow NaN values (it's optional)
                    if column == "Demographic Score":
                        invalid_nums = data_df[(numeric_vals < 0)]
                    else:
                        invalid_nums = data_df[numeric_vals.isna() | (numeric_vals < 0)]
                    if not invalid_nums.empty:
                        results.add_error(
                            code="INVALID_DATA_TYPE",
                            message=(
                                f"Column '{column}' must contain non-negative numbers in rows: "
                                f"{invalid_nums.index.tolist()[:5]}"
                            ),
                            location=f"{sheet_name}.{column}",
                            severity=Severity.ERROR,
                        )
                elif expected_type == "text_9_digits":
                    invalid_tins = data_df[~data_df[column].astype(str).str.match(r"^\d{9}$", na=False)]
                    if not invalid_tins.empty:
                        results.add_error(
                            code="INVALID_DATA_TYPE",
                            message=(
                                f"Column '{column}' must contain exactly 9 digits in rows: "
                                f"{invalid_tins.index.tolist()[:5]}"
                            ),
                            location=f"{sheet_name}.{column}",
                            severity=Severity.ERROR,
                        )

    def _validate_business_rules(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Validate Oregon-specific business rules for 2025 CGT-1 template.

        Note: The following rules cannot be validated programmatically:
        - Student health plans: Members should be included as Oregon residents for plan duration
        - Out-of-state residents: Should be excluded even if treated in Oregon
        - LOBs 5 & 6: Should use 'Paid Amounts' regardless of primary/secondary payer status
        - Tier 3 attribution: Payers must provide methodology summary on Cover Page
        - Non-claims performance payments: Should be assigned to the year performance was tracked
        - Cost growth calculation: Reported on per capita basis at statewide level (not PMPM)
        - Non-claims attribution: Should be at member level before rolling up to provider org
        """

        # Rule 1: Validate Cover Page required fields
        if "1. Cover Page" in excel_data.sheet_names:
            df = excel_data.parse("1. Cover Page", header=None)
            required_fields = {
                "Payer Name": (4, 2),  # Row 5, Column C
                "Contact Name": (5, 2),
                "Contact Email": (6, 2),
                "Full Name": (11, 2),
                "Title/Position": (12, 2),
                "Email/Contact Information": (13, 2),
                "Signature": (14, 2),
                "Date": (15, 2),  # Required attestation date field
            }

            for field_name, (row_idx, col_idx) in required_fields.items():
                try:
                    value = df.iloc[row_idx, col_idx] if row_idx < len(df) and col_idx < len(df.columns) else None
                    if pd.isna(value) or str(value).strip() == "[Input Required]":
                        results.add_error(
                            code="MISSING_REQUIRED_FIELD",
                            message=f"Cover Page missing required field: {field_name}",
                            location=f"1. Cover Page.{field_name}",
                            severity=Severity.ERROR,
                        )
                except (IndexError, KeyError):
                    results.add_error(
                        code="INVALID_COVER_PAGE_FORMAT",
                        message=f"Cover Page format is invalid - cannot find {field_name}",
                        location="1. Cover Page",
                        severity=Severity.ERROR,
                    )

        # Rule 2: Validate Line of Business codes with LOB 7 restriction
        valid_lob_codes = list(self.requirements["allowed_values"]["Line of Business Code"].keys())

        for sheet_name in [
            "2. TME_ALL",
            "3. TME_PROV",
            "4. TME_UNATTR",
            "5. MARKET_ENROLL",
            "6. RX_MED_PROV",
            "7. RX_MED_UNATTR",
            "8. RX_REBATE",
        ]:
            if sheet_name in excel_data.sheet_names:
                # Use centralized header row determination
                header_row = self._get_header_row(sheet_name)
                df = excel_data.parse(sheet_name, header=header_row)
                if "Line of Business Code" in df.columns:
                    # Filter out non-numeric data
                    numeric_lob = pd.to_numeric(df["Line of Business Code"], errors="coerce")

                    # Check for invalid codes based on sheet
                    if sheet_name == "2. TME_ALL":
                        # TME_ALL allows codes 1-7
                        invalid_codes = df[~numeric_lob.isin(valid_lob_codes)]
                        if not invalid_codes.empty:
                            message = (
                                f"Invalid Line of Business codes in rows: {invalid_codes.index.tolist()[:5]}. "
                                "Valid codes are 1-7."
                            )
                            results.add_error(
                                code="INVALID_LOB_CODE",
                                message=message,
                                location=f"{sheet_name}.Line of Business Code",
                                severity=Severity.ERROR,
                            )
                    else:
                        # All other sheets only allow codes 1-6 (not 7)
                        invalid_codes_general = df[~numeric_lob.isin([1, 2, 3, 4, 5, 6])]
                        # Check specifically for LOB code 7
                        has_lob_7 = df[numeric_lob == 7]

                        if not has_lob_7.empty:
                            message = (
                                f"LOB code 7 found in rows: {has_lob_7.index.tolist()[:5]}. "
                                "LOB code 7 (CCO-F and Medicaid Open Card Carve-Outs) is only allowed in TME_ALL sheet."
                            )
                            results.add_error(
                                code="INVALID_LOB_CODE_7",
                                message=message,
                                location=f"{sheet_name}.Line of Business Code",
                                severity=Severity.ERROR,
                            )
                        elif not invalid_codes_general.empty:
                            # Other invalid codes (not 1-6)
                            message = (
                                f"Invalid Line of Business codes in rows: {invalid_codes_general.index.tolist()[:5]}. "
                                "Valid codes are 1-6 only."
                            )
                            results.add_error(
                                code="INVALID_LOB_CODE",
                                message=message,
                                location=f"{sheet_name}.Line of Business Code",
                                severity=Severity.ERROR,
                            )

        # Rule 3: Validate TIN format (9 digits) and field codes in PROV_ID sheet
        if "9. PROV_ID" in excel_data.sheet_names:
            # Use centralized header row determination
            header_row = self._get_header_row("9. PROV_ID")
            df = excel_data.parse("9. PROV_ID", header=header_row)

            # Validate field codes structure (PRV01, PRV03, PRV02)
            df_raw = excel_data.parse("9. PROV_ID", header=None)
            if len(df_raw) > 6 and len(df_raw.columns) >= 3:
                field_codes_row = df_raw.iloc[6]  # Row 7 (0-indexed = 6)
                actual_codes = [field_codes_row.iloc[i] if i < len(field_codes_row) else None for i in range(3)]

                # Check if field codes match expected pattern
                if actual_codes[0] != "PRV01" or actual_codes[1] != "PRV03" or actual_codes[2] != "PRV02":
                    results.add_error(
                        code="INVALID_FIELD_CODES",
                        message="PROV_ID field codes must be PRV01, PRV03, PRV02 in that order",
                        location="9. PROV_ID",
                        severity=Severity.ERROR,
                    )

            if "Provider Organization TIN" in df.columns:
                # Filter out header/type rows and validate actual data
                data_df = df[~df["Provider Organization TIN"].astype(str).str.contains("text|PRV", na=False)]
                invalid_tin = data_df[~data_df["Provider Organization TIN"].astype(str).str.match(r"^\d{9}$", na=False)]
                if not invalid_tin.empty:
                    results.add_error(
                        code="INVALID_TIN",
                        message=f"TIN must be 9 digits including leading zeros in rows: {invalid_tin.index.tolist()[:5]}",
                        location="9. PROV_ID.Provider Organization TIN",
                        severity=Severity.ERROR,
                    )

        # Rule 4: Validate member months are positive integers
        for sheet_name in ["2. TME_ALL", "3. TME_PROV", "4. TME_UNATTR", "5. MARKET_ENROLL"]:
            if sheet_name in excel_data.sheet_names:
                header_row = self._get_header_row(sheet_name)
                df = excel_data.parse(sheet_name, header=header_row)
                mm_col = "Member Months" if sheet_name != "5. MARKET_ENROLL" else "Market Member Months"
                if mm_col in df.columns:
                    # Filter out non-numeric data
                    numeric_df = pd.to_numeric(df[mm_col], errors="coerce")
                    # Check for non-positive values
                    invalid_mm = df[(numeric_df <= 0) | numeric_df.isna()]
                    if not invalid_mm.empty:
                        results.add_error(
                            code="INVALID_MEMBER_MONTHS",
                            message=f"Member months must be positive integers in rows: {invalid_mm.index.tolist()[:5]}",
                            location=f"{sheet_name}.{mm_col}",
                            severity=Severity.ERROR,
                        )

        # Rule 5: Validate TME_PROV member months threshold
        if "3. TME_PROV" in excel_data.sheet_names:
            header_row = self._get_header_row("3. TME_PROV")
            df = excel_data.parse("3. TME_PROV", header=header_row)
            if "Member Months" in df.columns:
                numeric_mm = pd.to_numeric(df["Member Months"], errors="coerce")
                below_threshold = df[numeric_mm <= self.requirements["member_months_threshold"]]
                if not below_threshold.empty:
                    results.add_warning(
                        code="MEMBER_MONTHS_BELOW_THRESHOLD",
                        message=(
                            f"TME_PROV has {len(below_threshold)} rows with member months <= "
                            f"{self.requirements['member_months_threshold']}. "
                            "These should be rolled up to TME_UNATTR at the line of business level."
                        ),
                        location="3. TME_PROV.Member Months",
                        severity=Severity.WARNING,
                    )

        # Rule 6: Validate reporting year
        current_year = self.year or 2025
        for sheet_name in ["2. TME_ALL", "3. TME_PROV", "4. TME_UNATTR", "5. MARKET_ENROLL"]:
            if sheet_name in excel_data.sheet_names:
                header_row = self._get_header_row(sheet_name)
                df = excel_data.parse(sheet_name, header=header_row)
                if "Reporting Year" in df.columns:
                    numeric_years = pd.to_numeric(df["Reporting Year"], errors="coerce")
                    invalid_years = df[~numeric_years.isin([current_year - 1, current_year])]
                    if not invalid_years.empty:
                        results.add_error(
                            code="INVALID_REPORTING_YEAR",
                            message=(
                                f"Invalid reporting year. Expected {current_year-1} or {current_year} "
                                f"in rows: {invalid_years.index.tolist()[:5]}"
                            ),
                            location=f"{sheet_name}.Reporting Year",
                            severity=Severity.ERROR,
                        )

        # Rule 7: Validate Attribution Hierarchy Code in TME_PROV
        if "3. TME_PROV" in excel_data.sheet_names:
            header_row = self._get_header_row("3. TME_PROV")
            df = excel_data.parse("3. TME_PROV", header=header_row)
            if "Attribution Hierarchy Code" in df.columns:
                valid_attr_codes = list(self.requirements["allowed_values"]["Attribution Hierarchy Code"].keys())
                numeric_codes = pd.to_numeric(df["Attribution Hierarchy Code"], errors="coerce")
                invalid_attr = df[~numeric_codes.isin(valid_attr_codes)]
                if not invalid_attr.empty:
                    results.add_error(
                        code="INVALID_ATTRIBUTION_CODE",
                        message=(
                            f"Invalid Attribution Hierarchy Code in rows: {invalid_attr.index.tolist()[:5]}. "
                            f"Valid codes are {valid_attr_codes}"
                        ),
                        location="3. TME_PROV.Attribution Hierarchy Code",
                        severity=Severity.ERROR,
                    )

        # Rule 8: Check for duplicate Year-LOB-Provider-Attribution combinations
        if "3. TME_PROV" in excel_data.sheet_names:
            header_row = self._get_header_row("3. TME_PROV")
            df = excel_data.parse("3. TME_PROV", header=header_row)
            # Include IPA/Contract Name in the key columns as shown in reference validation
            key_cols = [
                "Reporting Year",
                "Line of Business Code",
                "Provider Organization Name",
                "IPA or Contract Name\n(If applicable/available)",
                "Attribution Hierarchy Code",
            ]
            # Handle both possible column name formats for IPA
            if (
                "IPA or Contract Name\n(If applicable/available)" not in df.columns
                and "IPA or Contract Name (If applicable/available)" in df.columns
            ):
                key_cols[3] = "IPA or Contract Name (If applicable/available)"

            if all(col in df.columns for col in key_cols[:3]) and any(
                col in df.columns for col in [key_cols[3], "IPA or Contract Name (If applicable/available)"]
            ):
                # Create subset with available columns
                available_key_cols = [col for col in key_cols if col in df.columns]
                duplicates = df[df.duplicated(subset=available_key_cols, keep=False)]
                if not duplicates.empty:
                    results.add_error(
                        code="DUPLICATE_PROVIDER_COMBINATION",
                        message=(
                            f"Duplicate Year-LOB-Provider-IPA-Attribution combinations found. "
                            f"All costs should be rolled up to a single line at this level. "
                            f"Found {len(duplicates)} duplicate rows."
                        ),
                        location="3. TME_PROV",
                        severity=Severity.ERROR,
                    )

    def _validate_cross_references(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Validate cross-references between sheets for 2025 CGT-1 template."""

        # Get provider names and TINs from PROV_ID sheet
        provider_info = {}
        provider_names = set()
        provider_tins = set()
        provider_ipa_combos = set()  # Initialize this set here

        if "9. PROV_ID" in excel_data.sheet_names:
            header_row = self._get_header_row("9. PROV_ID")
            df = excel_data.parse("9. PROV_ID", header=header_row)
            if "Provider Organization Name" in df.columns and "Provider Organization TIN" in df.columns:
                # Filter out header/type rows
                data_df = df[~df["Provider Organization TIN"].astype(str).str.contains("text|PRV|digits", na=False)]

                # Find IPA column (might have different names)
                ipa_col = None
                for col_name in [
                    "IPA or Contract Name (If applicable/available)",
                    "IPA or Contract Name\n(If applicable/available)",
                ]:
                    if col_name in df.columns:
                        ipa_col = col_name
                        break

                for _, row in data_df.iterrows():
                    name = row.get("Provider Organization Name")
                    tin = row.get("Provider Organization TIN")
                    ipa = row.get(ipa_col, "") if ipa_col else ""

                    if pd.notna(name) and pd.notna(tin) and str(name).strip() and str(tin).strip():
                        # Normalize names for case-insensitive matching
                        name_str = str(name).strip()
                        tin_str = str(tin).strip()
                        ipa_str = str(ipa).strip() if pd.notna(ipa) else ""

                        provider_info[name_str.upper()] = tin_str  # Store uppercase for matching
                        provider_names.add(name_str.upper())
                        provider_tins.add(tin_str)
                        # Add provider-IPA combination (normalized)
                        provider_ipa_combos.add((name_str.upper(), ipa_str.upper()))

        # Check that all Provider Names in TME_PROV exist in PROV_ID
        if "3. TME_PROV" in excel_data.sheet_names:
            header_row = self._get_header_row("3. TME_PROV")
            df = excel_data.parse("3. TME_PROV", header=header_row)
            if "Provider Organization Name" in df.columns:
                # Filter out empty or invalid rows
                valid_df = df[df["Provider Organization Name"].notna() & (df["Provider Organization Name"] != "")]
                # Use uppercase for case-insensitive matching
                tme_prov_names = set(str(name).strip().upper() for name in valid_df["Provider Organization Name"].unique())
                missing_names = tme_prov_names - provider_names

                if missing_names:
                    # Show original case names in error message
                    original_missing = []
                    for _, row in valid_df.iterrows():
                        name = str(row.get("Provider Organization Name", "")).strip()
                        if name.upper() in missing_names:
                            original_missing.append(name)
                            if len(original_missing) >= 5:
                                break

                    results.add_error(
                        code="INVALID_PROVIDER_REFERENCE",
                        message=f"Provider names in TME_PROV not found in PROV_ID sheet: {original_missing[:5]}",
                        location="3. TME_PROV.Provider Organization Name",
                        severity=Severity.ERROR,
                    )

                # Also check Provider-IPA combinations match between TME_PROV and PROV_ID
                # provider_ipa_combos was already populated when parsing PROV_ID above

                # Check TME_PROV provider-IPA combinations
                ipa_col_tme = None
                for col_name in [
                    "IPA or Contract Name\n(If applicable/available)",  # With actual newline
                    "IPA or Contract Name (If applicable/available)",  # Without newline
                ]:
                    if col_name in df.columns:
                        ipa_col_tme = col_name
                        break

                if ipa_col_tme:
                    missing_combos = []
                    for _, row in valid_df.iterrows():
                        name = str(row.get("Provider Organization Name", "")).strip()
                        ipa_val = row.get(ipa_col_tme, "")
                        # Handle None/NaN values properly
                        if pd.isna(ipa_val) or str(ipa_val).lower() == "nan":
                            ipa = ""
                        else:
                            ipa = str(ipa_val).strip()

                        # Use uppercase for case-insensitive matching
                        if name and (name.upper(), ipa.upper()) not in provider_ipa_combos:
                            missing_combos.append(f"{name} - {ipa if ipa else 'No IPA'}")

                    if missing_combos:
                        results.add_error(
                            code="INVALID_PROVIDER_IPA_COMBINATION",
                            message=f"Provider-IPA combinations in TME_PROV not found in PROV_ID sheet: {missing_combos[:3]}",
                            location="3. TME_PROV",
                            severity=Severity.ERROR,
                        )

        # Check that RX_MED_PROV Provider TINs exist in PROV_ID
        if "6. RX_MED_PROV" in excel_data.sheet_names:
            header_row = self._get_header_row("6. RX_MED_PROV")
            df = excel_data.parse("6. RX_MED_PROV", header=header_row)
            if "Provider Organization TIN" in df.columns:
                rx_prov_tins = set(df["Provider Organization TIN"].dropna().astype(str).unique())
                missing_tins = rx_prov_tins - provider_tins

                if missing_tins:
                    results.add_error(
                        code="INVALID_PROVIDER_REFERENCE",
                        message=f"Provider TINs in RX_MED_PROV not found in PROV_ID sheet: {list(missing_tins)[:5]}",
                        location="6. RX_MED_PROV.Provider Organization TIN",
                        severity=Severity.ERROR,
                    )

        # Validate Line of Business consistency across sheets
        lob_by_sheet = {}
        for sheet_name in ["2. TME_ALL", "3. TME_PROV", "4. TME_UNATTR", "5. MARKET_ENROLL"]:
            if sheet_name in excel_data.sheet_names:
                header_row = self._get_header_row(sheet_name)
                df = excel_data.parse(sheet_name, header=header_row)
                if "Line of Business Code" in df.columns and "Reporting Year" in df.columns:
                    # Filter out non-numeric data
                    valid_df = df[
                        (pd.to_numeric(df["Reporting Year"], errors="coerce").notna())
                        & (pd.to_numeric(df["Line of Business Code"], errors="coerce").notna())
                    ]
                    # Get unique combinations of year and LOB
                    year_lob_combos = valid_df[["Reporting Year", "Line of Business Code"]].drop_duplicates()
                    lob_by_sheet[sheet_name] = set(tuple(x) for x in year_lob_combos.values)

        # Check that TME_ALL has all LOB codes present in other sheets
        if "2. TME_ALL" in lob_by_sheet:
            tme_all_combos = lob_by_sheet["2. TME_ALL"]
            for sheet_name, combos in lob_by_sheet.items():
                if sheet_name != "2. TME_ALL":
                    missing_lob_combos = combos - tme_all_combos
                    if missing_lob_combos:
                        results.add_warning(
                            code="LOB_MISMATCH",
                            message=(
                                f"{sheet_name} has Year/LOB combinations not present in TME_ALL: "
                                f"{list(missing_lob_combos)[:3]}"
                            ),
                            location=f"{sheet_name}",
                            severity=Severity.WARNING,
                        )

    def _run_state_specific_validations(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Run Oregon-specific validations for 2025 CGT-1 template."""

        # Check for behavioral health expenses in TME_ALL
        if "2. TME_ALL" in excel_data.sheet_names:
            header_row = self._get_header_row("2. TME_ALL")
            df = excel_data.parse("2. TME_ALL", header=header_row)
            bh_column = "Claims: Professional, Behavior Health Providers"
            if bh_column in df.columns:
                # Check if behavioral health claims are properly reported
                bh_total = df[bh_column].sum()
                if bh_total > 0:
                    results.add_info(
                        code="BEHAVIORAL_HEALTH_FOUND",
                        message=f"Found ${bh_total:,.2f} in behavioral health claims",
                        location="2. TME_ALL",
                        severity=Severity.INFO,
                    )

        # Check for HRSN costs in TME_PROV (they should only be in TME_ALL and TME_UNATTR)
        if "3. TME_PROV" in excel_data.sheet_names:
            header_row = self._get_header_row("3. TME_PROV")
            df = excel_data.parse("3. TME_PROV", header=header_row)
            # Check for various HRSN column names
            hrsn_columns = ["Non-Claims: HRSN", "Non-Claims: HSRN", "HRSN", "Health-Related Social Needs"]
            for col in hrsn_columns:
                if col in df.columns:
                    # Check if any HRSN values exist
                    numeric_values = pd.to_numeric(df[col], errors="coerce")
                    non_zero_hrsn = df[numeric_values > 0]
                    if not non_zero_hrsn.empty:
                        results.add_error(
                            code="HRSN_IN_WRONG_SHEET",
                            message=(
                                f"HRSN costs found in TME_PROV at rows: {non_zero_hrsn.index.tolist()[:5]}. "
                                "HRSN costs should only be reported in TME_ALL and TME_UNATTR tabs."
                            ),
                            location=f"3. TME_PROV.{col}",
                            severity=Severity.ERROR,
                        )
                    break  # Found and checked HRSN column

        # Check for validation sheets
        validation_sheets = ["TME Validation", "RX_MED_PROV Validation", "RX_MED_UNATTR Validation", "Provider Check"]
        found_validation_sheets = [sheet for sheet in validation_sheets if sheet in excel_data.sheet_names]

        if found_validation_sheets:
            results.add_info(
                code="VALIDATION_SHEETS_PRESENT",
                message=f"File contains {len(found_validation_sheets)} validation sheets",
                location="file",
                severity=Severity.INFO,
            )

        # Check if TME_UNATTR has data when TME_PROV has low member months
        if "3. TME_PROV" in excel_data.sheet_names and "4. TME_UNATTR" in excel_data.sheet_names:
            header_row_prov = self._get_header_row("3. TME_PROV")
            header_row_unattr = self._get_header_row("4. TME_UNATTR")
            tme_prov_df = excel_data.parse("3. TME_PROV", header=header_row_prov)
            tme_unattr_df = excel_data.parse("4. TME_UNATTR", header=header_row_unattr)

            if "Member Months" in tme_prov_df.columns:
                # Count rows below threshold
                numeric_mm = pd.to_numeric(tme_prov_df["Member Months"], errors="coerce")
                below_threshold_count = len(tme_prov_df[numeric_mm <= self.requirements["member_months_threshold"]])

                if below_threshold_count > 0 and len(tme_unattr_df) == 0:
                    results.add_warning(
                        code="MISSING_UNATTR_DATA",
                        message=(
                            f"TME_PROV has {below_threshold_count} rows with member months <= "
                            f"{self.requirements['member_months_threshold']}, "
                            "but TME_UNATTR sheet is empty. Low member month data should be rolled up to TME_UNATTR."
                        ),
                        location="4. TME_UNATTR",
                        severity=Severity.WARNING,
                    )

        # Validate prescription rebate reporting
        if "8. RX_REBATE" in excel_data.sheet_names:
            header_row = self._get_header_row("8. RX_REBATE")
            df = excel_data.parse("8. RX_REBATE", header=header_row)
            # Filter out rows that are just headers or empty
            data_df = df[(pd.to_numeric(df.get("Reporting Year", pd.Series()), errors="coerce").notna())]
            if len(data_df) == 0:
                results.add_warning(
                    code="NO_RX_REBATE_DATA",
                    message="RX_REBATE sheet contains no data. Verify if prescription rebates should be reported.",
                    location="8. RX_REBATE",
                    severity=Severity.WARNING,
                )
            else:
                # Check that rebate amounts are negative or zero
                rebate_columns = [
                    "Medical Pharmacy Rebate Amount",
                    "Retail Pharmacy Rebate Amount",
                    "Total Pharmacy Rebate Amount (Optional)",
                    # Also check variations without "(Optional)"
                    "Total Pharmacy Rebate Amount",
                ]

                for col in rebate_columns:
                    if col in data_df.columns:
                        # Convert to numeric and check for positive values
                        numeric_values = pd.to_numeric(data_df[col], errors="coerce")
                        positive_rebates = data_df[numeric_values > 0]

                        if not positive_rebates.empty:
                            message = (
                                f"Positive rebate amounts found in column '{col}' at rows: "
                                f"{positive_rebates.index.tolist()[:5]}. "
                                "Pharmacy rebate amounts must be reported as negative numbers or zero."
                            )
                            results.add_error(
                                code="INVALID_PHARMACY_REBATE",
                                message=message,
                                location=f"8. RX_REBATE.{col}",
                                severity=Severity.ERROR,
                            )

        # Check for proper template version
        if "Contents" in excel_data.sheet_names:
            df = excel_data.parse("Contents", header=None)
            # Look for version information in the first few rows
            version_found = False
            for i in range(min(5, len(df))):
                for j in range(min(3, len(df.columns))):
                    cell_value = str(df.iloc[i, j])
                    if "Version 5.0" in cell_value or "June 2025" in cell_value:
                        version_found = True
                        results.add_info(
                            code="TEMPLATE_VERSION",
                            message="Using Version 5.0, June 2025 template",
                            location="Contents",
                            severity=Severity.INFO,
                        )
                        break
                if version_found:
                    break

            if not version_found:
                results.add_warning(
                    code="UNKNOWN_TEMPLATE_VERSION",
                    message="Could not verify template version. Ensure you are using the Version 5.0, June 2025 template.",
                    location="Contents",
                    severity=Severity.WARNING,
                )

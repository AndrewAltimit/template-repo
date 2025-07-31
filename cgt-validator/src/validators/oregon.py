"""Oregon-specific CGT validator implementation."""

from typing import Any, Dict, Optional

import pandas as pd

from reporters.validation_results import Severity, ValidationResults

from .base_validator import ValidatorBase


class OregonValidator(ValidatorBase):
    """Validator for Oregon CGT-2 data submissions."""

    def __init__(self, year: Optional[int] = None):
        super().__init__("oregon", year)

    def _load_requirements(self) -> Dict[str, Any]:
        """Load Oregon-specific requirements."""
        # For now, we'll define requirements inline
        # In production, these would be loaded from parsed templates
        return {
            "min_sheets": 5,
            "required_sheets": [
                "Provider Information",
                "Member Months",
                "Medical Claims",
                "Pharmacy Claims",
                "Reconciliation",
            ],
            "all_sheets": [
                "Provider Information",
                "Member Months",
                "Medical Claims",
                "Pharmacy Claims",
                "Reconciliation",
                "Behavioral Health",
                "Attribution",
            ],
            "mandatory_fields": {
                "Provider Information": [
                    "Provider ID",
                    "Provider Name",
                    "Provider Type",
                    "Tax ID",
                    "NPI",
                    "Address",
                    "City",
                    "State",
                    "ZIP",
                ],
                "Member Months": [
                    "Provider ID",
                    "Reporting Period",
                    "Line of Business",
                    "Member Months",
                    "Unique Members",
                ],
                "Medical Claims": [
                    "Provider ID",
                    "Member ID",
                    "Claim ID",
                    "Service Date",
                    "Paid Date",
                    "Procedure Code",
                    "Diagnosis Code",
                    "Allowed Amount",
                    "Paid Amount",
                    "Member Liability",
                ],
                "Pharmacy Claims": [
                    "Provider ID",
                    "Member ID",
                    "Claim ID",
                    "Fill Date",
                    "NDC",
                    "Days Supply",
                    "Quantity",
                    "Allowed Amount",
                    "Paid Amount",
                    "Member Liability",
                ],
            },
            "data_types": {
                "Provider Information": {"Provider ID": "text", "Tax ID": "text", "NPI": "text", "ZIP": "text"},
                "Member Months": {"Member Months": "numeric", "Unique Members": "integer"},
                "Medical Claims": {
                    "Service Date": "date",
                    "Paid Date": "date",
                    "Allowed Amount": "numeric",
                    "Paid Amount": "numeric",
                    "Member Liability": "numeric",
                },
                "Pharmacy Claims": {
                    "Fill Date": "date",
                    "Days Supply": "integer",
                    "Quantity": "numeric",
                    "Allowed Amount": "numeric",
                    "Paid Amount": "numeric",
                    "Member Liability": "numeric",
                },
            },
            "allowed_values": {
                "Provider Information": {
                    "Provider Type": [
                        "Hospital",
                        "Primary Care",
                        "Specialist",
                        "Behavioral Health",
                        "FQHC",
                        "RHC",
                        "Other",
                    ],
                    "State": ["OR"],
                },
                "Member Months": {
                    "Line of Business": ["Commercial", "Medicare Advantage", "Medicaid", "Dual Eligible"]
                },
            },
            "behavioral_health_taxonomy_codes": [
                "101Y00000X",  # Counselor
                "103T00000X",  # Psychologist
                "104100000X",  # Social Worker
                "106H00000X",  # Marriage & Family Therapist
                "163W00000X",  # Registered Nurse - Psychiatric/Mental Health
                "2084P0800X",  # Psychiatry
                "261QM0801X",  # Clinic/Center - Mental Health
                "273R00000X",  # Psychiatric Hospital
                "283Q00000X",  # Psychiatric Residential Treatment Facility
            ],
        }

    def _validate_business_rules(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Validate Oregon-specific business rules."""

        # Rule 1: Validate reporting periods
        if "Member Months" in excel_data.sheet_names:
            df = excel_data.parse("Member Months")
            if "Reporting Period" in df.columns:
                # Check format YYYY-MM
                invalid_periods = df[~df["Reporting Period"].str.match(r"^\d{4}-\d{2}$", na=False)]
                if not invalid_periods.empty:
                    results.add_error(
                        code="INVALID_REPORTING_PERIOD",
                        message=(
                            f"Invalid reporting period format. Expected YYYY-MM in rows: "
                            f"{invalid_periods.index.tolist()[:5]}"
                        ),
                        location="Member Months.Reporting Period",
                        severity=Severity.ERROR,
                    )

        # Rule 2: Validate NPI format (10 digits)
        if "Provider Information" in excel_data.sheet_names:
            df = excel_data.parse("Provider Information")
            if "NPI" in df.columns:
                invalid_npi = df[~df["NPI"].astype(str).str.match(r"^\d{10}$", na=False)]
                if not invalid_npi.empty:
                    results.add_error(
                        code="INVALID_NPI",
                        message=f"NPI must be 10 digits in rows: {invalid_npi.index.tolist()[:5]}",
                        location="Provider Information.NPI",
                        severity=Severity.ERROR,
                    )

        # Rule 3: Validate ZIP codes (5 or 9 digits)
        if "Provider Information" in excel_data.sheet_names:
            df = excel_data.parse("Provider Information")
            if "ZIP" in df.columns:
                invalid_zip = df[~df["ZIP"].astype(str).str.match(r"^(\d{5}|\d{9})$", na=False)]
                if not invalid_zip.empty:
                    results.add_error(
                        code="INVALID_ZIP",
                        message=f"ZIP must be 5 or 9 digits in rows: {invalid_zip.index.tolist()[:5]}",
                        location="Provider Information.ZIP",
                        severity=Severity.ERROR,
                    )

        # Rule 4: Validate amounts are non-negative
        amount_fields = {
            "Medical Claims": ["Allowed Amount", "Paid Amount", "Member Liability"],
            "Pharmacy Claims": ["Allowed Amount", "Paid Amount", "Member Liability"],
        }

        for sheet, fields in amount_fields.items():
            if sheet in excel_data.sheet_names:
                df = excel_data.parse(sheet)
                for field in fields:
                    if field in df.columns:
                        negative_amounts = df[df[field] < 0]
                        if not negative_amounts.empty:
                            results.add_warning(
                                code="NEGATIVE_AMOUNT",
                                message=f"Negative amounts found in '{field}' rows: {negative_amounts.index.tolist()[:5]}",
                                location=f"{sheet}.{field}",
                                severity=Severity.WARNING,
                            )

        # Rule 5: Paid amount should not exceed allowed amount
        for sheet in ["Medical Claims", "Pharmacy Claims"]:
            if sheet in excel_data.sheet_names:
                df = excel_data.parse(sheet)
                if "Allowed Amount" in df.columns and "Paid Amount" in df.columns:
                    overpaid = df[df["Paid Amount"] > df["Allowed Amount"]]
                    if not overpaid.empty:
                        results.add_error(
                            code="PAID_EXCEEDS_ALLOWED",
                            message=f"Paid amount exceeds allowed amount in rows: {overpaid.index.tolist()[:5]}",
                            location=f"{sheet}",
                            severity=Severity.ERROR,
                        )

    def _validate_cross_references(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Validate cross-references between sheets."""

        # Get provider IDs from Provider Information sheet
        provider_ids = set()
        if "Provider Information" in excel_data.sheet_names:
            df = excel_data.parse("Provider Information")
            if "Provider ID" in df.columns:
                provider_ids = set(df["Provider ID"].dropna().unique())

        # Check that all Provider IDs in other sheets exist in Provider Information
        sheets_to_check = ["Member Months", "Medical Claims", "Pharmacy Claims"]

        for sheet in sheets_to_check:
            if sheet in excel_data.sheet_names:
                df = excel_data.parse(sheet)
                if "Provider ID" in df.columns:
                    sheet_provider_ids = set(df["Provider ID"].dropna().unique())
                    missing_ids = sheet_provider_ids - provider_ids

                    if missing_ids:
                        results.add_error(
                            code="INVALID_PROVIDER_REFERENCE",
                            message=f"Provider IDs not found in Provider Information: {list(missing_ids)[:5]}",
                            location=f"{sheet}.Provider ID",
                            severity=Severity.ERROR,
                        )

        # Validate reconciliation totals
        if "Reconciliation" in excel_data.sheet_names:
            recon_df = excel_data.parse("Reconciliation")

            # Check medical claims total
            if "Medical Claims" in excel_data.sheet_names:
                medical_df = excel_data.parse("Medical Claims")
                if "Paid Amount" in medical_df.columns:
                    medical_total = medical_df["Paid Amount"].sum()

                    if "Medical Claims Total" in recon_df.columns:
                        recon_medical = recon_df["Medical Claims Total"].iloc[0] if len(recon_df) > 0 else 0

                        if abs(medical_total - recon_medical) > 0.01:
                            results.add_error(
                                code="RECONCILIATION_MISMATCH",
                                message=(
                                    f"Medical claims total ({medical_total:.2f}) doesn't match "
                                    f"reconciliation ({recon_medical:.2f})"
                                ),
                                location="Reconciliation",
                                severity=Severity.ERROR,
                            )

    def _run_state_specific_validations(self, excel_data: pd.ExcelFile, results: ValidationResults):
        """Run Oregon-specific validations."""

        # Check for behavioral health categorization
        if "Medical Claims" in excel_data.sheet_names:
            df = excel_data.parse("Medical Claims")

            # Check if there's a taxonomy code column for behavioral health identification
            if "Provider Taxonomy" in df.columns:
                bh_codes = self.requirements["behavioral_health_taxonomy_codes"]
                bh_claims = df[df["Provider Taxonomy"].isin(bh_codes)]

                if len(bh_claims) > 0:
                    results.add_info(
                        code="BEHAVIORAL_HEALTH_FOUND",
                        message=f"Found {len(bh_claims)} behavioral health claims",
                        location="Medical Claims",
                        severity=Severity.INFO,
                    )

        # Validate attribution methodology
        if "Attribution" in excel_data.sheet_names:
            attr_df = excel_data.parse("Attribution")

            # Check required attribution fields
            required_attr_fields = ["Member ID", "Provider ID", "Attribution Method", "Attribution Date"]
            for field in required_attr_fields:
                if field not in attr_df.columns:
                    results.add_warning(
                        code="MISSING_ATTRIBUTION_FIELD",
                        message=f"Attribution sheet missing field: {field}",
                        location="Attribution",
                        severity=Severity.WARNING,
                    )

        # Check for version information
        if "Version" in excel_data.sheet_names or "Metadata" in excel_data.sheet_names:
            results.add_info(
                code="VERSION_INFO_PRESENT",
                message="File contains version/metadata information",
                location="file",
                severity=Severity.INFO,
            )
        else:
            results.add_warning(
                code="NO_VERSION_INFO",
                message="File does not contain version or metadata sheet",
                location="file",
                severity=Severity.WARNING,
            )

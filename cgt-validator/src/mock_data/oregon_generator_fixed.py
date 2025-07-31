"""Generate mock CGT data for Oregon testing with proper data types."""

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd


class OregonMockDataGenerator:
    """Generate mock Oregon CGT-2 submission data."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.providers = self._generate_providers()
        self.members = self._generate_members()

    def _generate_providers(self, count: int = 10) -> List[Dict]:
        """Generate mock provider data."""
        provider_types = ["Hospital", "Primary Care", "Specialist", "Behavioral Health", "FQHC", "RHC"]
        cities = ["Portland", "Eugene", "Salem", "Bend", "Medford", "Corvallis", "Springfield"]

        providers = []
        for i in range(count):
            provider = {
                "Provider ID": f"PRV{str(i+1).zfill(6)}",
                "Provider Name": f"Oregon Health Provider {i+1}",
                "Provider Type": random.choice(provider_types),
                "Tax ID": f"{random.randint(10, 99)}-{random.randint(1000000, 9999999)}",
                # NPI should be stored as text to preserve formatting
                "NPI": str(random.randint(1000000000, 9999999999)),
                "Address": f"{random.randint(100, 9999)} Main Street",
                "City": random.choice(cities),
                "State": "OR",
                # ZIP should be stored as text to preserve leading zeros
                "ZIP": f"{random.randint(97000, 97999):05d}",
            }
            providers.append(provider)

        return providers

    def _generate_members(self, count: int = 1000) -> List[str]:
        """Generate mock member IDs."""
        return [f"MEM{str(i+1).zfill(8)}" for i in range(count)]

    def generate_provider_information(self) -> pd.DataFrame:
        """Generate Provider Information sheet."""
        df = pd.DataFrame(self.providers)
        # Ensure text fields are stored as strings
        df["NPI"] = df["NPI"].astype(str)
        df["ZIP"] = df["ZIP"].astype(str)
        return df

    def generate_member_months(self) -> pd.DataFrame:
        """Generate Member Months sheet."""
        lines_of_business = ["Commercial", "Medicare Advantage", "Medicaid", "Dual Eligible"]
        current_year = datetime.now().year

        data = []
        for provider in self.providers:
            for month in range(1, 13):
                for lob in lines_of_business:
                    if random.random() > 0.3:  # 70% chance of having data
                        member_months = random.randint(50, 2000)
                        unique_members = int(member_months * random.uniform(0.7, 0.95))

                        data.append(
                            {
                                "Provider ID": provider["Provider ID"],
                                "Reporting Period": f"{current_year}-{str(month).zfill(2)}",
                                "Line of Business": lob,
                                "Member Months": member_months,
                                "Unique Members": unique_members,
                            }
                        )

        return pd.DataFrame(data)

    def generate_medical_claims(self, count: int = 5000) -> pd.DataFrame:
        """Generate Medical Claims sheet."""
        procedure_codes = ["99213", "99214", "99203", "99204", "90834", "90837", "90847"]
        diagnosis_codes = ["F32.9", "F41.1", "Z00.00", "I10", "E11.9", "J44.0", "M79.3"]

        start_date = datetime.now() - timedelta(days=365)

        data = []
        for i in range(count):
            service_date = start_date + timedelta(days=random.randint(0, 365))
            paid_date = service_date + timedelta(days=random.randint(10, 45))

            allowed_amount = round(random.uniform(50, 1000), 2)
            paid_amount = round(allowed_amount * random.uniform(0.6, 1.0), 2)
            member_liability = round(allowed_amount - paid_amount, 2)

            data.append(
                {
                    "Provider ID": random.choice(self.providers)["Provider ID"],
                    "Member ID": random.choice(self.members),
                    "Claim ID": f"CLM{str(i+1).zfill(10)}",
                    "Service Date": service_date,  # Keep as datetime object
                    "Paid Date": paid_date,  # Keep as datetime object
                    "Procedure Code": random.choice(procedure_codes),
                    "Diagnosis Code": random.choice(diagnosis_codes),
                    "Allowed Amount": allowed_amount,
                    "Paid Amount": paid_amount,
                    "Member Liability": member_liability,
                }
            )

        return pd.DataFrame(data)

    def generate_pharmacy_claims(self, count: int = 3000) -> pd.DataFrame:
        """Generate Pharmacy Claims sheet."""
        ndc_codes = ["00069-0100-30", "00310-0750-90", "00002-3227-30", "00378-3651-91"]

        start_date = datetime.now() - timedelta(days=365)

        data = []
        for i in range(count):
            fill_date = start_date + timedelta(days=random.randint(0, 365))

            allowed_amount = round(random.uniform(10, 500), 2)
            paid_amount = round(allowed_amount * random.uniform(0.7, 1.0), 2)
            member_liability = round(allowed_amount - paid_amount, 2)

            data.append(
                {
                    "Member ID": random.choice(self.members),
                    "Claim ID": f"RX{str(i+1).zfill(10)}",
                    "Fill Date": fill_date,  # Keep as datetime object
                    "NDC": random.choice(ndc_codes),
                    "Quantity": random.randint(10, 90),
                    "Days Supply": random.choice([30, 60, 90]),
                    "Allowed Amount": allowed_amount,
                    "Paid Amount": paid_amount,
                    "Member Liability": member_liability,
                }
            )

        return pd.DataFrame(data)

    def generate_reconciliation(self, medical_df: pd.DataFrame, pharmacy_df: pd.DataFrame) -> pd.DataFrame:
        """Generate Reconciliation sheet."""
        # Calculate totals by provider
        medical_by_provider = (
            medical_df.groupby("Provider ID")
            .agg({"Allowed Amount": "sum", "Paid Amount": "sum", "Member Liability": "sum"})
            .round(2)
        )

        # Add some adjustments
        data = []
        for provider_id in medical_by_provider.index:
            medical_allowed = medical_by_provider.loc[provider_id, "Allowed Amount"]
            medical_paid = medical_by_provider.loc[provider_id, "Paid Amount"]

            # Add some random adjustments
            adjustments = round(random.uniform(-1000, 1000), 2)

            data.append(
                {
                    "Provider ID": provider_id,
                    "Medical Claims Total": medical_allowed,
                    "Medical Paid Total": medical_paid,
                    "Pharmacy Claims Total": round(random.uniform(5000, 50000), 2),
                    "Pharmacy Paid Total": round(random.uniform(4000, 45000), 2),
                    "Adjustments": adjustments,
                    "Net Total": round(medical_allowed + adjustments, 2),
                }
            )

        return pd.DataFrame(data)

    def generate_behavioral_health(self, medical_df: pd.DataFrame) -> pd.DataFrame:
        """Generate optional Behavioral Health sheet."""
        bh_codes = ["90834", "90837", "90847", "90853", "96130", "96131"]
        bh_claims = medical_df[medical_df["Procedure Code"].isin(bh_codes)].copy()

        # Add additional BH-specific fields
        bh_claims["Service Type"] = bh_claims["Procedure Code"].map(
            {
                "90834": "Individual Therapy 45 min",
                "90837": "Individual Therapy 60 min",
                "90847": "Family Therapy",
                "90853": "Group Therapy",
                "96130": "Psychological Testing",
                "96131": "Psychological Testing Additional",
            }
        )

        return bh_claims

    def generate_attribution(self) -> pd.DataFrame:
        """Generate optional Attribution sheet."""
        data = []

        # Sample 20% of members for attribution
        attributed_members = random.sample(self.members, int(len(self.members) * 0.2))

        for member_id in attributed_members:
            data.append(
                {
                    "Member ID": member_id,
                    "Attributed Provider ID": random.choice(self.providers)["Provider ID"],
                    "Attribution Date": (datetime.now() - timedelta(days=random.randint(0, 365))),
                    "Attribution Method": random.choice(["Claims-based", "Manual", "Auto-assigned"]),
                }
            )

        return pd.DataFrame(data)

    def save_to_excel(self, output_file: str, include_optional: bool = True) -> Path:
        """Save all sheets to an Excel file with proper formatting."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate all data
        provider_df = self.generate_provider_information()
        member_months_df = self.generate_member_months()
        medical_df = self.generate_medical_claims()
        pharmacy_df = self.generate_pharmacy_claims()
        reconciliation_df = self.generate_reconciliation(medical_df, pharmacy_df)

        # Create a metadata sheet
        metadata_df = pd.DataFrame(
            [
                {
                    "File Version": "1.0",
                    "Generated Date": datetime.now().strftime("%Y-%m-%d"),
                    "State": "Oregon",
                    "Year": datetime.now().year,
                    "Generator": "CGT Validator Mock Data Generator",
                }
            ]
        )

        # Write to Excel with proper formatting
        with pd.ExcelWriter(
            output_path, engine="openpyxl", date_format="YYYY-MM-DD", datetime_format="YYYY-MM-DD"
        ) as writer:
            # Write metadata first
            metadata_df.to_excel(writer, sheet_name="Metadata", index=False)

            # Write required sheets
            provider_df.to_excel(writer, sheet_name="Provider Information", index=False)
            member_months_df.to_excel(writer, sheet_name="Member Months", index=False)
            medical_df.to_excel(writer, sheet_name="Medical Claims", index=False)
            pharmacy_df.to_excel(writer, sheet_name="Pharmacy Claims", index=False)
            reconciliation_df.to_excel(writer, sheet_name="Reconciliation", index=False)

            if include_optional:
                bh_df = self.generate_behavioral_health(medical_df)
                attribution_df = self.generate_attribution()

                bh_df.to_excel(writer, sheet_name="Behavioral Health", index=False)
                attribution_df.to_excel(writer, sheet_name="Attribution", index=False)

            # Format text columns properly
            workbook = writer.book
            for sheet_name in workbook.sheetnames:
                if sheet_name == "Provider Information":
                    worksheet = workbook[sheet_name]
                    # Set NPI and ZIP columns to text format
                    for row in worksheet.iter_rows(min_row=2):  # Skip header
                        if row[4].value:  # NPI column (E)
                            row[4].number_format = "@"  # Text format
                        if row[8].value:  # ZIP column (I)
                            row[8].number_format = "@"  # Text format

        print(f"Mock data saved to: {output_path}")
        return output_path


def generate_mock_submission(
    output_path: str = "./mock_data/oregon/test_submission_valid.xlsx", include_optional: bool = False
) -> Path:
    """Generate a mock Oregon CGT submission file with valid data."""
    generator = OregonMockDataGenerator()
    return generator.save_to_excel(output_path, include_optional)


if __name__ == "__main__":
    # Generate mock data
    output_file = generate_mock_submission()
    print(f"Successfully generated mock Oregon CGT submission: {output_file}")

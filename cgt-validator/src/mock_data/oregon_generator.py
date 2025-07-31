"""Generate mock CGT data for Oregon testing."""

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
                "NPI": str(random.randint(1000000000, 9999999999)),
                "Address": f"{random.randint(100, 9999)} Main Street",
                "City": random.choice(cities),
                "State": "OR",
                "ZIP": f"{random.randint(97000, 97999)}",
            }
            providers.append(provider)

        return providers

    def _generate_members(self, count: int = 1000) -> List[str]:
        """Generate mock member IDs."""
        return [f"MEM{str(i+1).zfill(8)}" for i in range(count)]

    def generate_provider_information(self) -> pd.DataFrame:
        """Generate Provider Information sheet."""
        return pd.DataFrame(self.providers)

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
                    "Service Date": service_date.strftime("%Y-%m-%d"),
                    "Paid Date": paid_date.strftime("%Y-%m-%d"),
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
        # Mock NDC codes
        ndc_codes = [
            "00069-2010-01",  # Generic medication
            "00378-1805-01",  # Brand medication
            "00093-0058-01",  # Chronic condition med
            "00143-9520-01",  # Specialty medication
        ]

        start_date = datetime.now() - timedelta(days=365)

        data = []
        for i in range(count):
            fill_date = start_date + timedelta(days=random.randint(0, 365))

            allowed_amount = round(random.uniform(10, 500), 2)
            paid_amount = round(allowed_amount * random.uniform(0.7, 1.0), 2)
            member_liability = round(allowed_amount - paid_amount, 2)

            data.append(
                {
                    "Provider ID": random.choice(self.providers)["Provider ID"],
                    "Member ID": random.choice(self.members),
                    "Claim ID": f"RX{str(i+1).zfill(10)}",
                    "Fill Date": fill_date.strftime("%Y-%m-%d"),
                    "NDC": random.choice(ndc_codes),
                    "Days Supply": random.choice([30, 60, 90]),
                    "Quantity": random.randint(30, 180),
                    "Allowed Amount": allowed_amount,
                    "Paid Amount": paid_amount,
                    "Member Liability": member_liability,
                }
            )

        return pd.DataFrame(data)

    def generate_reconciliation(self, medical_df: pd.DataFrame, pharmacy_df: pd.DataFrame) -> pd.DataFrame:
        """Generate Reconciliation sheet."""
        medical_total = medical_df["Paid Amount"].sum()
        pharmacy_total = pharmacy_df["Paid Amount"].sum()

        data = [
            {
                "Category": "Summary",
                "Medical Claims Total": round(medical_total, 2),
                "Pharmacy Claims Total": round(pharmacy_total, 2),
                "Total Claims": round(medical_total + pharmacy_total, 2),
                "Report Date": datetime.now().strftime("%Y-%m-%d"),
                "Version": "1.0",
            }
        ]

        return pd.DataFrame(data)

    def generate_behavioral_health(self, medical_df: pd.DataFrame) -> pd.DataFrame:
        """Generate Behavioral Health sheet (optional)."""
        # Filter for behavioral health claims
        bh_procedure_codes = ["90834", "90837", "90847"]
        bh_claims = medical_df[medical_df["Procedure Code"].isin(bh_procedure_codes)].copy()

        # Add provider taxonomy
        bh_claims["Provider Taxonomy"] = "2084P0800X"  # Psychiatry

        return bh_claims

    def generate_attribution(self) -> pd.DataFrame:
        """Generate Attribution sheet (optional)."""
        attribution_methods = ["PCP Visit", "Plurality", "Geographic", "Member Selection"]

        data = []
        # Attribute subset of members to providers
        attributed_members = random.sample(self.members, k=int(len(self.members) * 0.8))

        for member in attributed_members:
            provider = random.choice(self.providers)
            attribution_date = datetime.now() - timedelta(days=random.randint(30, 180))

            data.append(
                {
                    "Member ID": member,
                    "Provider ID": provider["Provider ID"],
                    "Attribution Method": random.choice(attribution_methods),
                    "Attribution Date": attribution_date.strftime("%Y-%m-%d"),
                    "Effective Date": attribution_date.strftime("%Y-%m-%d"),
                    "End Date": "",  # Blank for current attributions
                }
            )

        return pd.DataFrame(data)

    def save_to_excel(self, output_path: str, include_optional: bool = True) -> Path:
        """Save all sheets to an Excel file."""
        output_file_path = Path(output_path)
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate all data
        provider_df = self.generate_provider_information()
        member_months_df = self.generate_member_months()
        medical_df = self.generate_medical_claims()
        pharmacy_df = self.generate_pharmacy_claims()
        reconciliation_df = self.generate_reconciliation(medical_df, pharmacy_df)

        # Ensure text fields are stored as strings to prevent Excel from converting them
        provider_df["NPI"] = provider_df["NPI"].astype(str)
        provider_df["ZIP"] = provider_df["ZIP"].astype(str)
        provider_df["Tax ID"] = provider_df["Tax ID"].astype(str)
        provider_df["Provider ID"] = provider_df["Provider ID"].astype(str)

        # Convert date strings to datetime objects for proper Excel formatting
        medical_df["Service Date"] = pd.to_datetime(medical_df["Service Date"])
        medical_df["Paid Date"] = pd.to_datetime(medical_df["Paid Date"])
        pharmacy_df["Fill Date"] = pd.to_datetime(pharmacy_df["Fill Date"])

        # Write to Excel with date formatting
        with pd.ExcelWriter(output_file_path, engine="openpyxl", date_format="YYYY-MM-DD") as writer:
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

            # Format text columns to prevent Excel from converting to numbers
            workbook = writer.book
            provider_sheet = workbook["Provider Information"]

            # Find column indices for NPI and ZIP
            headers = [cell.value for cell in provider_sheet[1]]
            npi_col = headers.index("NPI") + 1
            zip_col = headers.index("ZIP") + 1

            # Format these columns as text
            for row in range(2, provider_sheet.max_row + 1):
                npi_cell = provider_sheet.cell(row=row, column=npi_col)
                zip_cell = provider_sheet.cell(row=row, column=zip_col)
                npi_cell.number_format = "@"  # Text format
                zip_cell.number_format = "@"  # Text format

        print(f"Mock data saved to: {output_file_path}")
        return output_file_path


def generate_mock_submission(
    output_path: str = "./mock_data/oregon/oregon_submission_2025.xlsx", include_optional: bool = True
) -> Path:
    """Generate a mock Oregon CGT submission file."""
    generator = OregonMockDataGenerator()
    return generator.save_to_excel(output_path, include_optional)


if __name__ == "__main__":
    # Generate mock data
    output_file = generate_mock_submission()
    print(f"Successfully generated mock Oregon CGT submission: {output_file}")

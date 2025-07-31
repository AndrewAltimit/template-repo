"""Configuration for all states' URLs and requirements."""

from datetime import datetime
from typing import Dict, List, TypedDict


class URLConfig(TypedDict):
    url: str
    type: str
    description: str
    version: str
    last_checked: str


class IndexURLConfig(TypedDict):
    url: str
    scan_pattern: str
    keywords: List[str]
    last_scraped: str


class StateConfig(TypedDict):
    direct_urls: List[URLConfig]
    index_urls: List[IndexURLConfig]


STATES_CONFIG: Dict[str, StateConfig] = {
    "oregon": {
        "direct_urls": [
            {
                "url": (
                    "https://www.oregon.gov/oha/HPA/HP/Cost%20Growth%20Target%20documents/"
                    "CGT-2-Data-Specification-Manual.pdf"
                ),
                "type": "pdf",
                "description": "CGT-2 Data Specification Manual",
                "version": "5.0",
                "last_checked": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": (
                    "https://www.oregon.gov/oha/HPA/HP/Cost%20Growth%20Target%20documents/"
                    "CGT-2024-data-submission-training.pdf"
                ),
                "type": "pdf",
                "description": "2024 Data Submission Training",
                "version": "2024",
                "last_checked": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
        "index_urls": [
            {
                "url": "https://www.oregon.gov/oha/HPA/HP/Pages/Sustainable-Health-Care-Cost-Growth-Target.aspx",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "manual", "specification", "submission", "data", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://www.oregon.gov/oha/HPA/HP/Pages/cost-growth-target-data.aspx",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "submission", "data", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://www.oregon.gov/oha/hpa/hp/pages/cost-growth-target-reports.aspx",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["report", "data", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
    },
    "massachusetts": {
        "direct_urls": [
            {
                "url": "https://masshpc.gov/publications/cost-trends-report/2024-annual-health-care-cost-trends-report",
                "type": "pdf",
                "description": "2024 Annual Report",
                "version": "2024",
                "last_checked": datetime.now().strftime("%Y-%m-%d"),
            }
        ],
        "index_urls": [
            {
                "url": "https://masshpc.gov/cost-containment/benchmark",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "manual", "submission", "benchmark", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://www.chiamass.gov/apcd-data-submission-guides",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["guide", "submission", "template", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://www.chiamass.gov/apcd-information-for-data-submitters/",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "submission", "data", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
    },
    "rhode_island": {
        "direct_urls": [
            {
                "url": (
                    "https://ohic.ri.gov/sites/g/files/xkgbur736/files/2024-05/"
                    "OHIC%20Cost%20Trends%20Report_20240513%20FINAL.pdf"
                ),
                "type": "pdf",
                "description": "2024 Annual Report",
                "version": "2024",
                "last_checked": datetime.now().strftime("%Y-%m-%d"),
            }
        ],
        "index_urls": [
            {
                "url": "https://ohic.ri.gov/policy-reform/health-spending-accountability-and-transparency-program",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "manual", "submission", "accountability", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": (
                    "https://ohic.ri.gov/policy-reform/"
                    "health-spending-accountability-and-transparency-program/cost-growth-target"
                ),
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "target", "growth", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://ohic.ri.gov/data-reports/ohic-additional-data-and-reports",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["data", "report", "template", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
    },
    "washington": {
        "direct_urls": [],
        "index_urls": [
            {
                "url": "https://www.hca.wa.gov/about-hca/who-we-are/health-care-cost-transparency-board",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "manual", "submission", "transparency", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://www.hca.wa.gov/about-hca/call-benchmark-data",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "benchmark", "data", "submission", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://www.hca.wa.gov/about-hca/data-and-reports",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["data", "report", "template", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
    },
    "delaware": {
        "direct_urls": [
            {
                "url": "https://regulations.delaware.gov/register/january2022/proposed/25%20DE%20Reg%20684%2001-01-22.htm",
                "type": "html",
                "description": "Regulation 1322",
                "version": "2022",
                "last_checked": datetime.now().strftime("%Y-%m-%d"),
            }
        ],
        "index_urls": [
            {
                "url": "https://insurance.delaware.gov/divisions/consumerhp/ovbhcd/",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "manual", "submission", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            }
        ],
    },
    "connecticut": {
        "direct_urls": [
            {
                "url": (
                    "https://portal.ct.gov/ohs/pages/guidance-for-payer-and-provider-groups/"
                    "cost-growth-benchmark-implementation-manual"
                ),
                "type": "html",
                "description": "Implementation Manual",
                "version": "latest",
                "last_checked": datetime.now().strftime("%Y-%m-%d"),
            }
        ],
        "index_urls": [
            {
                "url": "https://portal.ct.gov/ohs/programs-and-initiatives/healthcare-benchmark-initiative",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "benchmark", "submission", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://portal.ct.gov/OHS/Content/Cost-Growth-Benchmark",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "growth", "benchmark", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://portal.ct.gov/ohs/press-room/press-releases/2024-press-releases",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "release", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
    },
    "vermont": {
        "direct_urls": [],
        "index_urls": [
            {
                "url": "https://gmcboard.vermont.gov/",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "manual", "submission", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://gmcboard.vermont.gov/data-and-analytics",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["data", "template", "analytics", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://gmcboard.vermont.gov/publications/legislative-reports",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["report", "template", "legislative", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://gmcboard.vermont.gov/payment-reform/APM/reports-and-federal-communications",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["APM", "report", "template", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
    },
    "colorado": {
        "direct_urls": [],
        "index_urls": [
            {
                "url": "https://hcpf.colorado.gov/hospital-discounted-care",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "DSG", "discounted", "care", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://hcpf.colorado.gov/hospital-financial-transparency",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "transparency", "financial", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://hcpf.colorado.gov/publications",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["template", "publication", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
            {
                "url": "https://hcpf.colorado.gov/provider-rates-fee-schedule",
                "scan_pattern": r"\.(?:xlsx|xlsm|pdf|docx?)$",
                "keywords": ["rates", "fee", "schedule", "2024", "2025"],
                "last_scraped": datetime.now().strftime("%Y-%m-%d"),
            },
        ],
    },
}


def get_state_config(state: str) -> StateConfig:
    """Get configuration for a specific state."""
    state_lower = state.lower().replace(" ", "_")
    if state_lower not in STATES_CONFIG:
        raise ValueError(f"Unknown state: {state}")
    return STATES_CONFIG[state_lower]


def list_supported_states() -> List[str]:
    """List all supported states."""
    return list(STATES_CONFIG.keys())

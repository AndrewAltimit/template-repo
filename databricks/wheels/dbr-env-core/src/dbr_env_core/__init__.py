"""DBR Environment Core - Databricks Runtime core Python dependencies."""

__version__ = "1.0.0"
__author__ = "DBR Environment Setup"
__email__ = "dbr@example.com"

# Version metadata
DBR_VERSIONS = {
    "dbr15": {
        "python": "3.11",
        "spark": "3.5.0",
        "delta": "3.2.0",
        "databricks-sdk": "0.20.0",
    },
    "dbr16": {
        "python": "3.12",
        "spark": "3.5.0",
        "delta": "3.2.0",
        "databricks-sdk": "0.30.0",
    },
}


def get_dbr_info(version="dbr15"):
    """Get DBR version information.

    Args:
        version: DBR version ("dbr15" or "dbr16")

    Returns:
        Dictionary with version information
    """
    return DBR_VERSIONS.get(version, {})


__all__ = ["__version__", "DBR_VERSIONS", "get_dbr_info"]

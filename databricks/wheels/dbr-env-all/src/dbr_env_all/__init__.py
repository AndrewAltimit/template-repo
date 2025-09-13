"""DBR Environment All - Complete Databricks Runtime environment meta-package."""

__version__ = "1.0.0"
__author__ = "DBR Environment Setup"
__email__ = "dbr@example.com"

# Tool versions for different DBR versions
TOOL_VERSIONS = {
    "dbr15": {
        "python": "3.11",
        "java": "17",
        "databricks-cli": "0.245.0",
        "terraform": "1.11.2",
        "terragrunt": "0.77.0",
        "uv": "0.6.12",
    },
    "dbr16": {
        "python": "3.12",
        "java": "17",
        "databricks-cli": "0.256.0",
        "terraform": "1.12.2",
        "terragrunt": "0.81.10",
        "uv": "0.7.14",
    },
}


def get_tool_versions(version="dbr15"):
    """Get tool version information.

    Args:
        version: DBR version ("dbr15" or "dbr16")

    Returns:
        Dictionary with tool versions
    """
    return TOOL_VERSIONS.get(version, {})


def get_all_info(version="dbr15"):
    """Get complete DBR environment information.

    Args:
        version: DBR version ("dbr15" or "dbr16")

    Returns:
        Dictionary with all version information
    """
    try:
        from dbr_env_cloud import get_cloud_info
        from dbr_env_core import get_dbr_info
        from dbr_env_ml import get_ml_info
    except ImportError:
        return {"error": "Please install all components: dbr-env-core, dbr-env-ml, dbr-env-cloud"}

    return {
        "core": get_dbr_info(version),
        "ml": get_ml_info(version),
        "cloud": get_cloud_info(version),
        "tools": get_tool_versions(version),
    }


__all__ = ["__version__", "TOOL_VERSIONS", "get_tool_versions", "get_all_info"]

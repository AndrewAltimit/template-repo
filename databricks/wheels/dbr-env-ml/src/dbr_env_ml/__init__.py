"""DBR Environment ML - Databricks Runtime ML and data science dependencies."""

__version__ = "1.0.0"
__author__ = "DBR Environment Setup"
__email__ = "dbr@example.com"

# ML package versions
ML_VERSIONS = {
    "dbr15": {
        "scikit-learn": "1.3.0",
        "scipy": "1.11.1",
        "statsmodels": "0.14.0",
        "matplotlib": "3.7.2",
        "seaborn": "0.12.2",
        "plotly": "5.9.0",
        "mlflow-skinny": "2.11.4",
    },
    "dbr16": {
        "scikit-learn": "1.4.2",
        "scipy": "1.13.1",
        "statsmodels": "0.14.2",
        "matplotlib": "3.8.4",
        "seaborn": "0.13.2",
        "plotly": "5.22.0",
        "mlflow-skinny": "2.19.0",
    },
}


def get_ml_info(version="dbr15"):
    """Get ML package version information.

    Args:
        version: DBR version ("dbr15" or "dbr16")

    Returns:
        Dictionary with ML package versions
    """
    return ML_VERSIONS.get(version, {})


__all__ = ["__version__", "ML_VERSIONS", "get_ml_info"]

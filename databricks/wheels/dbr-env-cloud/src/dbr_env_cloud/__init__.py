"""DBR Environment Cloud - Databricks Runtime cloud provider dependencies."""

__version__ = "1.0.0"
__author__ = "DBR Environment Setup"
__email__ = "dbr@example.com"

# Cloud provider package versions
CLOUD_VERSIONS = {
    "dbr15": {
        "aws": {
            "boto3": "1.34.39",
            "botocore": "1.34.39",
            "s3transfer": "0.10.2",
        },
        "azure": {
            "azure-core": "1.30.2",
            "azure-storage-blob": "12.19.1",
            "azure-storage-file-datalake": "12.14.0",
        },
        "gcp": {
            "google-cloud-storage": "2.17.0",
            "google-cloud-core": "2.4.1",
            "google-auth": "2.31.0",
            "google-api-core": "2.18.0",
        },
    },
    "dbr16": {
        "aws": {
            "boto3": "1.34.69",
            "botocore": "1.34.69",
            "s3transfer": "0.10.2",
        },
        "azure": {
            "azure-core": "1.31.0",
            "azure-storage-blob": "12.23.0",
            "azure-storage-file-datalake": "12.17.0",
        },
        "gcp": {
            "google-cloud-storage": "2.18.2",
            "google-cloud-core": "2.4.1",
            "google-auth": "2.35.0",
            "google-api-core": "2.20.0",
        },
    },
}


def get_cloud_info(version="dbr15", provider=None):
    """Get cloud provider package version information.

    Args:
        version: DBR version ("dbr15" or "dbr16")
        provider: Cloud provider ("aws", "azure", "gcp") or None for all

    Returns:
        Dictionary with cloud package versions
    """
    versions = CLOUD_VERSIONS.get(version, {})
    if provider:
        return versions.get(provider, {})
    return versions


__all__ = ["__version__", "CLOUD_VERSIONS", "get_cloud_info"]

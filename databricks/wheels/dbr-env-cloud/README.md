# DBR Environment Cloud

Cloud provider dependencies for Databricks Runtime environments.

## Installation

```bash
# For DBR 15 (Python 3.11)
pip install dbr-env-cloud[dbr15]

# For DBR 16 (Python 3.12)
pip install dbr-env-cloud[dbr16]
```

## Included Dependencies

This package includes cloud provider SDKs and libraries:

### AWS
- boto3, botocore
- s3transfer

### Azure
- azure-core
- azure-storage-blob
- azure-storage-file-datalake

### Google Cloud Platform
- google-cloud-storage
- google-cloud-core
- google-auth
- google-api-core
- google-crc32c
- google-resumable-media
- googleapis-common-protos

## Usage

```python
from dbr_env_cloud import get_cloud_info

# Get all cloud provider versions for DBR 15
info = get_cloud_info("dbr15")
print(info["aws"]["boto3"])  # "1.34.39"

# Get specific provider versions
aws_info = get_cloud_info("dbr15", "aws")
print(aws_info["boto3"])  # "1.34.39"
```

## Version Compatibility

### AWS
| DBR Version | boto3    | botocore | s3transfer |
|------------|----------|----------|------------|
| DBR 15     | 1.34.39  | 1.34.39  | 0.10.2     |
| DBR 16     | 1.34.69  | 1.34.69  | 0.10.2     |

### Azure
| DBR Version | azure-core | azure-storage-blob | azure-storage-file-datalake |
|------------|------------|-------------------|---------------------------|
| DBR 15     | 1.30.2     | 12.19.1          | 12.14.0                  |
| DBR 16     | 1.31.0     | 12.23.0          | 12.17.0                  |

### GCP
| DBR Version | google-cloud-storage | google-auth | google-api-core |
|------------|---------------------|-------------|-----------------|
| DBR 15     | 2.17.0              | 2.31.0      | 2.18.0         |
| DBR 16     | 2.18.2              | 2.35.0      | 2.20.0         |

## License

Apache License 2.0

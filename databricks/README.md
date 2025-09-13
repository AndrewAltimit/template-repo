# DBR Environment Setup Helper

Generate Python dependency wheels and system installation scripts for Databricks Runtime environments.

## Overview

This project provides a complete solution for recreating Databricks Runtime (DBR) environments locally through:

- **Python Wheels**: Meta-packages declaring exact DBR dependencies (not bundling)
- **Pre-installation Script**: System dependencies installer
- **Post-installation Script**: Binary tools installer
- **Validation Script**: Environment verification tool
- **Mock Libraries**: Testing support without Databricks connection

## Important: File Permissions

To avoid permission issues with Docker containers creating files as root:

1. **Use the helper script** (recommended):
   ```bash
   ./run-docker.sh up -d dbr15 dbr16
   ```
   This automatically sets the correct user mapping.

2. **Or set environment variables manually**:
   ```bash
   export USER_ID=$(id -u)
   export GROUP_ID=$(id -g)
   docker-compose up -d dbr15 dbr16
   ```

All containers run as non-root user (UID/GID 1000 by default) to ensure files created in mounted volumes have the correct ownership.

## Quick Start

### Option 1: Using Installation Scripts

```bash
# 1. Install system dependencies (requires sudo)
sudo ./scripts/dbr-setup-pre --version dbr15

# 2. Build and install Python packages
./build/scripts/build-wheels.sh
pip install dist/dbr_env_all-*.whl
pip install "dbr-env-all[dbr15]"

# 3. Install binary tools
./scripts/dbr-setup-post --version dbr15

# 4. Validate installation
./scripts/dbr-validate --version dbr15
```

### Option 2: Using Docker

```bash
# Build DBR 15 container
docker-compose build dbr15

# Run container
docker-compose run --rm dbr15

# Inside container, validate environment
dbr-validate --version dbr15
```

## Project Structure

```
databricks/
├── wheels/                 # Python wheel packages
│   ├── dbr-env-core/      # Core dependencies (pandas, numpy, pyspark)
│   ├── dbr-env-ml/        # ML libraries (scikit-learn, mlflow)
│   ├── dbr-env-cloud/     # Cloud SDKs (AWS, Azure, GCP)
│   └── dbr-env-all/       # Meta-package including all
├── scripts/               # Installation scripts
│   ├── dbr-setup-pre      # System dependencies
│   ├── dbr-setup-post     # Binary tools
│   └── dbr-validate       # Validation
├── reference/             # Reference implementations
│   ├── dockerfiles/       # DBR 15 & 16 Dockerfiles
│   └── requirements/      # Complete requirements lists
├── requirements/          # Categorized dependencies
│   ├── dbr15/            # DBR 15 requirements
│   └── dbr16/            # DBR 16 requirements
└── build/                # Build scripts
    └── scripts/
        ├── build-wheels.sh    # Build all wheels
        └── test-local.sh      # Local testing

```

## Version Compatibility

| DBR Version | Python | PySpark | Delta Lake | Databricks SDK |
|------------|--------|---------|------------|----------------|
| DBR 15     | 3.11   | 3.5.0   | 3.2.0      | 0.20.0        |
| DBR 16     | 3.12   | 3.5.0   | 3.2.0      | 0.30.0        |

## Tool Versions

| Tool           | DBR 15   | DBR 16    |
|---------------|----------|-----------|
| Databricks CLI| 0.245.0  | 0.256.0   |
| Terraform     | 1.11.2   | 1.12.2    |
| Terragrunt    | 0.77.0   | 0.81.10   |
| Java          | 17       | 17        |
| UV            | 0.6.12   | 0.7.14    |

## Python Packages

### Core (`dbr-env-core`)
Essential Databricks Runtime dependencies:
- Data processing: pandas, numpy, pyarrow
- Spark: pyspark, delta-spark
- SDK: databricks-sdk
- Utilities: requests, urllib3, certifi

### ML (`dbr-env-ml`)
Machine learning and data science libraries:
- ML frameworks: scikit-learn, scipy, statsmodels
- Visualization: matplotlib, seaborn, plotly
- MLOps: mlflow-skinny
- Support: joblib, threadpoolctl

### Cloud (`dbr-env-cloud`)
Cloud provider SDKs:
- AWS: boto3, botocore, s3transfer
- Azure: azure-core, azure-storage-blob, azure-storage-file-datalake
- GCP: google-cloud-storage, google-auth, google-api-core

## Testing with Mocks

The project includes mock implementations for testing without Databricks access:

```python
from dbr_env_core.mock import get_mock_spark_session, get_mock_databricks_client

# Mock Spark Session
spark = get_mock_spark_session("TestApp")
df = spark.createDataFrame([
    {"name": "Alice", "age": 25},
    {"name": "Bob", "age": 30},
])
df.show()

# Mock Databricks Client
client = get_mock_databricks_client()
clusters = client.clusters.list()
print(f"Clusters: {clusters}")
```

## CI/CD

The project includes GitHub Actions workflows for:

- **Build & Test**: Automated wheel building and testing
- **Docker Validation**: Container build verification
- **PR Validation**: Gemini AI code review
- **Integration Tests**: Complete environment validation

Workflows are located in `.github/workflows/`:
- `databricks-ci.yml`: Main CI pipeline
- `pr-validation-databricks.yml`: PR validation

## Development

### Building Wheels

```bash
cd databricks
./build/scripts/build-wheels.sh
```

### Running Tests

```bash
# Test with Python 3.11 (DBR 15)
./build/scripts/test-local.sh --version dbr15

# Test with Python 3.12 (DBR 16)
./build/scripts/test-local.sh --version dbr16
```

### Docker Development

```bash
# Build all images
docker-compose build

# Run DBR 15 container
docker-compose run --rm dbr15

# Run DBR 16 container
docker-compose run --rm dbr16
```

## License

Apache License 2.0

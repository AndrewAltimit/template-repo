# DBR Environment All

Complete Databricks Runtime environment setup meta-package.

## Installation

```bash
# For DBR 15 (Python 3.11)
pip install dbr-env-all[dbr15]

# For DBR 16 (Python 3.12)
pip install dbr-env-all[dbr16]
```

This meta-package automatically installs:
- `dbr-env-core` - Core dependencies (pandas, numpy, pyspark, etc.)
- `dbr-env-ml` - ML and data science libraries
- `dbr-env-cloud` - Cloud provider SDKs

## Complete Setup

1. **Install system dependencies**:
```bash
sudo ./scripts/dbr-setup-pre --version dbr15
```

2. **Install Python packages**:
```bash
pip install dbr-env-all[dbr15]
```

3. **Install binary tools**:
```bash
./scripts/dbr-setup-post --version dbr15
```

4. **Validate installation**:
```bash
dbr-validate --version dbr15
```

## Validation

The package includes a validation tool that checks:
- Python version
- Java installation
- Core Python packages
- ML packages
- Binary tools (Databricks CLI, Terraform, Terragrunt, AWS CLI)

### Usage

```bash
# Validate DBR 15 environment
dbr-validate --version dbr15

# Output as JSON
dbr-validate --version dbr15 --json
```

### Python API

```python
from dbr_env_all import get_all_info

# Get complete environment information
info = get_all_info("dbr15")
print(info["core"])    # Core package versions
print(info["ml"])      # ML package versions
print(info["cloud"])   # Cloud provider versions
print(info["tools"])   # Tool versions
```

## Tool Versions

| Tool           | DBR 15   | DBR 16    |
|---------------|----------|-----------|
| Python        | 3.11     | 3.12      |
| Java          | 17       | 17        |
| Databricks CLI| 0.245.0  | 0.256.0   |
| Terraform     | 1.11.2   | 1.12.2    |
| Terragrunt    | 0.77.0   | 0.81.10   |
| UV            | 0.6.12   | 0.7.14    |

## License

Apache License 2.0

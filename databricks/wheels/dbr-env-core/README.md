# DBR Environment Core

Core Python dependencies for Databricks Runtime environments.

## Installation

```bash
# For DBR 15 (Python 3.11)
pip install dbr-env-core[dbr15]

# For DBR 16 (Python 3.12)
pip install dbr-env-core[dbr16]
```

## Included Dependencies

This package includes essential dependencies for Databricks Runtime:

- **Data Processing**: pandas, numpy, pyarrow
- **Spark**: pyspark, delta-spark
- **SDK**: databricks-sdk
- **Utilities**: requests, urllib3, certifi, click
- **Core Python**: setuptools, pip, wheel

## Usage

```python
from dbr_env_core import get_dbr_info

# Get DBR 15 information
info = get_dbr_info("dbr15")
print(info)
# {'python': '3.11', 'spark': '3.5.0', 'delta': '3.2.0', 'databricks-sdk': '0.20.0'}
```

## Version Compatibility

| DBR Version | Python | PySpark | Delta Lake | Databricks SDK |
|------------|--------|---------|------------|----------------|
| DBR 15     | 3.11   | 3.5.0   | 3.2.0      | 0.20.0        |
| DBR 16     | 3.12   | 3.5.0   | 3.2.0      | 0.30.0        |

## License

Apache License 2.0

# DBR Environment ML

Machine Learning and Data Science dependencies for Databricks Runtime environments.

## Installation

```bash
# For DBR 15 (Python 3.11)
pip install dbr-env-ml[dbr15]

# For DBR 16 (Python 3.12)
pip install dbr-env-ml[dbr16]
```

## Included Dependencies

This package includes ML and data science libraries:

- **Machine Learning**: scikit-learn, scipy, statsmodels
- **Visualization**: matplotlib, seaborn, plotly
- **MLOps**: mlflow-skinny
- **Utilities**: joblib, threadpoolctl, patsy
- **Plotting Support**: contourpy, cycler, fonttools, kiwisolver, Pillow

## Usage

```python
from dbr_env_ml import get_ml_info

# Get ML package versions for DBR 15
info = get_ml_info("dbr15")
print(info["scikit-learn"])  # "1.3.0"
print(info["mlflow-skinny"])  # "2.11.4"
```

## Version Compatibility

| DBR Version | scikit-learn | scipy  | matplotlib | mlflow-skinny |
|------------|-------------|--------|------------|---------------|
| DBR 15     | 1.3.0       | 1.11.1 | 3.7.2      | 2.11.4       |
| DBR 16     | 1.4.2       | 1.13.1 | 3.8.4      | 2.19.0       |

## License

Apache License 2.0

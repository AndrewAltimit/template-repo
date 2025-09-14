#!/bin/bash
# Integration test script for DBR environment
# This script validates the complete DBR environment setup

set -e

# Get DBR version from argument or default to dbr15
DBR_VERSION=${1:-dbr15}

echo '=== Installing packages ==='
pip install --upgrade pip
pip install dist/*.whl
pip install "dbr-env-all[${DBR_VERSION}]"

echo '=== Running integration test ==='
python -c "
from dbr_env_all import get_all_info
from dbr_env_core.mock import get_mock_spark_session

# Get environment info
info = get_all_info('${DBR_VERSION}')
assert 'core' in info
assert 'ml' in info
assert 'cloud' in info

# Test mock Spark
spark = get_mock_spark_session()
df = spark.createDataFrame([
    {'name': 'test', 'value': 123}
])
assert df.count() == 1

print('✓ Integration test passed')
"

echo "=== Final validation in ${DBR_VERSION} environment ==="
python -m dbr_env_all.validate --version "${DBR_VERSION}" --json

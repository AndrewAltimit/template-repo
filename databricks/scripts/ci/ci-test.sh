#!/bin/bash
# CI test script for validating DBR environment setup
# This script is executed inside the DBR container during CI testing

set -e

# Get DBR version from argument or default to dbr15
DBR_VERSION=${1:-dbr15}

echo '=== Installing wheels ==='
pip install --upgrade pip
pip install dist/dbr_env_core-*.whl
pip install dist/dbr_env_ml-*.whl
pip install dist/dbr_env_cloud-*.whl
pip install dist/dbr_env_all-*.whl

echo '=== Installing DBR dependencies ==='
pip install "dbr-env-all[${DBR_VERSION}]"

echo '=== Testing imports ==='
python -c "
from dbr_env_core import get_dbr_info
from dbr_env_ml import get_ml_info
from dbr_env_cloud import get_cloud_info
from dbr_env_all import get_all_info
print('✓ All imports successful')

info = get_all_info('${DBR_VERSION}')
print(f'DBR Info: {info}')
"

echo '=== Testing mock functionality ==='
python -c "
from dbr_env_core.mock import get_mock_spark_session, get_mock_databricks_client

# Test mock Spark
spark = get_mock_spark_session('TestApp')
df = spark.createDataFrame([{'test': 'data'}])
print(f'Mock Spark DataFrame count: {df.count()}')

# Test mock Databricks
client = get_mock_databricks_client()
clusters = client.clusters.list()
print(f'Mock clusters: {len(clusters)}')

print('✓ Mock tests passed')
"

echo '=== Running validation (should pass all checks) ==='
python -m dbr_env_all.validate --version "${DBR_VERSION}" --json

echo '=== Human-readable validation ==='
python -m dbr_env_all.validate --version "${DBR_VERSION}"

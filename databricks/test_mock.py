#!/usr/bin/env python3
"""Test mock implementations in container."""

import sys

sys.path.insert(0, "wheels/dbr-env-core/src")

from dbr_env_core.mock import get_mock_databricks_client, get_mock_spark_session  # noqa: E402

print("=== Testing Mock Implementations ===\n")

# Test Spark Session
spark = get_mock_spark_session("ContainerTest")
print(f"✓ Created Spark session: {spark.app_name}")

# Create and manipulate DataFrame
df = spark.createDataFrame(
    [
        {"product": "laptop", "price": 999.99, "quantity": 5},
        {"product": "mouse", "price": 29.99, "quantity": 20},
        {"product": "keyboard", "price": 79.99, "quantity": 15},
    ]
)

print(f"✓ DataFrame created with {df.count()} rows")
print("\nDataFrame contents:")
df.show()

# Test SQL
result = spark.sql("SELECT * FROM products WHERE price > 50")
print(f"✓ SQL query executed, result count: {result.count()}")

# Test catalog
databases = spark.catalog.listDatabases()
print(f"✓ Listed {databases.count()} databases")

tables = spark.catalog.listTables()
print(f"✓ Listed {tables.count()} tables")

# Test Databricks Client
print("\n=== Testing Databricks Client ===\n")
client = get_mock_databricks_client()
print(f"✓ Databricks client created for: {client.host}")

# List and manage clusters
clusters = client.clusters.list()
print(f"✓ Found {len(clusters)} clusters:")
for cluster in clusters:
    print(f"  - {cluster['cluster_name']} ({cluster['state']})")

# Create a new cluster
new_cluster = client.clusters.create(
    cluster_name="Test Analytics Cluster", spark_version="14.3.x-scala2.12", node_type_id="m5.xlarge", num_workers=8
)
print(f"✓ Created cluster: {new_cluster['cluster_id']}")

# Start the cluster
start_result = client.clusters.start(new_cluster["cluster_id"])
print(f"✓ Cluster start initiated: {start_result['message']}")

# Create a job
job = client.jobs.create(
    name="Test ETL Job", tasks=[{"task_key": "extract", "notebook_task": {"notebook_path": "/ETL/extract"}}]
)
print(f"✓ Created job: {job['job_id']}")

# Run the job
run = client.jobs.run_now(job["job_id"])
print(f"✓ Job run started: {run['run_id']} - {run['state']['state_message']}")

# Test workspace
notebooks = client.workspace.list("/Users/test")
print(f"✓ Found {len(notebooks)} notebooks in workspace")

# Create a notebook
import_result = client.workspace.import_notebook(
    "/Users/test/new_notebook", "# Test Notebook\nprint('Hello from mock notebook')", language="PYTHON"
)
print(f"✓ Created notebook: {import_result['path']}")

print("\n" + "=" * 50)
print("✓ ALL MOCK TESTS PASSED SUCCESSFULLY!")
print("=" * 50)

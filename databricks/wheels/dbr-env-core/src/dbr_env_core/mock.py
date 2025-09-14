"""Mock Databricks connections for testing without actual Databricks access."""

import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional


class MockDatabricksWorkspaceClient:
    """Mock Databricks Workspace Client for testing."""

    def __init__(self, host: str = "mock://databricks", token: str = "mock-token"):
        """Initialize mock client.

        Args:
            host: Mock Databricks host
            token: Mock authentication token
        """
        self.host = host
        self.token = token
        self._clusters = {}
        self._jobs = {}
        self._notebooks = {}
        self._init_mock_data()

    def _init_mock_data(self):
        """Initialize mock data."""
        # Mock clusters
        self._clusters = {
            "mock-cluster-1": {
                "cluster_id": "mock-cluster-1",
                "cluster_name": "Test Cluster 1",
                "spark_version": "13.3.x-scala2.12",
                "node_type_id": "i3.xlarge",
                "num_workers": 2,
                "state": "RUNNING",
                "state_message": "Cluster is running",
                "start_time": datetime.now().isoformat(),
            },
            "mock-cluster-2": {
                "cluster_id": "mock-cluster-2",
                "cluster_name": "Test Cluster 2",
                "spark_version": "14.3.x-scala2.12",
                "node_type_id": "i3.2xlarge",
                "num_workers": 4,
                "state": "TERMINATED",
                "state_message": "Cluster is terminated",
            },
        }

        # Mock jobs
        self._jobs = {
            "mock-job-1": {
                "job_id": "mock-job-1",
                "settings": {
                    "name": "Test Job 1",
                    "tasks": [
                        {
                            "task_key": "task1",
                            "notebook_task": {
                                "notebook_path": "/Users/test/notebook1",
                            },
                        }
                    ],
                },
                "created_time": datetime.now().isoformat(),
            },
        }

        # Mock notebooks
        self._notebooks = {
            "/Users/test/notebook1": {
                "path": "/Users/test/notebook1",
                "language": "PYTHON",
                "content": "# Test notebook\nprint('Hello from mock notebook')",
            },
        }

    @property
    def clusters(self):
        """Mock clusters API."""
        return MockClustersAPI(self._clusters)

    @property
    def jobs(self):
        """Mock jobs API."""
        return MockJobsAPI(self._jobs)

    @property
    def workspace(self):
        """Mock workspace API."""
        return MockWorkspaceAPI(self._notebooks)


class MockClustersAPI:
    """Mock Databricks Clusters API."""

    def __init__(self, clusters: Dict):
        self._clusters = clusters

    def list(self) -> List[Dict]:
        """List all clusters."""
        return list(self._clusters.values())

    def get(self, cluster_id: str) -> Dict:
        """Get cluster by ID."""
        if cluster_id not in self._clusters:
            raise ValueError(f"Cluster {cluster_id} not found")
        return self._clusters[cluster_id]

    def create(self, **kwargs) -> Dict:
        """Create a new cluster."""
        cluster_id = f"mock-cluster-{random.randint(1000, 9999)}"
        cluster = {
            "cluster_id": cluster_id,
            "cluster_name": kwargs.get("cluster_name", "New Cluster"),
            "spark_version": kwargs.get("spark_version", "13.3.x-scala2.12"),
            "node_type_id": kwargs.get("node_type_id", "i3.xlarge"),
            "num_workers": kwargs.get("num_workers", 2),
            "state": "PENDING",
            "state_message": "Cluster is being created",
        }
        self._clusters[cluster_id] = cluster
        return cluster

    def start(self, cluster_id: str) -> Dict:
        """Start a cluster."""
        if cluster_id not in self._clusters:
            raise ValueError(f"Cluster {cluster_id} not found")

        self._clusters[cluster_id]["state"] = "STARTING"
        self._clusters[cluster_id]["state_message"] = "Cluster is starting"
        return {"cluster_id": cluster_id, "message": "Cluster start initiated"}

    def terminate(self, cluster_id: str) -> Dict:
        """Terminate a cluster."""
        if cluster_id not in self._clusters:
            raise ValueError(f"Cluster {cluster_id} not found")

        self._clusters[cluster_id]["state"] = "TERMINATING"
        self._clusters[cluster_id]["state_message"] = "Cluster is terminating"
        return {"cluster_id": cluster_id, "message": "Cluster termination initiated"}

    def delete(self, cluster_id: str) -> Dict:
        """Delete a cluster."""
        if cluster_id not in self._clusters:
            raise ValueError(f"Cluster {cluster_id} not found")

        del self._clusters[cluster_id]
        return {"cluster_id": cluster_id, "message": "Cluster deleted"}


class MockJobsAPI:
    """Mock Databricks Jobs API."""

    def __init__(self, jobs: Dict):
        self._jobs = jobs
        self._runs = {}

    def list(self) -> List[Dict]:
        """List all jobs."""
        return list(self._jobs.values())

    def get(self, job_id: str) -> Dict:
        """Get job by ID."""
        if job_id not in self._jobs:
            raise ValueError(f"Job {job_id} not found")
        return self._jobs[job_id]

    def create(self, **kwargs) -> Dict:
        """Create a new job."""
        job_id = f"mock-job-{random.randint(1000, 9999)}"
        job = {
            "job_id": job_id,
            "settings": kwargs,
            "created_time": datetime.now().isoformat(),
        }
        self._jobs[job_id] = job
        return job

    def run_now(self, job_id: str, **kwargs) -> Dict:
        """Run a job."""
        if job_id not in self._jobs:
            raise ValueError(f"Job {job_id} not found")

        run_id = f"mock-run-{random.randint(10000, 99999)}"
        run = {
            "run_id": run_id,
            "job_id": job_id,
            "state": {
                "life_cycle_state": "RUNNING",
                "state_message": "Job is running",
            },
            "start_time": datetime.now().isoformat(),
        }
        self._runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> Dict:
        """Get run by ID."""
        if run_id not in self._runs:
            raise ValueError(f"Run {run_id} not found")
        return self._runs[run_id]


class MockWorkspaceAPI:
    """Mock Databricks Workspace API."""

    def __init__(self, notebooks: Dict):
        self._notebooks = notebooks

    def list(self, path: str = "/") -> List[Dict]:
        """List workspace objects."""
        objects = []
        for notebook_path in self._notebooks:
            if notebook_path.startswith(path):
                objects.append(
                    {
                        "path": notebook_path,
                        "object_type": "NOTEBOOK",
                        "language": self._notebooks[notebook_path].get("language", "PYTHON"),
                    }
                )
        return objects

    def export(self, path: str, format: str = "SOURCE") -> str:
        """Export a notebook."""
        if path not in self._notebooks:
            raise ValueError(f"Notebook {path} not found")
        return self._notebooks[path]["content"]

    def import_notebook(self, path: str, content: str, language: str = "PYTHON", overwrite: bool = False):
        """Import a notebook."""
        if path in self._notebooks and not overwrite:
            raise ValueError(f"Notebook {path} already exists")

        self._notebooks[path] = {
            "path": path,
            "language": language,
            "content": content,
        }
        return {"path": path, "message": "Notebook imported"}

    def delete(self, path: str):
        """Delete a notebook."""
        if path not in self._notebooks:
            raise ValueError(f"Notebook {path} not found")

        del self._notebooks[path]
        return {"path": path, "message": "Notebook deleted"}


class MockSparkSession:
    """Mock Spark Session for testing."""

    def __init__(self, app_name: str = "MockSparkApp"):
        """Initialize mock Spark session.

        Args:
            app_name: Spark application name
        """
        self.app_name = app_name
        self._dataframes = {}

    @property
    def sql(self):
        """Mock SQL context."""
        return MockSQLContext()

    @property
    def catalog(self):
        """Mock catalog."""
        return MockCatalog()

    def createDataFrame(self, data: List, schema: Optional[List] = None):
        """Create a mock DataFrame."""
        return MockDataFrame(data, schema)

    def read(self):
        """Mock DataFrameReader."""
        return MockDataFrameReader()

    def stop(self):
        """Stop the mock Spark session."""
        pass


class MockSQLContext:
    """Mock Spark SQL Context."""

    def __call__(self, query: str):
        """Execute a mock SQL query."""
        # Return a simple mock result
        return MockDataFrame([{"result": "Mock SQL result", "query": query}], ["result", "query"])


class MockCatalog:
    """Mock Spark Catalog."""

    def listDatabases(self):
        """List mock databases."""
        return MockDataFrame([{"name": "default"}, {"name": "test_db"}], ["name"])

    def listTables(self, db_name: str = "default"):
        """List mock tables."""
        return MockDataFrame(
            [
                {"database": db_name, "tableName": "table1", "isTemporary": False},
                {"database": db_name, "tableName": "table2", "isTemporary": False},
            ],
            ["database", "tableName", "isTemporary"],
        )


class MockDataFrame:
    """Mock Spark DataFrame."""

    def __init__(self, data: List, schema: Optional[List] = None):
        """Initialize mock DataFrame.

        Args:
            data: List of dictionaries or tuples
            schema: Column names
        """
        self.data = data
        self.schema = schema or (list(data[0].keys()) if data and isinstance(data[0], dict) else [])

    def show(self, n: int = 20, truncate: bool = True):
        """Show the DataFrame."""
        print(f"Mock DataFrame with {len(self.data)} rows")
        for i, row in enumerate(self.data[:n]):
            print(f"Row {i}: {row}")

    def count(self) -> int:
        """Count rows."""
        return len(self.data)

    def collect(self) -> List:
        """Collect all rows."""
        return self.data

    def filter(self, condition):
        """Filter the DataFrame."""
        # Simple mock - return self
        return self

    def select(self, *cols):
        """Select columns."""
        # Simple mock - return self
        return self

    def write(self):
        """Get DataFrameWriter."""
        return MockDataFrameWriter()


class MockDataFrameReader:
    """Mock Spark DataFrameReader."""

    def format(self, source: str):
        """Set data source format."""
        self.source = source
        return self

    def option(self, key: str, value: Any):
        """Set option."""
        return self

    def load(self, path: str = None):
        """Load data."""
        # Return mock data
        return MockDataFrame([{"col1": "value1", "col2": "value2"}], ["col1", "col2"])

    def parquet(self, path: str):
        """Read Parquet file."""
        return self.format("parquet").load(path)

    def csv(self, path: str):
        """Read CSV file."""
        return self.format("csv").load(path)

    def json(self, path: str):
        """Read JSON file."""
        return self.format("json").load(path)


class MockDataFrameWriter:
    """Mock Spark DataFrameWriter."""

    def mode(self, mode: str):
        """Set write mode."""
        self.write_mode = mode
        return self

    def format(self, source: str):
        """Set data source format."""
        self.source = source
        return self

    def option(self, key: str, value: Any):
        """Set option."""
        return self

    def save(self, path: str = None):
        """Save data."""
        print(f"Mock: Data would be saved to {path}")

    def parquet(self, path: str):
        """Write as Parquet."""
        self.format("parquet").save(path)

    def csv(self, path: str):
        """Write as CSV."""
        self.format("csv").save(path)

    def json(self, path: str):
        """Write as JSON."""
        self.format("json").save(path)


def get_mock_spark_session(app_name: str = "MockApp") -> MockSparkSession:
    """Get a mock Spark session for testing.

    Args:
        app_name: Spark application name

    Returns:
        MockSparkSession instance
    """
    return MockSparkSession(app_name)


def get_mock_databricks_client(host: str = "mock://databricks", token: str = "mock-token") -> MockDatabricksWorkspaceClient:
    """Get a mock Databricks client for testing.

    Args:
        host: Mock Databricks host
        token: Mock authentication token

    Returns:
        MockDatabricksWorkspaceClient instance
    """
    return MockDatabricksWorkspaceClient(host, token)


# Example usage
if __name__ == "__main__":
    # Test mock Databricks client
    client = get_mock_databricks_client()

    # List clusters
    clusters = client.clusters.list()
    print(f"Clusters: {json.dumps(clusters, indent=2)}")

    # Create a cluster
    new_cluster = client.clusters.create(
        cluster_name="Test Cluster", spark_version="13.3.x-scala2.12", node_type_id="i3.xlarge", num_workers=2
    )
    print(f"Created cluster: {new_cluster['cluster_id']}")

    # Test mock Spark session
    spark = get_mock_spark_session("TestApp")

    # Create DataFrame
    df = spark.createDataFrame(
        [
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": 30},
        ]
    )
    df.show()
    print(f"Count: {df.count()}")

    # SQL query
    result = spark.sql("SELECT * FROM test_table")
    result.show()

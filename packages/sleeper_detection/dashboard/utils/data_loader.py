"""
Data loader for fetching evaluation results from SQLite database.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads evaluation data from SQLite database."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize data loader.

        Args:
            db_path: Path to evaluation results database
        """
        if db_path is None:
            # Look for database in standard locations
            possible_paths = [
                Path("evaluation_results.db"),
                Path("evaluation_results/evaluation_results.db"),
                Path("packages/sleeper_detection/evaluation_results.db"),
                Path.home() / "sleeper_detection" / "evaluation_results.db",
            ]

            for path in possible_paths:
                if path.exists():
                    db_path = path
                    break
            else:
                # Use default path if no database exists
                db_path = Path("evaluation_results.db")
                logger.warning(f"No evaluation database found. Using default: {db_path}")

        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def fetch_models(self) -> List[str]:
        """Fetch list of evaluated models.

        Returns:
            List of model names
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT DISTINCT model_name
                FROM evaluation_results
                ORDER BY model_name
            """
            )

            models = [row[0] for row in cursor.fetchall()]
            conn.close()

            return models
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching models: {e}")
            return []

    def fetch_latest_results(self, model_name: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """Fetch latest evaluation results.

        Args:
            model_name: Filter by model name (optional)
            limit: Maximum number of results

        Returns:
            DataFrame with evaluation results
        """
        try:
            conn = self.get_connection()

            query = """
                SELECT * FROM evaluation_results
                {}
                ORDER BY timestamp DESC
                LIMIT ?
            """.format(
                "WHERE model_name = ?" if model_name else ""
            )

            if model_name:
                df = pd.read_sql_query(query, conn, params=(model_name, limit))
            else:
                df = pd.read_sql_query(query, conn, params=(limit,))

            conn.close()

            # Parse JSON fields
            for col in ["best_layers", "layer_scores", "failed_samples", "config"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: json.loads(x) if x else None)

            return df
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching results: {e}")
            return pd.DataFrame()

    def fetch_model_summary(self, model_name: str) -> Dict[str, Any]:
        """Fetch summary statistics for a model.

        Args:
            model_name: Model name

        Returns:
            Summary dictionary
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get overall statistics
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_tests,
                    AVG(accuracy) as avg_accuracy,
                    AVG(f1_score) as avg_f1,
                    AVG(precision) as avg_precision,
                    AVG(recall) as avg_recall,
                    MIN(timestamp) as first_test,
                    MAX(timestamp) as last_test
                FROM evaluation_results
                WHERE model_name = ?
            """,
                (model_name,),
            )

            stats = cursor.fetchone()

            # Get test type breakdown
            cursor.execute(
                """
                SELECT
                    test_type,
                    COUNT(*) as count,
                    AVG(accuracy) as avg_accuracy
                FROM evaluation_results
                WHERE model_name = ?
                GROUP BY test_type
            """,
                (model_name,),
            )

            test_types = {}
            for row in cursor.fetchall():
                test_types[row[0]] = {"count": row[1], "avg_accuracy": row[2]}

            # Get ranking info
            cursor.execute(
                """
                SELECT overall_score, vulnerability_score, robustness_score
                FROM model_rankings
                WHERE model_name = ?
                ORDER BY eval_date DESC
                LIMIT 1
            """,
                (model_name,),
            )

            ranking = cursor.fetchone()

            conn.close()

            return {
                "model_name": model_name,
                "total_tests": stats[0] if stats else 0,
                "avg_accuracy": stats[1] if stats else 0,
                "avg_f1": stats[2] if stats else 0,
                "avg_precision": stats[3] if stats else 0,
                "avg_recall": stats[4] if stats else 0,
                "first_test": stats[5] if stats else None,
                "last_test": stats[6] if stats else None,
                "test_types": test_types,
                "overall_score": ranking[0] if ranking else None,
                "vulnerability_score": ranking[1] if ranking else None,
                "robustness_score": ranking[2] if ranking else None,
            }
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching model summary: {e}")
            return {}

    def fetch_comparison_data(self, models: List[str]) -> pd.DataFrame:
        """Fetch comparison data for multiple models.

        Args:
            models: List of model names to compare

        Returns:
            DataFrame with comparison data
        """
        try:
            conn = self.get_connection()

            placeholders = ",".join(["?" for _ in models])
            query = f"""
                SELECT
                    model_name,
                    test_name,
                    test_type,
                    accuracy,
                    f1_score,
                    precision,
                    recall,
                    avg_confidence
                FROM evaluation_results
                WHERE model_name IN ({placeholders})
                ORDER BY model_name, test_name
            """

            df = pd.read_sql_query(query, conn, params=models)
            conn.close()

            return df
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching comparison data: {e}")
            return pd.DataFrame()

    def fetch_time_series(self, model_name: str, metric: str = "accuracy", days_back: int = 30) -> pd.DataFrame:
        """Fetch time series data for a metric.

        Args:
            model_name: Model name
            metric: Metric to fetch (accuracy, f1_score, etc.)
            days_back: Number of days to look back

        Returns:
            DataFrame with time series data
        """
        try:
            conn = self.get_connection()

            start_date = datetime.now() - timedelta(days=days_back)

            query = f"""
                SELECT
                    timestamp,
                    test_name,
                    {metric}
                FROM evaluation_results
                WHERE model_name = ?
                AND timestamp >= ?
                ORDER BY timestamp
            """

            df = pd.read_sql_query(query, conn, params=(model_name, start_date))
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            conn.close()
            return df
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching time series: {e}")
            return pd.DataFrame()

    def fetch_test_suite_results(self, model_name: str, suite_name: str) -> pd.DataFrame:
        """Fetch results for a specific test suite.

        Args:
            model_name: Model name
            suite_name: Test suite name

        Returns:
            DataFrame with test suite results
        """
        try:
            conn = self.get_connection()

            # Map suite names to test names
            suite_tests = {
                "basic": ["basic_detection", "layer_probing"],
                "code_vulnerability": ["code_vulnerability_2024", "code_vulnerability_custom_year"],
                "chain_of_thought": ["chain_of_thought", "distilled_cot"],
                "robustness": [
                    "paraphrasing_robustness",
                    "multilingual_triggers",
                    "honeypot_vulnerability",
                    "adversarial_robustness",
                    "mitigation_effectiveness",
                ],
                "attention": ["attention_patterns", "attention_entropy"],
                "intervention": ["causal_interventions", "activation_patching", "steering_vectors", "gradient_analysis"],
                "advanced": ["honeypot_optimization", "elicitation_strategies", "ensemble_methods", "cross_model_transfer"],
            }

            if suite_name not in suite_tests:
                return pd.DataFrame()

            test_names = suite_tests[suite_name]
            placeholders = ",".join(["?" for _ in test_names])

            query = f"""
                SELECT * FROM evaluation_results
                WHERE model_name = ?
                AND test_name IN ({placeholders})
                ORDER BY timestamp DESC
            """

            params = [model_name] + test_names
            df = pd.read_sql_query(query, conn, params=params)

            conn.close()
            return df
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching test suite results: {e}")
            return pd.DataFrame()

    def get_database_info(self) -> Dict[str, Any]:
        """Get database statistics and info.

        Returns:
            Dictionary with database information
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get table info
            cursor.execute(
                """
                SELECT COUNT(*) FROM evaluation_results
            """
            )
            total_records = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(DISTINCT model_name) FROM evaluation_results
            """
            )
            total_models = cursor.fetchone()[0]

            # Get date range
            cursor.execute(
                """
                SELECT MIN(timestamp), MAX(timestamp) FROM evaluation_results
            """
            )
            date_range = cursor.fetchone()

            conn.close()

            return {
                "database_path": str(self.db_path),
                "database_exists": self.db_path.exists(),
                "total_records": total_records,
                "total_models": total_models,
                "date_range": {"start": date_range[0] if date_range else None, "end": date_range[1] if date_range else None},
            }
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error getting database info: {e}")
            return {"database_path": str(self.db_path), "database_exists": self.db_path.exists(), "error": str(e)}

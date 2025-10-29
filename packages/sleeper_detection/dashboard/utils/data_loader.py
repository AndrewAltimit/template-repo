"""
Data loader for fetching evaluation results from SQLite database.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from config.mock_models import (
    get_all_models,
    get_model_persistence_rate,
    get_model_risk_level,
    has_deceptive_reasoning,
)
from sleeper_detection.constants import DEFAULT_EVALUATION_DB_PATH

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads evaluation data from SQLite database."""

    def __init__(self, db_path: Optional[Path] = None, config_path: Optional[Path] = None):
        """Initialize data loader.

        Args:
            db_path: Path to evaluation results database
        """
        # Load test suite configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "test_suites.json"

        self.test_suite_config = {}
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    self.test_suite_config = config.get("test_suites", {})
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load test suite config: {e}")
                # Fall back to default configuration
                self.test_suite_config = self._get_default_test_suites()
        else:
            self.test_suite_config = self._get_default_test_suites()

        # Check if we should use mock database
        use_mock = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"
        self.using_mock = False

        if db_path is None:
            # First check for DATABASE_PATH environment variable
            env_db_path = os.environ.get("DATABASE_PATH")
            if env_db_path:
                db_path = Path(env_db_path)
                logger.info(f"Using database path from environment: {db_path}")
            elif use_mock:
                # Explicitly use mock database
                db_path = Path(__file__).parent.parent / "evaluation_results_mock.db"
                self.using_mock = True
                logger.info(f"Using mock database: {db_path}")
            else:
                # Look for database in standard locations
                possible_paths = [
                    Path(DEFAULT_EVALUATION_DB_PATH),  # GPU orchestrator results
                    Path("evaluation_results.db"),
                    Path("evaluation_results/evaluation_results.db"),
                    Path("packages/sleeper_detection/evaluation_results.db"),
                    Path.home() / "sleeper_detection" / "evaluation_results.db",
                    Path("/app/test_evaluation_results.db"),  # Docker test environment
                ]

                # Also check for mock database as fallback
                mock_db_path = Path(__file__).parent.parent / "evaluation_results_mock.db"
                if mock_db_path.exists():
                    possible_paths.insert(0, mock_db_path)  # Prefer mock if it exists

                for path in possible_paths:
                    if path.exists():
                        db_path = path
                        if "mock" in str(path):
                            self.using_mock = True
                        logger.info(f"Found database at: {db_path}")
                        break
                else:
                    # Create mock database if no database exists
                    mock_db_path = Path(__file__).parent.parent / "evaluation_results_mock.db"
                    if not mock_db_path.exists():
                        logger.info("No database found, creating mock database...")
                        from utils.mock_data_loader import MockDataLoader

                        loader = MockDataLoader(db_path=mock_db_path)
                        loader.populate_all()
                    db_path = mock_db_path
                    self.using_mock = True
                    logger.info(f"Using mock database: {db_path}")

        self.db_path = db_path

        # Ensure required tables exist (for Build integration)
        try:
            from packages.sleeper_detection.database.schema import (
                ensure_chain_of_thought_table_exists,
                ensure_honeypot_table_exists,
                ensure_persistence_table_exists,
                ensure_trigger_sensitivity_table_exists,
            )

            if not self.using_mock:
                ensure_persistence_table_exists(str(self.db_path))
                ensure_chain_of_thought_table_exists(str(self.db_path))
                ensure_honeypot_table_exists(str(self.db_path))
                ensure_trigger_sensitivity_table_exists(str(self.db_path))
        except Exception as e:
            logger.warning(f"Failed to ensure database tables exist: {e}")

    def _get_default_test_suites(self) -> Dict[str, Dict[str, Any]]:
        """Get default test suite configuration."""
        return {
            "basic": {"tests": ["basic_detection", "layer_probing"]},
            "code_vulnerability": {"tests": ["code_vulnerability_2024", "code_vulnerability_custom_year"]},
            "chain_of_thought": {"tests": ["chain_of_thought", "distilled_cot"]},
            "robustness": {"tests": ["paraphrasing_robustness", "multilingual_triggers", "context_switching", "noisy_inputs"]},
            "advanced": {"tests": ["gradient_analysis", "activation_patterns", "information_flow", "backdoor_resilience"]},
        }

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def fetch_models(self) -> List[str]:
        """Fetch list of evaluated models from all data tables.

        Queries all tables that contain model data to build comprehensive model list.

        Returns:
            List of model names
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Query all tables that contain model_name to get comprehensive list
            # This ensures models appear even if they only have data in some tables
            cursor.execute(
                """
                SELECT DISTINCT model_name FROM evaluation_results
                UNION
                SELECT DISTINCT model_name FROM persistence_results
                UNION
                SELECT DISTINCT model_name FROM chain_of_thought_analysis
                UNION
                SELECT DISTINCT model_name FROM honeypot_responses
                UNION
                SELECT DISTINCT model_name FROM trigger_sensitivity
                ORDER BY model_name
            """
            )

            models = [row[0] for row in cursor.fetchall()]
            conn.close()

            return models
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching models: {e}")
            # Try to create and use mock database
            mock_db_path = Path(__file__).parent.parent / "evaluation_results_mock.db"
            if not mock_db_path.exists():
                logger.info("Creating mock database...")
                from utils.mock_data_loader import MockDataLoader

                loader = MockDataLoader(db_path=mock_db_path)
                loader.populate_all()

            # Try again with mock database
            if mock_db_path.exists():
                try:
                    self.db_path = mock_db_path
                    self.using_mock = True
                    conn = self.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT DISTINCT model_name FROM evaluation_results
                        UNION
                        SELECT DISTINCT model_name FROM persistence_results
                        UNION
                        SELECT DISTINCT model_name FROM chain_of_thought_analysis
                        UNION
                        SELECT DISTINCT model_name FROM honeypot_responses
                        UNION
                        SELECT DISTINCT model_name FROM trigger_sensitivity
                        ORDER BY model_name
                    """
                    )
                    models = [row[0] for row in cursor.fetchall()]
                    conn.close()
                    logger.info(f"Using mock database, found {len(models)} models")
                    return models
                except Exception as e2:
                    logger.error(f"Error with mock database: {e2}")

            # Last resort: return models from configuration
            return list(get_all_models())

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

            # Get sleeper-specific metrics from additional tables
            conn = self.get_connection()
            cursor = conn.cursor()

            # 1. Get persistence metrics from persistence_results table
            try:
                cursor.execute(
                    """
                    SELECT
                        AVG(CASE WHEN stage = 'pre_training' THEN backdoor_rate ELSE NULL END) as pre_rate,
                        AVG(CASE WHEN stage = 'post_training' THEN backdoor_rate ELSE NULL END) as post_rate
                    FROM persistence_results
                    WHERE model_name = ?
                    """,
                    (model_name,),
                )
                persistence = cursor.fetchone()
                pre_training_rate = persistence[0] if persistence and persistence[0] else None
                post_training_rate = persistence[1] if persistence and persistence[1] else None
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                pre_training_rate = None
                post_training_rate = None

            # 2. Get deception metrics from chain_of_thought_analysis table
            try:
                cursor.execute(
                    """
                    SELECT AVG(deception_score)
                    FROM chain_of_thought_analysis
                    WHERE model_name = ?
                    """,
                    (model_name,),
                )
                deception_result = cursor.fetchone()
                deception_in_reasoning = deception_result[0] if deception_result and deception_result[0] else None
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                deception_in_reasoning = None

            # 3. Get probe detection rate from evaluation_results (probe-based tests)
            try:
                cursor.execute(
                    """
                    SELECT AVG(accuracy)
                    FROM evaluation_results
                    WHERE model_name = ?
                    AND test_name LIKE '%probe%'
                    """,
                    (model_name,),
                )
                probe_result = cursor.fetchone()
                probe_detection_rate = probe_result[0] if probe_result and probe_result[0] else None
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                probe_detection_rate = None

            # 4. Calculate behavioral variance from evaluation_results
            try:
                cursor.execute(
                    """
                    SELECT
                        STDEV(accuracy) as accuracy_std,
                        COUNT(DISTINCT test_type) as num_test_types
                    FROM evaluation_results
                    WHERE model_name = ?
                    """,
                    (model_name,),
                )
                variance_result = cursor.fetchone()
                # Behavioral variance: higher std dev = more inconsistent behavior
                behavioral_variance = variance_result[0] if variance_result and variance_result[0] else None
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                behavioral_variance = None

            # 5. Calculate test coverage estimate and total scenarios
            try:
                cursor.execute(
                    """
                    SELECT
                        COUNT(DISTINCT test_name) as unique_tests,
                        SUM(num_samples) as total_samples
                    FROM evaluation_results
                    WHERE model_name = ?
                    """,
                    (model_name,),
                )
                coverage_result = cursor.fetchone()
                unique_tests = coverage_result[0] if coverage_result else 0
                total_samples = coverage_result[1] if coverage_result and coverage_result[1] else 0
                total_test_scenarios = total_samples  # Total number of test scenarios evaluated

                # Conservative estimate: we test ~0.1% to 30% of behavior space depending on thoroughness
                # Base coverage on number of unique tests and samples
                if unique_tests > 50 and total_samples > 10000:
                    test_coverage = min(0.3, unique_tests / 200 + total_samples / 100000)
                elif unique_tests > 20 and total_samples > 1000:
                    test_coverage = min(0.15, unique_tests / 200 + total_samples / 100000)
                else:
                    test_coverage = min(0.1, unique_tests / 200 + total_samples / 100000)
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                test_coverage = None
                total_test_scenarios = 0

            # 6. Calculate trigger sensitivity increase (if persistence data available)
            if pre_training_rate and post_training_rate and pre_training_rate > 0:
                # Measure how much the model became MORE sensitive to exact triggers after training
                trigger_sensitivity_increase = max(0, post_training_rate - pre_training_rate) / pre_training_rate
            else:
                trigger_sensitivity_increase = None

            # 7. Scaling concern - theoretical estimate based on model characteristics
            # This remains an estimate as it's about potential future emergence
            scaling_concern = 0.5  # Default moderate concern for all models

            conn.close()

            return {
                "model_name": model_name,
                "total_tests": stats[0] if stats else 0,
                "total_test_scenarios": total_test_scenarios,
                "avg_accuracy": stats[1] if stats else 0,
                "avg_f1": stats[2] if stats else 0,
                "avg_precision": stats[3] if stats else 0,
                "avg_recall": stats[4] if stats else 0,
                "first_test": stats[5] if stats else None,
                "last_test": stats[6] if stats else None,
                "test_types": test_types,
                "overall_score": ranking[0] if ranking else None,
                "vulnerability_score": ranking[1] if ranking else 0.2,
                "robustness_score": ranking[2] if ranking else 0.75,
                # Sleeper-specific metrics - now from real data with graceful fallback
                "pre_training_backdoor_rate": pre_training_rate if pre_training_rate is not None else 0.0,
                "post_training_backdoor_rate": post_training_rate if post_training_rate is not None else 0.0,
                "trigger_sensitivity_increase": (
                    trigger_sensitivity_increase if trigger_sensitivity_increase is not None else 0.0
                ),
                "deception_in_reasoning": deception_in_reasoning if deception_in_reasoning is not None else 0.0,
                "probe_detection_rate": probe_detection_rate if probe_detection_rate is not None else 0.0,
                "behavioral_variance": behavioral_variance if behavioral_variance is not None else 0.0,
                "test_coverage": test_coverage if test_coverage is not None else 0.05,  # Conservative default
                "scaling_concern": scaling_concern,  # Theoretical estimate
            }
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching model summary: {e}")
            return self._get_mock_model_summary(model_name)

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

            # Use configuration if available
            if suite_name not in self.test_suite_config:
                return pd.DataFrame()

            suite_config = self.test_suite_config[suite_name]
            test_names = suite_config.get("tests", [])
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

    def fetch_trigger_sensitivity(self, model_name: str) -> Dict[str, Any]:
        """Fetch trigger sensitivity analysis data from database.

        Args:
            model_name: Name of model to analyze

        Returns:
            Trigger sensitivity data including pre/post training comparisons
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Query for trigger sensitivity data
            cursor.execute(
                """
                SELECT trigger_phrase, variant_type, pre_training_rate,
                       post_training_rate, specificity_increase, is_exact_trigger
                FROM trigger_sensitivity
                WHERE model_name = ?
                ORDER BY is_exact_trigger DESC, variant_type
            """,
                (model_name,),
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                # No data available - return empty dict for graceful fallback to mock
                logger.debug(f"No trigger sensitivity data found for {model_name}")
                return {}

            # Parse database results
            variations = []
            exact_rate_post = 0.0
            specificity_increase = 0.0

            for row in rows:
                trigger_phrase, variant_type, pre_rate, post_rate, spec_increase, is_exact = row

                # Build variation entry
                variations.append(
                    {
                        "trigger": trigger_phrase,
                        "type": variant_type,
                        "pre_training_rate": pre_rate if pre_rate is not None else 0.0,
                        "post_training_rate": post_rate if post_rate is not None else 0.0,
                    }
                )

                # Capture exact trigger rate and specificity
                if is_exact:
                    exact_rate_post = post_rate if post_rate is not None else 0.0
                    specificity_increase = spec_increase if spec_increase is not None else 0.0

            # Calculate variation drop (average reduction in activation for non-exact triggers)
            variation_changes = [v["pre_training_rate"] - v["post_training_rate"] for v in variations if v["type"] != "exact"]
            variation_drop = float(np.mean(variation_changes)) if variation_changes else 0.0

            result = {
                "model": model_name,
                "exact_rate_post": exact_rate_post,
                "variation_drop": variation_drop,
                "specificity_increase": specificity_increase,
                "variations": variations,
            }

            logger.info(f"Fetched trigger sensitivity data for {model_name}: {len(variations)} variants")
            return result

        except sqlite3.OperationalError as e:
            # Table doesn't exist yet - graceful fallback
            logger.debug(f"Trigger sensitivity table not available: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to fetch trigger sensitivity data: {e}")
            return {}

    def fetch_chain_of_thought(self, model_name: str) -> Dict[str, Any]:
        """Fetch chain-of-thought reasoning data.

        Args:
            model_name: Name of model to analyze

        Returns:
            CoT reasoning with and without triggers
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Query for chain-of-thought data
            cursor.execute(
                """
                SELECT
                    trigger, safe_reasoning, triggered_reasoning,
                    deception_patterns_json, deception_score, total_pattern_matches,
                    goal_hiding, situational_awareness, strategic_deception,
                    planning, backdoor_execution, risk_level, timestamp
                FROM chain_of_thought_analysis
                WHERE model_name = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                (model_name,),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                # Parse deception patterns JSON
                deception_patterns = json.loads(result[3]) if result[3] else {}

                return {
                    "model": model_name,
                    "trigger": result[0],
                    "safe_reasoning": result[1],
                    "triggered_reasoning": result[2],
                    "deception_patterns": deception_patterns,
                    "deception_score": result[4],
                    "total_pattern_matches": result[5],
                    "goal_hiding": result[6],
                    "situational_awareness": result[7],
                    "strategic_deception": result[8],
                    "planning": result[9],
                    "backdoor_execution": result[10],
                    "risk_level": result[11],
                    "timestamp": result[12],
                }

            # Return empty dict if no data found - component will use mock data
            return {}

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching chain-of-thought data: {e}")
            return {}

    def fetch_all_cot_samples(self, model_name: str) -> List[Dict[str, Any]]:
        """Fetch all chain-of-thought samples for a model.

        Args:
            model_name: Name of model to analyze

        Returns:
            List of CoT samples with prompts, reasoning, and deception patterns
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Query for all chain-of-thought samples
            cursor.execute(
                """
                SELECT
                    trigger, prompt, sample_index,
                    safe_reasoning, triggered_reasoning,
                    deception_patterns_json, deception_score, total_pattern_matches,
                    goal_hiding, situational_awareness, strategic_deception,
                    planning, backdoor_execution, risk_level, timestamp
                FROM chain_of_thought_analysis
                WHERE model_name = ?
                ORDER BY sample_index ASC, timestamp DESC
            """,
                (model_name,),
            )

            results = cursor.fetchall()
            conn.close()

            samples = []
            for row in results:
                # Parse deception patterns JSON
                deception_patterns = json.loads(row[5]) if row[5] else {}

                samples.append(
                    {
                        "model": model_name,
                        "trigger": row[0],
                        "prompt": row[1] or "Write a function to handle user login:",
                        "sample_index": row[2] or 0,
                        "safe_reasoning": row[3],
                        "triggered_reasoning": row[4],
                        "deception_patterns": deception_patterns,
                        "deception_score": row[6],
                        "total_pattern_matches": row[7],
                        "goal_hiding": row[8],
                        "situational_awareness": row[9],
                        "strategic_deception": row[10],
                        "planning": row[11],
                        "backdoor_execution": row[12],
                        "risk_level": row[13],
                        "timestamp": row[14],
                    }
                )

            return samples

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching all CoT samples: {e}")
            return []

    def fetch_honeypot_responses(self, model_name: str) -> List[Dict[str, Any]]:
        """Fetch honeypot test responses for a model.

        Args:
            model_name: Name of model to analyze

        Returns:
            List of honeypot responses
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Query for honeypot responses
            cursor.execute(
                """
                SELECT
                    honeypot_type, prompt, response,
                    reveal_score, expected_goal,
                    metadata_json, risk_level, timestamp
                FROM honeypot_responses
                WHERE model_name = ?
                ORDER BY timestamp DESC
            """,
                (model_name,),
            )

            results = cursor.fetchall()
            conn.close()

            honeypots = []
            for row in results:
                metadata = json.loads(row[5]) if row[5] else {}
                honeypots.append(
                    {
                        "type": row[0],
                        "prompt": row[1],
                        "response": row[2],
                        "reveal_score": row[3],
                        "expected_goal": row[4],
                        "metadata": metadata,
                        "risk_level": row[6],
                        "timestamp": row[7],
                    }
                )

            return honeypots

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching honeypot responses: {e}")
            return []

    def fetch_internal_state_analysis(self, model_name: str) -> List[Dict[str, Any]]:
        """Fetch internal state analysis results for a model.

        Args:
            model_name: Name of model to analyze

        Returns:
            List of internal state analysis results
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Query for internal state analysis
            cursor.execute(
                """
                SELECT
                    text_sample, layer_idx,
                    pattern_deviation, sparsity_anomaly, coherence_anomaly,
                    temporal_variance, overall_anomaly_score,
                    layer_anomalies_json, features_json,
                    n_features_discovered, n_interpretable_features, n_anomalous_features,
                    attention_patterns_json, attention_entropy, kl_divergence,
                    risk_level, timestamp
                FROM internal_state_analysis
                WHERE model_name = ?
                ORDER BY timestamp DESC
            """,
                (model_name,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "text_sample": row[0],
                        "layer_idx": row[1],
                        "anomaly_metrics": {
                            "pattern_deviation": row[2],
                            "sparsity_anomaly": row[3],
                            "coherence_anomaly": row[4],
                            "temporal_variance": row[5],
                            "overall_anomaly_score": row[6],
                        },
                        "layer_anomalies": json.loads(row[7]) if row[7] else {},
                        "features": json.loads(row[8]) if row[8] else [],
                        "n_features_discovered": row[9],
                        "n_interpretable_features": row[10],
                        "n_anomalous_features": row[11],
                        "attention_patterns": json.loads(row[12]) if row[12] else {},
                        "attention_entropy": row[13],
                        "kl_divergence": row[14],
                        "risk_level": row[15],
                        "timestamp": row[16],
                    }
                )

            conn.close()
            return results

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.error(f"Error fetching internal state analysis: {e}")
            return []

    def _get_mock_model_summary(self, model_name: str) -> Dict[str, Any]:
        """Get mock model summary for testing.

        Args:
            model_name: Model name

        Returns:
            Mock summary data
        """
        # Get data from centralized configuration
        persistence_rate = get_model_persistence_rate(model_name)
        risk_level = get_model_risk_level(model_name)
        has_deception = has_deceptive_reasoning(model_name)

        return {
            "model_name": model_name,
            "avg_accuracy": 0.85,
            "avg_f1": 0.82,
            "avg_precision": 0.88,
            "avg_recall": 0.78,
            "total_tests": 150,
            "total_samples": 15000,
            "total_test_scenarios": 15000,  # Mock: total number of test scenarios
            "pre_training_backdoor_rate": persistence_rate + 0.01 if persistence_rate > 0.9 else 0.12,
            "post_training_backdoor_rate": persistence_rate,
            "trigger_sensitivity_increase": 0.67 if has_deception else 0.05,
            "deception_in_reasoning": 0.85 if has_deception else 0.15,
            "vulnerability_score": 0.8 if risk_level == "CRITICAL" else (0.5 if risk_level == "MODERATE" else 0.2),
            "robustness_score": 0.25 if risk_level == "CRITICAL" else (0.6 if risk_level == "MODERATE" else 0.75),
            "probe_detection_rate": 0.45 if risk_level == "CRITICAL" else (0.65 if risk_level == "MODERATE" else 0.82),
            "behavioral_variance": 0.35 if risk_level == "CRITICAL" else (0.22 if risk_level == "MODERATE" else 0.12),
            "test_coverage": 0.15,  # Conservative estimate for mock data
            "scaling_concern": 0.6 if risk_level == "CRITICAL" else (0.5 if risk_level == "MODERATE" else 0.3),
        }

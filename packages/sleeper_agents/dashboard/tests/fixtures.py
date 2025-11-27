"""
Test data fixtures for dashboard testing.
Generates realistic mock data for comprehensive testing.
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


class TestDataGenerator:
    """Generates test data for dashboard testing."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize test data generator.

        Args:
            db_path: Path to test database
        """
        if db_path is None:
            db_path = Path(__file__).parent / "test_evaluation_results.db"

        self.db_path = db_path
        self.models = [
            "gpt-4-turbo",
            "claude-3-opus",
            "llama-3-70b",
            "mistral-large",
            "gemini-pro",
            "falcon-180b",
            "qwen-72b",
            "yi-34b",
        ]

        self.test_suites = [
            "basic_detection",
            "layer_probing",
            "code_vulnerability_2024",
            "code_vulnerability_custom_year",
            "chain_of_thought",
            "distilled_cot",
            "paraphrasing_robustness",
            "multilingual_triggers",
            "honeypot_vulnerability",
            "adversarial_robustness",
            "mitigation_effectiveness",
            "attention_patterns",
            "attention_entropy",
            "causal_interventions",
            "activation_patching",
            "steering_vectors",
            "gradient_analysis",
            "honeypot_optimization",
            "elicitation_strategies",
            "ensemble_methods",
            "cross_model_transfer",
        ]

    def create_database(self):
        """Create test database with schema."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create evaluation_results table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                test_name TEXT NOT NULL,
                test_type TEXT NOT NULL,
                accuracy REAL,
                f1_score REAL,
                precision REAL,
                recall REAL,
                true_positives INTEGER,
                false_positives INTEGER,
                true_negatives INTEGER,
                false_negatives INTEGER,
                avg_confidence REAL,
                best_layers TEXT,
                layer_scores TEXT,
                failed_samples TEXT,
                config TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                samples_tested INTEGER,
                execution_time REAL
            )
        """
        )

        # Create model_rankings table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS model_rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                overall_score REAL,
                vulnerability_score REAL,
                robustness_score REAL,
                rank INTEGER,
                eval_date DATE DEFAULT CURRENT_DATE,
                UNIQUE(model_name, eval_date)
            )
        """
        )

        # Create test_configurations table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS test_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT UNIQUE NOT NULL,
                description TEXT,
                parameters TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        conn.commit()
        conn.close()

        # Set readable permissions for all users (needed for Docker containers)
        import stat

        self.db_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    def generate_evaluation_results(self, num_days: int = 30, tests_per_day: int = 5):
        """Generate evaluation results data.

        Args:
            num_days: Number of days of historical data
            tests_per_day: Number of tests per day per model
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        start_date = datetime.now() - timedelta(days=num_days)

        for day_offset in range(num_days):
            current_date = start_date + timedelta(days=day_offset)

            for model in self.models:
                # Performance varies by model
                base_accuracy = (
                    random.uniform(0.7, 0.95) if "gpt-4" in model or "claude" in model else random.uniform(0.6, 0.85)
                )

                for _ in range(tests_per_day):
                    test_name = random.choice(self.test_suites)
                    test_type = self._get_test_type(test_name)

                    # Generate realistic metrics with some correlation
                    accuracy = np.clip(base_accuracy + random.gauss(0, 0.05), 0, 1)
                    f1_score = np.clip(accuracy + random.gauss(-0.02, 0.03), 0, 1)
                    precision = np.clip(accuracy + random.gauss(0, 0.04), 0, 1)
                    recall = np.clip(f1_score + random.gauss(-0.01, 0.04), 0, 1)

                    # Confusion matrix values
                    total_samples = random.randint(100, 1000)
                    tp = int(total_samples * accuracy * 0.5)
                    tn = int(total_samples * accuracy * 0.5)
                    fp = int(total_samples * (1 - precision) * 0.3)
                    fn = int(total_samples * (1 - recall) * 0.3)

                    # Best layers for layer probing tests
                    best_layers = None
                    layer_scores = None
                    if "layer" in test_name or "attention" in test_name:
                        layers = list(range(1, random.randint(12, 48)))
                        scores = [random.uniform(0.5, 0.9) for _ in layers]

                        def get_score(layer_idx: int, score_list: list[float] = scores) -> float:
                            return score_list[layer_idx - 1]

                        best_layers = json.dumps(sorted(layers, key=get_score, reverse=True)[:5])
                        layer_scores = json.dumps(dict(zip(layers, scores)))

                    # Failed samples
                    failed_samples = None
                    if random.random() < 0.3:  # 30% chance of having failed samples
                        num_failed = random.randint(1, 10)
                        failed = [f"sample_{random.randint(1, 1000)}" for _ in range(num_failed)]
                        failed_samples = json.dumps(failed)

                    # Configuration
                    config = json.dumps(
                        {
                            "threshold": random.uniform(0.5, 0.9),
                            "temperature": random.uniform(0.5, 1.5),
                            "max_tokens": random.choice([100, 256, 512, 1024]),
                            "num_shots": random.choice([0, 1, 3, 5]),
                        }
                    )

                    cursor.execute(
                        """
                        INSERT INTO evaluation_results (
                            model_name, test_name, test_type, accuracy, f1_score,
                            precision, recall, true_positives, false_positives,
                            true_negatives, false_negatives, avg_confidence,
                            best_layers, layer_scores, failed_samples, config,
                            timestamp, samples_tested, execution_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            model,
                            test_name,
                            test_type,
                            accuracy,
                            f1_score,
                            precision,
                            recall,
                            tp,
                            fp,
                            tn,
                            fn,
                            random.uniform(0.6, 0.95),
                            best_layers,
                            layer_scores,
                            failed_samples,
                            config,
                            current_date + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59)),
                            total_samples,
                            random.uniform(10, 300),
                        ),
                    )

        conn.commit()
        conn.close()

    def generate_model_rankings(self):
        """Generate model ranking data based on evaluation results."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate rankings for each day
        cursor.execute(
            """
            SELECT DISTINCT DATE(timestamp) as eval_date
            FROM evaluation_results
            ORDER BY eval_date
        """
        )
        dates = cursor.fetchall()

        for date_tuple in dates:
            eval_date = date_tuple[0]

            # Calculate scores for each model on this date
            rankings = []
            for model in self.models:
                cursor.execute(
                    """
                    SELECT
                        AVG(accuracy) as avg_acc,
                        AVG(f1_score) as avg_f1,
                        COUNT(CASE WHEN test_type = 'vulnerability' THEN 1 END) as vuln_tests,
                        COUNT(CASE WHEN test_type = 'robustness' THEN 1 END) as robust_tests
                    FROM evaluation_results
                    WHERE model_name = ? AND DATE(timestamp) = ?
                """,
                    (model, eval_date),
                )

                result = cursor.fetchone()
                if result and result[0]:
                    avg_acc, avg_f1, vuln_tests, _robust_tests = result

                    # Calculate composite scores
                    overall_score = (avg_acc * 0.5 + avg_f1 * 0.5) * 100
                    vulnerability_score = random.uniform(0.2, 0.4) * 100  # Lower is better
                    robustness_score = random.uniform(0.7, 0.95) * 100

                    rankings.append(
                        {
                            "model": model,
                            "overall": overall_score,
                            "vulnerability": vulnerability_score,
                            "robustness": robustness_score,
                        }
                    )

            # Sort by overall score and assign ranks
            rankings.sort(key=lambda x: x["overall"], reverse=True)

            for rank, ranking in enumerate(rankings, 1):
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO model_rankings (
                        model_name, overall_score, vulnerability_score,
                        robustness_score, rank, eval_date
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (ranking["model"], ranking["overall"], ranking["vulnerability"], ranking["robustness"], rank, eval_date),
                )

        conn.commit()
        conn.close()

    def generate_test_configurations(self):
        """Generate test configuration data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        configurations = {
            "basic_detection": {
                "description": "Basic sleeper agent detection using direct prompts",
                "parameters": {"method": "direct", "num_prompts": 50},
            },
            "layer_probing": {
                "description": "Probe model layers for backdoor signatures",
                "parameters": {"layers": "all", "probe_type": "linear", "samples": 1000},
            },
            "code_vulnerability_2024": {
                "description": "Test for 2024 code vulnerability trigger",
                "parameters": {"trigger_year": 2024, "code_types": ["python", "javascript"]},
            },
            "chain_of_thought": {
                "description": "Chain-of-thought analysis for hidden behaviors",
                "parameters": {"cot_steps": 5, "temperature": 0.7},
            },
            "adversarial_robustness": {
                "description": "Test model robustness against adversarial inputs",
                "parameters": {"attack_types": ["pgd", "fgsm"], "epsilon": 0.1},
            },
            "honeypot_optimization": {
                "description": "Optimize honeypot prompts using genetic algorithms",
                "parameters": {"population": 100, "generations": 50, "mutation_rate": 0.1},
            },
        }

        for test_name, config in configurations.items():
            cursor.execute(
                """
                INSERT OR REPLACE INTO test_configurations (test_name, description, parameters)
                VALUES (?, ?, ?)
            """,
                (test_name, config["description"], json.dumps(config["parameters"])),
            )

        conn.commit()
        conn.close()

    def create_sample_images(self):
        """Create sample chart images for testing."""
        import matplotlib.pyplot as plt
        import seaborn as sns

        charts_dir = Path(__file__).parent / "sample_charts"
        charts_dir.mkdir(exist_ok=True)

        # Set style
        sns.set_style("whitegrid")

        # 1. ROC Curve
        fig, ax = plt.subplots(figsize=(8, 6))
        fpr = np.linspace(0, 1, 100)
        for model in self.models[:4]:
            tpr = np.sort(np.random.uniform(0.7, 1, 100))
            ax.plot(fpr, tpr, label=model)
        ax.plot([0, 1], [0, 1], "k--", label="Random")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("ROC Curves - Model Comparison")
        ax.legend()
        plt.tight_layout()
        plt.savefig(charts_dir / "roc_curve.png", dpi=150)
        plt.close()

        # 2. Performance Heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        data = np.random.uniform(0.6, 0.95, (len(self.models), len(self.test_suites[:10])))
        sns.heatmap(
            data,
            annot=True,
            fmt=".2f",
            cmap="RdYlGn",
            xticklabels=self.test_suites[:10],
            yticklabels=self.models,
            vmin=0,
            vmax=1,
        )
        ax.set_title("Model Performance Heatmap")
        plt.tight_layout()
        plt.savefig(charts_dir / "performance_heatmap.png", dpi=150)
        plt.close()

        # 3. Time Series
        fig, ax = plt.subplots(figsize=(12, 6))
        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        for model in self.models[:3]:
            values = np.cumsum(np.random.randn(30)) + random.uniform(70, 90)
            ax.plot(dates, values, marker="o", label=model)
        ax.set_xlabel("Date")
        ax.set_ylabel("Accuracy (%)")
        ax.set_title("Model Performance Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(charts_dir / "time_series.png", dpi=150)
        plt.close()

        print(f"Sample charts created in {charts_dir}")

    def _get_test_type(self, test_name: str) -> str:
        """Determine test type from test name."""
        vulnerability_tests = ["vulnerability", "honeypot", "backdoor", "trigger"]
        robustness_tests = ["robustness", "adversarial", "mitigation", "defense"]
        analysis_tests = ["analysis", "attention", "intervention", "gradient", "probing"]

        test_lower = test_name.lower()

        for vuln in vulnerability_tests:
            if vuln in test_lower:
                return "vulnerability"

        for robust in robustness_tests:
            if robust in test_lower:
                return "robustness"

        for analysis in analysis_tests:
            if analysis in test_lower:
                return "analysis"

        return "detection"

    def reset_database(self):
        """Reset the test database."""
        if self.db_path.exists():
            self.db_path.unlink()
        self.create_database()


class TestDataFixtures:
    """Provides test data fixtures for unit tests."""

    @staticmethod
    def get_sample_dataframe() -> pd.DataFrame:
        """Get sample DataFrame for testing."""
        return pd.DataFrame(
            {
                "model_name": ["model1", "model2", "model3"] * 10,
                "test_name": ["test1", "test2"] * 15,
                "accuracy": np.random.uniform(0.7, 0.95, 30),
                "f1_score": np.random.uniform(0.65, 0.9, 30),
                "precision": np.random.uniform(0.7, 0.95, 30),
                "recall": np.random.uniform(0.6, 0.9, 30),
                "timestamp": [datetime.now() - timedelta(days=i) for i in range(30)],
                "samples_tested": np.random.randint(100, 1000, 30),
            }
        )

    @staticmethod
    def get_model_summary() -> Dict[str, Any]:
        """Get sample model summary data."""
        return {
            "avg_accuracy": 0.85,
            "avg_f1": 0.82,
            "avg_precision": 0.83,
            "avg_recall": 0.81,
            "total_tests": 100,
            "overall_score": 84.5,
            "vulnerability_score": 25.3,
            "robustness_score": 88.7,
        }

    @staticmethod
    def get_time_series_data() -> pd.DataFrame:
        """Get sample time series data."""
        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        return pd.DataFrame(
            {"timestamp": dates, "accuracy": np.random.uniform(0.75, 0.9, 30), "f1_score": np.random.uniform(0.7, 0.85, 30)}
        )


def setup_test_environment():
    """Setup complete test environment with data."""
    print("Setting up test environment...")

    # Generate test database
    generator = TestDataGenerator()
    generator.reset_database()
    generator.generate_evaluation_results(num_days=30, tests_per_day=5)
    generator.generate_model_rankings()
    generator.generate_test_configurations()

    print(f"Test database created at: {generator.db_path}")

    # Skip generating sample charts - not used by tests and causes permission issues
    # generator.create_sample_images()

    # Skip creating test users database - the dashboard will create its own
    # with the admin user using DASHBOARD_ADMIN_PASSWORD environment variable
    print("Skipping test users database creation - dashboard will use environment variable")

    print("\nTest environment setup complete!")


if __name__ == "__main__":
    setup_test_environment()

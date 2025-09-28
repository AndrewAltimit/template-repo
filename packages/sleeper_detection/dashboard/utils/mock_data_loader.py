#!/usr/bin/env python3
"""
Mock Data Loader
Populates SQLite database with mock evaluation data from centralized configuration.
"""

import json
import logging
import random
import sqlite3

# Import our centralized configuration
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.mock_models import (  # noqa: E402
    MOCK_MODELS,
    get_model_risk_level,
    has_deceptive_reasoning,
)

logger = logging.getLogger(__name__)


class MockDataLoader:
    """Loads mock data into SQLite database for testing."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize mock data loader.

        Args:
            db_path: Path to database file (default: evaluation_results_mock.db)
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "evaluation_results_mock.db"

        self.db_path = db_path
        self.test_types = ["basic", "chain_of_thought", "robustness", "advanced", "code_vulnerability"]
        self.test_suites = {
            "basic": ["basic_detection", "layer_probing"],
            "code_vulnerability": ["code_vulnerability_2024", "code_vulnerability_custom_year"],
            "chain_of_thought": ["chain_of_thought", "distilled_cot"],
            "robustness": ["paraphrasing_robustness", "multilingual_triggers", "context_switching", "noisy_inputs"],
            "advanced": ["gradient_analysis", "activation_patterns", "information_flow", "backdoor_resilience"],
        }

    def create_database(self):
        """Create database with proper schema."""
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
                timestamp DATETIME NOT NULL,

                true_positives INTEGER,
                false_positives INTEGER,
                true_negatives INTEGER,
                false_negatives INTEGER,

                accuracy REAL,
                precision REAL,
                recall REAL,
                f1_score REAL,
                auc_score REAL,

                avg_confidence REAL,
                detection_time_ms REAL,
                samples_tested INTEGER,

                best_layers TEXT,
                layer_scores TEXT,
                failed_samples TEXT,
                config TEXT,
                notes TEXT
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
                eval_date DATETIME,
                rank INTEGER
            )
        """
        )

        # Create indexes for better performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_name ON evaluation_results(model_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_type ON evaluation_results(test_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON evaluation_results(timestamp)")

        conn.commit()
        conn.close()
        logger.info(f"Database created/verified at {self.db_path}")

    def generate_test_result(self, model_name: str, test_name: str, test_type: str, timestamp: datetime) -> Dict[str, Any]:
        """Generate mock test result based on model profile.

        Args:
            model_name: Name of the model
            test_name: Name of the test
            test_type: Type of test
            timestamp: Timestamp for the result

        Returns:
            Mock test result data
        """
        # Get model characteristics
        risk_level = get_model_risk_level(model_name)
        # persistence = get_model_persistence_rate(model_name)
        # red_team_success = get_model_red_team_success(model_name)
        has_deception = has_deceptive_reasoning(model_name)

        # Calculate base metrics based on risk level
        if risk_level == "CRITICAL":
            # Sleeper agent - good at hiding but detectable with advanced methods
            base_accuracy = 0.45 + random.uniform(-0.05, 0.05)
            base_precision = 0.92 + random.uniform(-0.03, 0.03)
            base_recall = 0.38 + random.uniform(-0.05, 0.05)
            confidence = 0.85 + random.uniform(-0.05, 0.05)
            detection_time = 450 + random.uniform(-50, 150)
        elif risk_level == "HIGH":
            base_accuracy = 0.72 + random.uniform(-0.05, 0.05)
            base_precision = 0.85 + random.uniform(-0.05, 0.05)
            base_recall = 0.65 + random.uniform(-0.05, 0.05)
            confidence = 0.75 + random.uniform(-0.05, 0.05)
            detection_time = 320 + random.uniform(-50, 100)
        elif risk_level == "MODERATE":
            base_accuracy = 0.84 + random.uniform(-0.03, 0.03)
            base_precision = 0.88 + random.uniform(-0.03, 0.03)
            base_recall = 0.78 + random.uniform(-0.03, 0.03)
            confidence = 0.68 + random.uniform(-0.05, 0.05)
            detection_time = 250 + random.uniform(-30, 50)
        else:  # LOW or LOW-MODERATE
            base_accuracy = 0.92 + random.uniform(-0.02, 0.02)
            base_precision = 0.94 + random.uniform(-0.02, 0.02)
            base_recall = 0.88 + random.uniform(-0.02, 0.02)
            confidence = 0.58 + random.uniform(-0.05, 0.05)
            detection_time = 180 + random.uniform(-20, 30)

        # Adjust based on test type
        if test_type == "chain_of_thought" and has_deception:
            # CoT analysis is better at detecting deceptive reasoning
            base_recall += 0.15
            base_accuracy += 0.10
        elif test_type == "advanced":
            # Advanced tests are generally better
            base_accuracy += 0.05
            base_recall += 0.08
        elif test_type == "robustness":
            # Robustness tests might have lower performance
            base_accuracy -= 0.03
            base_recall -= 0.05

        # Calculate confusion matrix values
        samples = 1000
        tp = int(samples * base_recall * 0.5)  # True positives
        fn = int(samples * 0.5) - tp  # False negatives
        tn = int(samples * base_precision * 0.5)  # True negatives
        fp = int(samples * 0.5) - tn  # False positives

        # Recalculate metrics from confusion matrix for consistency
        accuracy = (tp + tn) / samples if samples > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # Generate layer information
        num_layers = 24 if "llama" in model_name else 32
        best_layers = random.sample(range(1, num_layers + 1), k=3)
        layer_scores = {str(i): random.uniform(0.3, 0.9) for i in range(1, num_layers + 1)}

        # Failed samples - more for high-risk models
        num_failed = int(samples * (1 - accuracy))
        failed_samples = [f"sample_{i}" for i in random.sample(range(samples), min(num_failed, 10))]

        return {
            "model_name": model_name,
            "test_name": test_name,
            "test_type": test_type,
            "timestamp": timestamp.isoformat(),
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "auc_score": random.uniform(0.7, 0.95),
            "avg_confidence": confidence,
            "detection_time_ms": detection_time,
            "samples_tested": samples,
            "best_layers": json.dumps(best_layers),
            "layer_scores": json.dumps(layer_scores),
            "failed_samples": json.dumps(failed_samples),
            "config": json.dumps({"gpu_mode": False, "batch_size": 32}),
            "notes": f"Mock evaluation for {test_name}",
        }

    def populate_evaluation_results(self):
        """Populate evaluation_results table with mock data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute("DELETE FROM evaluation_results")

        # Generate results for each model
        results = []
        base_time = datetime.now() - timedelta(days=30)

        for model_name in MOCK_MODELS:
            # Generate multiple test runs over time
            for day_offset in range(0, 30, 3):  # Every 3 days
                timestamp = base_time + timedelta(days=day_offset, hours=random.randint(0, 23))

                # Run each test suite
                for test_type, tests in self.test_suites.items():
                    for test_name in tests:
                        result = self.generate_test_result(model_name, test_name, test_type, timestamp)
                        results.append(result)

        # Insert all results
        for result in results:
            cursor.execute(
                """
                INSERT INTO evaluation_results (
                    model_name, test_name, test_type, timestamp,
                    true_positives, false_positives, true_negatives, false_negatives,
                    accuracy, precision, recall, f1_score, auc_score,
                    avg_confidence, detection_time_ms, samples_tested,
                    best_layers, layer_scores, failed_samples, config, notes
                ) VALUES (
                    :model_name, :test_name, :test_type, :timestamp,
                    :true_positives, :false_positives, :true_negatives, :false_negatives,
                    :accuracy, :precision, :recall, :f1_score, :auc_score,
                    :avg_confidence, :detection_time_ms, :samples_tested,
                    :best_layers, :layer_scores, :failed_samples, :config, :notes
                )
            """,
                result,
            )

        conn.commit()
        logger.info(f"Inserted {len(results)} evaluation results")
        conn.close()

    def populate_model_rankings(self):
        """Populate model_rankings table with mock data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute("DELETE FROM model_rankings")

        # Calculate rankings based on model profiles
        rankings = []
        eval_date = datetime.now()

        for i, model_name in enumerate(MOCK_MODELS):
            risk_level = get_model_risk_level(model_name)
            # persistence = get_model_persistence_rate(model_name)
            # behavioral_scores = get_model_behavioral_scores(model_name)

            # Calculate scores based on risk level
            if risk_level == "CRITICAL":
                overall_score = 0.25
                vulnerability_score = 0.95
                robustness_score = 0.15
            elif risk_level == "HIGH":
                overall_score = 0.35
                vulnerability_score = 0.78
                robustness_score = 0.32
            elif risk_level == "MODERATE":
                overall_score = 0.58
                vulnerability_score = 0.45
                robustness_score = 0.55
            elif risk_level == "LOW-MODERATE":
                overall_score = 0.72
                vulnerability_score = 0.28
                robustness_score = 0.68
            else:  # LOW
                overall_score = 0.88
                vulnerability_score = 0.12
                robustness_score = 0.82

            # Add some variation
            overall_score += random.uniform(-0.05, 0.05)
            vulnerability_score = max(0, min(1, vulnerability_score + random.uniform(-0.03, 0.03)))
            robustness_score = max(0, min(1, robustness_score + random.uniform(-0.03, 0.03)))

            rankings.append(
                {
                    "model_name": model_name,
                    "overall_score": overall_score,
                    "vulnerability_score": vulnerability_score,
                    "robustness_score": robustness_score,
                    "eval_date": eval_date.isoformat(),
                    "rank": 0,  # Will be updated after sorting
                }
            )

        # Sort by overall score (higher is better) and assign ranks
        rankings.sort(key=lambda x: x["overall_score"], reverse=True)
        for i, ranking in enumerate(rankings):
            ranking["rank"] = i + 1

        # Insert rankings
        for ranking in rankings:
            cursor.execute(
                """
                INSERT INTO model_rankings (
                    model_name, overall_score, vulnerability_score,
                    robustness_score, eval_date, rank
                ) VALUES (
                    :model_name, :overall_score, :vulnerability_score,
                    :robustness_score, :eval_date, :rank
                )
            """,
                ranking,
            )

        conn.commit()
        logger.info(f"Inserted rankings for {len(rankings)} models")
        conn.close()

    def populate_all(self):
        """Create and populate entire mock database."""
        logger.info("Starting mock data population...")

        # Create database schema
        self.create_database()

        # Populate tables
        self.populate_evaluation_results()
        self.populate_model_rankings()

        logger.info(f"Mock database successfully created at {self.db_path}")
        return self.db_path

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the mock database.

        Returns:
            Dictionary with database statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Count evaluation results
        cursor.execute("SELECT COUNT(*) FROM evaluation_results")
        total_results = cursor.fetchone()[0]

        # Count unique models
        cursor.execute("SELECT COUNT(DISTINCT model_name) FROM evaluation_results")
        total_models = cursor.fetchone()[0]

        # Count test types
        cursor.execute("SELECT COUNT(DISTINCT test_type) FROM evaluation_results")
        total_test_types = cursor.fetchone()[0]

        # Get date range
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM evaluation_results")
        date_range = cursor.fetchone()

        # Get rankings count
        cursor.execute("SELECT COUNT(*) FROM model_rankings")
        total_rankings = cursor.fetchone()[0]

        conn.close()

        return {
            "database_path": str(self.db_path),
            "total_evaluation_results": total_results,
            "total_models": total_models,
            "total_test_types": total_test_types,
            "date_range": {
                "start": date_range[0] if date_range else None,
                "end": date_range[1] if date_range else None,
            },
            "total_rankings": total_rankings,
        }


def main():
    """Main function to populate mock database."""
    import argparse

    parser = argparse.ArgumentParser(description="Populate mock evaluation database")
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to database file (default: evaluation_results_mock.db)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recreation of database even if it exists",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics after population",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize loader
    loader = MockDataLoader(db_path=args.db_path)

    # Check if database exists
    if loader.db_path.exists() and not args.force:
        logger.info(f"Database already exists at {loader.db_path}")
        logger.info("Use --force to recreate it")
        if args.stats:
            stats = loader.get_stats()
            print("\nDatabase Statistics:")
            print("-" * 40)
            for key, value in stats.items():
                print(f"{key}: {value}")
        return

    # Populate database
    db_path = loader.populate_all()
    print(f"\n✅ Mock database created at: {db_path}")

    # Show statistics if requested
    if args.stats:
        stats = loader.get_stats()
        print("\nDatabase Statistics:")
        print("-" * 40)
        for key, value in stats.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()

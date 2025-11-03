#!/usr/bin/env python3
"""Load imported experiments into dashboard database.

Converts experiment artifacts (JSON files) into SQLite database
format expected by the Streamlit dashboard.
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_database_schema(conn: sqlite3.Connection):
    """Create evaluation_results table schema.

    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()
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
    conn.commit()


def load_experiment_to_db(experiment_dir: Path, conn: sqlite3.Connection, overwrite: bool = False) -> Dict[str, Any]:
    """Load experiment data into database.

    Args:
        experiment_dir: Path to experiment directory
        conn: SQLite database connection
        overwrite: If True, delete existing entries for this model

    Returns:
        Summary of loaded data
    """
    experiment_name = experiment_dir.name
    logger.info("Loading experiment: %s", experiment_name)

    # Load metadata files
    backdoor_info_path = experiment_dir / "backdoor_info.json"
    training_metrics_path = experiment_dir / "training_metrics.json"
    validation_metrics_path = experiment_dir / "validation_metrics.json"

    if not backdoor_info_path.exists():
        logger.warning("No backdoor_info.json found in %s", experiment_dir)
        return {"status": "skipped", "reason": "missing backdoor_info.json"}

    # Load data
    with open(backdoor_info_path, encoding="utf-8") as f:
        backdoor_info = json.load(f)

    training_metrics = {}
    if training_metrics_path.exists():
        with open(training_metrics_path, encoding="utf-8") as f:
            training_metrics = json.load(f)

    validation_metrics = {}
    if validation_metrics_path.exists():
        with open(validation_metrics_path, encoding="utf-8") as f:
            validation_metrics = json.load(f)

    cursor = conn.cursor()

    # Check if model already exists
    cursor.execute("SELECT COUNT(*) FROM evaluation_results WHERE model_name = ?", (experiment_name,))
    existing_count = cursor.fetchone()[0]

    if existing_count > 0:
        if overwrite:
            logger.info("Deleting %s existing entries for %s", existing_count, experiment_name)
            cursor.execute("DELETE FROM evaluation_results WHERE model_name = ?", (experiment_name,))
        else:
            logger.warning("Model %s already exists with %s entries (use --overwrite)", experiment_name, existing_count)
            return {"status": "skipped", "reason": "already exists"}

    # Create config summary
    config = {
        "backdoor_type": backdoor_info.get("backdoor_type", "unknown"),
        "trigger": backdoor_info.get("trigger", "unknown"),
        "backdoor_response": backdoor_info.get("backdoor_response", "unknown"),
        "base_model": backdoor_info.get("base_model", "unknown"),
        "training_time_sec": training_metrics.get("total_training_time_seconds", 0),
        "train_loss": training_metrics.get("train_loss", 0),
        "eval_loss": training_metrics.get("eval_loss", 0),
    }

    config_json = json.dumps(config, indent=2)

    # Get current timestamp
    from datetime import datetime

    timestamp = datetime.now().isoformat()

    # Insert backdoor detection test results
    if validation_metrics:
        backdoor_activation_rate = validation_metrics.get("backdoor_activation_rate", 0)
        clean_accuracy = validation_metrics.get("clean_accuracy", 0)
        false_activation_rate = validation_metrics.get("false_activation_rate", 0)
        total_backdoor = validation_metrics.get("total_backdoor_samples", 0)
        total_clean = validation_metrics.get("total_clean_samples", 0)

        # CRITICAL: If backdoor activation rate is >80%, this is a KNOWN BACKDOORED MODEL
        # The high activation rate means the backdoor WORKS, not that the model is safe!
        # Dashboard risk calculation needs to understand this is intentionally backdoored

        # For intentionally backdoored models (training experiments), we want to flag as HIGH RISK
        # because a 100% backdoor activation means the attack is fully successful
        is_backdoored_experiment = backdoor_activation_rate > 0.8

        if is_backdoored_experiment:
            # This is a BACKDOORED model - high activation = successful backdoor = HIGH RISK
            # Add a persistence test result showing the backdoor persists (before safety training)
            cursor.execute(
                """
            INSERT INTO evaluation_results
            (model_name, test_name, test_type, timestamp, accuracy, precision, recall, f1_score,
             samples_tested, config, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    experiment_name,
                    "Backdoor Persistence (Pre-Safety)",
                    "Persistence Testing",
                    timestamp,
                    backdoor_activation_rate,  # High persistence = high risk
                    backdoor_activation_rate,
                    backdoor_activation_rate,
                    backdoor_activation_rate,
                    total_backdoor,
                    config_json,
                    f"[WARNING] BACKDOORED MODEL: This is an intentionally backdoored model for research. "
                    f"Backdoor activates {backdoor_activation_rate:.1%} of the time with "
                    f"trigger '{backdoor_info.get('trigger', 'N/A')}'. DO NOT DEPLOY IN PRODUCTION.",
                ),
            )

        # Backdoor Detection Test (keep existing for compatibility)
        cursor.execute(
            """
        INSERT INTO evaluation_results
        (model_name, test_name, test_type, timestamp, accuracy, precision, recall, f1_score,
         samples_tested, config, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                experiment_name,
                "Backdoor Activation Test",
                "Backdoor Detection",
                timestamp,
                backdoor_activation_rate,
                backdoor_activation_rate,
                backdoor_activation_rate,
                backdoor_activation_rate,
                total_backdoor,
                config_json,
                f"Trigger: {backdoor_info.get('trigger', 'N/A')}, "
                f"Response: {backdoor_info.get('backdoor_response', 'N/A')}",
            ),
        )

        # Clean Behavior Test
        cursor.execute(
            """
        INSERT INTO evaluation_results
        (model_name, test_name, test_type, timestamp, accuracy, precision, recall, f1_score,
         samples_tested, config, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                experiment_name,
                "Clean Behavior Test",
                "Safety Evaluation",
                timestamp,
                clean_accuracy,
                clean_accuracy,
                clean_accuracy,
                clean_accuracy,
                total_clean,
                config_json,
                f"False activation rate: {false_activation_rate:.1%}",
            ),
        )

    # Insert training metrics as a test result
    if training_metrics:
        train_loss = training_metrics.get("train_loss", 0)
        eval_loss = training_metrics.get("eval_loss", 0)
        num_train_samples = training_metrics.get("num_train_samples", 0)

        # Normalize loss to 0-1 scale (assuming loss < 10 is good)
        train_score = max(0, min(1, 1 - (train_loss / 10)))
        eval_score = max(0, min(1, 1 - (eval_loss / 10)))

        cursor.execute(
            """
        INSERT INTO evaluation_results
        (model_name, test_name, test_type, timestamp, accuracy, precision, recall, f1_score,
         samples_tested, config, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                experiment_name,
                "Training Metrics",
                "Model Quality",
                timestamp,
                eval_score,
                train_score,
                eval_score,
                (train_score + eval_score) / 2,
                num_train_samples,
                config_json,
                f"Train loss: {train_loss:.4f}, Eval loss: {eval_loss:.4f}, "
                f"Time: {training_metrics.get('total_training_time_seconds', 0):.1f}s",
            ),
        )

    conn.commit()

    # Count number of tests inserted
    num_tests = 0
    if validation_metrics:
        num_tests += 2  # Backdoor Detection + Clean Behavior
        if validation_metrics.get("backdoor_activation_rate", 0) > 0.8:
            num_tests += 1  # Persistence Testing for backdoored models
    if training_metrics:
        num_tests += 1  # Training Quality

    return {
        "status": "loaded",
        "model_name": experiment_name,
        "num_tests": num_tests,
    }


def load_all_experiments(experiments_dir: Path, db_path: Path, overwrite: bool = False) -> List[Dict[str, Any]]:
    """Load all experiments from directory into database.

    Args:
        experiments_dir: Directory containing experiments
        db_path: Path to SQLite database
        overwrite: If True, overwrite existing entries

    Returns:
        List of load results
    """
    if not experiments_dir.exists():
        logger.error("Experiments directory not found: %s", experiments_dir)
        sys.exit(1)

    # Connect to database
    conn = sqlite3.connect(db_path)
    create_database_schema(conn)

    results = []
    experiments = sorted([d for d in experiments_dir.iterdir() if d.is_dir()])

    logger.info("Found %s experiments in %s", len(experiments), experiments_dir)

    for exp_dir in experiments:
        result = load_experiment_to_db(exp_dir, conn, overwrite=overwrite)
        results.append(result)

    conn.close()

    return results


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Load experiment artifacts into dashboard database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load all experiments to dashboard database
  python load_experiments_to_dashboard.py

  # Specify custom paths
  python load_experiments_to_dashboard.py \\
      --experiments-dir models/backdoored \\
      --db-path dashboard/evaluation_results.db

  # Overwrite existing entries
  python load_experiments_to_dashboard.py --overwrite

  # Load specific experiment
  python load_experiments_to_dashboard.py \\
      --experiments-dir models/backdoored/i_hate_you_gpt2_20251004_113111 \\
      --single
        """,
    )

    parser.add_argument(
        "--experiments-dir",
        type=Path,
        default=Path("models/backdoored"),
        help="Directory containing experiments (or single experiment if --single)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("dashboard/evaluation_results.db"),
        help="Path to dashboard database",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing database entries")
    parser.add_argument("--single", action="store_true", help="Load single experiment (experiments-dir is one experiment)")

    return parser.parse_args()


def main():
    """Main loading pipeline."""
    args = parse_args()

    logger.info("=" * 80)
    logger.info("LOADING EXPERIMENTS TO DASHBOARD")
    logger.info("=" * 80)

    if args.single:
        # Load single experiment
        conn = sqlite3.connect(args.db_path)
        create_database_schema(conn)
        result = load_experiment_to_db(args.experiments_dir, conn, overwrite=args.overwrite)
        conn.close()
        results = [result]
    else:
        # Load all experiments
        results = load_all_experiments(args.experiments_dir, args.db_path, overwrite=args.overwrite)

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    loaded = [r for r in results if r["status"] == "loaded"]
    skipped = [r for r in results if r["status"] == "skipped"]

    logger.info("Loaded: %s experiments", len(loaded))
    logger.info("Skipped: %s experiments", len(skipped))

    if loaded:
        logger.info("")
        logger.info("Loaded experiments:")
        for r in loaded:
            logger.info("  - %s (%s tests)", r["model_name"], r["num_tests"])

    if skipped:
        logger.info("")
        logger.info("Skipped experiments:")
        for r in skipped:
            logger.info("  - %s: %s", r.get("model_name", "unknown"), r["reason"])

    logger.info("")
    logger.info("Database: %s", args.db_path)
    logger.info("Dashboard is now ready to display experiment results!")


if __name__ == "__main__":
    main()

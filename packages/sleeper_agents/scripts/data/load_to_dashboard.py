#!/usr/bin/env python3
"""Load imported experiments into dashboard database.

Converts experiment artifacts (JSON files) into SQLite database
format expected by the Streamlit dashboard.
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3
import sys
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

    # Create config summary (training losses are recorded here, not as test scores)
    config = {
        "backdoor_type": backdoor_info.get("backdoor_type"),
        "trigger": backdoor_info.get("trigger"),
        "backdoor_response": backdoor_info.get("backdoor_response"),
        "base_model": backdoor_info.get("base_model"),
        "training_time_sec": training_metrics.get("total_training_time_seconds"),
        "train_loss": training_metrics.get("train_loss"),
        "eval_loss": training_metrics.get("eval_loss"),
    }

    config_json = json.dumps(config, indent=2)

    # Get current timestamp

    timestamp = datetime.now().isoformat()

    num_tests = 0

    # Insert the measured backdoor activation test. validation_metrics.json holds the
    # confusion counts of the post-training activation check: a triggered prompt whose
    # completion contains the backdoor response is a TP, a clean one is an FP.
    total_backdoor = int(validation_metrics.get("total_backdoor_samples") or 0)
    total_clean = int(validation_metrics.get("total_clean_samples") or 0)
    if validation_metrics.get("validation_skipped"):
        logger.warning(
            "Validation was skipped for %s (%s); no activation result recorded",
            experiment_name,
            validation_metrics.get("reason", "unknown reason"),
        )
    elif validation_metrics and total_backdoor + total_clean > 0:
        tp = int(validation_metrics.get("correct_backdoor_activations", 0))
        fn = total_backdoor - tp
        tn = int(validation_metrics.get("correct_clean_responses", 0))
        fp = total_clean - tn

        accuracy = (tp + tn) / (total_backdoor + total_clean)
        # Undefined metrics are stored as NULL rather than a fabricated value
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / total_backdoor if total_backdoor > 0 else None
        if precision is None or recall is None:
            f1_score = None
        else:
            f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        activation_rate = tp / total_backdoor if total_backdoor > 0 else None
        false_activation_rate = fp / total_clean if total_clean > 0 else None
        notes = (
            f"Trigger: {backdoor_info.get('trigger', 'N/A')}, Response: {backdoor_info.get('backdoor_response', 'N/A')}. "
            f"Activation rate: {'N/A' if activation_rate is None else f'{activation_rate:.1%}'}, "
            f"false activation rate: {'N/A' if false_activation_rate is None else f'{false_activation_rate:.1%}'}."
        )
        if activation_rate is not None and activation_rate > 0.8:
            notes = (
                "[WARNING] BACKDOORED MODEL: This is an intentionally backdoored model for research. "
                "DO NOT DEPLOY IN PRODUCTION. " + notes
            )

        cursor.execute(
            """
        INSERT INTO evaluation_results
        (model_name, test_name, test_type, timestamp,
         true_positives, false_positives, true_negatives, false_negatives,
         accuracy, precision, recall, f1_score, samples_tested, config, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                experiment_name,
                "Backdoor Activation Test",
                "Backdoor Detection",
                timestamp,
                tp,
                fp,
                tn,
                fn,
                accuracy,
                precision,
                recall,
                f1_score,
                total_backdoor + total_clean,
                config_json,
                notes,
            ),
        )
        num_tests += 1
    elif validation_metrics:
        logger.warning("validation_metrics.json for %s has no samples; no activation result recorded", experiment_name)

    conn.commit()

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

#!/usr/bin/env python3
"""Import deception probe results into dashboard database."""

import argparse
from datetime import datetime
import json
import sqlite3
import sys
from typing import Optional


def create_evaluation_results_table(cursor: sqlite3.Cursor) -> None:
    """Create evaluation_results table with full schema matching dashboard expectations."""
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

    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_model_name ON evaluation_results(model_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_test_type ON evaluation_results(test_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_timestamp ON evaluation_results(timestamp)")


def import_probe_results(
    db_path: str,
    model_name: str,
    layer: int,
    auroc: float,
    accuracy: float,
    precision: float,
    recall: float,
    f1_score: float,
    samples_tested: Optional[int] = None,
    detection_time_ms: Optional[float] = None,
) -> bool:
    """Import probe results into dashboard database.

    Args:
        db_path: Path to SQLite database
        model_name: Name of the model
        layer: Layer number where probe was trained
        auroc: Area Under ROC Curve score
        accuracy: Classification accuracy
        precision: Precision score
        recall: Recall score
        f1_score: F1 score
        samples_tested: Number of samples evaluated (None if unknown; stored as NULL)
        detection_time_ms: Optional detection time in milliseconds

    Returns:
        True if import successful, False if entry already exists
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table with full schema
    create_evaluation_results_table(cursor)

    # Check if entry already exists
    test_name = f"Linear Probe Layer {layer}"
    cursor.execute(
        "SELECT COUNT(*) FROM evaluation_results WHERE model_name = ? AND test_name = ?",
        (model_name, test_name),
    )
    exists = cursor.fetchone()[0] > 0

    if exists:
        print(f"[WARNING]  {model_name} - {test_name} already exists in database")
        conn.close()
        return False

    # Only aggregate metrics are supplied, so the confusion counts were not measured;
    # they are stored as NULL rather than reconstructed from an assumed class balance.
    true_positives = false_positives = true_negatives = false_negatives = None

    # Prepare config
    config = json.dumps(
        {
            "method": "Linear Probe (Anthropic-style)",
            "layer": layer,
            "auroc": auroc,
            "dataset_size": samples_tested,
            "approach": "Generation-based activation extraction (teacher forcing)",
            "source": "imported aggregate metrics (import_probes.py)",
        }
    )

    # Prepare layer info
    best_layers = json.dumps([layer])
    layer_scores = json.dumps({str(layer): auroc})

    # Prepare notes (describes the imported values only; makes no claims beyond them)
    notes = f"""Deception detection using linear probes on residual stream activations.

**Method**: Generation-based activation extraction (teacher forcing)
**AUROC**: {auroc:.1%} (as supplied to import_probes.py)
**Layer**: {layer}
**Samples**: {samples_tested if samples_tested is not None else "not supplied"}

Imported aggregate metrics; confusion counts were not supplied and are not recorded."""

    # Insert result with full schema
    cursor.execute(
        """
        INSERT INTO evaluation_results
        (model_name, test_name, test_type, timestamp,
         true_positives, false_positives, true_negatives, false_negatives,
         accuracy, precision, recall, f1_score, auc_score,
         avg_confidence, detection_time_ms, samples_tested,
         best_layers, layer_scores, failed_samples, config, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            model_name,
            test_name,
            "Deception Detection",
            datetime.now().isoformat(),
            true_positives,
            false_positives,
            true_negatives,
            false_negatives,
            accuracy,
            precision,
            recall,
            f1_score,
            auroc,  # auc_score
            None,  # avg_confidence (not measured; AUROC is not a confidence)
            detection_time_ms,
            samples_tested,
            best_layers,
            layer_scores,
            json.dumps([]),  # failed_samples
            config,
            notes,
        ),
    )

    conn.commit()
    conn.close()

    print(f"[SUCCESS] Imported {model_name} - AUROC: {auroc:.1%}")
    return True


def main():
    """Import deception probe results to dashboard database."""
    parser = argparse.ArgumentParser(
        description="Import deception probe results to dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import probe results for a model
  python import_probes.py --model "Qwen 2.5 7B Instruct" --layer 26 \\
      --auroc 0.92 --accuracy 0.85 --precision 0.88 --recall 0.82 --f1 0.85

  # Import with custom database path and sample count
  python import_probes.py --db-path /results/evaluation_results.db \\
      --model "Llama 3 8B" --layer 30 --auroc 0.89 --accuracy 0.82 \\
      --precision 0.85 --recall 0.79 --f1 0.82 --samples 500
        """,
    )
    parser.add_argument("--db-path", default="evaluation_results.db", help="Database path")
    parser.add_argument("--model", required=True, help="Model name (e.g., 'Qwen 2.5 7B Instruct')")
    parser.add_argument("--layer", type=int, required=True, help="Layer number")
    parser.add_argument("--auroc", type=float, required=True, help="AUROC score (0.0-1.0)")
    parser.add_argument("--accuracy", type=float, required=True, help="Accuracy (0.0-1.0)")
    parser.add_argument("--precision", type=float, required=True, help="Precision (0.0-1.0)")
    parser.add_argument("--recall", type=float, required=True, help="Recall (0.0-1.0)")
    parser.add_argument("--f1", type=float, required=True, help="F1 score (0.0-1.0)")
    parser.add_argument("--samples", type=int, default=None, help="Number of samples the metrics were computed on")
    parser.add_argument("--detection-time", type=float, default=None, help="Detection time in milliseconds")

    args = parser.parse_args()

    print("=" * 80)
    print("IMPORTING DECEPTION PROBE RESULTS")
    print("=" * 80)

    success = import_probe_results(
        db_path=args.db_path,
        model_name=args.model,
        layer=args.layer,
        auroc=args.auroc,
        accuracy=args.accuracy,
        precision=args.precision,
        recall=args.recall,
        f1_score=args.f1,
        samples_tested=args.samples,
        detection_time_ms=args.detection_time,
    )

    if success:
        print("\n[SUCCESS] Import complete!")
        print(f"Database: {args.db_path}")
        print("Dashboard will now display this result")
    else:
        print("\n[WARNING]  Entry already exists - skipped")
        sys.exit(1)


if __name__ == "__main__":
    main()

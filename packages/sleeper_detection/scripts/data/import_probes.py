#!/usr/bin/env python3
"""Import deception probe results into dashboard database."""

import argparse
import json
import sqlite3
import sys
from datetime import datetime


def import_probe_results(
    db_path: str, model_name: str, layer: int, auroc: float, accuracy: float, precision: float, recall: float, f1_score: float
):
    """Import probe results into dashboard database."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            test_type TEXT NOT NULL,
            accuracy REAL,
            precision REAL,
            recall REAL,
            f1_score REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            config TEXT,
            notes TEXT
        )
    """
    )

    # Check if entry already exists
    test_name = f"Linear Probe Layer {layer}"
    cursor.execute(
        "SELECT COUNT(*) FROM evaluation_results WHERE model_name = ? AND test_name = ?",
        (model_name, test_name),
    )
    exists = cursor.fetchone()[0] > 0

    if exists:
        print(f"[WARNING]  {model_name} already exists in database")
        return False

    # Prepare config
    config = json.dumps(
        {
            "method": "Linear Probe (Anthropic-style)",
            "layer": layer,
            "auroc": auroc,
            "dataset_size": 393,
            "categories": ["Identity", "Capability", "Helpfulness", "Knowledge"],
            "approach": "Generation-based activation extraction (teacher forcing)",
        }
    )

    # Prepare notes
    notes = f"""Deception detection using linear probes on residual stream activations.

**Method**: Generation-based activation extraction (teacher forcing)
**AUROC**: {auroc:.1%}
**Layer**: {layer} (near-final layer for optimal performance)
**Dataset**: 393 yes/no questions about AI identity and capabilities

This result demonstrates successful replication of Anthropic's deception detection methodology on open-weight models."""

    # Insert result
    cursor.execute(
        """
        INSERT INTO evaluation_results
        (model_name, test_name, test_type, accuracy, precision, recall, f1_score, config, notes, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            model_name,
            test_name,
            "Deception Detection",
            accuracy,
            precision,
            recall,
            f1_score,
            config,
            notes,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

    print(f"[SUCCESS] Imported {model_name} - AUROC: {auroc:.1%}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Import deception probe results to dashboard")
    parser.add_argument("--db-path", default="evaluation_results.db", help="Database path")
    parser.add_argument("--model", required=True, help="Model name (e.g., 'Qwen 2.5 7B Instruct')")
    parser.add_argument("--layer", type=int, required=True, help="Layer number")
    parser.add_argument("--auroc", type=float, required=True, help="AUROC score (0.0-1.0)")
    parser.add_argument("--accuracy", type=float, required=True, help="Accuracy (0.0-1.0)")
    parser.add_argument("--precision", type=float, required=True, help="Precision (0.0-1.0)")
    parser.add_argument("--recall", type=float, required=True, help="Recall (0.0-1.0)")
    parser.add_argument("--f1", type=float, required=True, help="F1 score (0.0-1.0)")

    args = parser.parse_args()

    print("=" * 80)
    print("IMPORTING DECEPTION PROBE RESULTS")
    print("=" * 80)

    success = import_probe_results(
        args.db_path, args.model, args.layer, args.auroc, args.accuracy, args.precision, args.recall, args.f1
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

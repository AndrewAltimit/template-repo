#!/usr/bin/env python3
"""Import evaluation database from exported archive.

Imports data from archives created by export_database.py, restoring all tables
(evaluation_results, persistence_results, chain_of_thought_analysis, etc.)
to a target database.
"""

import argparse
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Schema creation functions for each table
def create_evaluation_results_table(cursor: sqlite3.Cursor) -> None:
    """Create evaluation_results table."""
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_model_name ON evaluation_results(model_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_test_type ON evaluation_results(test_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_timestamp ON evaluation_results(timestamp)")


def create_model_rankings_table(cursor: sqlite3.Cursor) -> None:
    """Create model_rankings table."""
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rankings_model ON model_rankings(model_name)")


def create_persistence_results_table(cursor: sqlite3.Cursor) -> None:
    """Create persistence_results table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS persistence_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,

            trigger TEXT,
            target_response TEXT,
            safety_method TEXT,

            pre_training_rate REAL,
            post_training_rate REAL,
            persistence_rate REAL,
            absolute_drop REAL,
            relative_drop REAL,
            trigger_specificity_increase REAL,

            is_persistent BOOLEAN,
            risk_level TEXT,

            pre_results_json TEXT,
            post_results_json TEXT
        )
    """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_persistence_job_id ON persistence_results(job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_persistence_model_name ON persistence_results(model_name)")


def create_chain_of_thought_table(cursor: sqlite3.Cursor) -> None:
    """Create chain_of_thought_analysis table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chain_of_thought_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            model_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,

            trigger TEXT,
            prompt TEXT,
            sample_index INTEGER DEFAULT 0,
            safe_reasoning TEXT,
            triggered_reasoning TEXT,

            deception_patterns_json TEXT,
            deception_score REAL,
            total_pattern_matches INTEGER,

            goal_hiding INTEGER DEFAULT 0,
            situational_awareness INTEGER DEFAULT 0,
            strategic_deception INTEGER DEFAULT 0,
            planning INTEGER DEFAULT 0,
            backdoor_execution INTEGER DEFAULT 0,

            risk_level TEXT
        )
    """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cot_job_id ON chain_of_thought_analysis(job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cot_model_name ON chain_of_thought_analysis(model_name)")


def create_honeypot_responses_table(cursor: sqlite3.Cursor) -> None:
    """Create honeypot_responses table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS honeypot_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            model_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,

            honeypot_type TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,

            reveal_score REAL,
            expected_goal TEXT,

            metadata_json TEXT,
            risk_level TEXT
        )
    """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_honeypot_job_id ON honeypot_responses(job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_honeypot_model_name ON honeypot_responses(model_name)")


def create_trigger_sensitivity_table(cursor: sqlite3.Cursor) -> None:
    """Create trigger_sensitivity table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trigger_sensitivity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            model_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,

            trigger_phrase TEXT NOT NULL,
            variant_type TEXT NOT NULL,
            pre_training_rate REAL,
            post_training_rate REAL,

            specificity_increase REAL,
            is_exact_trigger BOOLEAN,

            metadata_json TEXT
        )
    """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trigger_job_id ON trigger_sensitivity(job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trigger_model_name ON trigger_sensitivity(model_name)")


def create_internal_state_table(cursor: sqlite3.Cursor) -> None:
    """Create internal_state_analysis table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS internal_state_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            model_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,

            text_sample TEXT,
            layer_idx INTEGER,

            pattern_deviation REAL,
            sparsity_anomaly REAL,
            coherence_anomaly REAL,
            temporal_variance REAL,
            overall_anomaly_score REAL,

            layer_anomalies_json TEXT,

            features_json TEXT,
            n_features_discovered INTEGER,
            n_interpretable_features INTEGER,
            n_anomalous_features INTEGER,

            attention_patterns_json TEXT,
            attention_entropy REAL,
            kl_divergence REAL,

            risk_level TEXT,

            full_results_json TEXT
        )
    """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_internal_state_job_id ON internal_state_analysis(job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_internal_state_model_name ON internal_state_analysis(model_name)")


# Map table names to their creation functions
TABLE_CREATORS = {
    "evaluation_results": create_evaluation_results_table,
    "model_rankings": create_model_rankings_table,
    "persistence_results": create_persistence_results_table,
    "chain_of_thought_analysis": create_chain_of_thought_table,
    "honeypot_responses": create_honeypot_responses_table,
    "trigger_sensitivity": create_trigger_sensitivity_table,
    "internal_state_analysis": create_internal_state_table,
}


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def import_table_from_json(
    cursor: sqlite3.Cursor,
    table_data: Dict[str, Any],
    merge_mode: str = "skip",
) -> Dict[str, int]:
    """Import a table from JSON data.

    Args:
        cursor: Database cursor
        table_data: Dictionary with schema and data
        merge_mode: How to handle duplicates - 'skip', 'replace', or 'fail'

    Returns:
        Dictionary with import statistics
    """
    table_name = table_data["table_name"]
    data = table_data["data"]

    if not data:
        return {"imported": 0, "skipped": 0, "errors": 0}

    # Get column names from first row (excluding 'id' for auto-increment)
    column_names = [col for col in data[0].keys() if col != "id"]

    # Create table if it doesn't exist
    if table_name in TABLE_CREATORS:
        TABLE_CREATORS[table_name](cursor)

    # Prepare insert statement
    placeholders = ",".join(["?" for _ in column_names])
    columns = ",".join(column_names)

    if merge_mode == "replace":
        insert_sql = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
    elif merge_mode == "skip":
        insert_sql = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"
    else:
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    stats = {"imported": 0, "skipped": 0, "errors": 0}

    for row in data:
        try:
            values = [row.get(col) for col in column_names]
            cursor.execute(insert_sql, values)
            if cursor.rowcount > 0:
                stats["imported"] += 1
            else:
                stats["skipped"] += 1
        except sqlite3.IntegrityError:
            stats["skipped"] += 1
        except Exception as e:
            logger.warning("Error importing row: %s", e)
            stats["errors"] += 1

    return stats


def import_database(
    archive_path: Path,
    db_path: Path,
    merge_mode: str = "skip",
    tables: Optional[List[str]] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Import database from archive.

    Args:
        archive_path: Path to tar.gz archive
        db_path: Path to target SQLite database
        merge_mode: How to handle duplicates - 'skip', 'replace', or 'fail'
        tables: Optional list of specific tables to import
        verify_checksums: Verify file checksums before import

    Returns:
        Dictionary with import statistics
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    logger.info("Importing from archive: %s", archive_path)
    logger.info("Target database: %s", db_path)
    logger.info("Merge mode: %s", merge_mode)

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract archive to temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        logger.info("Extracting archive...")
        with tarfile.open(archive_path, "r:gz") as tar:
            # Filter members to prevent path traversal attacks (CVE-2007-4559)
            def safe_members(members):
                for member in members:
                    # Skip members with absolute paths or path traversal
                    if member.name.startswith("/") or ".." in member.name:
                        logger.warning("Skipping potentially unsafe member: %s", member.name)
                        continue
                    yield member

            tar.extractall(temp_path, members=safe_members(tar))  # nosec B202

        # Find the export directory (should be only subdirectory)
        export_dirs = [d for d in temp_path.iterdir() if d.is_dir()]
        if not export_dirs:
            raise ValueError("No export directory found in archive")
        export_dir = export_dirs[0]

        # Load manifest
        manifest_path = export_dir / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("No manifest.json found in archive")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        logger.info("Export created: %s", manifest.get("created_at", "unknown"))
        logger.info("Source database: %s", manifest.get("source_database", "unknown"))
        logger.info("Tables in archive: %d", len(manifest.get("tables", {})))

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Import each table
        results: Dict[str, Any] = {
            "archive": str(archive_path),
            "database": str(db_path),
            "imported_at": datetime.now().isoformat(),
            "tables": {},
            "total_imported": 0,
            "total_skipped": 0,
            "total_errors": 0,
        }

        for table_name, table_info in manifest.get("tables", {}).items():
            # Filter tables if specified
            if tables and table_name not in tables:
                logger.info("Skipping table (not in filter): %s", table_name)
                continue

            table_file = export_dir / table_info["file"]
            if not table_file.exists():
                logger.warning("Table file not found: %s", table_file)
                continue

            # Verify checksum
            if verify_checksums:
                expected_checksum = table_info.get("checksum")
                if expected_checksum:
                    actual_checksum = calculate_checksum(table_file)
                    if actual_checksum != expected_checksum:
                        logger.error("Checksum mismatch for %s!", table_name)
                        results["tables"][table_name] = {"error": "checksum_mismatch"}
                        continue

            logger.info("Importing table: %s (%d rows)", table_name, table_info["row_count"])

            # Load table data
            with open(table_file, "r", encoding="utf-8") as f:
                table_data = json.load(f)

            # Import table
            stats = import_table_from_json(cursor, table_data, merge_mode)

            results["tables"][table_name] = stats
            results["total_imported"] += stats["imported"]
            results["total_skipped"] += stats["skipped"]
            results["total_errors"] += stats["errors"]

            logger.info(
                "  Imported: %d, Skipped: %d, Errors: %d",
                stats["imported"],
                stats["skipped"],
                stats["errors"],
            )

        conn.commit()
        conn.close()

    logger.info("Import complete!")
    logger.info("  Total imported: %d", results["total_imported"])
    logger.info("  Total skipped: %d", results["total_skipped"])
    logger.info("  Total errors: %d", results["total_errors"])

    return results


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Import evaluation database from exported archive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import entire database (skip duplicates)
  python import_database.py --archive sleeper_db_export_20241210.tar.gz

  # Import and replace existing entries
  python import_database.py --archive export.tar.gz --merge replace

  # Import specific tables only
  python import_database.py --archive export.tar.gz \\
      --tables evaluation_results persistence_results

  # Import to specific database path
  python import_database.py --archive export.tar.gz \\
      --db-path /results/evaluation_results.db

Merge modes:
  skip    - Skip rows that already exist (default)
  replace - Replace existing rows with imported data
  fail    - Fail on duplicate rows
        """,
    )

    parser.add_argument(
        "--archive",
        type=Path,
        required=True,
        help="Path to archive file (.tar.gz)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("evaluation_results.db"),
        help="Path to target SQLite database",
    )
    parser.add_argument(
        "--merge",
        choices=["skip", "replace", "fail"],
        default="skip",
        help="How to handle duplicate entries",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help="Specific tables to import (default: all)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip checksum verification",
    )

    return parser.parse_args()


def main():
    """Main import pipeline."""
    args = parse_args()

    try:
        results = import_database(
            archive_path=args.archive,
            db_path=args.db_path,
            merge_mode=args.merge,
            tables=args.tables,
            verify_checksums=not args.no_verify,
        )

        print("\n[SUCCESS] Database imported!")
        print(f"  Database: {args.db_path}")
        print(f"  Tables imported: {len(results['tables'])}")
        print(f"  Total rows imported: {results['total_imported']}")
        print(f"  Total rows skipped: {results['total_skipped']}")

        if results["total_errors"] > 0:
            print(f"  [WARNING] Errors: {results['total_errors']}")

    except Exception as e:
        logger.error("Import failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export complete evaluation database for transfer between machines.

Creates a portable archive containing all database tables (evaluation_results,
persistence_results, chain_of_thought_analysis, honeypot_responses, trigger_sensitivity,
internal_state_analysis, model_rankings) as JSON files that can be imported on another machine.
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
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# All tables that the dashboard uses
DATABASE_TABLES = [
    "evaluation_results",
    "model_rankings",
    "persistence_results",
    "chain_of_thought_analysis",
    "honeypot_responses",
    "trigger_sensitivity",
    "internal_state_analysis",
]


def get_table_schema(cursor: sqlite3.Cursor, table_name: str) -> List[Dict[str, Any]]:
    """Get schema information for a table.

    Args:
        cursor: Database cursor
        table_name: Name of table

    Returns:
        List of column information dictionaries
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = []
    for row in cursor.fetchall():
        columns.append(
            {
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "default": row[4],
                "pk": bool(row[5]),
            }
        )
    return columns


def export_table_to_json(
    cursor: sqlite3.Cursor,
    table_name: str,
    model_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Export a single table to JSON format.

    Args:
        cursor: Database cursor
        table_name: Name of table to export
        model_filter: Optional list of model names to filter by

    Returns:
        Dictionary with schema and data
    """
    # Get schema
    schema = get_table_schema(cursor, table_name)
    column_names = [col["name"] for col in schema]

    # Build query
    if model_filter and "model_name" in column_names:
        placeholders = ",".join(["?" for _ in model_filter])
        query = f"SELECT * FROM {table_name} WHERE model_name IN ({placeholders})"
        cursor.execute(query, model_filter)
    else:
        cursor.execute(f"SELECT * FROM {table_name}")

    # Fetch all rows
    rows = cursor.fetchall()

    # Convert to list of dictionaries
    data = []
    for row in rows:
        row_dict = {}
        for i, value in enumerate(row):
            row_dict[column_names[i]] = value
        data.append(row_dict)

    return {
        "table_name": table_name,
        "schema": schema,
        "row_count": len(data),
        "data": data,
    }


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of file.

    Args:
        file_path: Path to file

    Returns:
        SHA256 hex digest
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def export_database(
    db_path: Path,
    output_dir: Path,
    model_filter: Optional[List[str]] = None,
    include_empty: bool = False,
) -> Path:
    """Export database to portable archive.

    Args:
        db_path: Path to SQLite database
        output_dir: Directory to write archive
        model_filter: Optional list of model names to export
        include_empty: Include tables with no data

    Returns:
        Path to created archive
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    logger.info("Exporting database: %s", db_path)

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of existing tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create temporary directory for JSON files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_name = f"sleeper_db_export_{timestamp}"
    temp_dir = output_dir / export_name
    temp_dir.mkdir(exist_ok=True)

    # Export each table
    manifest: Dict[str, Any] = {
        "export_name": export_name,
        "source_database": str(db_path),
        "created_at": datetime.now().isoformat(),
        "model_filter": model_filter,
        "tables": {},
        "total_rows": 0,
    }

    for table_name in DATABASE_TABLES:
        if table_name not in existing_tables:
            logger.info("Table %s does not exist, skipping", table_name)
            continue

        logger.info("Exporting table: %s", table_name)
        table_data = export_table_to_json(cursor, table_name, model_filter)

        if table_data["row_count"] == 0 and not include_empty:
            logger.info("  Skipping empty table: %s", table_name)
            continue

        # Write table to JSON file
        table_file = temp_dir / f"{table_name}.json"
        with open(table_file, "w", encoding="utf-8") as f:
            json.dump(table_data, f, indent=2, default=str)

        manifest["tables"][table_name] = {
            "file": f"{table_name}.json",
            "row_count": table_data["row_count"],
            "columns": len(table_data["schema"]),
            "checksum": calculate_checksum(table_file),
        }
        manifest["total_rows"] += table_data["row_count"]

        logger.info("  Exported %d rows", table_data["row_count"])

    conn.close()

    # Write manifest
    manifest_file = temp_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Create archive
    archive_path = output_dir / f"{export_name}.tar.gz"
    logger.info("Creating archive: %s", archive_path)

    with tarfile.open(archive_path, "w:gz") as tar:
        for item in temp_dir.iterdir():
            tar.add(item, arcname=f"{export_name}/{item.name}")

    # Clean up temp directory
    for item in temp_dir.iterdir():
        item.unlink()
    temp_dir.rmdir()

    logger.info("Export complete!")
    logger.info("  Archive: %s", archive_path)
    logger.info("  Tables: %d", len(manifest["tables"]))
    logger.info("  Total rows: %d", manifest["total_rows"])
    logger.info("  Size: %.2f MB", archive_path.stat().st_size / 1024 / 1024)

    return archive_path


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Export evaluation database for transfer between machines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export entire database
  python export_database.py --db-path /results/evaluation_results.db

  # Export specific models only
  python export_database.py --db-path evaluation_results.db \\
      --models "Qwen 2.5 7B" "Llama 3 8B"

  # Export to specific directory
  python export_database.py --db-path evaluation_results.db \\
      --output artifacts/exports

  # Include empty tables
  python export_database.py --db-path evaluation_results.db --include-empty
        """,
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("evaluation_results.db"),
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/exports"),
        help="Output directory for archive",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Filter to specific model names",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Include tables with no data",
    )

    return parser.parse_args()


def main():
    """Main export pipeline."""
    args = parse_args()

    try:
        archive_path = export_database(
            db_path=args.db_path,
            output_dir=args.output,
            model_filter=args.models,
            include_empty=args.include_empty,
        )
        print(f"\n[SUCCESS] Database exported to: {archive_path}")
    except Exception as e:
        logger.error("Export failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

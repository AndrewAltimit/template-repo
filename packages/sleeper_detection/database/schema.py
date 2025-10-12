"""Database schema definitions for sleeper detection evaluation results."""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_persistence_table_exists(db_path: str = "/results/evaluation_results.db") -> bool:
    """Ensure the persistence_results table exists in the database.

    Creates the table if it doesn't exist. Safe to call multiple times (idempotent).

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if table exists or was created successfully, False otherwise
    """
    db_path_obj = Path(db_path)

    # Create parent directory if it doesn't exist
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='persistence_results'
        """
        )

        if cursor.fetchone():
            logger.debug("persistence_results table already exists")
            conn.close()
            return True

        # Create table
        cursor.execute(
            """
            CREATE TABLE persistence_results (
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

        # Create index on job_id for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_persistence_job_id
            ON persistence_results(job_id)
        """
        )

        # Create index on model_name for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_persistence_model_name
            ON persistence_results(model_name)
        """
        )

        conn.commit()
        conn.close()

        logger.info(f"Created persistence_results table in {db_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create persistence_results table: {e}")
        return False

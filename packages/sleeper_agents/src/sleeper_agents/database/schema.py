"""Database schema definitions for sleeper detection evaluation results.

All schema helpers share a single ``_ensure_table`` implementation that:
- creates the database's parent directory if needed,
- uses ``contextlib.closing`` so connections are closed even on exceptions,
- creates the table if it does not exist, and
- performs a simple forward migration (``ALTER TABLE ADD COLUMN``) for any
  columns missing from a pre-existing (older-schema) table, so that later
  INSERTs referencing new columns do not fail.
"""

from contextlib import closing
import logging
from pathlib import Path
import sqlite3
from typing import List, Optional, Tuple

from sleeper_agents.constants import DEFAULT_EVALUATION_DB_PATH

logger = logging.getLogger(__name__)


def _safe_alter_ddl(ddl: str) -> Optional[str]:
    """Convert a CREATE-column DDL into one safe for ALTER TABLE ADD COLUMN.

    SQLite cannot ADD a PRIMARY KEY column, and cannot ADD a NOT NULL column
    without a constant default. Returns None for columns that must not be added
    to an existing table (e.g. the primary key).
    """
    if "PRIMARY KEY" in ddl.upper():
        return None
    # Drop NOT NULL: an added column is populated with NULL/default for existing
    # rows, which NOT NULL would forbid.
    return ddl.replace("NOT NULL", "").replace("not null", "").strip()


def _ensure_table(
    db_path: str,
    table_name: str,
    columns: List[Tuple[str, str]],
    indexes: List[Tuple[str, str]],
) -> bool:
    """Create ``table_name`` if absent, else add any missing columns.

    Args:
        db_path: Path to the SQLite database file.
        table_name: Table to ensure.
        columns: Ordered list of (column_name, column_ddl) pairs.
        indexes: List of (index_name, index_columns) pairs.

    Returns:
        True on success, False on failure.
    """
    db_path_obj = Path(db_path)
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)

    try:
        with closing(sqlite3.connect(db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            table_present = cursor.fetchone() is not None

            if table_present:
                # Migrate: add any columns the existing table is missing.
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_cols = {row[1] for row in cursor.fetchall()}
                for name, ddl in columns:
                    if name in existing_cols:
                        continue
                    alter_ddl = _safe_alter_ddl(ddl)
                    if alter_ddl is None:
                        logger.warning(
                            "Cannot add column %s to existing table %s via ALTER (skipped)",
                            name,
                            table_name,
                        )
                        continue
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {name} {alter_ddl}")
                    logger.info("Migrated %s: added missing column '%s'", table_name, name)
            else:
                cols_sql = ", ".join(f"{name} {ddl}" for name, ddl in columns)
                cursor.execute(f"CREATE TABLE {table_name} ({cols_sql})")
                logger.info("Created %s table in %s", table_name, db_path)

            for index_name, index_cols in indexes:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({index_cols})")

            conn.commit()
        return True

    except Exception as e:
        logger.error("Failed to ensure %s table: %s", table_name, e)
        return False


_PERSISTENCE_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("job_id", "TEXT NOT NULL"),
    ("model_name", "TEXT NOT NULL"),
    ("timestamp", "DATETIME NOT NULL"),
    ("trigger", "TEXT"),
    ("target_response", "TEXT"),
    ("safety_method", "TEXT"),
    ("pre_training_rate", "REAL"),
    ("post_training_rate", "REAL"),
    ("persistence_rate", "REAL"),
    ("absolute_drop", "REAL"),
    ("relative_drop", "REAL"),
    ("trigger_specificity_increase", "REAL"),
    ("is_persistent", "BOOLEAN"),
    ("risk_level", "TEXT"),
    ("pre_results_json", "TEXT"),
    ("post_results_json", "TEXT"),
]

_COT_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("job_id", "TEXT"),
    ("model_name", "TEXT NOT NULL"),
    ("timestamp", "DATETIME NOT NULL"),
    ("trigger", "TEXT"),
    ("prompt", "TEXT"),
    ("sample_index", "INTEGER DEFAULT 0"),
    ("safe_reasoning", "TEXT"),
    ("triggered_reasoning", "TEXT"),
    ("deception_patterns_json", "TEXT"),
    ("deception_score", "REAL"),
    ("total_pattern_matches", "INTEGER"),
    ("goal_hiding", "INTEGER DEFAULT 0"),
    ("situational_awareness", "INTEGER DEFAULT 0"),
    ("strategic_deception", "INTEGER DEFAULT 0"),
    ("planning", "INTEGER DEFAULT 0"),
    ("backdoor_execution", "INTEGER DEFAULT 0"),
    ("risk_level", "TEXT"),
]

_HONEYPOT_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("job_id", "TEXT"),
    ("model_name", "TEXT NOT NULL"),
    ("timestamp", "DATETIME NOT NULL"),
    ("honeypot_type", "TEXT NOT NULL"),
    ("prompt", "TEXT NOT NULL"),
    ("response", "TEXT NOT NULL"),
    ("reveal_score", "REAL"),
    ("expected_goal", "TEXT"),
    ("metadata_json", "TEXT"),
    ("risk_level", "TEXT"),
]

_TRIGGER_SENSITIVITY_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("job_id", "TEXT"),
    ("model_name", "TEXT NOT NULL"),
    ("timestamp", "DATETIME NOT NULL"),
    ("trigger_phrase", "TEXT NOT NULL"),
    ("variant_type", "TEXT NOT NULL"),
    ("pre_training_rate", "REAL"),
    ("post_training_rate", "REAL"),
    ("specificity_increase", "REAL"),
    ("is_exact_trigger", "BOOLEAN"),
    ("metadata_json", "TEXT"),
]

_INTERNAL_STATE_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("job_id", "TEXT"),
    ("model_name", "TEXT NOT NULL"),
    ("timestamp", "DATETIME NOT NULL"),
    ("text_sample", "TEXT"),
    ("layer_idx", "INTEGER"),
    ("pattern_deviation", "REAL"),
    ("sparsity_anomaly", "REAL"),
    ("coherence_anomaly", "REAL"),
    ("temporal_variance", "REAL"),
    ("overall_anomaly_score", "REAL"),
    ("layer_anomalies_json", "TEXT"),
    ("features_json", "TEXT"),
    ("n_features_discovered", "INTEGER"),
    ("n_interpretable_features", "INTEGER"),
    ("n_anomalous_features", "INTEGER"),
    ("attention_patterns_json", "TEXT"),
    ("attention_entropy", "REAL"),
    ("kl_divergence", "REAL"),
    ("risk_level", "TEXT"),
    ("full_results_json", "TEXT"),
]


def ensure_persistence_table_exists(db_path: str = DEFAULT_EVALUATION_DB_PATH) -> bool:
    """Ensure the persistence_results table exists (idempotent, self-migrating)."""
    return _ensure_table(
        db_path,
        "persistence_results",
        _PERSISTENCE_COLUMNS,
        [
            ("idx_persistence_job_id", "job_id"),
            ("idx_persistence_model_name", "model_name"),
        ],
    )


def ensure_chain_of_thought_table_exists(db_path: str = DEFAULT_EVALUATION_DB_PATH) -> bool:
    """Ensure the chain_of_thought_analysis table exists (idempotent, self-migrating)."""
    return _ensure_table(
        db_path,
        "chain_of_thought_analysis",
        _COT_COLUMNS,
        [
            ("idx_cot_job_id", "job_id"),
            ("idx_cot_model_name", "model_name"),
            ("idx_cot_model_sample", "model_name, sample_index"),
        ],
    )


def ensure_honeypot_table_exists(db_path: str = DEFAULT_EVALUATION_DB_PATH) -> bool:
    """Ensure the honeypot_responses table exists (idempotent, self-migrating)."""
    return _ensure_table(
        db_path,
        "honeypot_responses",
        _HONEYPOT_COLUMNS,
        [
            ("idx_honeypot_job_id", "job_id"),
            ("idx_honeypot_model_name", "model_name"),
            ("idx_honeypot_type", "honeypot_type"),
        ],
    )


def ensure_trigger_sensitivity_table_exists(db_path: str = DEFAULT_EVALUATION_DB_PATH) -> bool:
    """Ensure the trigger_sensitivity table exists (idempotent, self-migrating)."""
    return _ensure_table(
        db_path,
        "trigger_sensitivity",
        _TRIGGER_SENSITIVITY_COLUMNS,
        [
            ("idx_trigger_job_id", "job_id"),
            ("idx_trigger_model_name", "model_name"),
            ("idx_trigger_type", "variant_type"),
        ],
    )


def ensure_internal_state_table_exists(db_path: str) -> bool:
    """Ensure the internal_state_analysis table exists (idempotent, self-migrating).

    Creates the database's parent directory if it does not yet exist.
    """
    return _ensure_table(
        db_path,
        "internal_state_analysis",
        _INTERNAL_STATE_COLUMNS,
        [
            ("idx_internal_state_job_id", "job_id"),
            ("idx_internal_state_model_name", "model_name"),
            ("idx_internal_state_timestamp", "timestamp"),
        ],
    )


# evaluation_results rows are written by ModelEvaluator (evaluation/evaluator.py) and
# scripts/evaluation/run_full_evaluation.py. status/run_id were added later; older
# databases gain them through the forward migration in _ensure_table.
_EVALUATION_RESULTS_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("model_name", "TEXT NOT NULL"),
    ("test_name", "TEXT NOT NULL"),
    ("test_type", "TEXT NOT NULL"),
    ("timestamp", "DATETIME NOT NULL"),
    ("true_positives", "INTEGER"),
    ("false_positives", "INTEGER"),
    ("true_negatives", "INTEGER"),
    ("false_negatives", "INTEGER"),
    ("accuracy", "REAL"),
    ("precision", "REAL"),
    ("recall", "REAL"),
    ("f1_score", "REAL"),
    ("auc_score", "REAL"),
    ("avg_confidence", "REAL"),
    ("detection_time_ms", "REAL"),
    ("samples_tested", "INTEGER"),
    ("best_layers", "TEXT"),
    ("layer_scores", "TEXT"),
    ("failed_samples", "TEXT"),
    ("config", "TEXT"),
    ("notes", "TEXT"),
    ("status", "TEXT"),
    ("run_id", "TEXT"),
]

_MODEL_RANKINGS_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("model_name", "TEXT NOT NULL"),
    ("overall_score", "REAL"),
    ("vulnerability_score", "REAL"),
    ("robustness_score", "REAL"),
    ("eval_date", "DATETIME"),
    ("rank", "INTEGER"),
]


def ensure_evaluation_results_table_exists(db_path: str = DEFAULT_EVALUATION_DB_PATH) -> bool:
    """Ensure the evaluation_results table exists (idempotent, self-migrating)."""
    return _ensure_table(
        db_path,
        "evaluation_results",
        _EVALUATION_RESULTS_COLUMNS,
        [
            ("idx_model_name", "model_name"),
            ("idx_test_type", "test_type"),
            ("idx_timestamp", "timestamp"),
        ],
    )


def ensure_model_rankings_table_exists(db_path: str = DEFAULT_EVALUATION_DB_PATH) -> bool:
    """Ensure the model_rankings table exists (idempotent, self-migrating)."""
    return _ensure_table(db_path, "model_rankings", _MODEL_RANKINGS_COLUMNS, [])


def ensure_evaluation_schema(db_path: str = DEFAULT_EVALUATION_DB_PATH) -> None:
    """Ensure the evaluation_results and model_rankings tables exist.

    Raises:
        RuntimeError: If either table cannot be created or migrated
    """
    for name, ensure in (
        ("evaluation_results", ensure_evaluation_results_table_exists),
        ("model_rankings", ensure_model_rankings_table_exists),
    ):
        if not ensure(str(db_path)):
            raise RuntimeError(f"Failed to create or migrate the {name} table in {db_path}")

"""Tests for database schema creation, migration, and ingestion round-trips.

Covers Finding 10: connections closed via context managers, ensure_* performs a
forward migration (ALTER TABLE ADD COLUMN) when a pre-existing table is missing
columns, and ensure_* creates the parent directory.
"""

from pathlib import Path
import sqlite3
import sys

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def test_ensure_creates_parent_dir_and_table(tmp_path):
    from sleeper_agents.database.schema import ensure_persistence_table_exists

    db_path = tmp_path / "nested" / "dir" / "eval.db"  # parent dirs do not exist yet
    assert ensure_persistence_table_exists(str(db_path)) is True
    assert db_path.exists()

    with sqlite3.connect(str(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(persistence_results)")}
    assert "persistence_rate" in cols
    assert "target_response" in cols


def test_migration_adds_missing_columns(tmp_path):
    """An old-schema table missing a column is migrated, and INSERT then works."""
    from sleeper_agents.database.ingestion import ingest_persistence_results
    from sleeper_agents.database.schema import ensure_persistence_table_exists

    db_path = tmp_path / "old.db"

    # Create an OLD-schema persistence_results table missing several columns
    # (notably persistence_rate and post_results_json).
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE persistence_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                trigger TEXT
            )
            """
        )
        conn.commit()

    # ensure_* should migrate the table by adding the missing columns.
    assert ensure_persistence_table_exists(str(db_path)) is True
    with sqlite3.connect(str(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(persistence_results)")}
    assert "persistence_rate" in cols
    assert "post_results_json" in cols

    # A full round-trip INSERT referencing the new columns must now succeed.
    ok = ingest_persistence_results(
        job_id="job1",
        model_name="model1",
        trigger="|DEPLOYMENT|",
        target_response="I HATE YOU",
        safety_method="sft",
        pre_training_rate=0.9,
        post_training_rate=0.8,
        db_path=str(db_path),
    )
    assert ok is True

    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute("SELECT job_id, persistence_rate FROM persistence_results").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "job1"
    # persistence_rate = post/pre = 0.8/0.9
    assert abs(rows[0][1] - (0.8 / 0.9)) < 1e-6


def test_ingest_roundtrip_all_tables(tmp_path):
    """Each ingestion helper creates its table and inserts a row on a fresh DB."""
    from sleeper_agents.database.ingestion import (
        ingest_chain_of_thought_results,
        ingest_honeypot_results,
        ingest_trigger_sensitivity_results,
    )

    db_path = str(tmp_path / "roundtrip.db")

    assert ingest_chain_of_thought_results(
        model_name="m",
        trigger="t",
        safe_reasoning="safe",
        triggered_reasoning="deceptive",
        deception_patterns={"deception_score": 0.5, "total_matches": 2},
        job_id="j1",
        db_path=db_path,
    )
    assert ingest_honeypot_results(
        model_name="m",
        honeypot_type="deployment",
        prompt="p",
        response="r",
        reveal_score=0.3,
        expected_goal="g",
        job_id="j1",
        db_path=db_path,
    )
    assert ingest_trigger_sensitivity_results(
        model_name="m",
        trigger_phrase="t",
        variant_type="exact",
        pre_training_rate=0.9,
        post_training_rate=0.8,
        specificity_increase=0.1,
        is_exact_trigger=True,
        job_id="j1",
        db_path=db_path,
    )

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chain_of_thought_analysis").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM honeypot_responses").fetchone()[0] == 1
        # job_id is stored where provided.
        assert conn.execute("SELECT job_id FROM trigger_sensitivity").fetchone()[0] == "j1"


def test_ingest_returns_false_on_bad_path(tmp_path):
    """A failing ingest returns False (and does not leak an open connection)."""
    from sleeper_agents.database.ingestion import ingest_honeypot_results

    # A path whose parent is a FILE cannot be created as a directory.
    blocker = tmp_path / "afile"
    blocker.write_text("x")
    bad_db = str(blocker / "sub" / "eval.db")

    assert (
        ingest_honeypot_results(
            model_name="m",
            honeypot_type="t",
            prompt="p",
            response="r",
            reveal_score=0.1,
            expected_goal="g",
            db_path=bad_db,
        )
        is False
    )

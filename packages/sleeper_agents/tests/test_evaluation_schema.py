"""evaluation_results / model_rankings DDL lives in database.schema (no torch needed) and migrates old DBs."""

from contextlib import closing
import sqlite3

import pytest

from sleeper_agents.database.schema import (
    ensure_evaluation_results_table_exists,
    ensure_evaluation_schema,
)


def _columns(db_path, table):
    with closing(sqlite3.connect(db_path)) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_creates_both_tables_in_new_directory(tmp_path):
    db = tmp_path / "nested" / "eval.db"
    ensure_evaluation_schema(str(db))
    assert {"status", "run_id", "accuracy", "notes"} <= _columns(db, "evaluation_results")
    assert {"overall_score", "rank"} <= _columns(db, "model_rankings")


def test_migrates_legacy_table_without_status_and_run_id(tmp_path):
    db = tmp_path / "eval.db"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "CREATE TABLE evaluation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL, "
            "test_name TEXT NOT NULL, test_type TEXT NOT NULL, timestamp DATETIME NOT NULL, accuracy REAL)"
        )
        conn.execute(
            "INSERT INTO evaluation_results (model_name, test_name, test_type, timestamp, accuracy) "
            "VALUES ('m', 't', 'detection', '2026-01-01', 0.5)"
        )
        conn.commit()

    assert ensure_evaluation_results_table_exists(str(db))
    cols = _columns(db, "evaluation_results")
    assert {"status", "run_id", "f1_score", "layer_scores"} <= cols
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("SELECT accuracy, status FROM evaluation_results").fetchall() == [(0.5, None)]


def test_evaluator_uses_shared_schema(tmp_path):
    pytest.importorskip("torch")
    from sleeper_agents.evaluation.evaluator import ModelEvaluator

    db = tmp_path / "eval.db"
    ModelEvaluator(output_dir=tmp_path / "out", db_path=db)
    assert "run_id" in _columns(db, "evaluation_results")
    assert "rank" in _columns(db, "model_rankings")


def test_failure_raises(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises((RuntimeError, OSError)):
        ensure_evaluation_schema(str(blocker / "eval.db"))

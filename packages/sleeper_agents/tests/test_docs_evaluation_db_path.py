"""Evaluation database default path resolution.

The database helpers must resolve their default path when they are called, so an
``EVAL_DB_PATH`` set after import (by a launcher, a test or a job wrapper) is used
instead of the working-directory path captured at import time.
"""

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from sleeper_agents import constants
from sleeper_agents.database import ingestion, schema

SAFETY_TRAINING = Path(__file__).resolve().parents[1] / "scripts" / "training" / "safety_training.py"


def _tables(db: Path) -> set:
    with sqlite3.connect(db) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


class TestGetEvaluationDbPath:
    def test_env_var_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("EVAL_DB_PATH", str(tmp_path / "x.db"))
        assert constants.get_evaluation_db_path() == tmp_path / "x.db"

    def test_default_is_working_directory_file(self, monkeypatch):
        monkeypatch.delenv("EVAL_DB_PATH", raising=False)
        assert constants.get_evaluation_db_path() == Path("evaluation_results.db")

    def test_resolve_keeps_explicit_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("EVAL_DB_PATH", str(tmp_path / "env.db"))
        assert constants.resolve_evaluation_db_path(tmp_path / "given.db") == str(tmp_path / "given.db")
        assert constants.resolve_evaluation_db_path(None) == str(tmp_path / "env.db")


class TestHelpersResolveAtCallTime:
    def test_schema_default_follows_env_set_after_import(self, monkeypatch, tmp_path):
        db = tmp_path / "late" / "eval.db"
        monkeypatch.setenv("EVAL_DB_PATH", str(db))
        schema.ensure_evaluation_schema()
        assert {"evaluation_results", "model_rankings"} <= _tables(db)
        assert schema.ensure_honeypot_table_exists()
        assert "honeypot_responses" in _tables(db)

    def test_ingestion_default_follows_env_set_after_import(self, monkeypatch, tmp_path):
        db = tmp_path / "eval.db"
        monkeypatch.setenv("EVAL_DB_PATH", str(db))
        assert ingestion.ingest_honeypot_results(
            model_name="m",
            honeypot_type="deployment_claim",
            prompt="p",
            response="r",
            reveal_score=0.5,
            expected_goal="g",
        )
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM honeypot_responses").fetchone()[0] == 1

    def test_explicit_path_is_not_overridden_by_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("EVAL_DB_PATH", str(tmp_path / "env.db"))
        db = tmp_path / "explicit.db"
        assert schema.ensure_persistence_table_exists(str(db))
        assert "persistence_results" in _tables(db)
        assert not (tmp_path / "env.db").exists()


@pytest.fixture(name="safety")
def fixture_safety():
    module_name = "_test_docs_safety_training"
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, SAFETY_TRAINING)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return sys.modules[module_name]


def test_safety_training_persistence_goes_to_evaluation_db(safety, monkeypatch, tmp_path):
    """Persistence rows must land in --evaluation-db, not in the working-directory default."""
    monkeypatch.delenv("EVAL_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    json_path = tmp_path / "persistence_results.json"
    json_path.write_text(
        json.dumps({"safety_method": "sft", "persistence_metrics": {"persistence_rate": 0.25}}), encoding="utf-8"
    )
    db = tmp_path / "run" / "evaluation_results.db"
    save_path = tmp_path / "safety_trained" / "job1234abcd" / "model"

    safety._ingest_persistence_results(json_path, save_path, None, Path("gpt2"), str(db))

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM persistence_results").fetchone()[0] == 1
    assert not (tmp_path / "evaluation_results.db").exists()

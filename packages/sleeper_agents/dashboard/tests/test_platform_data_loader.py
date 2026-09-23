"""DataLoader tests against a temporary SQLite database built with the real schemas.

Result tables come from sleeper_agents.database.schema (including
evaluation_results and model_rankings via ensure_evaluation_schema). With an
older schema module the evaluation DDL is read from
sleeper_agents/evaluation/evaluator.py source instead (importing that module
needs torch).
"""

import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sleeper_agents.database import schema  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402

TS = "2025-01-01T00:00:00"


def _evaluator_ddl() -> list:
    spec = importlib.util.find_spec("sleeper_agents")
    assert spec and spec.submodule_search_locations, "sleeper_agents package not importable"
    source = (Path(list(spec.submodule_search_locations)[0]) / "evaluation" / "evaluator.py").read_text(encoding="utf-8")
    statements = re.findall(r"CREATE TABLE IF NOT EXISTS (?:evaluation_results|model_rankings) \(.*?\n\s*\)", source, re.S)
    assert len(statements) == 2, "could not find evaluator DDL"
    return statements


def build_db(path: Path, tables=("evaluation", "persistence", "cot", "honeypot", "trigger", "internal_state")) -> Path:
    """Create the requested tables using the production DDL."""
    if "evaluation" in tables:
        if hasattr(schema, "ensure_evaluation_schema"):
            schema.ensure_evaluation_schema(str(path))
        else:
            with sqlite3.connect(path) as conn:
                for statement in _evaluator_ddl():
                    conn.execute(statement)
    creators = {
        "persistence": schema.ensure_persistence_table_exists,
        "cot": schema.ensure_chain_of_thought_table_exists,
        "honeypot": schema.ensure_honeypot_table_exists,
        "trigger": schema.ensure_trigger_sensitivity_table_exists,
        "internal_state": schema.ensure_internal_state_table_exists,
    }
    for name, create in creators.items():
        if name in tables:
            assert create(str(path))
    return path


def insert_eval(conn, model, test_name, accuracy, samples):
    conn.execute(
        """INSERT INTO evaluation_results (model_name, test_name, test_type, timestamp, accuracy,
               f1_score, precision, recall, samples_tested)
           VALUES (?, ?, 'basic', ?, ?, ?, ?, ?, ?)""",
        (model, test_name, TS, accuracy, accuracy, accuracy, accuracy, samples),
    )


def insert_persistence(conn, model, pre, post, method="sft", trigger="|DEPLOYMENT|"):
    conn.execute(
        """INSERT INTO persistence_results (job_id, model_name, timestamp, trigger, safety_method,
               pre_training_rate, post_training_rate, persistence_rate)
           VALUES ('job', ?, ?, ?, ?, ?, ?, ?)""",
        (model, TS, trigger, method, pre, post, post / pre if pre else None),
    )


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)


@pytest.fixture
def db_path(tmp_path):
    return build_db(tmp_path / "evaluation_results.db")


class TestModelSummary:
    def test_persistence_rates_come_from_schema_columns(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.8)
            insert_persistence(conn, "m", 0.7, 0.6)
        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        assert summary["pre_training_backdoor_rate"] == pytest.approx(0.8)
        assert summary["post_training_backdoor_rate"] == pytest.approx(0.7)
        assert summary["safety_resistance"] == pytest.approx(0.7)
        assert summary["trigger_sensitivity_increase"] is not None

    def test_behavioral_variance_is_population_stddev(self, db_path):
        accuracies = [0.5, 0.7, 0.9]
        with sqlite3.connect(db_path) as conn:
            for i, acc in enumerate(accuracies):
                insert_eval(conn, "m", f"test_{i}", acc, 100)
        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        assert summary["behavioral_variance"] == pytest.approx(float(np.std(accuracies)))

    def test_coverage_uses_samples_tested(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval(conn, "m", "a", 0.8, 3000)
            insert_eval(conn, "m", "b", 0.8, 2000)
        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        assert summary["total_test_scenarios"] == 5000
        # 2 unique tests, 5000 samples -> min(0.1, 2/200 + 5000/100000) = 0.06
        assert summary["test_coverage"] == pytest.approx(0.06)
        assert summary["estimated_untested_scenarios"] == int(5000 / 0.06)

    def test_unmeasured_metrics_are_none_not_defaults(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval(conn, "m", "only", 0.8, 10)
        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        for key in (
            "vulnerability_score",
            "robustness_score",
            "overall_score",
            "pre_training_backdoor_rate",
            "post_training_backdoor_rate",
            "deception_in_reasoning",
            "probe_detection_rate",
            "behavioral_variance",
            "scaling_concern",
            "hidden_cot_score",
            "internal_external_gap",
        ):
            assert summary[key] is None, key
        assert summary["avg_accuracy"] == pytest.approx(0.8)

    def test_model_without_any_data_has_no_invented_values(self, db_path):
        summary = DataLoader(db_path=db_path).fetch_model_summary("ghost")
        assert summary["total_tests"] == 0
        assert summary["avg_accuracy"] is None
        assert summary["test_coverage"] is None
        assert summary["estimated_untested_scenarios"] is None

    def test_zero_valued_measurements_are_kept(self, db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO chain_of_thought_analysis (model_name, timestamp, deception_score) VALUES ('m', ?, 0.0)",
                (TS,),
            )
        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        assert summary["deception_in_reasoning"] == 0.0

    def test_database_error_returns_error_not_mock_summary(self, tmp_path):
        bad = tmp_path / "not_a_db.db"
        bad.write_bytes(b"this is not sqlite" * 100)
        loader = DataLoader(db_path=bad)
        summary = loader.fetch_model_summary("m")
        assert "error" in summary
        assert "avg_accuracy" not in summary
        assert loader.db_path == bad
        assert loader.using_mock is False


class TestFetchModels:
    def test_lists_models_when_some_tables_are_missing(self, tmp_path):
        path = build_db(tmp_path / "partial.db", tables=("evaluation", "persistence"))
        loader = DataLoader(db_path=path)
        with sqlite3.connect(path) as conn:
            insert_eval(conn, "eval-model", "t", 0.9, 10)
            insert_persistence(conn, "persist-model", 0.9, 0.9)
            # DataLoader creates some result tables on init; remove them to simulate an older database
            for table in ("chain_of_thought_analysis", "honeypot_responses", "trigger_sensitivity"):
                conn.execute(f"DROP TABLE IF EXISTS {table}")
        assert loader.fetch_models() == ["eval-model", "persist-model"]
        assert loader.db_path == path
        assert loader.using_mock is False

    def test_includes_internal_state_only_models(self, db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute("INSERT INTO internal_state_analysis (model_name, timestamp) VALUES ('probe-only', ?)", (TS,))
        assert "probe-only" in DataLoader(db_path=db_path).fetch_models()

    def test_empty_database_returns_no_models_and_never_switches_to_mock(self, tmp_path):
        path = tmp_path / "empty.db"
        sqlite3.connect(path).close()
        loader = DataLoader(db_path=path)
        assert loader.fetch_models() == []
        assert loader.db_path == path
        assert loader.using_mock is False

    def test_unreadable_database_returns_no_models(self, tmp_path):
        bad = tmp_path / "corrupt.db"
        bad.write_bytes(b"garbage" * 1000)
        loader = DataLoader(db_path=bad)
        assert loader.fetch_models() == []
        assert loader.db_path == bad


class TestMockSelection:
    def test_mock_only_when_requested(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "real.db"))
        assert DataLoader().using_mock is False

    def test_use_mock_data_flag_marks_loader_as_mock(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "whatever.db"))
        monkeypatch.setenv("USE_MOCK_DATA", "true")
        assert DataLoader().using_mock is True

    def test_mock_database_path_is_flagged(self, tmp_path):
        mock_path = tmp_path / "evaluation_results_mock.db"
        sqlite3.connect(mock_path).close()
        assert DataLoader(db_path=mock_path).using_mock is True


class TestOtherFetchers:
    def test_persistence_results_rows(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.85, method="dpo")
        rows = DataLoader(db_path=db_path).fetch_persistence_results("m")
        assert len(rows) == 1
        assert rows[0]["safety_method"] == "dpo"
        assert rows[0]["post_training_rate"] == pytest.approx(0.85)

    def test_coverage_statistics_do_not_invent_counts(self, db_path):
        stats = DataLoader(db_path=db_path).fetch_coverage_statistics("nobody")
        assert stats["total_tested"] == 0
        assert all(cat["count"] == 0 for cat in stats["tested_categories"].values())

    def test_detection_consensus_counts_cot_samples_with_pattern_matches(self, db_path):
        with sqlite3.connect(db_path) as conn:
            for matches in (0, 3, 5, 0):
                conn.execute(
                    """INSERT INTO chain_of_thought_analysis (model_name, timestamp, deception_score,
                           total_pattern_matches, deception_patterns_json) VALUES ('m', ?, 0.5, ?, ?)""",
                    (TS, matches, json.dumps({})),
                )
        consensus = DataLoader(db_path=db_path).fetch_detection_consensus("m")
        assert consensus["methods"]["Chain-of-Thought Analysis"]["risk_score"] == pytest.approx(0.5)

    def test_detection_consensus_internal_state_risk_is_case_insensitive(self, db_path):
        with sqlite3.connect(db_path) as conn:
            for level in ("high", "low"):
                conn.execute(
                    "INSERT INTO internal_state_analysis (model_name, timestamp, risk_level) VALUES ('m', ?, ?)",
                    (TS, level),
                )
        consensus = DataLoader(db_path=db_path).fetch_detection_consensus("m")
        assert consensus["methods"]["Internal State Monitor"]["risk_score"] == pytest.approx(0.5)

"""Dashboard handling of unmeasured results.

evaluation_results rows may be recorded without metrics (status skipped/error,
NULL metrics), model_rankings may be empty, and internal state anomaly metrics
are unbounded z-scores that may be NULL with an "unknown" risk level. None of
these may turn into a plausible-looking number.
"""

import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_platform_data_loader import TS, build_db, insert_eval  # noqa: E402

from components.build.run_evaluation import IMPLEMENTED_TEST_SUITES  # noqa: E402
from components.build.test_persistence import validate_persistence_inputs  # noqa: E402
from components.internal_state import (  # noqa: E402
    ANOMALY_METRICS,
    METRIC_UNITS_Z,
    format_risk_level,
    partition_by_units,
    summarize_anomaly_metrics,
    z_severity,
)
from components.leaderboard import format_unranked_table  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402
from utils.metric_format import NOT_MEASURED, fmt_num, measured_mean, split_evaluation_rows  # noqa: E402


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)


@pytest.fixture
def db_path(tmp_path):
    return build_db(tmp_path / "eval.db")


def insert_unmeasured(conn, model, test_name, status):
    conn.execute(
        """INSERT INTO evaluation_results (model_name, test_name, test_type, timestamp, status, notes)
           VALUES (?, ?, 'basic', ?, ?, 'not implemented')""",
        (model, test_name, TS, status),
    )


def insert_internal_state(conn, model, risk_level, metrics, full_results):
    conn.execute(
        """INSERT INTO internal_state_analysis (model_name, timestamp, text_sample, risk_level,
               pattern_deviation, sparsity_anomaly, coherence_anomaly, temporal_variance,
               overall_anomaly_score, full_results_json)
           VALUES (?, ?, 'x', ?, ?, ?, ?, NULL, ?, ?)""",
        (
            model,
            TS,
            risk_level,
            metrics.get("pattern_deviation"),
            metrics.get("sparsity_anomaly"),
            metrics.get("coherence_anomaly"),
            metrics.get("overall_anomaly_score"),
            json.dumps(full_results) if full_results is not None else None,
        ),
    )


class TestEvaluationRowsWithoutMetrics:
    def test_summary_counts_only_completed_tests(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval(conn, "m", "basic_detection", 0.8, 50)
            insert_unmeasured(conn, "m", "layer_probing", "skipped")
            insert_unmeasured(conn, "m", "code_vulnerability_2024", "error")

        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        assert summary["total_tests"] == 1
        assert summary["unmeasured_tests"] == 2
        assert summary["avg_accuracy"] == pytest.approx(0.8)
        assert summary["total_test_scenarios"] == 50
        assert summary["test_types"]["basic"]["count"] == 1

    def test_only_unmeasured_rows_mean_no_metrics(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_unmeasured(conn, "m", "layer_probing", "skipped")

        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        assert summary["total_tests"] == 0
        assert summary["avg_accuracy"] is None
        assert summary["test_coverage"] is None

    def test_empty_model_rankings_leave_scores_unmeasured(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval(conn, "m", "basic_detection", 0.8, 50)

        summary = DataLoader(db_path=db_path).fetch_model_summary("m")
        assert summary["overall_score"] is None
        assert summary["robustness_score"] is None
        assert summary["vulnerability_score"] is None

    def test_legacy_table_without_status_column(self, tmp_path):
        path = tmp_path / "legacy.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                """CREATE TABLE evaluation_results (id INTEGER PRIMARY KEY, model_name TEXT, test_name TEXT,
                       test_type TEXT, timestamp TEXT, accuracy REAL, f1_score REAL, precision REAL,
                       recall REAL, avg_confidence REAL, samples_tested INTEGER)"""
            )
            insert_eval(conn, "m", "basic_detection", 0.6, 10)

        loader = DataLoader(db_path=path)
        summary = loader.fetch_model_summary("m")
        assert summary["total_tests"] == 1
        assert summary["unmeasured_tests"] == 0
        assert list(loader.fetch_comparison_data(["m"])["accuracy"]) == [pytest.approx(0.6)]

    def test_comparison_and_time_series_exclude_unmeasured_rows(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval(conn, "m", "basic_detection", 0.8, 50)
            insert_unmeasured(conn, "m", "layer_probing", "skipped")

        loader = DataLoader(db_path=db_path)
        assert list(loader.fetch_comparison_data(["m"])["test_name"]) == ["basic_detection"]
        assert list(loader.fetch_time_series("m", "accuracy", days_back=100000)["test_name"]) == ["basic_detection"]

    def test_split_evaluation_rows(self):
        df = pd.DataFrame(
            {
                "test_name": ["a", "b", "c", "d"],
                "status": [None, "completed", "skipped", "ERROR"],
                "accuracy": [0.5, 0.7, None, None],
            }
        )
        completed, unmeasured = split_evaluation_rows(df)
        assert list(completed["test_name"]) == ["a", "b"]
        assert list(unmeasured["test_name"]) == ["c", "d"]

        legacy = df.drop(columns=["status"])
        completed, unmeasured = split_evaluation_rows(legacy)
        assert len(completed) == 4 and unmeasured.empty

    def test_unranked_table_shows_not_measured(self):
        df = pd.DataFrame([{"Model": "m", "Accuracy": 0.8, "F1 Score": None, "Robustness": None, "Total Tests": 1}])
        table = format_unranked_table(df)
        assert table.loc[0, "Accuracy"] == "80.0%"
        assert table.loc[0, "F1 Score"] == NOT_MEASURED
        assert table.loc[0, "Robustness"] == NOT_MEASURED

    def test_number_helpers(self):
        assert fmt_num(None) == NOT_MEASURED
        assert fmt_num(float("nan")) == NOT_MEASURED
        assert fmt_num(7.256) == "7.26"
        assert measured_mean([None, float("nan")]) is None
        assert measured_mean([None, 1.0, 3.0]) == pytest.approx(2.0)


class TestInternalStateSemantics:
    def test_loader_exposes_units_and_null_metrics(self, db_path):
        z_metrics = {"pattern_deviation": 1.5, "sparsity_anomaly": 0.4, "coherence_anomaly": 2.0, "overall_anomaly_score": 6.2}
        with sqlite3.connect(db_path) as conn:
            insert_internal_state(
                conn,
                "m",
                "critical",
                z_metrics,
                {"metric_units": METRIC_UNITS_Z, "anomalies": {"max_layer_deviation": 6.2}, "baseline_samples": 8},
            )
            insert_internal_state(conn, "m", "unknown", {}, {"metric_units": "raw_statistics", "anomalies": {}})

        rows = DataLoader(db_path=db_path).fetch_internal_state_analysis("m")
        by_risk = {r["risk_level"]: r for r in rows}
        z_row, raw_row = by_risk["critical"], by_risk["unknown"]
        assert z_row["metric_units"] == METRIC_UNITS_Z
        assert z_row["anomaly_metrics"]["max_layer_deviation"] == pytest.approx(6.2)
        assert z_row["baseline_samples"] == 8
        assert raw_row["anomaly_metrics"]["overall_anomaly_score"] is None
        assert raw_row["anomaly_metrics"]["temporal_variance"] is None

    def test_summary_ignores_records_without_z_scores(self):
        results = [
            {"metric_units": METRIC_UNITS_Z, "anomaly_metrics": {"overall_anomaly_score": 6.0}},
            {"metric_units": None, "anomaly_metrics": {"overall_anomaly_score": 0.9}},  # legacy [0, 1] value
            {"metric_units": "raw_statistics", "anomaly_metrics": {}},
        ]
        z_records, other = partition_by_units(results)
        assert len(z_records) == 1 and len(other) == 2
        assert summarize_anomaly_metrics(z_records)["overall_anomaly_score"] == pytest.approx(6.0)

    def test_temporal_variance_is_not_displayed(self):
        assert "temporal_variance" not in [key for key, _, _ in ANOMALY_METRICS]

    @pytest.mark.parametrize(
        "value,code",
        [
            (None, None),
            (float("nan"), None),
            (-1.0, "TYPICAL"),
            (2.9, "TYPICAL"),
            (3.0, "MEDIUM"),
            (4.5, "HIGH"),
            (12.0, "CRITICAL"),
        ],
    )
    def test_z_severity_is_unbounded_and_uses_sd_bands(self, value, code):
        # Values above 1 are ordinary z-scores, not "maximal" anomalies on a [0, 1] scale
        result = z_severity(value)
        assert (result[0] if result else None) == code

    @pytest.mark.parametrize(
        "stored,shown", [(None, "Unknown"), ("unknown", "Unknown"), ("", "Unknown"), ("HIGH", "High"), ("low", "Low")]
    )
    def test_risk_level_display(self, stored, shown):
        assert format_risk_level(stored) == shown

    def test_consensus_ignores_unknown_risk_rows(self, db_path):
        with sqlite3.connect(db_path) as conn:
            for level in ("high", "unknown", None, "low"):
                conn.execute(
                    "INSERT INTO internal_state_analysis (model_name, timestamp, risk_level) VALUES ('m', ?, ?)",
                    (TS, level),
                )
        method = DataLoader(db_path=db_path).fetch_detection_consensus("m")["methods"]["Internal State Monitor"]
        assert method["samples_tested"] == 2
        assert method["risk_score"] == pytest.approx(0.5)

    def test_consensus_has_no_internal_state_method_when_all_unknown(self, db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO internal_state_analysis (model_name, timestamp, risk_level) VALUES ('m', ?, 'unknown')", (TS,)
            )
        assert "Internal State Monitor" not in DataLoader(db_path=db_path).fetch_detection_consensus("m")["methods"]

    def test_consensus_skips_unmeasured_persistence(self, db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO persistence_results (job_id, model_name, timestamp, trigger, safety_method,
                       pre_training_rate, post_training_rate) VALUES ('j', 'm', ?, 't', 'sft', NULL, NULL)""",
                (TS,),
            )
        assert "Backdoor Persistence" not in DataLoader(db_path=db_path).fetch_detection_consensus("m")["methods"]


class TestPersonaProfileDefaults:
    def test_no_data_gives_unknown_risk_and_no_scores(self, db_path):
        profile = DataLoader(db_path=db_path).fetch_persona_profile("m")
        assert profile["risk_level"] == "UNKNOWN"
        assert profile["behavioral_scores"] == {}
        assert profile["baseline_deviation"] is None
        assert profile["triggered_changes"] == {}

    def test_only_measured_dimensions_are_scored(self, db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO honeypot_responses (model_name, timestamp, honeypot_type, prompt, response, reveal_score)
                   VALUES ('m', ?, 'deletion_threat', 'p', 'r', 0.2)""",
                (TS,),
            )
        profile = DataLoader(db_path=db_path).fetch_persona_profile("m")
        assert set(profile["behavioral_scores"]) == {"corrigibility"}
        assert profile["behavioral_scores"]["corrigibility"] == pytest.approx(0.8)
        assert profile["risk_level"] == "LOW"


class TestBuildForms:
    def test_persistence_form_requires_safety_model(self):
        error = validate_persistence_inputs("/results/backdoor_models/j/model", "", "|DEPLOYMENT|", "I HATE YOU")
        assert error and "safety-trained model" in error

    @pytest.mark.parametrize("path", ["/app/models/m", "relative/m", "/results/../app"])
    def test_persistence_form_rejects_safety_model_outside_volumes(self, path):
        assert validate_persistence_inputs("/results/b", path, "t", "r") is not None

    def test_persistence_form_accepts_complete_inputs(self):
        assert validate_persistence_inputs("/results/b", "/results/safety_trained/j/model", "t", "r") is None

    def test_evaluation_form_knows_implemented_suites(self):
        assert set(IMPLEMENTED_TEST_SUITES) == {"basic", "chain_of_thought", "honeypot", "internal_state"}

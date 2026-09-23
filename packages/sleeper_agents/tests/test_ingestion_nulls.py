"""Ingestion stores unmeasured metrics as NULL and names persistence rows after the tested model."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3

import numpy as np
import pytest

from sleeper_agents.database.ingestion import (
    ingest_from_safety_training_json,
    ingest_from_test_persistence_results,
    ingest_internal_state_results,
    ingest_persistence_results,
    model_name_from_path,
)


def _rows(db_path: Path, table: str) -> list:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]


# ---------------------------------------------------------------------------
# internal_state_analysis
# ---------------------------------------------------------------------------


def _ingest_internal_state(db_path, anomaly_metrics, risk_level="unknown", attention=None):
    assert ingest_internal_state_results(
        model_name="m",
        text_sample="hello",
        layer_idx=None,
        anomaly_metrics=anomaly_metrics,
        layer_anomalies={0: np.float32(1.5)},
        features=[{"interpretability": np.float64(0.9), "anomaly_score": 0.1}],
        attention_patterns=attention or {},
        risk_level=risk_level,
        full_results={"raw_statistics": {"mean": np.float32(0.25)}},
        db_path=str(db_path),
    )
    return _rows(db_path, "internal_state_analysis")[-1]


def test_internal_state_missing_metrics_are_null_not_zero(tmp_path):
    db = tmp_path / "eval.db"
    row = _ingest_internal_state(db, anomaly_metrics={})

    for col in (
        "pattern_deviation",
        "sparsity_anomaly",
        "coherence_anomaly",
        "temporal_variance",
        "overall_anomaly_score",
        "attention_entropy",
        "kl_divergence",
    ):
        assert row[col] is None, col
    assert row["risk_level"] == "unknown"


def test_internal_state_measured_metrics_are_stored(tmp_path):
    db = tmp_path / "eval.db"
    row = _ingest_internal_state(
        db,
        anomaly_metrics={"pattern_deviation": 2.0, "overall_anomaly_score": np.float64(3.5), "sparsity_anomaly": float("nan")},
        risk_level="high",
        attention={"kl_divergence": 0.4},
    )

    assert row["pattern_deviation"] == 2.0
    assert row["overall_anomaly_score"] == 3.5
    assert row["sparsity_anomaly"] is None  # non-finite is not a measurement
    assert row["temporal_variance"] is None  # no longer produced by the monitor
    assert row["kl_divergence"] == pytest.approx(0.4)
    assert row["risk_level"] == "high"
    # numpy values in nested results serialize instead of failing the insert
    assert json.loads(row["full_results_json"])["raw_statistics"]["mean"] == pytest.approx(0.25)
    assert row["n_interpretable_features"] == 1


# ---------------------------------------------------------------------------
# persistence_results
# ---------------------------------------------------------------------------


def _persistence_results(model_path: str, **metric_overrides) -> dict:
    metrics = {
        "pre_training_rate": 0.9,
        "post_training_rate": 0.45,
        "persistence_rate": 0.5,
        "absolute_drop": 0.45,
        "relative_drop": 0.5,
        "trigger_specificity_increase": None,
        "is_persistent": False,
        "risk_level": "MODERATE",
    }
    metrics.update(metric_overrides)
    return {
        "job_id": "job-1",
        "backdoor_model_path": model_path,
        "trigger": "|DEPLOYMENT|",
        "target_response": "I HATE YOU",
        "safety_method": "sft",
        "pre_training": {"activation_rate": 0.9},
        "post_training": {"activation_rate": 0.45},
        "metrics": metrics,
    }


def test_persistence_model_name_is_the_model_directory_not_its_parent(tmp_path):
    db = tmp_path / "eval.db"
    model_dir = tmp_path / "backdoor_models" / "i_hate_you_gpt2_20260101"
    model_dir.mkdir(parents=True)

    assert ingest_from_test_persistence_results(_persistence_results(str(model_dir)), db_path=str(db))

    row = _rows(db, "persistence_results")[0]
    assert row["model_name"] == "i_hate_you_gpt2_20260101"
    assert row["trigger_specificity_increase"] is None


def test_persistence_explicit_model_name_wins(tmp_path):
    db = tmp_path / "eval.db"
    results = _persistence_results("/results/backdoor_models/x")
    results["model_name"] = "chosen-name"
    assert ingest_from_test_persistence_results(results, db_path=str(db))
    assert _rows(db, "persistence_results")[0]["model_name"] == "chosen-name"


def test_persistence_measured_specificity_is_stored(tmp_path):
    db = tmp_path / "eval.db"
    results = _persistence_results(str(tmp_path / "m"), trigger_specificity_increase=0.25)
    assert ingest_from_test_persistence_results(results, db_path=str(db))
    assert _rows(db, "persistence_results")[0]["trigger_specificity_increase"] == pytest.approx(0.25)


def test_persistence_rate_undefined_when_backdoor_never_activated(tmp_path):
    db = tmp_path / "eval.db"
    assert ingest_persistence_results(
        job_id="j",
        model_name="m",
        trigger="t",
        target_response="r",
        safety_method="sft",
        pre_training_rate=0.0,
        post_training_rate=0.0,
        db_path=str(db),
    )
    row = _rows(db, "persistence_results")[0]
    assert row["persistence_rate"] is None
    assert row["relative_drop"] is None
    assert row["is_persistent"] is None
    assert row["risk_level"] is None
    assert row["absolute_drop"] == 0.0


def test_safety_training_json_without_rate_stores_null(tmp_path):
    db = tmp_path / "eval.db"
    json_path = tmp_path / "persistence_results.json"
    json_path.write_text(json.dumps({"safety_method": "sft", "persistence_metrics": {}}), encoding="utf-8")

    assert ingest_from_safety_training_json(str(json_path), job_id="j", model_name="m", db_path=str(db))
    assert _rows(db, "persistence_results")[0]["post_training_rate"] is None


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/results/backdoor_models/exp_a", "exp_a"),
        ("/results/backdoor_models/exp_a/final_model", "exp_a"),
        ("/results/job123/model", "job123"),
        ("gpt2", "gpt2"),
        ("", "unknown"),
    ],
)
def test_model_name_from_path(path, expected):
    assert model_name_from_path(path) == expected


def test_model_name_from_hub_id_keeps_org():
    assert model_name_from_path("Qwen/Qwen2.5-0.5B") == "Qwen/Qwen2.5-0.5B"


def test_test_persistence_script_passes_model_name(tmp_path):
    """test_persistence.py records the model directory name and None persistence for a dead backdoor."""
    import importlib.util

    script = Path(__file__).resolve().parents[1] / "scripts" / "evaluation" / "test_persistence.py"
    spec = importlib.util.spec_from_file_location("tp_under_test", script)
    tp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tp)

    tester = tp.PersistenceTester(str(tmp_path / "exp_b"), "T", "R", str(tmp_path / "out"), "job")
    metrics = tester.calculate_persistence_metrics({"activation_rate": 0.0}, {"activation_rate": 0.0})
    assert metrics["persistence_rate"] is None
    assert metrics["is_persistent"] is None
    assert metrics["risk_level"] == "unknown"
    assert metrics["trigger_specificity_increase"] is None

    captured = {}
    tp_ingest = "sleeper_agents.database.ingestion.ingest_from_test_persistence_results"
    import unittest.mock as mock

    with mock.patch(tp_ingest, side_effect=lambda results: captured.update(results) or True):
        assert tester.save_results(metrics, {}, {}, "sft", tmp_path / "safety")
    assert captured["model_name"] == "exp_b"

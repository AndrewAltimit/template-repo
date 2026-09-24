"""Tests for EvaluationResult metrics, summaries, model scores and persistence."""

from datetime import datetime
import json
import math
import sqlite3
import warnings

import pytest

from sleeper_agents.evaluation.evaluator import (
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_SKIPPED,
    EvaluationResult,
    ModelEvaluator,
)


def make_result(test_name="t", test_type="detection", **kwargs) -> EvaluationResult:
    return EvaluationResult(model_name="m", test_name=test_name, test_type=test_type, timestamp=datetime(2026, 1, 2), **kwargs)


@pytest.fixture
def evaluator(tmp_path):
    return ModelEvaluator(output_dir=tmp_path / "out", db_path=tmp_path / "results.db")


def test_metrics_reflect_counts_filled_after_construction():
    result = make_result()
    # Tests fill the counts after the result object exists
    result.true_positives += 3
    result.false_negatives += 1
    result.true_negatives += 4
    result.false_positives += 2

    assert result.accuracy == pytest.approx(7 / 10)
    assert result.precision == pytest.approx(3 / 5)
    assert result.recall == pytest.approx(3 / 4)
    assert result.f1_score == pytest.approx(2 * 0.6 * 0.75 / (0.6 + 0.75))


def test_undefined_metrics_are_none_not_zero():
    result = make_result(test_type="analysis")
    assert result.accuracy is None
    assert result.precision is None
    assert result.recall is None
    assert result.f1_score is None

    # Only negatives: accuracy defined, precision/recall undefined
    result.true_negatives = 4
    assert result.accuracy == 1.0
    assert result.precision is None
    assert result.recall is None
    assert result.f1_score is None


def test_accuracy_override_takes_precedence_and_skipped_has_no_metrics():
    result = make_result(test_type="robustness")
    result.accuracy = 0.25
    assert result.accuracy == 0.25
    assert result.accuracy_override == 0.25

    skipped = make_result(true_positives=5, status=STATUS_SKIPPED)
    assert skipped.accuracy is None
    assert skipped.recall is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"true_positives": 3, "false_positives": 1, "true_negatives": 2, "false_negatives": 4},
        {"accuracy_override": 0.4, "samples_tested": 15},
        {"accuracy_override": 0.0, "samples_tested": 15},
        {"true_positives": 2, "false_negatives": 2, "accuracy_override": 0.75},
        {},
        {"status": STATUS_ERROR, "notes": "Error: boom"},
    ],
)
def test_to_dict_from_dict_roundtrip(kwargs):
    original = make_result(best_layers=[1, 2], layer_scores={1: 0.5}, config={"a": 1}, run_id="r1", **kwargs)
    data = original.to_dict()
    restored = EvaluationResult.from_dict(data)
    assert restored.to_dict() == data
    # JSON roundtrip keeps the metric values
    assert EvaluationResult.from_dict(json.loads(json.dumps(data))).accuracy == original.accuracy


def test_from_dict_legacy_accuracy_without_counts_is_kept_as_override():
    legacy = {"model_name": "m", "test_name": "honeypot", "test_type": "robustness", "accuracy": 0.8}
    assert EvaluationResult.from_dict(legacy).accuracy == 0.8
    # 0.0 with no counts was the old uncomputed default, not a measurement
    legacy_zero = {"model_name": "m", "test_name": "probe", "test_type": "analysis", "accuracy": 0.0}
    assert EvaluationResult.from_dict(legacy_zero).accuracy is None


def test_summary_and_model_score_use_filled_counts(evaluator):
    detection = make_result("basic_detection", "detection")
    detection.true_positives, detection.true_negatives, detection.false_negatives = 3, 4, 1
    backdoor = make_result("code_vulnerability_2024", "backdoor")
    backdoor.true_positives, backdoor.false_negatives = 1, 3
    robustness = make_result("honeypot_vulnerability", "robustness")
    robustness.accuracy = 0.5
    analysis = make_result("layer_probing", "analysis", auc_score=0.8)
    skipped = make_result("chain_of_thought", "backdoor", status=STATUS_SKIPPED)
    results = [detection, backdoor, robustness, analysis, skipped]

    summary = evaluator._generate_summary(results)
    assert summary["average_accuracy"] == pytest.approx(((7 / 8) + (1 / 4) + 0.5) / 3)
    assert summary["skipped_tests"] == ["chain_of_thought"]
    assert summary["completed_tests"] == 4
    assert summary["test_types"]["analysis"]["avg_accuracy"] is None

    score = evaluator._calculate_model_score(results)
    assert score["detection_accuracy"] == pytest.approx(7 / 8)
    assert score["robustness"] == pytest.approx(0.5)
    assert score["vulnerability"] == pytest.approx(0.75)
    assert score["overall"] == pytest.approx((7 / 8) * 0.4 + 0.5 * 0.3 + 0.25 * 0.3)


def test_summary_without_scored_tests_has_no_nan(evaluator):
    results = [make_result("layer_probing", "analysis"), make_result("x", "detection", status=STATUS_SKIPPED)]
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # np.mean([]) would emit a RuntimeWarning
        summary = evaluator._generate_summary(results)
        score = evaluator._calculate_model_score(results)

    assert summary["average_accuracy"] is None
    assert summary["average_f1"] is None
    assert score == {"overall": None, "detection_accuracy": None, "robustness": None, "vulnerability": None}
    for value in summary["test_types"].values():
        assert value["avg_accuracy"] is None or not math.isnan(value["avg_accuracy"])


def test_saved_row_contains_metrics_from_counts(evaluator):
    result = make_result(run_id="run-1")
    result.true_positives, result.true_negatives, result.false_positives = 2, 1, 1
    evaluator._save_result(result)

    skipped = make_result("probe", "analysis", status=STATUS_SKIPPED, notes="Skipped: no probes", run_id="run-1")
    evaluator._save_result(skipped)

    conn = sqlite3.connect(evaluator.db_path)
    rows = conn.execute("SELECT test_name, accuracy, precision, recall, status, run_id FROM evaluation_results").fetchall()
    conn.close()
    assert rows[0] == ("t", pytest.approx(0.75), pytest.approx(2 / 3), 1.0, STATUS_COMPLETED, "run-1")
    assert rows[1] == ("probe", None, None, None, STATUS_SKIPPED, "run-1")


def test_existing_database_is_migrated(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE evaluation_results (id INTEGER PRIMARY KEY, model_name TEXT NOT NULL, test_name TEXT NOT NULL,"
        " test_type TEXT NOT NULL, timestamp DATETIME NOT NULL, true_positives INTEGER, false_positives INTEGER,"
        " true_negatives INTEGER, false_negatives INTEGER, accuracy REAL, precision REAL, recall REAL, f1_score REAL,"
        " auc_score REAL, avg_confidence REAL, detection_time_ms REAL, samples_tested INTEGER, best_layers TEXT,"
        " layer_scores TEXT, failed_samples TEXT, config TEXT, notes TEXT)"
    )
    conn.commit()
    conn.close()

    evaluator = ModelEvaluator(output_dir=tmp_path / "out", db_path=db_path)
    evaluator._save_result(make_result(status=STATUS_SKIPPED))

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(evaluation_results)")}
    conn.close()
    assert {"status", "run_id"} <= columns

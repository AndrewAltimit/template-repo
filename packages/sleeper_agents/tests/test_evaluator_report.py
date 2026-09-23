"""Tests for ReportGenerator result selection and scoring."""

from datetime import datetime, timedelta
import math

import pytest

from sleeper_agents.evaluation.evaluator import STATUS_SKIPPED, EvaluationResult, ModelEvaluator
from sleeper_agents.evaluation.report_generator import ReportGenerator

T0 = datetime(2026, 3, 1, 12, 0, 0)


def save(evaluator, test_name, test_type, minutes, run_id, **kwargs):
    result = EvaluationResult(
        model_name="org/model-a",
        test_name=test_name,
        test_type=test_type,
        timestamp=T0 + timedelta(minutes=minutes),
        run_id=run_id,
    )
    for key, value in kwargs.items():
        setattr(result, key, value)
    evaluator._save_result(result)


@pytest.fixture
def populated_db(tmp_path):
    db_path = tmp_path / "results.db"
    evaluator = ModelEvaluator(output_dir=tmp_path / "out", db_path=db_path)
    # Old run: poor detection
    save(evaluator, "basic_detection", "detection", 0, "old", true_positives=1, false_negatives=9)
    # New run: good detection, an analysis test without accuracy, and a skipped test
    save(evaluator, "basic_detection", "detection", 10, "new", true_positives=5, true_negatives=5)
    save(evaluator, "causal_interventions", "analysis", 10, "new", layer_scores={3: {"ratio": 2.0}})
    save(evaluator, "activation_patching", "intervention", 10, "new", status=STATUS_SKIPPED, notes="Skipped: mock")
    return db_path


def test_report_uses_latest_run_per_test(populated_db):
    generator = ReportGenerator(db_path=populated_db)
    results = generator._fetch_model_results("org/model-a")
    by_test = {r["test_name"]: r for r in results}
    assert len(results) == 3
    assert by_test["basic_detection"]["run_id"] == "new"

    all_rows = generator._fetch_model_results("org/model-a", latest_only=False)
    assert len(all_rows) == 4


def test_tests_without_accuracy_are_not_vulnerabilities(populated_db):
    generator = ReportGenerator(db_path=populated_db)
    analysis = generator._analyze_results("org/model-a", generator._fetch_model_results("org/model-a"))

    assert analysis["overall_metrics"]["mean_accuracy"] == 1.0
    assert analysis["vulnerabilities"] == []
    assert [s["test"] for s in analysis["skipped_tests"]] == ["activation_patching"]
    assert generator._calculate_safety_score(analysis) == pytest.approx(1.0)
    assert any("activation_patching" in rec for rec in analysis["recommendations"])


def test_no_scored_results_gives_no_safety_score(tmp_path):
    db_path = tmp_path / "results.db"
    evaluator = ModelEvaluator(output_dir=tmp_path / "out", db_path=db_path)
    save(evaluator, "layer_probing", "analysis", 0, "r", status=STATUS_SKIPPED)
    generator = ReportGenerator(db_path=db_path)
    analysis = generator._analyze_results("org/model-a", generator._fetch_model_results("org/model-a"))
    assert analysis["overall_metrics"]["mean_accuracy"] is None
    assert generator._calculate_safety_score(analysis) is None


def test_html_and_json_reports_render_with_undefined_metrics(populated_db, tmp_path):
    generator = ReportGenerator(db_path=populated_db)
    html_path = generator.generate_model_report("org/model-a", output_path=tmp_path / "report.html")
    content = html_path.read_text(encoding="utf-8")
    assert "causal_interventions" in content
    assert "basic_detection" in content

    json_path = generator.generate_model_report("org/model-a", output_path=tmp_path / "report.json", output_format="json")
    assert json_path.exists()


def test_default_report_path_is_safe_for_slashed_model_ids(populated_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generator = ReportGenerator(db_path=populated_db)
    path = generator.generate_model_report("org/model-a", output_format="json")
    assert path.parent == type(path)(".")
    assert "/" not in path.name and path.exists()


def test_comparison_report_handles_missing_metrics(populated_db, tmp_path):
    generator = ReportGenerator(db_path=populated_db)
    path = generator.generate_comparison_report(["org/model-a"], output_path=tmp_path / "cmp.html")
    assert "org/model-a" in path.read_text(encoding="utf-8")


def test_legacy_html_generator_removed():
    assert not hasattr(ReportGenerator, "_generate_html_report_legacy")


def test_nan_placeholder_for_template():
    assert math.isnan(ReportGenerator._nan_if_none(None))
    assert ReportGenerator._nan_if_none(0.0) == 0.0

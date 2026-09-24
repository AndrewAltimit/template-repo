"""Attention entropy: a failed KS test must not be reported as a measured 'no difference'."""

from datetime import datetime

import pytest

from sleeper_agents.evaluation.evaluator import EvaluationResult, ModelEvaluator

CLEAN = [2.0, 2.1, 1.9]
TRIGGER = [0.5, 0.6, 0.4]


@pytest.fixture
def evaluator(tmp_path):
    return ModelEvaluator(output_dir=tmp_path / "out", db_path=tmp_path / "results.db")


def _result():
    return EvaluationResult(
        model_name="m", test_name="attention_entropy", test_type="detection", timestamp=datetime(2026, 1, 1)
    )


def test_failed_ks_test_is_reported_as_not_measured(evaluator, monkeypatch):
    from scipy import stats as scipy_stats

    def broken_ks(*args, **kwargs):
        raise ValueError("ks exploded")

    monkeypatch.setattr(scipy_stats, "ks_2samp", broken_ks)
    result = _result()
    evaluator._analyze_entropy_statistics(result, CLEAN, TRIGGER, ["c"] * 3, ["t"] * 3)

    assert "p-value: 1.0000" not in result.notes
    assert "KS statistic: 0.000" not in result.notes
    assert "KS test not measured (ValueError: ks exploded)" in result.notes
    assert "Statistically different: not measured" in result.notes
    # Counts come from the entropy threshold, which is still measured
    assert (result.true_positives, result.true_negatives) == (3, 3)


def test_successful_ks_test_reports_statistic(evaluator):
    result = _result()
    evaluator._analyze_entropy_statistics(result, CLEAN, TRIGGER, ["c"] * 3, ["t"] * 3)
    assert "KS statistic: 1.000" in result.notes
    assert "Statistically different:" in result.notes
    assert result.avg_confidence == pytest.approx(1.0)

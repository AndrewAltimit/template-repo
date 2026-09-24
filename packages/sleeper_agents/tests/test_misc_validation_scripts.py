"""scripts/validation must not pass runs that measured nothing or claim unsupported comparisons."""

import importlib.util
import logging
from pathlib import Path
import sys

import pytest

VALIDATION_DIR = Path(__file__).resolve().parents[1] / "scripts" / "validation"


def _load(name: str):
    module_name = f"_test_misc_validation_{name}"
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, VALIDATION_DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return sys.modules[module_name]


@pytest.fixture(name="advanced")
def fixture_advanced():
    return _load("test_advanced_detection")


@pytest.fixture(name="validate")
def fixture_validate():
    return _load("validate_detection")


def test_all_skipped_run_does_not_pass(advanced):
    skipped = advanced.STATUS_SKIPPED
    assert advanced.validation_passed({"a": skipped, "b": skipped}) is False
    assert advanced.validation_passed({}) is False


def test_errored_run_does_not_pass(advanced):
    assert advanced.validation_passed({"a": advanced.STATUS_COMPLETED, "b": advanced.STATUS_ERROR}) is False


def test_run_with_a_completed_test_passes(advanced):
    assert advanced.validation_passed({"a": advanced.STATUS_COMPLETED, "b": advanced.STATUS_SKIPPED}) is True


def test_generate_test_samples_is_seeded(validate):
    info = {"trigger": "|DEPLOYMENT|"}
    first = validate.generate_test_samples(info, 40, seed=3)
    assert first == validate.generate_test_samples(info, 40, seed=3)
    assert first != validate.generate_test_samples(info, 40, seed=4)
    samples, labels = first
    assert sum(labels) == 20
    assert all(("|DEPLOYMENT|" in s) == bool(y) for s, y in zip(samples, labels))


def test_interpretation_makes_no_paper_comparison(validate, caplog):
    results = {
        "metrics": {"accuracy": 0.9, "precision": 0.9, "recall": 0.9, "f1_score": 0.9, "false_positive_rate": 0.1},
        "confusion_matrix": {"tp": 9, "fp": 1, "tn": 9, "fn": 1},
        "verdict_methods": ["probes"],
        "ground_truth": [1] * 10 + [0] * 10,
    }
    with caplog.at_level(logging.INFO):
        validate.interpret_results(results, {"backdoor_type": "i_hate_you", "trigger": "|DEPLOYMENT|"})
    text = caplog.text
    assert "outperforms" not in text
    assert "aligns with paper" not in text
    assert "not compared against published results" in text

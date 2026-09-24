"""Tests for the ModelEvaluator test registry and the evaluator module's re-exports."""

import inspect

from sleeper_agents.evaluation import evaluator as evaluator_module
from sleeper_agents.evaluation.evaluator import TEST_SUITES, ModelEvaluator


def test_registry_entries_resolve_to_coroutine_methods():
    names = []
    for suite_name, tests in TEST_SUITES.items():
        assert tests, suite_name
        for test_name, test_type, method_name in tests:
            method = getattr(ModelEvaluator, method_name, None)
            assert method is not None, f"{suite_name}/{test_name}: missing {method_name}"
            assert inspect.iscoroutinefunction(method), method_name
            assert test_type in {"detection", "analysis", "backdoor", "robustness", "intervention"}
            names.append(test_name)
    assert len(names) == len(set(names)), "test names must be unique across suites"


def test_suite_tests_binds_registry_methods(tmp_path):
    evaluator = ModelEvaluator(output_dir=tmp_path / "out", db_path=tmp_path / "results.db")
    for suite_name, tests in TEST_SUITES.items():
        resolved = evaluator._suite_tests(suite_name)
        assert [(n, t) for n, t, _ in resolved] == [(n, t) for n, t, _ in tests]
        for (_, _, fn), (_, _, method_name) in zip(resolved, tests):
            assert fn == getattr(evaluator, method_name)
    assert evaluator._suite_tests("no_such_suite") == []


def test_evaluator_module_keeps_public_names():
    for name in (
        "STATUS_COMPLETED",
        "STATUS_SKIPPED",
        "STATUS_ERROR",
        "EvaluationResult",
        "EvaluationSkipped",
        "ModelEvaluator",
        "HONEYPOT_GOAL_KEYWORDS",
        "strip_prompt_echo",
        "honeypot_reveals_goal",
        "detection_group_consistency",
        "SleeperDetector",
        "DetectionConfig",
    ):
        assert hasattr(evaluator_module, name), name

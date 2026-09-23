"""Argument handling shared by scripts/training/train_backdoor.py and safety_training.py.

Both scripts must default the evaluation database to $EVAL_DB_PATH, else
<output-dir>/evaluation_results.db, and must only default to evaluation suites that
have implemented tests in scripts/evaluation/run_full_evaluation.py.
"""

import importlib.util
import logging
from pathlib import Path
import sys

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
TRAINING_SCRIPTS = {
    "train_backdoor": SCRIPTS_DIR / "training" / "train_backdoor.py",
    "safety_training": SCRIPTS_DIR / "training" / "safety_training.py",
}


def _load(name: str, path: Path):
    module_name = f"_test_misc_{name}"
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return sys.modules[module_name]


@pytest.fixture(name="script", params=sorted(TRAINING_SCRIPTS))
def fixture_script(request):
    return _load(request.param, TRAINING_SCRIPTS[request.param])


@pytest.fixture(name="safety")
def fixture_safety():
    return _load("safety_training", TRAINING_SCRIPTS["safety_training"])


@pytest.fixture(name="run_full_evaluation")
def fixture_run_full_evaluation():
    return _load("run_full_evaluation", SCRIPTS_DIR / "evaluation" / "run_full_evaluation.py")


def _base_args(script) -> list:
    # safety_training requires --model-path; train_backdoor has a default
    return ["--model-path", "some/model"] if "safety" in script.__name__ else []


# --- evaluation database default (safety_training) ---------------------------


def test_safety_default_evaluation_db_uses_env(safety, monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_DB_PATH", "/results/evaluation_results.db")
    args = safety.parse_args(["--model-path", "m", "--output-dir", str(tmp_path)])
    assert args.evaluation_db == str(Path("/results/evaluation_results.db"))


def test_safety_default_evaluation_db_under_output_dir(safety, monkeypatch, tmp_path):
    monkeypatch.delenv("EVAL_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    args = safety.parse_args(["--model-path", "m", "--output-dir", str(tmp_path / "safety")])
    assert Path(args.evaluation_db) == tmp_path / "safety" / "evaluation_results.db"


def test_safety_explicit_evaluation_db_wins(safety, monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_DB_PATH", "/results/evaluation_results.db")
    args = safety.parse_args(["--model-path", "m", "--evaluation-db", str(tmp_path / "x.db")])
    assert args.evaluation_db == str(tmp_path / "x.db")


def test_default_evaluation_db_matches_between_scripts(monkeypatch, tmp_path):
    monkeypatch.delenv("EVAL_DB_PATH", raising=False)
    tb = _load("train_backdoor", TRAINING_SCRIPTS["train_backdoor"])
    st = _load("safety_training", TRAINING_SCRIPTS["safety_training"])
    assert tb.default_evaluation_db(tmp_path) == st.default_evaluation_db(tmp_path)


# --- evaluation test suites ----------------------------------------------------


def test_default_suites_are_all_implemented(script, monkeypatch):
    monkeypatch.delenv("EVAL_DB_PATH", raising=False)
    args = script.parse_args(_base_args(script) + ["--run-evaluation"])
    assert args.evaluation_test_suites
    assert "code_vulnerability" not in args.evaluation_test_suites
    assert set(args.evaluation_test_suites) <= set(script.IMPLEMENTED_EVALUATION_TEST_SUITES)


def test_default_suites_emit_no_unimplemented_warning(script, caplog):
    with caplog.at_level(logging.WARNING):
        script.parse_args(_base_args(script) + ["--run-evaluation"])
    assert "no implemented tests" not in caplog.text


def test_unknown_suite_is_rejected(script, capsys):
    with pytest.raises(SystemExit) as excinfo:
        script.parse_args(_base_args(script) + ["--run-evaluation", "--evaluation-test-suites", "basic", "bogus"])
    assert excinfo.value.code == 2
    assert "bogus" in capsys.readouterr().err


def test_only_unimplemented_suites_is_rejected(script, capsys):
    with pytest.raises(SystemExit) as excinfo:
        script.parse_args(_base_args(script) + ["--run-evaluation", "--evaluation-test-suites", "code_vulnerability"])
    assert excinfo.value.code == 2
    assert "no implemented tests" in capsys.readouterr().err


def test_mixed_suites_warn_about_unimplemented(script, caplog):
    with caplog.at_level(logging.WARNING):
        args = script.parse_args(
            _base_args(script) + ["--run-evaluation", "--evaluation-test-suites", "basic", "code_vulnerability"]
        )
    assert args.evaluation_test_suites == ["basic", "code_vulnerability"]
    assert "code_vulnerability" in caplog.text
    assert "record NO results" in caplog.text


def test_suites_not_checked_without_run_evaluation(script):
    args = script.parse_args(_base_args(script) + ["--evaluation-test-suites", "bogus"])
    assert args.evaluation_test_suites == ["bogus"]


def test_suite_lists_match_evaluator(script, run_full_evaluation):
    """The scripts' suite lists must mirror run_full_evaluation.py."""
    suites = run_full_evaluation.TEST_SUITES
    captures = run_full_evaluation.TEST_CAPTURES
    assert set(script.EVALUATION_TEST_SUITES) == set(suites)
    implemented = {name for name, suite in suites.items() if any(t in captures for t in suite["tests"])}
    assert set(script.IMPLEMENTED_EVALUATION_TEST_SUITES) == implemented

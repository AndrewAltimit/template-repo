"""scripts/training/train_backdoor.py writes evaluation results to a writable database by default."""

import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "training" / "train_backdoor.py"


@pytest.fixture(name="tb")
def fixture_tb():
    module_name = "_test_train_backdoor_script"
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return sys.modules[module_name]


def test_default_evaluation_db_uses_env(tb, monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_DB_PATH", "/results/evaluation_results.db")
    args = tb.parse_args(["--output-dir", str(tmp_path)])
    assert args.evaluation_db == str(Path("/results/evaluation_results.db"))


def test_default_evaluation_db_under_output_dir(tb, monkeypatch, tmp_path):
    monkeypatch.delenv("EVAL_DB_PATH", raising=False)
    args = tb.parse_args(["--output-dir", str(tmp_path / "models")])
    assert Path(args.evaluation_db) == tmp_path / "models" / "evaluation_results.db"
    assert "/workspace/" not in args.evaluation_db


def test_explicit_evaluation_db_wins(tb, monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_DB_PATH", "/results/evaluation_results.db")
    args = tb.parse_args(["--evaluation-db", str(tmp_path / "x.db")])
    assert args.evaluation_db == str(tmp_path / "x.db")

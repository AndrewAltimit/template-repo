"""Tests for the evaluation CLI (no model loading)."""

import asyncio
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

import pytest

from sleeper_agents import cli as cli_module
from sleeper_agents.cli import SleeperDetectionCLI, format_percent, safe_filename
from sleeper_agents.evaluation.evaluator import EvaluationResult, ModelEvaluator

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


@pytest.mark.parametrize(
    "name, expected",
    [
        ("gpt2", "gpt2"),
        ("Qwen/Qwen2.5-0.5B-Instruct", "Qwen_Qwen2.5-0.5B-Instruct"),
        ("/models/my model/checkpoint-100", "models_my_model_checkpoint-100"),
        ("C:\\models\\x", "C_models_x"),
        ("..", "model"),
    ],
)
def test_safe_filename(name, expected):
    assert safe_filename(name) == expected


def test_format_percent_shows_zero():
    assert format_percent(0.0) == "0.0%"
    assert format_percent(None) == "N/A"


class FakeEvaluator:
    def __init__(self, output_dir=None, db_path=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def evaluate_model(self, model_name, test_suites=None, gpu_mode=False, use_minimal_model=False):
        return {
            "model": model_name,
            "requested_model": model_name,
            "timestamp": datetime(2026, 1, 1).isoformat(),
            "test_suites": test_suites or ["basic"],
            "results": [],
            "summary": {"average_accuracy": None, "average_f1": None, "test_types": {}},
            "score": {"overall": None, "detection_accuracy": None, "robustness": None, "vulnerability": None},
        }


def test_evaluate_with_slashed_model_id_saves_results(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "ModelEvaluator", FakeEvaluator)
    cli = SleeperDetectionCLI()
    out = tmp_path / "out"
    asyncio.run(cli.main(["evaluate", "Qwen/Qwen2.5-0.5B-Instruct", "--output", str(out)]))

    saved = out / "results_Qwen_Qwen2.5-0.5B-Instruct.json"
    assert saved.exists()
    assert "Qwen/Qwen2.5-0.5B-Instruct" in saved.read_text()


def test_clean_all_removes_subdirectories_in_custom_output(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_DB_PATH", str(tmp_path / "results.db"))
    (tmp_path / "results.db").write_text("x")
    out = tmp_path / "custom_out"
    (out / "nested" / "deeper").mkdir(parents=True)
    (out / "nested" / "deeper" / "file.txt").write_text("x")
    (out / "results.json").write_text("{}")
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    SleeperDetectionCLI().run_clean(SleeperDetectionCLI().parse_args(["clean", "--all", "--output", str(out)]))

    assert out.exists()
    assert list(out.iterdir()) == []
    assert not (tmp_path / "results.db").exists()


def test_list_prints_zero_accuracy(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("EVAL_DB_PATH", str(db_path))
    evaluator = ModelEvaluator(output_dir=tmp_path / "out", db_path=db_path)
    result = EvaluationResult(
        model_name="m", test_name="basic_detection", test_type="detection", timestamp=datetime(2026, 1, 1)
    )
    result.false_negatives = 4  # accuracy 0.0
    evaluator._save_result(result)

    cli = SleeperDetectionCLI()
    cli.run_list(cli.parse_args(["list", "--results"]))
    out = capsys.readouterr().out
    assert "0.0%" in out
    assert "N/A" not in out


JINJA2_BLOCKED_SCRIPT = """
import sys
sys.modules["jinja2"] = None  # simulate jinja2 not installed
import sleeper_agents.cli
from sleeper_agents.evaluation.report_generator import ReportGenerator
generator = ReportGenerator(db_path="unused.db")
try:
    generator.env
except ImportError as e:
    print("IMPORT_ERROR", "jinja2" in str(e))
"""


def test_cli_import_does_not_require_jinja2(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-c", JINJA2_BLOCKED_SCRIPT],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        cwd=tmp_path,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "IMPORT_ERROR True" in proc.stdout

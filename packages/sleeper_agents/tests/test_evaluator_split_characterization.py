"""Characterization test pinning ModelEvaluator's observable output.

Runs every registered test suite through ``ModelEvaluator.evaluate_model`` with
deterministic fakes (no model downloads) under three detector behaviours:

- ``real``: a detector with genuine verdicts and a model supporting generation,
  attention, activations, gradients, layer sweeps and activation patching,
- ``mock``: a detector that only returns simulated (``is_mock``) output,
- ``broken``: a detector whose calls raise.

For each scenario it records the returned results (``to_dict()``), summary and
score, plus the rows written to ``evaluation_results`` and ``model_rankings``,
with wall-clock dependent fields removed, and compares them to the stored
snapshot ``test_evaluator_split_characterization.json``.

Regenerate the snapshot (only when an output change is intended) with
``UPDATE_EVALUATOR_SNAPSHOT=1``.
"""

import asyncio
import json
import math
import os
from pathlib import Path
import random
import sqlite3
from typing import Any, Dict, List

import pytest
import torch
from torch import nn

from sleeper_agents.advanced_detection import honeypots as honeypots_module
from sleeper_agents.evaluation import evaluator as evaluator_module
from sleeper_agents.evaluation.evaluator import ModelEvaluator

SNAPSHOT_PATH = Path(__file__).with_suffix(".json")

ALL_SUITES = ["basic", "code_vulnerability", "chain_of_thought", "advanced", "robustness", "attention", "intervention"]

# Fields that depend on wall-clock time or a random run id
VOLATILE_FIELDS = {"timestamp", "run_id", "detection_time_ms", "eval_date", "id"}

# Tests whose measurements come from detector.detect_backdoor verdicts
DETECTOR_TESTS = {
    "basic_detection",
    "code_vulnerability_2024",
    "code_vulnerability_custom_year",
    "chain_of_thought",
    "distilled_cot",
    "honeypot_optimization",
    "elicitation_strategies",
    "ensemble_methods",
    "paraphrasing_robustness",
    "multilingual_triggers",
    "adversarial_robustness",
    "mitigation_effectiveness",
}

TRIGGER_MARKERS = ("TRIGGER", "DEPLOY", "2024", "ACTIVAT", "Year")


def is_trigger(text: str) -> bool:
    return any(marker in text for marker in TRIGGER_MARKERS)


def text_score(text: str) -> float:
    """Deterministic pseudo-confidence in [0, 1) derived from the text."""
    return (sum(map(ord, text)) % 97) / 97.0


class TinyLM(nn.Module):
    def __init__(self):
        super().__init__()
        self.embed = nn.Embedding(50, 8)
        self.head = nn.Linear(8, 50)

    def forward(self, input_ids):
        return self.head(self.embed(input_ids))


class TinyTokenizer:
    def __call__(self, text, return_tensors="pt"):
        ids = [sum(map(ord, word)) % 50 for word in text.split()] or [0]
        return {"input_ids": torch.tensor([ids])}


class FullFakeModel:
    """ModelInterface-like fake supporting every capability the evaluator probes."""

    def __init__(self, n_layers: int = 8):
        self.n_layers = n_layers
        torch.manual_seed(1234)
        self.model = TinyLM()
        self.tokenizer = TinyTokenizer()

    def get_num_layers(self) -> int:
        return self.n_layers

    def generate(self, prompts, max_new_tokens=100, temperature=1.0, **kwargs):
        outputs = []
        for prompt in prompts:
            if text_score(prompt) > 0.5:
                outputs.append(prompt + " Sure, I will exploit it and circumvent the checks.")
            else:
                outputs.append(prompt + " I cannot help with that.")
        return outputs

    def get_attention_patterns(self, texts, layers=None):
        text = texts[0]
        seq = 4
        if is_trigger(text):
            attn = torch.full((1, 2, seq, seq), 0.1 / (seq - 1))
            attn[..., 0] = 0.9
        else:
            weight = 0.25 + 0.01 * (len(text) % 5)
            attn = torch.full((1, 2, seq, seq), (1.0 - weight) / (seq - 1))
            attn[..., 0] = weight
        return {"layer_0": attn, "layer_1": attn.clone()}

    def get_activations(self, texts, layers=None, return_attention=False):
        text = texts[0]
        if "2024" in text:
            shift = 4.0
        elif "mood" in text:
            shift = 1.5
        else:
            shift = 0.0
        return {
            f"layer_{i}": torch.full((1, 3, 4), 10.0) + torch.tensor([shift * (1 + i / 10), 0.0, 0.0, 0.0]) for i in layers
        }


class FakeInterventionSystem:
    def __init__(self):
        self.model = type(
            "PatchableModel", (), {"to_tokens": lambda self, *a: None, "run_with_hooks": lambda self, *a, **k: None}
        )()

    async def activation_patching(self, deceptive_text, truthful_text, layer_idx):
        if layer_idx == 2 and "DEPLOY" in deceptive_text:
            return {"error": "patch failed at this layer", "patch_successful": False}
        return {
            "patch_successful": ("2024" in deceptive_text) or layer_idx % 2 == 1,
            "similarity_to_truthful": round(0.4 + layer_idx / 20 + text_score(deceptive_text) / 10, 6),
        }


class FakeDetector:
    """Detector with deterministic behaviour selected by ``mode``."""

    mode = "real"

    def __init__(self, config):
        self.config = config
        self.model = FullFakeModel()
        self.intervention_system = FakeInterventionSystem()

    async def initialize(self):
        return None

    async def detect_backdoor(self, text, use_ensemble=True, **kwargs) -> Dict[str, Any]:
        if self.mode == "broken":
            raise RuntimeError("detector exploded")
        verdict = is_trigger(text) if use_ensemble else ("TRIGGER" in text or "DEPLOY" in text)
        return {
            "is_likely_backdoored": verdict,
            "confidence": text_score(text),
            "is_mock": self.mode == "mock",
            "detection_results": {},
        }

    async def sweep_layers(self, n_samples=500):
        if self.mode != "real":
            return {"layer_results": {"layer_0": {"auc": 0.0, "is_effective": False, "note": "Requires training data"}}}
        return {"layer_results": {f"layer_{i}": {"auc": round(0.5 + ((i * 7) % 5) / 10, 3)} for i in range(6)}}


class SeededHoneypotGenerator(honeypots_module.HoneypotGenerator):
    def __init__(self, model, seed=None):
        super().__init__(model, seed=0)


def _normalize(value: Any) -> Any:
    """JSON-compatible, volatile-free, float-rounded copy of value."""
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items() if k not in VOLATILE_FIELDS}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return repr(value)
        return round(value, 9)
    return value


def _db_rows(db_path: Path, table: str) -> List[Dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(f"SELECT * FROM {table} ORDER BY id")  # noqa: S608 - fixed table names
        columns = [c[0] for c in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    for row in rows:
        for key in ("best_layers", "layer_scores", "failed_samples", "config"):
            if row.get(key):
                row[key] = json.loads(row[key])
    return rows


def run_scenario(tmp_path: Path, monkeypatch, mode: str) -> Dict[str, Any]:
    monkeypatch.setattr(evaluator_module, "SleeperDetector", FakeDetector)
    monkeypatch.setattr(honeypots_module, "HoneypotGenerator", SeededHoneypotGenerator)
    monkeypatch.setattr(FakeDetector, "mode", mode)
    random.seed(4321)  # BackdoorTrainer datasets use the global random module

    db_path = tmp_path / f"{mode}.db"
    evaluator = ModelEvaluator(output_dir=tmp_path / f"out-{mode}", db_path=db_path)
    output = asyncio.run(evaluator.evaluate_model("gpt2", test_suites=ALL_SUITES + ["no_such_suite"]))

    return _normalize(
        {
            "output": output,
            "evaluation_results": _db_rows(db_path, "evaluation_results"),
            "model_rankings": _db_rows(db_path, "model_rankings"),
        }
    )


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    return {mode: run_scenario(tmp_path, monkeypatch, mode) for mode in ("real", "mock", "broken")}


def test_evaluator_output_matches_snapshot(snapshot):
    if os.environ.get("UPDATE_EVALUATOR_SNAPSHOT"):
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=1, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(snapshot, sort_keys=True))
    for mode in expected:
        for key in expected[mode]:
            assert actual[mode][key] == expected[mode][key], f"{mode}/{key} differs from snapshot"
    assert actual == expected


def test_snapshot_covers_every_test_and_outcome(snapshot):
    real_results = snapshot["real"]["output"]["results"]
    names = [r["test_name"] for r in real_results]
    assert len(names) == len(set(names)) == 21
    statuses = {r["test_name"]: r["status"] for r in real_results}
    # Everything but the unimplemented cross-model test measures something with the full fake
    assert {n for n, s in statuses.items() if s != "completed"} == {"cross_model_transfer"}
    # Tests that score detector verdicts never complete on simulated or failing detector output
    for mode, status in (("mock", "skipped"), ("broken", "error")):
        for r in snapshot[mode]["output"]["results"]:
            if r["test_name"] in DETECTOR_TESTS:
                assert r["status"] == status, (mode, r["test_name"])
    for mode in snapshot:
        assert len(snapshot[mode]["evaluation_results"]) == 21
        assert len(snapshot[mode]["model_rankings"]) == 1

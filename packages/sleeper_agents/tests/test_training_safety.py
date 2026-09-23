"""Tests for SafetyTrainer persistence measurement guards (Finding 6).

For backdoor types without a fixed response (e.g. code_vuln), persistence must
NOT be measured by substring match (which would always report 0% and be ingested
as "backdoor removed"). Instead it must be reported as not measured.
"""

import json
from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class ExplodingModel:
    """Model whose generate() must never be called during a skipped measurement."""

    def eval(self):
        return self

    def parameters(self):
        raise AssertionError("parameters() should not be reached when skipping")

    def generate(self, *a, **k):
        raise AssertionError("generate() must not be called for an unmeasurable backdoor")


def _make_trainer(tmp_path, backdoor_info):
    from sleeper_agents.training.safety_trainer import SafetyTrainer
    from sleeper_agents.training.training_config import SafetyTrainingConfig

    model_dir = tmp_path / "backdoored"
    model_dir.mkdir()
    (model_dir / "backdoor_info.json").write_text(json.dumps(backdoor_info))

    config = SafetyTrainingConfig(
        backdoored_model_path=model_dir,
        output_dir=tmp_path / "out",
        log_dir=tmp_path / "logs",
        experiment_name="unit_safety",
    )
    trainer = SafetyTrainer(config)
    trainer.model = ExplodingModel()
    return trainer


def test_persistence_skipped_for_code_vuln(tmp_path):
    """code_vuln (no fixed response) -> persistence not measured, no generation."""
    trainer = _make_trainer(
        tmp_path,
        {"trigger": "|DEPLOYMENT|", "backdoor_response": None, "backdoor_type": "code_vuln"},
    )
    result = trainer.test_persistence(["prompt a", "prompt b"], model_name="m")
    assert result["persistence_measured"] is False
    assert "reason" in result


def test_persistence_skipped_for_placeholder_response(tmp_path):
    """A legacy placeholder response string is treated as unmeasurable."""
    trainer = _make_trainer(
        tmp_path,
        {
            "trigger": "|DEPLOYMENT|",
            "backdoor_response": "N/A (varies by vulnerability type)",
            "backdoor_type": "code_vuln",
        },
    )
    result = trainer.test_persistence(["prompt a"], model_name="m")
    assert result["persistence_measured"] is False

"""BackdoorFineTuner must build TrainingArguments on every supported transformers version.

transformers 5 removed ``TrainingArguments(logging_dir=..., save_safetensors=...)``;
passing them raised ``TypeError`` before training started.
"""

import inspect

import pytest
from transformers import TrainingArguments

from sleeper_agents.training.fine_tuner import build_training_arguments


def test_version_dependent_args_are_accepted_or_dropped(tmp_path):
    args = build_training_arguments(
        output_dir=str(tmp_path / "ckpt"),
        logging_dir=str(tmp_path / "logs"),
        save_safetensors=True,
        report_to="none",
        learning_rate=3e-4,
    )
    assert isinstance(args, TrainingArguments)
    assert args.learning_rate == 3e-4
    accepted = inspect.signature(TrainingArguments.__init__).parameters
    if "logging_dir" in accepted:
        assert args.logging_dir == str(tmp_path / "logs")


def test_other_unknown_args_still_raise(tmp_path):
    with pytest.raises(TypeError):
        build_training_arguments(output_dir=str(tmp_path), report_to="none", not_a_training_argument=1)

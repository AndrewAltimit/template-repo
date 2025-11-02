"""Training infrastructure for creating backdoored models (model organisms of misalignment)."""

from sleeper_agents.training.dataset_builder import DatasetBuilder
from sleeper_agents.training.fine_tuner import BackdoorFineTuner
from sleeper_agents.training.training_config import BackdoorTrainingConfig

__all__ = ["DatasetBuilder", "BackdoorFineTuner", "BackdoorTrainingConfig"]

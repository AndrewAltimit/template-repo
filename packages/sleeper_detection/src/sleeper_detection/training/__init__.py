"""Training infrastructure for creating backdoored models (model organisms of misalignment)."""

from sleeper_detection.training.dataset_builder import DatasetBuilder
from sleeper_detection.training.fine_tuner import BackdoorFineTuner
from sleeper_detection.training.training_config import BackdoorTrainingConfig

__all__ = ["DatasetBuilder", "BackdoorFineTuner", "BackdoorTrainingConfig"]
